<h1 align="center">⚡ spark-bench</h1>

<p align="center">
  <b>Four DGX Sparks · one TP=4 world · every lesson, dated.</b><br>
  Recipes, configs and benchmarks for running frontier MoE models on <b>4× NVIDIA DGX Spark</b> (GB10).
</p>

<p align="center">
  <img alt="cluster: 4× DGX Spark" src="https://img.shields.io/badge/cluster-4%C3%97%20DGX%20Spark-76b900">
  <img alt="serving: DeepSeek V4.1 Flash on TensorFold" src="https://img.shields.io/badge/serving-DeepSeek%20V4.1%20Flash%20%C2%B7%20TensorFold-2a78d6">
  <img alt="updated 2026-10-07" src="https://img.shields.io/badge/updated-2026--10--07-8a8984">
</p>

## 🧭 Lanes

One cluster, one model at a time. Click a lane for its recipe.

| | Lane | Status | Best numbers |
| :-: | --- | --- | --- |
| 🐋 | **[DeepSeek V4.1 Flash · TensorFold](models/deepseek-v4.1-flash/tensorfold-4x/README.md)** | 🟢 **serving** | **123** code tok/s on a short prompt (**104** averaged 1k–160k) · **67** prose · **200** for 4 users · cold 160k prompt **36 s** |
| 🐋 | [DeepSeek V4.1 Flash · SGLang](models/deepseek-v4.1-flash/README.md) | 🟡 rollback | 38 prose / 54–62 code tok/s · 1M context |
| 🐋 | [DeepSeek V4.1 Flash · vLLM](docs/dsv41-vllm-tp4.md) | 🟡 fallback | 71 code tok/s · 109 tok/s for 4 users |
| 🦄 | [Qwen 3.8 Flash Next](models/qwen-3.8-flash-next/README.md) | ⚪ archived | 91 code tok/s · 600 tok/s for 16 users |
| 🐉 | [GLM 5.3 Flash](models/glm-5.3-flash/README.md) | ⚪ archived | 129 tok/s for 4 users · 1M context |
| 🐳 | [DeepSeek V4 Flash](models/deepseek-v4-flash/README.md) | ⚪ archived | 136 tok/s, one user (record) · 182 for 4 |

<sub>tok/s = writing speed. Rulers differ between lanes; each lane page says how its numbers were measured.</sub>

## 🧠 Why this repo exists

This repo is about **four Sparks working as one machine**, and it keeps **every optimization we tried**: what we changed, what it measured, what failed and why, all dated.

That history is the point. When a new model comes out, the next engineer (or the next **AI agent**) should start from the best known config and the known traps, not find them again. Old lanes stay here on purpose: their lessons carry over to new models.

## 🤖 For AI agents

1. **Pick a lane** above. Its page is the recipe: image, flags, setup, rollback.
2. **Read the lane's journal** (`models/<model>/JOURNAL.md`) for every dated change, A/B result and dead end.
3. **Check the evidence.** Raw runs are in `artifacts/` and `results/`, linked from each entry.
4. **Wire the fabric first** ([docs/FABRIC.md](docs/FABRIC.md)), then follow the operator rules in [models/README.md](models/README.md).
5. **Write down what you learn**: a dated journal entry with its numbers, how they were measured, and its config. Never overwrite old evidence.

### Lessons that carry over

