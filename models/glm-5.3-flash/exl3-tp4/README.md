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

## For external users: what you build vs. what you just download

**You do NOT hand-build any kernel.** The fat-expert CUDA kernel
(`exl3_fat_gemm.cu`) lives in the upstream recipe's `overlay/` at the pinned
commit in `UPSTREAM-COMMIT.txt` and is compiled automatically when the Docker
image builds. One-time steps:

1. **Image (build once, ~long):** clone
   [MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks)
   at the pinned commit, `docker build -t local/glm53-exl3:e2 .` on all four
   nodes (or `docker save | ssh docker load` one build everywhere). The
   `ghcr.io/miaai-lab/...:exl3` prebuilt tag predates the E2 kernel — use it
   only if you don't need the 2× cold-prefill gains.
2. **Weights (download):** HF `Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw` +
   `incoai/GLM-5.3-Flash-DFlash2` on all four nodes (see launcher paths).
3. **NCCL:** staged automatically by the launcher (it extracts the image's pip
   NCCL 2.30.7 to the host on first run — the stock image NCCL breaks RoCE).
4. **Launcher:** copy this directory's `launch-glm53-exl3-tp4.sh` to your head
   node and edit the host-path variables at the top (`MODEL_HOST`,
   `DFLASH_HOST`, fabric IPs if yours differ). Standing bench config:
   `ASYNC_SCHEDULING=1 DFLASH_TOKENS=7 GLM53_MIXED_PREFILL_SMALL_OK=2048` —
   and do **not** force `NCCL_ALGO`/`NCCL_PROTO` (see main README dead-ends).

No other manual compilation. Everything else (boot-shape warmup, patches) is
runtime-mounted from the upstream checkout by the launcher itself.
