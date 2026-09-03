# GLM-5.3-Flash EXL3 — TP4 launchers (4× DGX Spark)

Our TP4 adaptation of the MiaAI 2-node EXL3 kit. Image `local/glm53-exl3:e2` is built
from the upstream repo at the commit in `UPSTREAM-COMMIT.txt` (Dockerfile unchanged);
everything TP4-specific lives in these launchers, which mount the `overlay/` patches
at runtime.

- `launch-glm53-exl3-tp4.sh` — base checkpoint (`Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw`)
- `launch-glm53-uncens-exl3-tp4.sh` — our uncensored quant (`neko-legends/GLM-5.3-Flash-Uncensored-EXL3`)

State as of 2026-09-02: E2 fat-expert kernel, MNBT 7168, spinwait 16 ms, PR63 chat
template, mixed-prefill `skip`, 1M ctx, DFlash2 k=7 draft-TP1. Bench archive in
`../../../results/` and harnesses in `../../../scripts/`.
