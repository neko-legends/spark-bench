import json, time, urllib.request, hashlib
BASE="http://127.0.0.1:8000"; MODEL="qwen3.8-flash-next"
def chat(prompt, max_tokens=400, think=False):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0,"stream":True,"stream_options":{"include_usage":True},"chat_template_kwargs":{"enable_thinking":think}}
    req=urllib.request.Request(BASE+"/v1/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    tf=tl=None; usage=None; text=""
    with urllib.request.urlopen(req,timeout=600) as r:
        for line in r:
            if not line.startswith(b"data:"): continue
            p=line[5:].strip()
            if p==b"[DONE]": break
            try: c=json.loads(p)
            except: continue
            if c.get("usage"): usage=c["usage"]
            d=((c.get("choices") or [{}])[0].get("delta") or {})
            ch=d.get("content") or d.get("reasoning") or ""
            if ch:
                now=time.monotonic()
                if tf is None: tf=now
                tl=now; text+=ch
    ct=(usage or {}).get("completion_tokens",0)
    return text, ct, round((ct-1)/(tl-tf),1) if tf and ct>1 else 0
# greedy identity first
hs=[]
for _ in range(3):
    t,ct,ts=chat("What is the capital of Australia? Just the city.",64); hs.append(hashlib.sha256(t.encode()).hexdigest()[:10])
print("IDENTITY","PASS" if len(set(hs))==1 else "FAIL",hs)
CODE="Write a complete, idiomatic Python implementation of a binary search tree with insert, delete, search, traversal, height, docstrings, and pytest tests. Code only."
PROSE="Write a detailed 3-paragraph essay about the history of the transcontinental railroad."
for tag,p in [("code",CODE),("prose",PROSE)]:
    for think in (False,True):
        r=[]
        for _ in range(3):
            t,ct,ts=chat(p,400,think); r.append(ts)
        print("SS",tag,"think="+str(think),sorted(r)[1],"tok/s (median of",r,")")