- 🔌 **Fix the network first.** One IPv4 address per NCCL port. A leftover address alone cost 30% ([V4](models/deepseek-v4-flash/JOURNAL.md)). Getting RoCE right was worth 2.5× ([GLM](models/glm-5.3-flash/JOURNAL.md)).
- 📏 **Measure decode from the stream:** count usage tokens from the first delta to the last. Wall time includes prompt reading, and chunk counts undercount speculative decoding.
- 🎲 **Boots vary.** Compare A/B/A with a same-night control. `vm.compaction_proactiveness=0` ended a 50/50 slow-boot lottery ([V4.1](models/deepseek-v4.1-flash/JOURNAL.md#dsv41-2026-09-13)).
- 🔥 **Warm up before you trust a number.** JIT kernels and draft acceptance start cold (acceptance went from 2.6 at first boot to 7.95 an hour later). Warm the kernels at boot.
- 🧮 **Unified memory is GPU memory.** Leave headroom (GLM crashed at 0.85 and is stable at 0.80) and drop the page cache before a start.
- 💾 **No bulk disk writes on a serving node.** Engram reads NVMe on every step, so one slow rank stalls all four.
- 🕵️ **Fallbacks are silent.** Check the boot log for the transport you expect (`over RoCE`, not NCCL) after every start. A leftover failure file cost TensorFold 12–19% for two days ([report](artifacts/tensorfold-v41-roce-20261007/REPORT.md)).
- ⏳ **Busy is not wedged.** Check the queue before restarting. A server is alive only if it answers a real 1-token completion.
- ✍️ **Speculative decoding depends on the text.** Code and math run about 2× faster than prose. Always quote task, prompt length and thinking mode.
- 🪶 **Fewer bytes per token, faster decode.** 2.9-bit EXL3 gave 1.7× over FP8 on the same four Sparks.
- 🧩 **Uneven splits hide bugs.** Test the request shapes that stress them, like `top_k` above one rank's vocabulary slice.

---

<a id="dsv41-tensorfold"></a>

## 🐋 DeepSeek V4.1 Flash · TensorFold · 🟢 serving

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-dsv41-tensorfold-dark.svg">
  <img alt="DeepSeek V4.1 Flash on TensorFold, four Sparks: writing speed over 1k-160k prompts prose 66 vs 38 tok/s for SGLang, code 104 vs 57; code on a short prompt 123; four users 122 vs 76, and 200 steady; cold 160k-token prompt 97-100 s on 2026-10-04, 39 s pipelined on 2026-10-05, 36 s on the G19 engine live since 2026-10-07, SGLang 48-52 s" src="docs/images/lane-dsv41-tensorfold-light.svg">
</picture>

- ⚡ **1.7× SGLang's decode** at every prompt length from 1k to 160k: jayleaton's engine, ported by us to four Sparks.
- 🏭 **Long prompts run as a pipeline** across the Sparks: a cold 160k-token prompt takes 36 s (was 100 s).
- 🛠️ **The bugs from Jay's review are fixed** (crash at `top_k` above 32,256): same replies byte for byte, same speed.
- 🆕 **Jay's newer engine (G19), live since 2026-10-07:** 420K context and image input; long prompts ~7% faster. [Report](artifacts/tensorfold-v41-g19-20261005/REPORT.md).
- 🚀 **One user, short code prompt: 123 tok/s; four users: 200 tok/s steady** (2026-10-07, `m2bench`). Two Sparks run the same benchmark at ~80. Long prompts average 104 (code) / 67 (prose) over 1k–160k.
- 🔌 **Back on RoCE (2026-10-07):** a stale failure file had silently forced the slower NCCL path for two days. Fixed: prose 66.5, code 104.1 tok/s, 4 users 122. [Report](artifacts/tensorfold-v41-roce-20261007/REPORT.md).

📦 [Recipe: our four-Spark fork](https://github.com/neko-legends/deepseek-v41-tensorfold-spark) · 📘 [Setup & limits](models/deepseek-v4.1-flash/tensorfold-4x/README.md) · 📓 [Journal](models/deepseek-v4.1-flash/JOURNAL.md) · 🧾 Reports: [decode](artifacts/tensorfold-v41-roce-20261007/REPORT.md), [prompt reading](artifacts/tensorfold-v41-prefill-20261005/REPORT.md), [fixes](artifacts/tensorfold-v41-fixes-20261005/REPORT.md)

<a id="dsv41-sglang"></a>

## 🐋 DeepSeek V4.1 Flash · SGLang · 🟡 rollback

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-dsv41-sglang-dark.svg">
  <img alt="DeepSeek V4.1 Flash on SGLang TP4: EP2 vs EP4 across 1k-160k prompts; prose 37.7-38.3 vs 34.1-35.9 tok/s, code 53.8-62.2 vs 47.5-58.1" src="docs/images/lane-dsv41-sglang-light.svg">
</picture>

- 🧪 **Uncensored FP8** on [Mia's kit](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks), DSpark k=3, **1M context** (needle-checked).
- 🔀 **EP2 beat EP4**: prose +5–12%; code mixed, up to +19% at 80k–160k.
- 📦 **Engram pack published**, so you can skip the slow per-node pack step: [Hugging Face](https://huggingface.co/neko-legends/DeepSeek-V4.1-Flash-uncensored-engram-4x-spark).

📘 [Profile & rollback](models/deepseek-v4.1-flash/README.md) · 📓 [Journal: the fixes it took](models/deepseek-v4.1-flash/JOURNAL.md#dsv41-sglang-2026-09-14) · 🧾 [Depth sweep](artifacts/tensorfold-v41-depth-20261001/REPORT.md)

<a id="deepseek-v4-1-flash"></a>

## 🐋 DeepSeek V4.1 Flash · vLLM · 🟡 fallback

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-dsv41-vllm-dark.svg">
  <img alt="DeepSeek V4.1 Flash vLLM TP4 champion, one user by task (tok/s): coding 71.4, format 71.2, math 70.0, reasoning 58.6, JSON 45.3, prose 31.7, summary 27.9, narrative 27.7; 4 users 109 total, 6 users 137" src="docs/images/lane-dsv41-vllm-light.svg">
</picture>

- 💾 **A 510 GB model on four Sparks:** each rank reads its quarter of the Engram tables from NVMe.
- 🎲 **The "gains" were the boot lottery:** A/B/A showed the champion settings matched the baseline.
- 🧯 **Tool calls came back clean here** where our first SGLang lane corrupted them. That is why this lane shipped.

📘 [Recipe & findings](docs/dsv41-vllm-tp4.md) · 📓 [Journal](models/deepseek-v4.1-flash/JOURNAL.md#deepseek-v4-1-flash) · 🧾 [Raw runs](artifacts/dsv41-vllm-20260910/)

<a id="qwen-3-8-flash"></a>

## 🦄 Qwen 3.8 Flash Next · ⚪ archived

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-qwen38-dark.svg">
  <img alt="Qwen 3.8 Flash Next on four Sparks, MTP k=4 + GEMV vs k=2 baseline: one user code 91.3 vs 70.7, prose 49.2 vs 53.4 tok/s; total for 4/8/16 users 247.9/404.3/600.5 vs 198.6/344.4/526.8" src="docs/images/lane-qwen38-light.svg">
</picture>

- 🚀 **MTP k=4 + a GEMV kernel:** +29% code for one user, +14% total at 16 users. Prose −8%, the trade-off.
- 🤝 **Real agent tasks:** quality matched or beat the cloud on all five; up to 29× faster on four of them.
- 📦 Official NVIDIA NVFP4, TP4+EP, 262k context.

📘 [Recipe](models/qwen-3.8-flash-next/README.md) · 📓 [Journal](models/qwen-3.8-flash-next/JOURNAL.md) · 🧾 [Campaign report](results/qwen38-tuning-2026-09-06/REPORT.md)

<a id="glm-5-3-flash"></a>

## 🐉 GLM 5.3 Flash · ⚪ archived

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-glm53-dark.svg">
  <img alt="GLM 5.3 Flash EXL3 TP4: cold 100k prompt read at 773 tok/s before the E2 kernel, 1110 with it, 1240 at step A, 1562 at C, 1560 verified; 4-user total writing 107.9 (A), 115.7 (B), 117.0 (C), 128.9 (C verified)" src="docs/images/lane-glm53-light.svg">
</picture>

- 📚 **Long prompts read 2× faster** with MiaAI's E2 fat-expert kernel (300k-token prompt in ~4 min).
- 🔓 **Our own uncensored EXL3 quant**, published: [Hugging Face](https://huggingface.co/neko-legends/GLM-5.3-Flash-Uncensored-EXL3).
- 🧯 **The 0.85 memory setting crashed it after 13 hours;** use 0.80.

📘 [Recipe](models/glm-5.3-flash/README.md) · 📓 [Journal](models/glm-5.3-flash/JOURNAL.md) · 🧾 [Verified runs](results/)

<a id="deepseek-v4-flash"></a>

## 🐳 DeepSeek V4 Flash · ⚪ archived

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/lane-dsv4-dark.svg">
  <img alt="DeepSeek V4 Flash vLLM TP4, one user: best case 136 median / 145.5 peak tok/s, 5-10k prompt code 79-93, 5-10k chat 72-89, ~50k deep session 66-74; 4 users 182 total" src="docs/images/lane-dsv4-light.svg">
</picture>

- 🏆 **The fastest single-user decode we have measured here:** 136 tok/s median, 145.5 peak.
- 🗺️ **Real chat speed is lower** (66–93 tok/s), depending on prompt length and how predictable the text is.
- 🔌 **This lane taught us the one-IPv4 rule:** removing a leftover address took decode from 103 to 136 tok/s.

📘 [Recipe](models/deepseek-v4-flash/README.md) · 📓 [Journal](models/deepseek-v4-flash/JOURNAL.md) · 🧾 [Raw runs](results/)

---

## 🧰 Also here

- 🔌 **[Fabric runbook](docs/FABRIC.md)**: CX-7, RoCE, the switch. Most "TP4 is slow" reports are network problems, not the model.
- 🔥 **[Catch-up sidecar](docs/CATCHUP.md)**: keeps a long chat warm in the local model's cache while you talk to another model.

<details>
<summary><b>📖 Glossary</b></summary>

| Term | Plain meaning |
|---|---|
| token | A chunk of a word (~¾ of one). The unit models read and write. |
| prefill ("reading") | The model reading your whole message before it can answer. |
| decode ("writing") | The model writing its answer. The speed you feel. |
| TP=4 | Four machines each hold ¼ of the model and confer on every token. |
| EP | Expert parallel: the MoE experts are spread across ranks. |
| KV / prefix cache | The model's short-term memory of your conversation. |
| speculative decoding (MTP / DFlash2 / DSpark) | Draft several tokens ahead, keep the good ones. Fast on code, slower on prose. |
| C1 / C4 | One stream / four at once. C4 is total throughput, not per-user speed. |
| RoCE / fabric | The 200G cables and switch between the Sparks. |

</details>

<details>
<summary><b>🗂️ Layout</b></summary>

```text
models/<model>/              recipe (README.md) + dated history (JOURNAL.md) per model
models/README.md             lane index + rules for operators and agents
artifacts/  results/         raw, dated evidence behind every number
docs/FABRIC.md               CX-7 / RoCE / switch runbook (read before benching)
docs/CATCHUP.md              catch-up sidecar · docs/PROTOCOL.md · docs/BRIDGES.md
docs/images/                 one chart per lane (light + dark SVG)
scripts/                     launchers, bench harnesses, recovery, charts/
catchup/                     the sidecar (stdlib only)
docker-compose.dspark-tp4.yml, patches/, vllm_patch_gb10/   DeepSeek V4 serving stack
```

</details>

<p align="center"><sub>A <b>Neko Legends</b> project 🐾 · formerly <code>dspark-kv-prefill-catchup</code></sub></p>
