import json, time, urllib.request, threading, uuid
BASE="http://127.0.0.1:8000"; MODEL="qwen3.8-flash-next"
CODE=("Write a complete, idiomatic Python implementation of a binary search tree with insert, delete, search, traversal, height, docstrings, and tests. Code only. Add exhaustive tests using pytest, covering edge cases.")
def gen(prompt, max_tokens):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt+" nonce="+uuid.uuid4().hex}],"max_tokens":max_tokens,"temperature":0,"stream":True,"stream_options":{"include_usage":True},"chat_template_kwargs":{"enable_thinking":False}}
    req=urllib.request.Request(BASE+"/v1/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    tf=tl=None; usage=None
    with urllib.request.urlopen(req,timeout=900) as r:
        for line in r:
            if not line.startswith(b"data:"): continue
            p=line[5:].strip()
            if p==b"[DONE]": break
            try: c=json.loads(p)
            except: continue
            if c.get("usage"): usage=c["usage"]
            d=((c.get("choices") or [{}])[0].get("delta") or {})
            if d.get("content") or d.get("reasoning"):
                now=time.monotonic()
                if tf is None: tf=now
                tl=now
    ct=int((usage or {}).get("completion_tokens") or 0)
    return ct, (ct-1)/(tl-tf) if tf and ct>1 else 0
def run(n, mt=1200):
    outs=[None]*n
    def w(i): outs[i]=gen(CODE, mt)
    ts=[threading.Thread(target=w,args=(i,)) for i in range(n)]
    t0=time.monotonic(); [t.start() for t in ts]; [t.join() for t in ts]; t1=time.monotonic()
    tot=sum(o[0] for o in outs if o); per=[round(o[1],1) for o in outs if o]
    print(f"AGG x{n}: e2e={tot/(t1-t0):.1f} tok/s  per-stream={per}  tokens={tot}", flush=True)
for n in (4,8,16): run(n)
