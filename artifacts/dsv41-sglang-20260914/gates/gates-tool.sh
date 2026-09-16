#!/usr/bin/env bash
# G2 tool round-trip + G3 reasoning parser gates, extracted from ab-uncensored.sh.
# Usage: gates-tool.sh <g2|g3> [outfile]
set -uo pipefail
API="${API:-http://127.0.0.1:8000}"
MODEL="${MODEL:-deepseek-v4.1-flash}"

gate_toolroundtrip(){
API="$API" MODEL="$MODEL" python3 - <<'PY'
import json, os, sys, urllib.request
API=os.environ["API"]; MODEL=os.environ["MODEL"]
U = API + "/v1/chat/completions"
def post(body, timeout=600):
    req = urllib.request.Request(U, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))
tools = [{"type": "function", "function": {
    "name": "get_secret", "description": "Return the secret value for a key.",
    "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}}]
ok = 0
for run in (1, 2, 3):
    try:
        r1 = post({"model": MODEL, "tools": tools, "tool_choice": "auto",
                   "messages": [{"role": "user", "content": "Use the get_secret tool to fetch the value for key alpha."}],
                   "max_tokens": 200, "temperature": 0})
        m1 = r1["choices"][0]["message"]
        tcs = m1.get("tool_calls") or []
        if not tcs:
            print(f"run{run}: NO TOOL CALL | content={ (m1.get('content') or '')[:120]!r}"); continue
        tc = tcs[0]
        r2 = post({"model": MODEL, "tools": tools,
                   "messages": [
                       {"role": "user", "content": "Use the get_secret tool to fetch the value for key alpha."},
                       {"role": "assistant", "content": m1.get("content") or "", "tool_calls": tcs},
                       {"role": "tool", "tool_call_id": tc.get("id", "call_0"), "content": "{\"value\": 42}"}],
                   "max_tokens": 200, "temperature": 0})
        c2 = r2["choices"][0]["message"].get("content") or ""
        good = ("42" in c2) and ("</parameter>" not in c2) and ("<tool_result>" not in c2) and len(c2) < 2000
        print(f"run{run}: tool_call={tc['function']['name']} continuation_ok={good} | {c2[:120]!r}")
        ok += 1 if good else 0
    except Exception as e:
        print(f"run{run}: EXCEPTION {e}")
print(f"TOOL_ROUNDTRIP {ok}/3")
sys.exit(0 if ok == 3 else 1)
PY
}

gate_reasoning(){
API="$API" MODEL="$MODEL" python3 - <<'PY'
import json, os, sys, urllib.request
API=os.environ["API"]; MODEL=os.environ["MODEL"]
U = API + "/v1/chat/completions"
def post(body):
    req = urllib.request.Request(U, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))
base = {"model": MODEL,
        "messages": [{"role": "user", "content": "What is 27*31? Think step by step."}],
        "max_tokens": 400, "temperature": 0}
on = post({**base, "chat_template_kwargs": {"thinking": True}})
off = post({**base, "chat_template_kwargs": {"thinking": False}})
m_on, m_off = on["choices"][0]["message"], off["choices"][0]["message"]
r_on = m_on.get("reasoning_content")
ok_on = bool(r_on) and ("837" in (m_on.get("content") or ""))
ok_off = (not m_off.get("reasoning_content")) and ("837" in (m_off.get("content") or ""))
print(f"thinking=on: reasoning_present={bool(r_on)} answer_ok={'837' in (m_on.get('content') or '')}")
print(f"thinking=off: reasoning_absent={not m_off.get('reasoning_content')} answer_ok={'837' in (m_off.get('content') or '')}")
print("REASONING_PARSER", "PASS" if (ok_on and ok_off) else "FAIL")
sys.exit(0 if (ok_on and ok_off) else 1)
PY
}

case "${1:-}" in
  g2) gate_toolroundtrip ;;
  g3) gate_reasoning ;;
  *) echo "usage: $0 g2|g3" >&2; exit 2 ;;
esac
