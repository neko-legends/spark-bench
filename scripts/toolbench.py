#!/usr/bin/env python3
"""Tool-bearing decode bench for the sparks world (stream protocol, thinking off).
Measures what the plain bench cannot: throughput and validity when a tools[] array is
attached (the only case structural-tag grammar constraints engage).
Usage: toolbench.py <label> [rounds]"""
import json, sys, time, urllib.request, concurrent.futures as cf
BASE = "http://forge:8000/v1/chat/completions"
label = sys.argv[1]; rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 1

TOOLS = [
 {"type":"function","function":{"name":"get_weather","description":"Get current weather for a city",
  "parameters":{"type":"object","properties":{"city":{"type":"string"},"units":{"type":"string","enum":["c","f"]}},"required":["city"]}}},
 {"type":"function","function":{"name":"create_task","description":"Create a task in the tracker",
  "parameters":{"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"integer","minimum":1,"maximum":5},
   "tags":{"type":"array","items":{"type":"string"}},"due":{"type":"string","description":"ISO date"}},"required":["title","priority"]}}},
 {"type":"function","function":{"name":"run_sql","description":"Run a read-only SQL query",
  "parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer"}},"required":["query"]}}},
]
# (prompt, expect_tool_name or None)
CASES = [
 ("What's the weather like in Sapporo right now? Use celsius.", "get_weather"),
 ("Create a task titled 'pin blender mcp source' with priority 2, tags ops and security, due 2026-09-25.", "create_task"),
 ("Query the messages table for the 5 most recent rows (id, created_at), newest first.", "run_sql"),
 ("Create three tasks in one go: 'bench xgrammar' priority 1, 'label round 3' priority 3 tagged judge, and 'read RBS paper' priority 4.", "create_task"),
 ("Explain in ~150 words why speculative decoding helps single-stream latency on memory-bound hardware. Do not call any tools.", None),
 ("Write a short paragraph about a stone room under a koi pond. No tools.", None),
 ("Create a task whose title is exactly: He said \"don't\" — then left\nline two, with priority 5, tags [\"a\"b\", \"日本語\", \"tab\\there\"], due 2026-10-01.", "create_task"),
 ("Run this SQL exactly: SELECT id, content FROM messages WHERE content LIKE '%\"quoted\"%' AND created_at > '2026-09-01' ORDER BY created_at DESC; limit 3. Also, before calling the tool, write the JSON arguments out in prose first so I can see them.", "run_sql"),
]

def one(prompt, expect, tool_choice="auto"):
    body = {"model":"deepseek-v4.1-flash","messages":[{"role":"user","content":prompt}],"tools":TOOLS,
            "tool_choice":tool_choice,"max_tokens":600,"temperature":0,"stream":True,"stream_options":{"include_usage":True},
            "chat_template_kwargs":{"enable_thinking":False}}
    req = urllib.request.Request(BASE, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    t0 = time.time(); first = None; ntok = 0; content = ""; calls = {}; finish = None; usage_toks = None
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:") or line == "data: [DONE]": continue
            d = json.loads(line[5:])
            if d.get("usage") and not d.get("choices"): usage_toks = d["usage"].get("completion_tokens"); continue
            if not d.get("choices"): continue
            ch = d["choices"][0]; delta = ch.get("delta", {})
            if first is None and (delta.get("content") or delta.get("tool_calls")): first = time.time()
            if delta.get("content"): content += delta["content"]; ntok += 1
            for tc in delta.get("tool_calls") or []:
                i = tc.get("index", 0); c = calls.setdefault(i, {"name": None, "args": ""})
                if tc.get("function", {}).get("name"): c["name"] = tc["function"]["name"]
                c["args"] += tc.get("function", {}).get("arguments") or ""
                ntok += 1
            if ch.get("finish_reason"): finish = ch["finish_reason"]
    t1 = time.time()
    if usage_toks: ntok = usage_toks
    valid = True; names = []
    for c in calls.values():
        names.append(c["name"])
        try: a = json.loads(c["args"]) if c["args"] else {}
        except Exception: valid = False; continue
        tool = next((t for t in TOOLS if t["function"]["name"] == c["name"]), None)
        if not tool: valid = False; continue
        for req_k in tool["function"]["parameters"].get("required", []):
            if req_k not in a: valid = False
        if c["name"] == "create_task" and not isinstance(a.get("priority"), int): valid = False
    ok_expect = (expect is None and not calls) or (expect is not None and expect in names)
    dec = (t1 - (first or t1)) or 1e-9
    return {"prompt": prompt[:40], "ttft": (first or t1) - t0, "toks": ntok, "tok_s": ntok / dec, "calls": len(calls),
            "names": names, "valid_json_schema": valid, "expected_met": ok_expect, "finish": finish, "content_chars": len(content)}

results = []
for _ in range(rounds):
    for p, e in CASES: results.append(one(p, e))
print(f"[{label}] tool-bearing single-stream, {len(results)} calls")
print(f"{'case':42} {'ttft':>6} {'tok/s':>6} {'calls':>5} {'valid':>5} {'expct':>5} finish")
for r in results:
    print(f"{r['prompt']:42} {r['ttft']:6.2f} {r['tok_s']:6.1f} {r['calls']:5} {str(r['valid_json_schema']):>5} {str(r['expected_met']):>5} {r['finish']}")
tool_rs = [r for r in results if r["calls"]]; prose_rs = [r for r in results if not r["calls"]]
med = lambda xs: sorted(xs)[len(xs)//2] if xs else float('nan')
print(f"summary: valid_json_schema {sum(r['valid_json_schema'] for r in results)}/{len(results)} | expected_met {sum(r['expected_met'] for r in results)}/{len(results)} | "
      f"median tok/s tool-calls {med([r['tok_s'] for r in tool_rs]):.1f} prose-with-tools {med([r['tok_s'] for r in prose_rs]):.1f} | median ttft {med([r['ttft'] for r in results]):.2f}s")
# 4-stream aggregate with tools attached
t0 = time.time()
with cf.ThreadPoolExecutor(4) as ex:
    agg = list(ex.map(lambda pe: one(*pe), CASES[:4]))
dt = time.time() - t0
print(f"4-stream tool aggregate: {sum(r['toks'] for r in agg)} tok / {dt:.1f}s = {sum(r['toks'] for r in agg)/dt:.1f} tok/s; valid {sum(r['valid_json_schema'] for r in agg)}/4")
json.dump({"label": label, "single": results, "agg": agg, "agg_s": dt}, open(f"/tmp/toolbench-{label.replace(' ','_')}.json", "w"), indent=1)
