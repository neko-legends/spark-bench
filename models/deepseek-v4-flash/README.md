# DeepSeek V4 Flash

**2026-09-05: not serving; archived NVFP4/DSpark TP4 recipe.**

- [Recipe entry points and deployment prerequisites](nvfp4-tp4/README.md)
- [Dated benchmark history and original launch guide](../../README.md#deepseek-v4-flash)
- [Shared fabric runbook](../../docs/FABRIC.md)

This lane uses a different image, checkpoint, speculative-decoding implementation
and KV format from Qwen and GLM. Do not combine their launch parameters.
Historical headline figures use different workloads and timing definitions;
consult the dated history rather than comparing isolated headline numbers.

The existing root Compose/patch layout and `scripts/*dspark*` implementations
are preserved to avoid breaking deployed paths. The model-local scripts are
thin entry-point wrappers, not divergent copies of the deployment logic.
