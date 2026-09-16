import json, sys, urllib.request
sys.path.insert(0, '/sgl-workspace/sglang/python/sglang/srt/entrypoints/openai')
import encoding_dsv41 as enc

tool_payload = {"type":"function","function":{"name":"lookup_fixture","description":"Retrieve a stored test value.","parameters":{"type":"object","properties":{"key":{"type":"string"}},"required":["key"],"additionalProperties":False}}}
assistant_call = {"role":"assistant","content":"I'll retrieve the value for key \"alpha\" using the lookup_fixture tool.","tool_calls":[{"id":"call_1","type":"function","function":{"name":"lookup_fixture","arguments":"{\"key\": \"alpha\"}"}}]}
tool_result = {"role":"tool","tool_call_id":"call_1","content":"{\"value\":42}"}
messages = [
    {"role":"system","content":"","tools":[tool_payload]},
    {"role":"user","content":"Use lookup_fixture to retrieve the value for key alpha. Do not guess."},
    assistant_call,
    tool_result,
]
prompt, media = enc.encode_messages(messages, thinking_mode="chat", return_multi_modal_data=True)
print("=== SECOND-TURN PROMPT (tail 1500 chars) ==="); print(prompt[-1500:])
payload = {"text": prompt, "sampling_params": {"temperature": 0, "max_new_tokens": 200}}
r = urllib.request.Request('http://127.0.0.1:8000/generate', headers={'Content-Type':'application/json'}, data=json.dumps(payload).encode())
with urllib.request.urlopen(r, timeout=300) as resp:
    res = json.loads(resp.read())
print("=== RAW OUTPUT ==="); print(res.get('text')[:600])
