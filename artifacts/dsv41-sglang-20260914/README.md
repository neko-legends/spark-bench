# DSV4.1-Flash on SGLang TP4 — serving world since 2026-09-14

Snapshot of how the 4× DGX Spark serving world is actually configured, so the
next person (or agent) can rebuild it without archaeology. Narrative and
numbers: the `2026-09-14 → 15` section of the top-level README.

| file | what |
|---|---|
| `kit/UPSTREAM_HEAD` | commit of [MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks) the world runs (clone lives at `forge:~/dsv41-sglang-trial-20260914/mia`) |
| `kit/env.tp4.redacted` | our `.env.tp4` — fabric (RoCE rail), NFS share, 1M ctx / 8M KV pin / 8 seats / 1024 chunk, `--enable-session-radix-cache`, Mia's 2026-09-15 hardening knobs, **k=5 kept** |
| `kit/nfs-share.local.patch` | our one local patch to the kit (`local -a` fix + dsv41-nfs exporter reuse) — reapply after `git pull` |
| `kit/recover-sglang.sh` | forge-side recovery entry: stop → memory drain → **share before serve** → serve → probe → prewarm |
| `../../scripts/dsv41-recover-sglang.sh` | nest/watchdog-side wrapper: `/v1/loads` busy-vs-wedged check before any restart |

Restart procedure (≈20 min: 8 min weight read + draft + KV + CUDA graphs + prewarm):

```bash
systemctl --user stop spark-forge-watchdog.timer          # on eva-core: don't let the watchdog fight you
ssh forge 'cd ~/dsv41-sglang-trial-20260914/mia && ./stop.sh; sleep 5; nohup ~/dsv41-sglang-trial-20260914/recover-sglang.sh > /tmp/recover.log 2>&1 &'
# wait for RECOVERED in /tmp/recover.log, then:
systemctl --user start spark-forge-watchdog.timer
```

Taking an upstream update: `git stash && git pull && git stash pop` (keeps the nfs patch),
diff `.env.tp4.example` against `kit/env.tp4.redacted`, merge knobs you want, `./start-tp4.sh build`
(rebuilds the overlay image on all nodes while serving continues), then the restart above.
Measure with `scripts/bench-decode.py`'s stream protocol — **not** non-streaming wall time,
which includes prefill and cost us a false-alarm bisection on 2026-09-15.
