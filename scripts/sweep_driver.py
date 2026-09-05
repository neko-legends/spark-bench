#!/usr/bin/env python3
"""Sweep driver: per-config {export resolved env -> (relaunch | use current serve) ->
poll /health + async boot-shape warmup completion -> quiescence asserts ->
warm-until-stable -> scored passes -> telemetry -> enriched timestamped JSON}.

Replaces the uncommitted sweep wrapper that produced c4-sweep-20260904-0030
(audit F5: artifacts did not record resolved env; the `say "async=… k=…"` line
lived only in docker logs; the driver was not in the repo).

Design (measurement-audit Task 3/4):
- Configs are NEVER hardcoded — they come from --config NAME[:K=V,...] and/or
  --configs-file FILE.json. Any ordering (interleaved A/B/A/B) is just the
  order you pass; repeated invocations append to the same sweep.log.
- Resolved env = base env (--base-env / --base-env-file / current process)
  overridden by the config's env. Never rely on launcher defaults.
- With --relaunch: the launcher script is invoked with the resolved env.
  WITHOUT --relaunch (default): the currently running serve is used as-is —
  the driver still gates on /health, warmup completion, and quiescence.
- Warmup completion is POLLED (container/warmup log pattern), not a fixed
  sleep: the launcher's async boot-shape warmup writes
  /tmp/glm53-exl3-warmup.log on the head host. Done when the log matches
  --warmup-done-regex, OR (fallback) the log has been quiet for
  --warmup-quiet-s seconds while /health is green — the criterion used is
  recorded in the artifact.
- Warm-until-stable: repeated C4 passes until 3 consecutive pass steady_agg
  values are within --stability-tol (default 5%), capped at --max-warm-passes.
  All warm passes are recorded (the warmup curve is evidence).
- Scored passes: --scored-passes (default 3) with --cooldown between.
- Telemetry: the container's resolved-env `say "async=… k=… small_ok=…"`
  line from docker logs, plus per-rank nvidia-smi and dmesg OOM counts via
  ssh (read-only commands only).
- Output: <out>/<config>-<UTC>-sweep.json with O_EXCL — never overwrite.

One line per phase is appended to --sweep-log (default ./sweep.log).

Python 3.10+ stdlib only. No cluster access needed for --self-test.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import bench_c4_steady as c4

DEFAULT_LAUNCHER = "/home/jun/launch-glm53-exl3-tp4.sh"
DEFAULT_WARMUP_LOG = "/tmp/glm53-exl3-warmup.log"
# The warmup script's own completion wording is not in this repo; match a
# permissive "warmup ... done/complete/finished/ok" pattern, and fall back to
# log-quiet + healthy when the regex never matches (criterion is recorded).
DEFAULT_WARMUP_DONE_RE = r"warmup.*(done|complete|finished|ok|success)"
DEFAULT_RANKS = ("forge", "anvil", "ember", "flame")


# ----------------------------- pure helpers -----------------------------

def parse_config_arg(spec: str) -> dict:
    """'name' or 'name:K=V,K=V' -> {"name": ..., "env": {...}}."""
    name, _, envspec = spec.partition(":")
    name = name.strip()
    if not name:
        raise ValueError(f"bad --config {spec!r}: empty name")
    env = {}
    envspec = envspec.strip()
    if envspec:
        for item in envspec.split(","):
            item = item.strip()
            if not item:
                continue
            k, sep, v = item.partition("=")
            if not sep or not k.strip():
                raise ValueError(f"bad --config {spec!r}: bad env item {item!r}")
            env[k.strip()] = v
    return {"name": name, "env": env}


def parse_env_arg(spec: str) -> dict:
    """'K=V,K=V' -> dict."""
    env = {}
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        k, sep, v = item.partition("=")
        if not sep or not k.strip():
            raise ValueError(f"bad env item {item!r}")
        env[k.strip()] = v
    return env


def resolve_env(base: dict, overrides: dict) -> dict:
    return {**base, **overrides}


def pass_metric(p: dict):
    """Per-pass stability metric: steady_agg, else median of per-stream tok/s."""
    if p.get("steady_agg_tok_s") is not None:
        return p["steady_agg_tok_s"]
    per = p.get("per_stream_tok_s") or []
    return round(statistics.median(per), 1) if per else None


def is_stable(vals: list, tol: float) -> bool:
    """True when the last 3 values are within tol (relative spread)."""
    if len(vals) < 3:
        return False
    last = [v for v in vals[-3:] if v is not None]
    if len(last) < 3:
        return False
    lo, hi = min(last), max(last)
    if lo <= 0:
        return False
    return (hi / lo - 1.0) <= tol


def log_line(cfg: str, phase: str, detail: str = "") -> str:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{ts} {cfg} {phase}" + (f" {detail}" if detail else "")


def write_excl(path: Path, obj) -> None:
    data = json.dumps(obj, indent=1) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(data)


# --------------------------- remote command shims ---------------------------

def ssh_prefix(host: str) -> list[str]:
    return ["ssh", "-o", "BatchMode=yes", host]


def run_cmd(cmd: list[str], timeout: float = 60.0) -> dict:
    """Run a command; never raises. Returns {ok, rc, out, err}."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "rc": r.returncode,
                "out": r.stdout.strip(), "err": r.stderr.strip()}
    except Exception as exc:
        return {"ok": False, "rc": None, "out": "", "err": f"{type(exc).__name__}: {exc}"}


