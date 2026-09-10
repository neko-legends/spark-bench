import re
p="/home/jun/launch-glm53-exl3-tp4.sh"; s=open(p).read()
old="MAX_NUM_BATCHED_TOKENS=7168\n"
assert old in s
s=s.replace(old,"MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-7168}\n",1)
old="  -e MAX_NUM_SEQS=$MAX_NUM_SEQS -e MAX_NUM_BATCHED_TOKENS=$MAX_NUM_BATCHED_TOKENS \\\n"
assert old in s, "env line"
s=s.replace(old, old+"  -e SKIP_PATCHES=\"${SKIP_PATCHES:-}\" \\\n",1)
lines=s.split("\n"); out=[]; replaced=0; helper=False
for ln in lines:
    m=re.match(r"^\[ -f (/opt/glm53/patch_[a-z0-9_]+\.py) \] && python3 \1 \|\| true$", ln)
    if m:
        if not helper:
            out.append('# C4-sweep toggles (2026-09-03): SKIP_PATCHES="patch_a.py patch_b.py" skips named patches.')
            out.append('apply_patch() { local p="$1" b; b=$(basename "$p"); case " ${SKIP_PATCHES:-} " in *" $b "*) echo "[patch] SKIPPED $b (SKIP_PATCHES)"; return 0;; esac; [ -f "$p" ] && python3 "$p" || true; }')
            helper=True
        out.append(f"apply_patch {m.group(1)}"); replaced+=1
    else: out.append(ln)
assert replaced>=10, replaced
open(p,"w").write("\n".join(out)); print("ok patches:",replaced)
