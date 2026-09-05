#!/usr/bin/env python3
"""Tiny mock vLLM serve for offline harness self-verification (stdlib only).

Serves canned endpoints on 127.0.0.1:<port>:
- GET  /health                -> 200 ok
- GET  /v1/models             -> one model, id GLM-5.3-Flash-EXL3, max_model_len 1000000
- GET  /metrics               -> prometheus text; counters advance per request
- POST /tokenize              -> {"count": ~word count of prompt content}
- POST /v1/chat/completions   -> SSE stream: N content deltas, finish_reason,
                                 final usage chunk with prompt_tokens,
                                 completion_tokens, prompt_tokens_details.cached_tokens

Behavior knobs (CLI):
  --port P            default 18999
  --tokens N          completion_tokens per request (default 40)
  --chunk-delay S     seconds between SSE deltas (default 0.001)
  --cached N          cached_tokens reported in usage (default 100)
  --gen-start N       initial vllm:generation_tokens_total (default 0)

Cached-prefix rule: if the request's user content starts with a salt marker
("COLD-PREFILL salt=" or "MIXED-GUARD salt="), cached_tokens=0 (front-salted
cold prompt); otherwise cached_tokens = --cached. This lets the mixed-guard /
toggle checks see the cold-vs-warm distinction offline.

Prefix cache counters advance per request (hits += cached, queries += 1).
Spec counters advance by fixed amounts per request, incl. per-position.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "GLM-5.3-Flash-EXL3"
COLD_MARKERS = ("COLD-PREFILL salt=", "MIXED-GUARD salt=")

state = {"generation_tokens_total": 0.0, "spec_drafts": 0.0, "spec_draft_tokens": 0.0,
         "spec_accepted": 0.0, "per_pos": {p: 0.0 for p in range(7)},
         "prefix_hits": 0.0, "prefix_queries": 0.0,
         "running": 0, "lock": threading.Lock()}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b'{"status":"ok"}')
        elif self.path == "/v1/models":
            obj = {"data": [{"id": MODEL, "max_model_len": 1000000}]}
            self._send(200, json.dumps(obj).encode())
        elif self.path == "/metrics":
            self._send(200, metrics_text().encode(), ctype="text/plain; version=0.0.4")
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        if self.path == "/tokenize":
            try:
                body = json.loads(raw)
                text = " ".join(m.get("content", "") for m in body.get("messages", []))
                count = len(text.split())
            except Exception:
                count = 0
            self._send(200, json.dumps({"count": count}).encode())
            return
        if self.path != "/v1/chat/completions":
            self._send(404, b'{"error":"not found"}')
            return
        try:
            body = json.loads(raw)
        except Exception:
            self._send(400, b'{"error":"bad json"}')
            return
        self.serve_chat(body)

    def serve_chat(self, body):
        cfg = self.server.cfg
        user = ""
        for m in body.get("messages", []):
            user += " " + str(m.get("content", ""))
        ptok = max(len(user.split()), 1)
        cold = any(m in user for m in COLD_MARKERS)
        cached = 0 if cold else cfg["cached"]
        ct = cfg["tokens"]
        stream = body.get("stream", False)
        with state["lock"]:
            state["running"] += 1
        try:
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                # chunked-ish: no content-length; close-delimited
                self.send_header("Connection", "close")
                self.end_headers()
                for i in range(ct):
                    chunk = {"id": "chatcmpl-mock", "object": "chat.completion.chunk",
                             "choices": [{"index": 0, "delta": {"content": "x"}}]}
                    if i == ct - 1:
                        chunk["choices"][0]["finish_reason"] = cfg["finish"]
                    self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                    self.wfile.flush()
                    time.sleep(cfg["chunk_delay"])
                usage_chunk = {"id": "chatcmpl-mock", "object": "chat.completion.chunk",
                               "choices": [{"index": 0, "delta": {}}],
                               "usage": {"prompt_tokens": ptok, "completion_tokens": ct,
                                         "prompt_tokens_details": {"cached_tokens": cached}}}
                self.wfile.write(b"data: " + json.dumps(usage_chunk).encode() + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                obj = {"id": "chatcmpl-mock", "object": "chat.completion",
                       "choices": [{"index": 0, "message": {"content": "OK"},
                                    "finish_reason": cfg["finish"]}],
                       "usage": {"prompt_tokens": ptok, "completion_tokens": ct,
                                 "prompt_tokens_details": {"cached_tokens": cached}}}
                self._send(200, json.dumps(obj).encode())
        finally:
            with state["lock"]:
                state["running"] -= 1
                state["generation_tokens_total"] += ct
                state["spec_drafts"] += ct
                state["spec_draft_tokens"] += ct * 7
                state["spec_accepted"] += ct * 3.5
                for p in range(7):
                    state["per_pos"][p] += ct * (7 - p) / 7.0
                state["prefix_hits"] += cached
                state["prefix_queries"] += 1


def metrics_text() -> str:
    with state["lock"]:
        lines = [
            "# HELP vllm:generation_tokens_total Number of generated tokens.\n",
            "# TYPE vllm:generation_tokens_total counter\n",
            f'vllm:generation_tokens_total{{engine="0",model_name="{MODEL}"}} {state["generation_tokens_total"]}\n',
            f'vllm:spec_decode_num_drafts_total{{engine="0",model_name="{MODEL}"}} {state["spec_drafts"]}\n',
            f'vllm:spec_decode_num_draft_tokens_total{{engine="0",model_name="{MODEL}"}} {state["spec_draft_tokens"]}\n',
            f'vllm:spec_decode_num_accepted_tokens_total{{engine="0",model_name="{MODEL}"}} {state["spec_accepted"]}\n',
        ]
        for p, v in state["per_pos"].items():
            lines.append(f'vllm:spec_decode_num_accepted_tokens_per_pos_total{{engine="0",model_name="{MODEL}",position="{p}"}} {v}\n')
        lines += [
            f'vllm:prefix_cache_hits_total{{engine="0",model_name="{MODEL}"}} {state["prefix_hits"]}\n',
            f'vllm:prefix_cache_queries_total{{engine="0",model_name="{MODEL}"}} {state["prefix_queries"]}\n',
            f'vllm:gpu_cache_usage_perc{{engine="0",model_name="{MODEL}"}} 0.42\n',
            f'vllm:num_requests_running{{engine="0",model_name="{MODEL}"}} {state["running"]}\n',
            f'vllm:num_requests_waiting{{engine="0",model_name="{MODEL}"}} 0.0\n',
        ]
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18999)
    ap.add_argument("--tokens", type=int, default=40)
    ap.add_argument("--chunk-delay", type=float, default=0.001)
    ap.add_argument("--cached", type=int, default=100)
    ap.add_argument("--finish", default="length")
    ap.add_argument("--gen-start", type=float, default=0.0)
    args = ap.parse_args()
    state["generation_tokens_total"] = args.gen_start
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.cfg = {"tokens": args.tokens, "chunk_delay": args.chunk_delay,
               "cached": args.cached, "finish": args.finish}
    print(f"mock serve on 127.0.0.1:{args.port} tokens={args.tokens} "
          f"cached={args.cached} finish={args.finish}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