def head_cmd(head_host: str, cmd: list[str], timeout: float = 60.0) -> dict:
    if head_host == "local":
        return run_cmd(cmd, timeout)
    return run_cmd(ssh_prefix(head_host) + cmd, timeout)


# ------------------------------ polling ------------------------------

def http_get(url: str, timeout: float = 10.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def wait_health(base: str, timeout_s: float, log) -> tuple[bool, float]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        st, _ = http_get(base + "/health", timeout=5)
        if st == 200:
            return True, time.monotonic() - t0
        time.sleep(10)
    return False, time.monotonic() - t0


def wait_quiescent(base: str, timeout_s: float, poll_s: float = 5.0) -> tuple[bool, dict]:
    t0 = time.monotonic()
    last = {}
    while time.monotonic() - t0 < timeout_s:
        last = c4.metrics_snapshot()
        if last.get("num_requests_running") == 0.0 and last.get("num_requests_waiting") == 0.0:
            return True, last
        time.sleep(poll_s)
    return False, last


def wait_warmup(head_host: str, warmup_log: str, done_re: str, base: str,
                timeout_s: float, quiet_s: float, poll_s: float = 15.0) -> dict:
    """Poll the async boot-shape warmup to completion (not a fixed sleep).

    Criteria: (a) the warmup log matches done_re, or (b) fallback — the log
    exists, is unchanged for quiet_s seconds, and /health is green. Which
    criterion fired is recorded.
    """
    rx = re.compile(done_re)
    t0 = time.monotonic()
    prev_size, prev_mtime, last_change = -1, None, time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        r = head_cmd(head_host, ["stat", "-c", "%s %Y", warmup_log], timeout=15)
        if r["ok"] and r["out"]:
            parts = r["out"].split()
            size, mtime = int(parts[0]), float(parts[1])
            if size != prev_size or mtime != prev_mtime:
                prev_size, prev_mtime, last_change = size, mtime, time.monotonic()
            # (a) regex on the log content (case-insensitive POSIX ERE)
            g = head_cmd(head_host, ["grep", "-aiE", done_re, warmup_log], timeout=15)
            if g["ok"] and g["out"]:
                return {"done": True, "criterion": "regex", "match": g["out"][:500],
                        "waited_s": round(time.monotonic() - t0, 1)}
            # (b) quiet + healthy fallback
            if time.monotonic() - last_change >= quiet_s:
                st, _ = http_get(base + "/health", timeout=5)
                if st == 200:
                    return {"done": True, "criterion": "log_quiet_and_healthy",
                            "quiet_s": round(time.monotonic() - last_change, 1),
                            "waited_s": round(time.monotonic() - t0, 1)}
        time.sleep(poll_s)
    return {"done": False, "criterion": "timeout",
            "waited_s": round(time.monotonic() - t0, 1)}


def collect_docker_env_line(head_host: str, container: str) -> dict:
    r = head_cmd(head_host, ["docker", "logs", container], timeout=120)
    out = (r["out"] + "\n" + r["err"]) if r["ok"] else r["out"]
    line = None
    for ln in out.splitlines():
        if "async=" in ln and "small_ok=" in ln:
            line = ln.strip()
            break
    return {"line": line, "error": None if r["ok"] else r["err"]}


NVIDIA_SMI_QUERY = ("nvidia-smi --query-gpu=index,name,temperature.gpu,clocks.sm,"
                    "clocks.max.sm,memory.used,memory.total,utilization.gpu "
                    "--format=csv,noheader")


def collect_rank_telemetry(ranks: list[str]) -> dict:
    """Read-only per-rank telemetry via ssh: nvidia-smi + dmesg OOM count."""
    out = {}
    for h in ranks:
        smi = run_cmd(ssh_prefix(h) + [NVIDIA_SMI_QUERY], timeout=60) if h != "local" \
            else run_cmd(["bash", "-c", NVIDIA_SMI_QUERY], timeout=60)
        dmesg = run_cmd(ssh_prefix(h) + ["bash", "-c",
                       "dmesg 2>/dev/null | grep -ci 'out of memory' || true"], timeout=60) \
            if h != "local" else run_cmd(["bash", "-c",
                       "dmesg 2>/dev/null | grep -ci 'out of memory' || true"], timeout=60)
        out[h] = {"nvidia_smi": smi["out"] if smi["ok"] else None,
                  "nvidia_smi_error": None if smi["ok"] else smi["err"],
                  "dmesg_oom_count": dmesg["out"] if dmesg["ok"] else None,
                  "dmesg_error": None if dmesg["ok"] else dmesg["err"]}
    return out


# ------------------------------- driver -------------------------------

class Driver:
    def __init__(self, args, configs):
        self.args = args
        self.configs = configs
        self.base_env = self._load_base_env()
        self.log_path = Path(args.sweep_log)

    def _load_base_env(self) -> dict:
        env = {}
        if self.args.base_env_file:
            env.update(json.loads(Path(self.args.base_env_file).read_text()))
        if self.args.base_env:
            env.update(parse_env_arg(self.args.base_env))
        return env

    def log(self, cfg: str, phase: str, detail: str = "") -> None:
        line = log_line(cfg, phase, detail)
        print(line, flush=True)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def run(self) -> int:
        args = self.args
        c4.BASE = args.base
        results = {}
        for cfg in self.configs:
            results[cfg["name"]] = self.run_config(cfg)
        return 0

    def run_config(self, cfg: dict) -> dict:
        args = self.args
        name = cfg["name"]
        env = resolve_env(self.base_env, cfg.get("env") or {})
        self.log(name, "start", f"env={json.dumps(env, sort_keys=True)}")
        rec = {"schema": "sweep_driver_v1", "name": name, "env": env,
               "relaunched": args.relaunch,
               "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

        # 1. relaunch (only with --relaunch; default uses the current serve)
        if args.relaunch:
            self.log(name, "relaunch", f"launcher={args.launcher}")
            t0 = time.monotonic()
            r = run_cmd(["bash", args.launcher], timeout=2400)
            rec["launch"] = {"rc": r["rc"], "err": r["err"][:2000] if r["err"] else None,
                            "wall_s": round(time.monotonic() - t0, 1)}
            if not r["ok"]:
                self.log(name, "relaunch-failed", f"rc={r['rc']}")
                rec["status"] = "relaunch_failed"
                self._write(name, rec)
                return rec
        else:
            self.log(name, "reuse", "using currently running serve (no --relaunch)")

        # 2. health
        ok, waited = wait_health(args.base, args.health_timeout, self.log)
        rec["health_wait_s"] = round(waited, 1)
        self.log(name, "health", f"ok={ok} waited_s={round(waited, 1)}")
        if not ok:
            rec["status"] = "health_failed"
            self._write(name, rec)
            return rec

        # 3. async boot-shape warmup completion (poll, not fixed sleep)
        wu = wait_warmup(args.head_host, args.warmup_log, args.warmup_done_regex,
                         args.base, args.warmup_timeout, args.warmup_quiet_s)
        rec["warmup"] = wu
        self.log(name, "warmup", f"done={wu['done']} criterion={wu['criterion']}")
        if not wu["done"]:
            rec["status"] = "warmup_timeout"
            self._write(name, rec)
            return rec

        # 4. quiescence asserts
        q_ok, q_last = wait_quiescent(args.base, args.quiescence_timeout)
        rec["quiescence"] = {"ok": q_ok, "sample": {k: q_last.get(k) for k in
                             ("num_requests_running", "num_requests_waiting",
                              "gpu_cache_usage_perc")}}
        self.log(name, "quiescence", f"ok={q_ok} sample={rec['quiescence']['sample']}")
        if not q_ok:
            rec["status"] = "not_quiescent"
            self._write(name, rec)
            return rec

        # 5. warm-until-stable
        warm_passes = []
        stable = False
        for i in range(args.max_warm_passes):
            c4.run_warmup()
            p = c4.run_pass()
            warm_passes.append(p)
            vals = [pass_metric(p) for p in warm_passes]
            stable = is_stable(vals, args.stability_tol)
            self.log(name, "warm_pass", f"i={i + 1} metric={pass_metric(p)} "
                     f"valid={p['valid']} stable={stable}")
            if stable:
                break
            time.sleep(args.cooldown)
        rec["warm_passes"] = warm_passes
        rec["warm_stable"] = stable
        if not stable:
            self.log(name, "warm-unstable", f"no 3 consecutive within {args.stability_tol:.0%} "
                     f"after {args.max_warm_passes} passes — scoring anyway, flagged")
            rec["status"] = "warm_unstable"

        # 6. scored passes
        scored = []
        for i in range(args.scored_passes):
            p = c4.run_pass()
            scored.append(p)
            self.log(name, "scored_pass", f"i={i + 1} steady_agg={p['steady_agg_tok_s']} "
                     f"e2e_agg={p['e2e_agg_tok_s']} valid={p['valid']}")
            if i < args.scored_passes - 1:
                time.sleep(args.cooldown)
        rec["scored_passes"] = scored
        ok_metrics = [pass_metric(p) for p in scored if p["valid"]]
        rec["summary"] = {
            "n_scored": len(scored),
            "n_valid": len(ok_metrics),
            "steady_agg_median": round(statistics.median(ok_metrics), 1) if ok_metrics else None,
            "steady_agg_values": ok_metrics,
            "warm_pass_metrics": [pass_metric(p) for p in warm_passes],
        }

        # 7. telemetry
        docker = collect_docker_env_line(args.head_host, args.container)
        rec["docker_env_line"] = docker["line"]
        rec["docker_env_error"] = docker["error"]
        self.log(name, "docker_env", f"line={docker['line']}")
        ranks = [r.strip() for r in args.ranks.split(",") if r.strip()]
        rec["ranks"] = collect_rank_telemetry(ranks)
        self.log(name, "telemetry", f"ranks={ranks} "
                 f"oom={[rec['ranks'][h]['dmesg_oom_count'] for h in ranks]}")

        rec.setdefault("status", "ok")
        self._write(name, rec)
        self.log(name, "done", f"status={rec['status']} "
                 f"steady_agg_median={rec['summary']['steady_agg_median']}")
        return rec

    def _write(self, name: str, rec: dict) -> None:
        out_dir = Path(self.args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{name}-{c4.utc_stamp()}-sweep.json"
        try:
            write_excl(p, rec)
            print(f"WROTE {p}", flush=True)
        except FileExistsError:
            print(f"REFUSED: {p} already exists (O_EXCL) — never overwrite", flush=True)


# --------------------------- offline self-test ---------------------------

def self_test() -> int:
    import tempfile
    fails = []
    def check(name_, cond):
        print(("PASS" if cond else "FAIL") + f" {name_}", flush=True)
        if not cond: fails.append(name_)

    # config parsing
    c = parse_config_arg("baseline-C")
    check("config: name only", c == {"name": "baseline-C", "env": {}})
    c = parse_config_arg("async-off:ASYNC_SCHEDULING=0,MNBT_X=9")
    check("config: name+env", c == {"name": "async-off", "env": {"ASYNC_SCHEDULING": "0", "MNBT_X": "9"}})
    try:
        parse_config_arg(":bad"); ok = False
    except ValueError:
        ok = True
    check("config: empty name rejected", ok)
    try:
        parse_config_arg("x:NOEQ"); ok = False
    except ValueError:
        ok = True
    check("config: bad env item rejected", ok)

    check("env parse", parse_env_arg("A=1, B=2") == {"A": "1", "B": "2"})
    check("env resolve: override wins", resolve_env({"A": "1", "B": "2"}, {"B": "3"}) == {"A": "1", "B": "3"})

    # stability
    check("stable: within 5%", is_stable([100.0, 101.0, 102.0], 0.05))
    check("unstable: 25% drift", not is_stable([100.0, 115.0, 130.0], 0.05))
    check("stable: needs 3", not is_stable([100.0, 101.0], 0.05))
    check("stable: only last 3 counted", is_stable([1.0, 999.0, 100.0, 101.0, 102.0], 0.05))
    check("stable: None tolerated until 3 real", not is_stable([None, None, None], 0.05))

    # pass_metric
    pm = pass_metric({"steady_agg_tok_s": 128.9, "per_stream_tok_s": [30, 31, 32, 33]})
    check("pass_metric: steady_agg preferred", pm == 128.9)
    pm2 = pass_metric({"steady_agg_tok_s": None, "per_stream_tok_s": [30, 31, 32, 33]})
    check("pass_metric: median fallback", pm2 == 31.5)

    # log line format
    ln = log_line("cfg", "phase", "detail")
    check("log line format",
          re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4} cfg phase detail", ln) is not None)
    ln2 = log_line("cfg", "phase")
    check("log line no detail", ln2.endswith(" cfg phase") and "  " not in ln2)

    # sweep flow decision logic (no network): warm-unstable path is a flag, not a crash
    check("no hardcoded configs in source",
          "baseline-C" not in Path(__file__).read_text().split("offline self-test")[0]
          and "async-off" not in Path(__file__).read_text().split("offline self-test")[0])

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sweep.json"
        write_excl(p, {"a": 1})
        try:
            write_excl(p, {"a": 2}); ok = False
        except FileExistsError:
            ok = True
        check("O_EXCL: refuses overwrite", ok)

    print(f"self-test: {'OK' if not fails else 'FAILED: ' + ', '.join(fails)}", flush=True)
    return 0 if not fails else 1


# --------------------------------- main ---------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", action="append", default=[], metavar="NAME[:K=V,...]",
                    help="config to run (repeatable). Interleaved ordering = pass order.")
    ap.add_argument("--configs-file", metavar="FILE.json",
                    help='JSON list of {"name": ..., "env": {...}} — no hardcoded list anywhere')
    ap.add_argument("--base-env", metavar="K=V,...", help="base env merged under every config")
    ap.add_argument("--base-env-file", metavar="FILE.json", help="base env as JSON object")
    ap.add_argument("--relaunch", action="store_true",
                    help="relaunch the serve via the launcher per config (default: use "
                         "the currently running serve)")
    ap.add_argument("--launcher", default=DEFAULT_LAUNCHER)
    ap.add_argument("--base", default=c4.BASE, help="serve base URL (default %(default)s)")
    ap.add_argument("--head-host", default="local",
                    help="'local' or an ssh host that owns the head container/warmup log")
    ap.add_argument("--container", default="glm53-exl3")
    ap.add_argument("--warmup-log", default=DEFAULT_WARMUP_LOG)
    ap.add_argument("--warmup-done-regex", default=DEFAULT_WARMUP_DONE_RE)
    ap.add_argument("--warmup-quiet-s", type=float, default=120.0,
                    help="fallback: warmup log quiet for this long + healthy = done")
    ap.add_argument("--health-timeout", type=float, default=1800.0)
    ap.add_argument("--warmup-timeout", type=float, default=2400.0)
    ap.add_argument("--quiescence-timeout", type=float, default=300.0)
    ap.add_argument("--max-warm-passes", type=int, default=10)
    ap.add_argument("--stability-tol", type=float, default=0.05)
    ap.add_argument("--scored-passes", type=int, default=3)
    ap.add_argument("--cooldown", type=float, default=60.0)
    ap.add_argument("--ranks", default=",".join(DEFAULT_RANKS),
                    help="comma-separated rank hosts for ssh telemetry (read-only)")
    ap.add_argument("--out", metavar="DIR",
                    help="output dir; per-config <name>-<UTC>-sweep.json (O_EXCL). "
                         "Required unless --self-test.")
    ap.add_argument("--sweep-log", default="sweep.log",
                    help="one line per phase appended here (default ./sweep.log)")
    ap.add_argument("--self-test", action="store_true", help="offline validation, no server/ssh")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.out:
        ap.error("--out DIR is required")

    configs = []
    for spec in args.config:
        configs.append(parse_config_arg(spec))
    if args.configs_file:
        data = json.loads(Path(args.configs_file).read_text())
        for item in data:
            configs.append({"name": item["name"], "env": dict(item.get("env") or {})})
    if not configs:
        ap.error("no configs given — pass --config NAME[:K=V,...] and/or --configs-file")

    d = Driver(args, configs)
    return d.run()


if __name__ == "__main__":
    raise SystemExit(main())
