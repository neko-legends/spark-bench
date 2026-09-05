# DeepSeek NVFP4 TP4 — archived recipe entry points

Run from the **Forge/head machine**, not an arbitrary workstation. These wrappers
resolve the repository location and delegate without altering arguments/environment:

```bash
models/deepseek-v4-flash/nvfp4-tp4/status-dspark-tp4.sh
# Only after an approved model switch and prepared deployment:
models/deepseek-v4-flash/nvfp4-tp4/start-dspark-tp4.sh
models/deepseek-v4-flash/nvfp4-tp4/stop-dspark-tp4.sh
```

## Required inputs; this is not a one-command fresh-clone deployment

Read the [original launch guide](../../../README.md#deepseek-v4-flash) first.
The retained implementations are [start](../../../scripts/start-dspark-tp4.sh),
[status](../../../scripts/status-dspark-tp4.sh) and [stop](../../../scripts/stop-dspark-tp4.sh).

- Root [Compose file](../../../docker-compose.dspark-tp4.yml),
  [environment example](../../../.env.example), `patches/` and `vllm_patch_gb10/`
  remain in their original locations because bind mounts depend on that layout.
- `start` defaults to an operator-provided `.env.dspark.tp4.railb-200g.bench`
  and Compose file beside the legacy scripts. Those staging assumptions do not
  match a bare clone. Set **absolute `ENV_FILE` and `COMPOSE_FILE` explicitly**.
- `status`/`stop` default to root `.env`. Use the same explicit `ENV_FILE` for all
  three commands. Review host lists: the start script uses forge/anvil/ember/flame;
  status/stop use `HEAD_HOST` and comma-separated `WORKER_HOSTS`.
- Prepare matching paths on workers. The start script copies env, Compose and
  helper scripts, **not the complete patch/plugin tree or checkpoints**. Its remote
  staging also assumes companion env/Compose filenames beside the helper scripts.
  Inspect that staging before launch; arbitrary external filenames are not portable.
- Check Compose relative bind mounts on every host; changing the Compose location
  changes their resolution. Use absolute mount overrides when staging elsewhere.
- Verify the image, checkpoint/revision, encoding files, MTP settings, port, IP/HCA
  selection and memory budget against the intended historical run. Defaults alone
  do not reproduce every record. Preserve logs before any launcher removes containers.

Do not run start/stop while Qwen is serving. The status helper prints diagnostics;
its exit status alone is not a complete health gate. The launcher enables container
restart after its speculative-counter check; review that policy during a model switch.

This reorganization changes navigation only, not the runtime logic. Deployment
portability improvements need their own tested change; no cluster boot was performed.
