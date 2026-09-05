# GLM 5.3 Flash

**2026-09-05: stopped for the Qwen campaign.** Archived recipes, not a live endpoint.

- [Primary EXL3 TP4 recipe](exl3-tp4/README.md): vLLM, EXL3 4bpw, DFlash2.
- [Dated benchmark history and operating notes](../../README.md#glm-5-3-flash).
- Earlier experiments: [SGLang findings](sglang-attempt/FINDINGS-2026-08-26.md)
  and [vLLM findings](vllm-attempt/FINDINGS-2026-08-26.md).

The root files in this directory include earlier experimental Compose/overlay
inputs; they are not interchangeable with the later `exl3-tp4/` recipe. Start
with that recipe and read the dated hardening notes before choosing a launcher.

Do not restart GLM while Qwen occupies the cluster. Check recovery watchdogs,
image identity, all-rank memory headroom and fabric settings before an approved
switch. A short benchmark is not a substitute for a long soak: historical
OOM incidents and the resulting memory-budget changes are documented in the
main history. Older present-tense entries describe their date, not today's serve.
