"""Pure catch-up logic. No HTTP here so tests stay offline."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

REASONS = ("turn", "compact", "boot", "restore", "touch")
# "off" mirrors eva-core's offStatus(): the admin switch is off for this session.
COLORS = ("grey", "orange", "green", "red", "off")

# Reserve headroom below max_context for the chat-template overhead (role/special
# tokens, the tools definition) and for the 4-chars/token estimate's inaccuracy.
# Without it, a prompt the estimate calls ~max_context tokens can tokenize past
# the engine's hard limit — the 1M-context sparks model rejects at 1048576 with a
# 400 ("input_tokens: 1048576") — and the session wedges red instead of prewarming.
RESERVE_FRACTION = 0.10


def reserved_limit(value) -> int:
    limit = int(value or 0)
    if limit <= 0:
        return 0
    return max(1, limit - int(limit * RESERVE_FRACTION))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def estimate_prompt_tokens(messages: list | None, extra_text: str = "") -> int:
    total = len(extra_text)
    for message in messages or []:
        content = message.get("content") if isinstance(message, Mapping) else None
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, Mapping):
                    total += len(str(part.get("text") or ""))
                else:
                    total += len(str(part or ""))
        elif content is not None:
            total += len(json.dumps(content, ensure_ascii=False, sort_keys=True))
        for key in ("name", "tool_call_id"):
            total += len(str(message.get(key) or "")) if isinstance(message, Mapping) else 0
        if isinstance(message, Mapping) and message.get("tool_calls"):
            total += len(json.dumps(message["tool_calls"], ensure_ascii=False, sort_keys=True))
    return max(1, (total + 3) // 4)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def normalize_snapshot(body: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(body or {})
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("snapshot requires a non-empty messages array")
    tools = payload.get("tools")
    if tools is None:
        tools = []
    if not isinstance(tools, list):
        raise ValueError("tools must be an array")
    kwargs = payload.get("chat_template_kwargs") or {}
    if not isinstance(kwargs, dict):
        raise ValueError("chat_template_kwargs must be an object")
    session_id = _clean(payload.get("session_id"))
    if not session_id:
        raise ValueError("snapshot requires session_id")
    reason = _clean(payload.get("reason")).lower() or "turn"
    if reason not in REASONS:
        reason = "turn"
    max_context = int(payload.get("max_context") or 0)
    return {
        "session_id": session_id,
        "messages": messages,
        "tools": tools,
        "chat_template_kwargs": kwargs,
        "model": _clean(payload.get("model")),
        "reason": reason,
        "max_context": max_context,
    }


def hash_snapshot(messages: list, tools: list | None = None, chat_template_kwargs: Mapping | None = None) -> str:
    blob = json.dumps(
        _canonical({
            "messages": messages,
            "tools": tools or [],
            "chat_template_kwargs": chat_template_kwargs or {},
        }),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def apply_rolling_window(messages: list, max_context: int) -> list:
    limit = reserved_limit(max_context)
    if limit <= 0 or estimate_prompt_tokens(messages) <= limit:
        return list(messages)
    kept = list(messages)
    system = []
    if kept and isinstance(kept[0], Mapping) and kept[0].get("role") == "system":
        system = [kept.pop(0)]
    while kept and estimate_prompt_tokens(system + kept) > limit:
        # Drop the oldest non-system message. Never drop the last user turn.
        if len(kept) <= 1:
            break
        kept.pop(0)
    return system + kept


def color_for(state: str) -> str:
    if state == "warm":
        return "green"
    if state == "error":
        return "red"
    if state in {"warming", "stale"}:
        return "orange"
    if state == "off":
        return "off"
    return "grey"


@dataclass
class SessionState:
    session_id: str
    state: str = "idle"
    current_hash: str | None = None
    warmed_hash: str | None = None
    prompt_estimate: int = 0
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    reason: str = ""
    error: str | None = None
    updated_at: float = 0.0
    generation: int = 0

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("generation", None)
        payload["color"] = color_for(self.state)
        return payload


WarmupFn = Callable[[dict[str, Any]], Mapping[str, Any]]


class WarmupAborted(Exception):
    """The admin switch went off while this warm was in flight."""


def _shutdown_socket(sock: socket.socket | None) -> None:
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


# Abort semantics (2026-10-05 fix pass). What the sidecar can do is close its
# TCP connection; the engine aborts the request when it sees the disconnect
# (vLLM's OpenAI server wraps chat completions in with_cancellation and logs
# "Aborted request <X-Request-Id>"; the scheduler drops it at the next step, so
# at most the current chunked-prefill chunk still runs). There is no HTTP abort
# endpoint in vLLM to escalate to, and killing the shared engine is not an option,
# so escalation stops at the client: shutdown() unblocks the warm thread, the
# connect phase is bounded by CONNECT_TIMEOUT_S (shutdown cannot interrupt a
# connect() in progress), and a watchdog logs loudly if a warm thread is still
# alive ABORT_CONFIRM_S after its abort.
CONNECT_TIMEOUT_S = 10.0
ABORT_CONFIRM_S = 5.0


# Dispatch order for queued warms. Lower sorts first. Someone typing ("turn")
# beats a lane that just booted, which beats housekeeping touches; and a lane's
# interactive session always beats its ":background" sibling.
REASON_RANK = {"turn": 0, "restore": 1, "compact": 2, "boot": 3, "touch": 4}
BACKGROUND_SUFFIX = ":background"


AUTO = "auto"


def sparks_engine():
    """The engine serving the Sparks now: nest scripts/lib/sparks_engine.py (2026-10-16:
    any model, any port; 30 s cache there). SPARKS_ENGINE_LIB overrides the lib dir."""
    lib = os.environ.get("SPARKS_ENGINE_LIB") or os.path.expanduser("~/nest/scripts/lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import sparks_engine as engine_lib
    return engine_lib.resolve()


class CatchupService:
    def __init__(
        self,
        *,
        vllm_url: str = "",
        model: str = "",
        max_context: int = 1_000_000,
        timeout_s: float = 1800.0,
        max_inflight: int = 2,
        warmup_fn: WarmupFn | None = None,
        now: Callable[[], float] | None = None,
        switch: Any = None,
    ) -> None:
        self.vllm_url = vllm_url.rstrip("/")
        self.model = model
        self.max_context = int(max_context or 1_000_000)
        self.timeout_s = float(timeout_s)
        # Backpressure (2026-09-13): the sidecar used to spawn one warm thread per
        # snapshot with no cap. 30 warms in flight against an 8-seat world evicted
        # each other's KV blocks, turning cache hits into full re-prefills and the
        # queue into a 49-deep pile. Now at most max_inflight warms run; the rest
        # wait in _pending, latest snapshot per session wins, dispatched by priority.
        self.max_inflight = max(1, int(max_inflight or 1))
        self._inflight = 0
        self._pending: dict[str, dict[str, Any]] = {}
        self._warmup_fn = warmup_fn or self._http_warmup
        self._now = now or time.time
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionState] = {}
        # eva-core admin switch (catchup.switch.CatchupSwitch, or anything with
        # allows(session_id) / add_listener(fn)). None = always on.
        self._switch = switch
        self._running: dict[int, dict[str, Any]] = {}
        self.abort_confirm_s = ABORT_CONFIRM_S
        if switch is not None and hasattr(switch, "add_listener"):
            switch.add_listener(self.apply_switch)

    def _allows(self, session_id: str) -> bool:
        return self._switch is None or bool(self._switch.allows(session_id))

    def _mark_off_locked(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.state = "off"
        session.error = None
        session.updated_at = self._now()

    def apply_switch(self) -> dict[str, list[str]]:
        """Re-check the switch: drop queued warms and abort in-flight ones it no
        longer allows. Turning back ON replays nothing; like eva-core, catch-up
        resumes with the next snapshot posted."""
        dropped: list[str] = []
        aborted: list[str] = []
        with self._lock:
            for sid in [sid for sid in self._pending if not self._allows(sid)]:
                self._pending.pop(sid)
                self._mark_off_locked(sid)
                dropped.append(sid)
            for work in self._running.values():
                if self._allows(work["session_id"]) or work["cancel"].is_set():
                    continue
                work["cancel"].set()
                work["aborted_at"] = time.monotonic()
                aborter = work.get("abort")
                if aborter is not None:
                    aborter()
                aborted.append(work["session_id"])
                watchdog = threading.Timer(self.abort_confirm_s, self._confirm_abort, args=(work,))
                watchdog.daemon = True
                watchdog.start()
            self._dispatch_locked()
        if dropped or aborted:
            print(
                f"[kv-catchup] switch applied: dropped queued {sorted(dropped)}, aborted in-flight {sorted(aborted)}",
                flush=True,
            )
        return {"dropped": dropped, "aborted": aborted}

    def _confirm_abort(self, work: dict[str, Any]) -> None:
        with self._lock:
            stuck = id(work) in self._running
        if stuck:
            print(
                f"[kv-catchup] WARNING abort of warm {work.get('request_id') or '?'} for {work['session_id']} "
                f"not confirmed after {self.abort_confirm_s:g}s: warm thread still blocked",
                flush=True,
            )

    def _allowed_public_locked(self, session: SessionState) -> dict[str, Any]:
        """Never report warm/green while the switch is off for this session (eva-core's
        offStatus shape: state/color "off"). Once allowed again, a session parked
        "off" reads idle/grey until its next snapshot."""
        payload = session.public()
        if not self._allows(session.session_id):
            payload["state"] = "off"
            payload["color"] = color_for("off")
        elif payload["state"] == "off":
            payload["state"] = "idle"
            payload["color"] = color_for("idle")
        return payload

    def stats(self) -> dict[str, Any]:
        switched_on = self._switch is None or bool(getattr(self._switch, "is_on", lambda: True)())
        with self._lock:
            return {
                # Master switch as the sidecar applies it; /v1/health shows "off", never green, while off.
                "state": "on" if switched_on else "off",
                "color": "green" if switched_on else color_for("off"),
                "max_inflight": self.max_inflight,
                "inflight": self._inflight,
                "pending": len(self._pending),
                "pending_sessions": sorted(self._pending),
                "switch": self._switch.snapshot() if hasattr(self._switch, "snapshot") else None,
            }

    @staticmethod
    def _priority(work: Mapping[str, Any]) -> tuple:
        sid = str(work.get("session_id") or "")
        background = 1 if sid.endswith(BACKGROUND_SUFFIX) else 0
        return (background, REASON_RANK.get(str(work.get("reason") or ""), 9), float(work.get("submitted_at") or 0.0))

    def _dispatch_locked(self) -> None:
        """Start pending warms up to max_inflight, best priority first. Caller holds _lock."""
        while self._inflight < self.max_inflight and self._pending:
            sid = min(self._pending, key=lambda key: self._priority(self._pending[key]))
            work = self._pending.pop(sid)
            if not self._allows(sid):
                self._mark_off_locked(sid)
                continue
            self._inflight += 1
            self._running[id(work)] = work
            threading.Thread(target=self._run_warmup, args=(work,), daemon=True).start()

    def get(self, session_id: str = "") -> dict[str, Any] | list[dict[str, Any]]:
        with self._lock:
            if session_id:
                session = self._sessions.get(session_id) or SessionState(session_id=session_id, updated_at=self._now())
                return self._allowed_public_locked(session)
            return [self._allowed_public_locked(session) for session in self._sessions.values()]

    def submit(self, body: Mapping[str, Any]) -> dict[str, Any]:
        snapshot = normalize_snapshot(body)
        limit = reserved_limit(min(snapshot["max_context"] or self.max_context, self._engine_context()))
        rolled = apply_rolling_window(snapshot["messages"], limit)
        digest = hash_snapshot(rolled, snapshot["tools"], snapshot["chat_template_kwargs"])
        estimate = estimate_prompt_tokens(rolled)
        if estimate >= limit:
            raise ValueError(
                f"prompt is about {estimate} tokens and the reserved window is {limit}"
            )
        with self._lock:
            session = self._sessions.setdefault(snapshot["session_id"], SessionState(session_id=snapshot["session_id"]))
            session.current_hash = digest
            session.prompt_estimate = estimate
            session.reason = snapshot["reason"]
            session.updated_at = self._now()
            session.error = None
            if not self._allows(snapshot["session_id"]):
                # Switched off: record the snapshot, start nothing. The generation
                # bump also discards any still-running warm's result. Checked before
                # the already-warm shortcut so an off session never answers green.
                session.generation += 1
                self._pending.pop(snapshot["session_id"], None)
                session.state = "off"
                return session.public()
            if session.warmed_hash == digest and session.state == "warm":
                return session.public()
            session.state = "warming"
            session.generation += 1
            generation = session.generation
            work = {
                "session_id": snapshot["session_id"],
                "messages": rolled,
                "tools": snapshot["tools"],
                "chat_template_kwargs": snapshot["chat_template_kwargs"],
                "model": snapshot["model"] or self.model,
                "hash": digest,
                "generation": generation,
                "reason": snapshot["reason"],
                "submitted_at": self._now(),
                # Set when the switch goes off mid-warm. _http_warmup also
                # registers work["abort"] to cut the engine socket (vLLM aborts
                # the request on client disconnect); injected warmup_fns may poll it.
                "cancel": threading.Event(),
            }
            # Latest snapshot wins: a newer snapshot for a session that is still
            # waiting replaces the queued one (its prefill was never started, so
            # nothing is wasted). An already-running warm cannot be cancelled;
            # it finishes, is marked stale by the generation check, and the
            # newer snapshot runs next.
            self._pending[snapshot["session_id"]] = work
            self._dispatch_locked()
            return self._sessions[snapshot["session_id"]].public()

    def _run_warmup(self, work: dict[str, Any]) -> None:
        try:
            self._run_warmup_inner(work)
        finally:
            with self._lock:
                self._running.pop(id(work), None)
                self._inflight = max(0, self._inflight - 1)
                self._dispatch_locked()

    def _run_warmup_inner(self, work: dict[str, Any]) -> None:
        error_text = None
        prompt_tokens = None
        cached_tokens = None
        aborted = False
        try:
            result = self._warmup_fn(work)
            usage = result.get("usage") if isinstance(result, Mapping) else {}
            usage = usage or {}
            prompt_tokens = _as_int(usage.get("prompt_tokens"))
            details = usage.get("prompt_tokens_details") or {}
            cached_tokens = _as_int(details.get("cached_tokens"))
        except WarmupAborted:
            aborted = True
        except Exception as exc:  # noqa: BLE001 — surface any engine failure as red
            error_text = str(exc) or exc.__class__.__name__
        if aborted:
            took = time.monotonic() - work.get("aborted_at", time.monotonic())
            print(
                f"[kv-catchup] warm {work.get('request_id') or '?'} for {work['session_id']} aborted: "
                f"engine connection closed {took:.2f}s after switch-off",
                flush=True,
            )
        with self._lock:
            session = self._sessions.get(work["session_id"])
            if not session or session.generation != work["generation"]:
                return
            if aborted:
                self._mark_off_locked(work["session_id"])
                return
            session.prompt_tokens = prompt_tokens
            session.cached_tokens = cached_tokens
            session.updated_at = self._now()
            if error_text:
                session.state = "error"
                session.error = error_text
                return
            if session.current_hash != work["hash"]:
                session.state = "stale"
                return
            session.warmed_hash = work["hash"]
            session.state = "warm"
            session.error = None

    def _engine_context(self) -> int:
        """With vllm_url=auto, never roll past the context the Sparks engine reports."""
        if self.vllm_url != AUTO:
            return self.max_context
        try:
            return int(sparks_engine().context_length or self.max_context)
        except Exception:  # noqa: BLE001 - no engine: the warm itself fails later
            return self.max_context

    def _http_warmup(self, work: dict[str, Any]) -> Mapping[str, Any]:
        if not self.vllm_url:
            raise RuntimeError("CATCHUP_VLLM_URL is not set")
        base, model = self.vllm_url, work["model"]
        if base == AUTO:  # warm whatever serves the Sparks now; nothing ready -> this warm fails
            engine = sparks_engine()
            base, model = engine.base_url, (model if model and model != AUTO else engine.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": work["messages"],
            "max_tokens": 1,
            "temperature": 0,
            "stream": False,
        }
        if work.get("tools"):
            payload["tools"] = work["tools"]
        if work.get("chat_template_kwargs"):
            payload["chat_template_kwargs"] = work["chat_template_kwargs"]
        target = urlsplit(f"{base}/chat/completions")
        conn_cls = HTTPSConnection if target.scheme == "https" else HTTPConnection
        # Short connect timeout: shutdown() cannot interrupt a connect() in
        # progress, so a dead engine must not pin an aborted warm for timeout_s.
        conn = conn_cls(target.hostname, target.port, timeout=min(CONNECT_TIMEOUT_S, self.timeout_s))
        cancel = work.get("cancel") or threading.Event()
        # Engine-side request id, so "Aborted request kvwarm-..." in the engine
        # log can be matched to the abort the sidecar logged.
        request_id = work.setdefault("request_id", f"kvwarm-{uuid.uuid4().hex[:16]}")
        # http.client rather than urlopen so the switch can cut the socket
        # mid-prefill: shutdown() wakes the blocked read with a disconnect.
        # The socket is captured at connect time, not read from conn.sock at abort
        # time: on a "Connection: close" response getresponse() sets conn.sock =
        # None and the body read runs on the response's handle to the same socket
        # (fix pass 2). shutdown() acts on the fd, so it cuts that read too.
        held: list[socket.socket] = []
        work["abort"] = lambda: _shutdown_socket(held[0] if held else None)
        try:
            conn.connect()
            conn.sock.settimeout(self.timeout_s)
            held.append(conn.sock)
            # An abort that landed before the socket was held found nothing to
            # shut down (apply_switch sets cancel before calling abort).
            if cancel.is_set():
                raise WarmupAborted()
            conn.request(
                "POST",
                target.path,
                body=json.dumps(payload).encode("utf-8"),
                headers={"content-type": "application/json", "x-request-id": request_id},
            )
            response = conn.getresponse()
            raw = response.read()
        except WarmupAborted:
            raise
        except (OSError, HTTPException) as exc:
            if cancel.is_set():
                raise WarmupAborted() from exc
            raise RuntimeError(f"vLLM unreachable: {exc}") from exc
        finally:
            conn.close()
        if cancel.is_set():
            raise WarmupAborted()
        if response.status >= 400:
            detail = raw.decode("utf-8", errors="replace")
            raise RuntimeError(f"vLLM HTTP {response.status}: {detail[:400]}")
        return json.loads(raw.decode("utf-8") or "{}")


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
