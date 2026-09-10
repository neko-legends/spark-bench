"""Read-only, bounded GitHub source audit; writes only alongside this script."""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'upstream'
def get(url, name):
    req = urllib.request.Request(url, headers={'User-Agent':'spark-bench-source-audit', 'Accept':'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        (ROOT / name).write_bytes(data)
        print(name, len(data), url)
        return json.loads(data) if name.endswith('.json') else data
    except Exception as exc:
        print('FAILED', url, str(exc))
        return None

repo='MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks'
head=get(f'https://api.github.com/repos/{repo}/commits/HEAD','recipe-head.json')
if head:
    sha=head['sha']
    get(f'https://api.github.com/repos/{repo}/compare/eb0469fbb2b49fd7c025f594a3339a121e58f7a9...{sha}','recipe-compare.json')
    get(f'https://raw.githubusercontent.com/{repo}/{sha}/overlay/exl3.py','recipe-latest-exl3.py')
for repo,path,name in [
 ('turboderp-org/exllamav3','exllamav3/exllamav3_ext/quant/exl3_moe.cu','exllama-moe'),
 ('vllm-project/vllm','vllm/v1/worker/gpu/spec_decode/dflash/utils.py','vllm-dflash'),
 ('Reederey87/glm53-flash-exl3-2x-dgx-spark','README.md','reederey')]:
    history=get(f'https://api.github.com/repos/{repo}/commits?path={path}&per_page=8',name+'-history.json')
    if isinstance(history,list) and history:
        get(f'https://raw.githubusercontent.com/{repo}/{history[0]["sha"]}/{path}',name+'-latest-source.txt')
