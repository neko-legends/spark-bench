import json, time, urllib.request, random, string
BASE="http://127.0.0.1:8000"; MODEL="qwen3.8-flash-next"
NEEDLE="The secret launch code for the observatory telescope is NEBULA-7742-KOALA."
QUESTION="What is the secret launch code for the observatory telescope? Answer with just the code."
WORDS="the quick brown fox jumps over a lazy dog near the river bank while autumn leaves drift slowly past the old mill and distant thunder rolls over quiet hills".split()
def filler(n):
    rnd=random.Random(42); return " ".join(rnd.choice(WORDS) for _ in range(n))
def ask(prompt, mt=64):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":mt,"temperature":0,"chat_template_kwargs":{"enable_thinking":False}}
    req=urllib.request.Request(BASE+"/v1/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    t0=time.monotonic()
    r=json.load(urllib.request.urlopen(req,timeout=900))
    return r["choices"][0]["message"].get("content") or "", time.monotonic()-t0
# rough token budget: ~1.3 tok/word for this filler; calibrate sizes
for target in (4000, 32000, 128000):
    words=int(target/1.35)
    for depth in (0, 50, 100):
        body=filler(words)
        pos=int(len(body)*depth/100)
        hay=body[:pos]+" "+NEEDLE+" "+body[pos:]
        ans,dt=ask(hay+"\n\n"+QUESTION)
        ok="NEBULA-7742-KOALA" in ans
        print(json.dumps({"ctx":target,"depth":depth,"pass":ok,"s":round(dt,1),"ans":ans[:60]}),flush=True)
