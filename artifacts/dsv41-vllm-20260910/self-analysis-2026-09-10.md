### elapsed 508s | prompt 953 | completion 5279 | reasoning 0 | finish stop

=== REASONING ===



=== ANSWER ===

# DeepSeek-V4.1-Flash on 4× DGX Spark: Deep Engineering Analysis

I'll be direct about uncertainty: I don't have privileged access to the exact GB10 memory subsystem, the actual dsv41 kernel source on your branch, or the DSpark acceptance statistics beyond what you gave me. Where I'm inferring, I'll say so. Where the numbers don't add up, I'll flag it.

---

## (a) Ranking the listed levers by expected gain

I'll rank by **expected tok/s gain at batch 1**, which is what your bimodal 48/70 problem is really about. Aggregate C6 is a different problem (KV bandwidth + all-reduce scaling) and I'll treat it separately.

### Tier 1 — likely >15% single-stream

**1. (14) Quantize Engram to FP4 → fully memory-resident.**
This is the single biggest structural win. Your Engram tables are ~203 GB FP8 across 4 ranks = ~51 GB/rank, and you're reading ~64 rows/token from NVMe. Each row is 256 B + scales. That's ~16 KB/token/rank of NVMe traffic, plus the Python `torch.unique` + 32-thread `preadv` + CPU dequant + H2D path. Your measured ~3 ms/step is dominated by this pipeline, not by the GPU.

If FP4 (with ue4m3 or per-128 scales) preserves enough n-gram fidelity — and for a lookup table it very likely does, since these are essentially learned embeddings, not weights that need fine dynamic range — each rank slice drops to ~26 GB. That fits in the 128 GB unified pool alongside the 81.6 GiB of weights + KV pool *if* you shrink KV pool or gmu. Expected: **eliminates ~2–2.5 ms/step of the 3 ms Engram path**, i.e. potentially +50–80% single-stream. Risk: quality regression on the exact categories where Engram matters (counting, tables — where your DSpark accept is 6). This is the lever I'd prototype first, with an A/B on your eval suite.

**2. (11) io_uring batch + GPU-side dequant of raw FP8 rows.**
Even if you don't go FP4, the current path is architecturally wrong for this hardware. `torch.unique` on CPU, then 32 Python threads doing `preadv`, then CPU dequant, then H2D — that's three serialization points and a GIL-adjacent fan-out. On GB10, host and device share LPDDR5X; the H2D "copy" is not a PCIe transfer, it's a memcpy across a unified aperture. So the right design is: **one io_uring submission of all unique row offsets → DMA into a pinned staging buffer → the GPU reads the raw FP8 bytes directly and dequants in the Engram kernel.** This removes the CPU dequant entirely and collapses the thread fan-out. Expected: **+15–30% single-stream**, and it stacks with (14). If you do (14), this lever becomes moot for the table itself but still applies to any residual spill.

**3. (12) Prefetch Engram rows for the 5 drafted tokens during draft stage.**
This is nearly free and you already listed it. DSpark drafts 5 tokens; their Engram n-gram lookups are almost certainly known before verification (the draft model conditions on the same context). Issuing those NVMe reads during draft compute hides the latency behind the draft forward. Expected: **+10–20% single-stream**, and it's the lever most likely to *fix the bimodality* (see part b). Do this regardless of (11)/(14).

### Tier 2 — 5–15%

**4. (3) Greedy draft at temp 0.**
You're running `draft_sample_method=probabilistic`. If your workload is mostly temp 0 (coding, math), probabilistic drafting is throwing away accept length. Greedy draft + block rejection typically adds 0.3–0.8 to mean accept length on deterministic tasks. Your math/coding are already at 71 tok/s; prose at 33 is where accept length is ~2. Expected: **+5–10% aggregate, more on prose if the draft is the bottleneck there** (it may not be — prose accept ~2 suggests the draft model itself is weak on prose, not that sampling is the issue).

**5. (2) DSpark k sweep 4/6/7.**
k=5 with mean accept 3.57 is not obviously optimal. The cost of drafting is roughly linear in k; the benefit saturates. On prose (accept ~2), k=5 is likely wasteful — you're paying for 5 draft forwards and getting 2 tokens. On counting/tables (accept ~6), k=5 is *capping* you. A per-category or adaptive k would help, but even a static k=4 or k=6 is worth a sweep. Expected: **+3–8%**, category-dependent.

**6. (9) NCCL algo/proto tuning for the small all-reduces.**
90 all-reduces at 4.4–5.7 ms total = ~50–63 µs each. On 200G RoCE with 4 nodes, that's high for what should be small messages. You're likely hitting a latency-bound regime where Tree vs Ring and LL vs Simple matter enormously. For small messages on 4 ranks, **Tree + LL128 or Simple** usually wins; NCCL defaults often pick Ring. Also check `NCCL_MIN_NCHANNELS` and whether you're paying a kernel-launch tax per collective. Expected: **+5–12% single-stream**, and it scales to C6 where all-reduce count grows.

**7. (1) Reduce host memory pressure so Engram rows get page cache.**
You have ~6 GB host free and swap in use. That's a red flag. If the Engram working set (hot n-grams) fit in page cache, you'd avoid NVMe reads entirely for the hot path. But 6 GB is not enough for a meaningful hot set, and swappiness is likely evicting useful pages. Fixing this is a prerequisite for (12) and (11) to pay off. Expected: **+5–15%, highly variable**, and it's the most likely *proximate* cause of bimodality.

### Tier 3 — <5% or uncertain

**8. (13) GPU-resident hot-row hash cache.**
Good idea in principle, but 6 GB free host and a KV pool at 731k tokens means you have almost no GPU memory to spare. You'd need to shrink KV pool or gmu to make room. If you can carve out even 2–4 GB for a hot-row cache (say the top 1M n-grams by frequency), it could eliminate most NVMe reads. But this competes with (14) for the same memory. **Do (14) first; (13) is a fallback if FP4 quality fails.**

**9. (5) Check MoE MXFP4 kernel path on SM120.**
Worth verifying, but your MoE weights are already FP4 and you're at 81.6 GiB/rank. If the kernel is falling back to a slower path on SM120, that's a real win, but I'd expect it to show up as a uniform slowdown, not bimodality. Expected: **unknown, possibly 0–10%**. Check `torch.profiler` for the MoE kernel name and whether it's using `cutlass` MXFP4 or a fallback.

**10. (6) vLLM compile fusion passes.**
Generic. On a 40-layer model with heavy custom ops (DSA, Engram, DSpark), the fusion opportunities are limited. Expected: **0–5%**.

**11. (7) Chunked prefill 4096.**
Only affects prefill, not decode. Your cold prefill is 1.0–1.5k tok/s; doubling chunk size might help or hurt depending on KV pressure. Not a decode lever.

**12. (4) Unlock GPU clock for prefill.**
Prefill-only. Doesn't touch decode bimodality.

**13. (8) DeepSelect top-k kernels.**
Marginal unless profiling shows top-k is hot. On batch 1, top-k over 384 experts is tiny.

**14. (10) Pin Engram reader threads to efficiency cores.**
This is backwards on GB10. The efficiency cores are for background work; you want the reader threads on performance cores to minimize latency, or better, eliminate them entirely (see 11). If anything, pin them to P-cores and give them real-time priority. Expected: **negative if done as listed**.

---

## (b) The bimodal 48-vs-70 behavior

This is the most diagnostically interesting thing in your data. Bimodal, not noisy. Runs land at ~48 or ~66–75, nothing in between. That pattern almost always means **a discrete state change**, not gradual contention.

My top hypotheses, ranked:

**1. Page cache hit vs miss on the Engram hot set.**
This is my leading hypothesis. If the hot n-gram rows for a given prompt happen to be in page cache when the run starts, you get ~70 tok/s. If they're not, every step pays NVMe latency and you get ~48. The fact that it's per-run (not per-token) suggests the hot set is established early and then stable. The 6 GB free host memory is exactly the regime where this flips. **Test:** run the same prompt 10× and check `vmstat` / `/proc/vmstat` for `pgmajfault` and NVMe read counts per run. If the 48 runs have 10× the major faults, this is it.

**2. DSpark accept-length regime change.**
Mean accept 3.57, but if a run's draft model happens to be in a good regime (e.g., the prompt is repetitive/countable), accept goes to 5–6 and you get 70. If it's in a bad regime (prose-like), accept ~2 and you get 48. But you said prose is consistently 33, so this would predict three modes, not two. Unless your "single stream decode" category mix is bimodal. **Test:** log accept length per run and correlate with tok/s.

**3. NCCL collective path selection.**
NCCL sometimes picks different algorithms based on message size, which can vary slightly per step (e.g., due to padding). If some runs consistently hit a fast path and others a slow path, you'd see bimodality. Less likely than (1) or (2), but cheap to test: set `NCCL_ALGO` and `NCCL_PROTO` explicitly and see if bimodality disappears.

**4. CUDA graph capture size mismatch.**
You capture at multiples of 6. If a run's batch shape (including DSpark draft tokens) lands on a captured size, you get graph replay. If it lands off, you get eager execution. At batch 1 with k=5, the verify batch is 6 tokens — that's a multiple of 6, so it should always hit. But if DSpark sometimes drafts fewer than 5 (early termination), you might fall off the graph. **Test:** check whether the 48 runs have different draft lengths than the 70 runs.

**5. Thermal / clock throttling.**
You said clock is locked at 2200 MHz. If that's a hard lock, rule this out. If it's a "lock" that still allows thermal downclock, this is a candidate. GB10 in a DGX Spark chassis is thermally constrained; sustained runs could throttle. But locked clock usually means locked. **Test:** `nvidia-smi -q -d CLOCK` during a 48 run vs a 70 run.

My money is on **(1)**, with **(2)** as the secondary. The fix for (1) is exactly lever (12) + (1) + (14): prefetch, free host memory, and shrink the table.

---

## (c) Five new levers not on your list

These are specific to your architecture (Engram, DSA, DSpark, hyper-connections, compressed KV) on GB10's unified memory over RoCE.

### New lever 1: Exploit unified memory — skip the H2D "copy" entirely

On GB10, host and device share LPDDR5X. The "H2D copy" in your Engram path is not a PCIe transfer; it's a memcpy across a unified aperture, and it's pure overhead if the GPU can read the staging buffer directly. **Map the pinned staging buffer as device-accessible (zero-copy) and have the Engram kernel read raw FP8 rows directly from it.** This eliminates one full copy of ~16 KB/token/rank and, more importantly, eliminates the synchronization point between the reader threads and the forward pass. On a discrete GPU this would be a bad idea (PCIe latency); on GB10 it's strictly better. Expected: **+5–15% single-stream**, stacks with (11).

### New lever 2: Fuse Engram lookup into the DSpark draft forward

Right now, Engram rows are fetched per *verified* token. But DSpark drafts 5 tokens ahead. The draft model's forward pass already computes hidden states for those 5 positions. **If the Engram lookup is a function of the draft hidden state (or the token IDs, which are known), you can issue the lookup as part of the draft kernel and have the rows ready before verification.** This is lever (12) done properly — not as a CPU prefetch, but as a fused GPU-side operation. The draft stage has spare compute (it's a small model); use it to hide Engram latency. Expected: **+10–20%**, and it's the cleanest fix for bimodality.

### New lever 3: Compress the Engram table with a learned codebook, not just FP4

FP4 quantization (lever 14) is the obvious move, but n-gram tables have structure: many rows are near-duplicates (common n-grams with similar contexts). **A product-quantization or residual-VQ codebook over the 256-byte rows could get you to ~2–4 bits/byte effective, i.e. ~13–26 GB/rank, without the quality loss of naive FP4.** This is essentially what FAISS/OPQ do for embeddings. The lookup becomes: fetch codebook index (2–4 bytes), gather from a small GPU-resident codebook, reconstruct. If the codebook fits in GPU memory (it will — a few hundred MB), you eliminate NVMe entirely. Expected: **+30–60% single-stream**, potentially better than FP4 because you can keep more effective precision. This is the idea I'd bet on if FP4 quality fails.

### New lever 4: Overlap the 90 all-reduces with Engram fetches

You have 90 all-reduces at 4.4–5.7 ms total per step, and an Engram fetch path that's ~2–3 ms. These are **independent** — the all-reduces are for MoE/attention, the Engram fetch is for the n-gram lookup. Right now they're almost certainly serialized. **Issue the Engram NVMe reads (or io_uring submissions) before the first all-reduce, and let them complete during the collective-heavy part of the step.** On GB10, the CPU is free during GPU collectives (they're async), so the reader threads can work in parallel. This requires restructuring the step to be a proper DAG rather than a linear sequence. Expected: **+10–20% single-stream**, and it directly attacks the 3 ms/step Engram cost without changing the table.

### New lever 5: Use the DSA indexer's top-k as a sparsity signal for Engram

Your DSA lightning indexer computes top-k attention positions per token. Those positions correlate with which n-grams are actually relevant. **Instead of looking up all 64 n-grams per token, use the DSA top-k to prune the Engram lookup to the n-grams that overlap with attended positions.** If DSA top-k is, say, 2048 out of 128k, and Engram n-grams are keyed by position, you can skip most lookups. This is a *semantic* optimization, not a systems one, and it depends on whether Engram n-grams are position-keyed or content-keyed. If content-keyed, this doesn't apply. **I'm unsure of your Engram keying scheme** — if it's content-hash-based, ignore this. If it's position-based, this could cut Engram traffic by 5–10×. Expected: **unknown, potentially large**.

### New lever 6 (bonus): Split the Engram table across NVMe and GPU by frequency, with a learned router

Instead of a static hot-row cache (lever 13), train a tiny router (or use n-gram frequency statistics from a calibration set) to predict which rows will be needed for a given prompt, and **preload those rows into GPU memory at prefill time**. This is essentially a learned prefetcher. On GB10, where you have 128 GB unified but only ~6 GB host free, the router's job is to decide what to evict from the KV pool vs what to keep in the Engram cache. This is a joint KV/Engram memory management problem, and nobody does it because discrete GPUs don't have this tradeoff. Expected: **+10–25%**, but requires training infrastructure.

---

## (d) Things that are wrong or risky in the described setup

**1. `torch.unique` on CPU for Engram row dedup is a serialization point.**
At batch 1, ~64 rows/token, dedup saves little (n-grams rarely repeat within a token). The `torch.unique` call is likely pure overhead. **Drop it** and let the io_uring batch handle duplicates, or dedup on GPU after the fetch. This alone might be worth 0.2–0.5 ms/step.

**2. 32 Python threads doing `preadv` is a GIL and scheduler disaster.**
Python threads doing blocking I/O release the GIL, so it's not as bad as it sounds, but 32 threads on a GB10 (which has, I believe, 10 P-cores + 10 E-cores or similar) means heavy context switching and cache thrash. **Use io_uring with a single submission queue and let the kernel handle parallelism.** This is lever (11), but the specific point is that 32 threads is the wrong number — it should be 1 thread + io_uring, or `O_DIRECT` + `preadv2` with `RWF_NOWAIT`.

**3. `gpu_memory_utilization 0.80` with 731k KV tokens is aggressive given 6 GB host free.**
You're trading host memory for KV pool. On GB10, host and device share the same physical LPDDR5X, so "host memory" and "GPU memory" are the same pool with different allocation policies. **The 6 GB host free is not a separate resource from the 128 GB unified pool — it's a consequence of how you've partitioned it.** You may be able to reclaim host memory by shrinking the KV pool slightly, which would let Engram rows stay in page cache. This is a direct tradeoff: **KV pool size vs Engram page cache hit rate.** At batch 1, you're not using 731k tokens of KV; you could probably halve it and gain more from Engram cache hits than you lose from KV capacity. Expected: **+5–15% single-stream**, and it's the cheapest fix for bimodality.

**4. Adaptive verification OFF because "padded batches hang SM120 sparse MLA" is a red flag.**
This means your sparse MLA kernel has a bug or a missing shape specialization on SM120. You're leaving performance on the table (adaptive verification would help prose, where accept is ~2) because of a kernel issue. **This is worth fixing at the kernel level**, not working around. If padded batches hang, the kernel is likely reading out of bounds on the padding. Fix the kernel, turn adaptive verification on, and you get better accept length on prose. Expected: **+5–10% on prose**, which is your worst category.

**5. DSpark k=5 with block rejection and probabilistic sampling may be misconfigured.**
Block rejection with probabilistic sampling is unusual — block rejection is typically used with greedy or speculative sampling with a proper acceptance ratio. If the acceptance test is wrong, you're rejecting tokens you should accept. **Verify the acceptance math** against the DSpark paper (or your branch's implementation). Mean accept 3.57 with k=5 is plausible but not obviously optimal; if the math is wrong, you could be at 4.5+.

**6. The 90 all-reduces at 4.4–5.7 ms total is suspiciously high for 4 ranks.**
50–63 µs per all-reduce on 200G RoCE is high. For small messages (which these likely are — hidden states at batch 1), you should be at 10–20 µs. **This suggests either a kernel-launch tax per collective, a bad NCCL algorithm choice, or synchronization overhead.** Profile with `nsys` and look at the gap between collective launches. If it's launch-bound, consider **fusing multiple all-reduces into one** (e.g., concatenate the tensors and do one all-reduce, then split). This is a known technique for small-collective-heavy models. Expected: **+5–15% single-stream**, and it scales to C6.

**7. You're running a 510 GB model on 4×128 GB = 512 GB unified, with 81.6 GiB/rank of weights.**
That's 326 GiB of weights across 4 ranks, plus 203 GB Engram (not resident), plus KV pool. The math is tight. **Any memory pressure anywhere causes eviction somewhere else.** This is why bimodality exists. The structural fix is (14) or the codebook idea (new lever 3): get the Engram table resident so it stops competing with KV and weights for the unified pool.

**8. `max_num_seqs 8` with `max_num_batched_tokens 8192` and chunked prefill 2048.**
At C6, you're at 132 tok/s aggregate, and per-stream falls fast. This is consistent with KV bandwidth saturation, not compute. **The KV pool at 731k tokens is likely the bottleneck at C6**, not the Engram path. If you shrink KV pool to free host memory for Engram, you might *hurt* C6 while helping single-stream. **Measure both.** The optimal gmu is probably different for single-stream vs C6, and you may want a runtime knob.

---

## Summary: what I'd do first

1. **Diagnose bimodality** (part b): log page faults, NVMe reads, accept length, and NCCL algorithm per run. This tells you which lever matters.
2. **Fix the Engram path**: io_uring + GPU-side dequant (11), prefetch during draft (12), and prototype FP4 or codebook quantization (14 / new lever 3).
3. **Fix NCCL**: explicit algo/proto, consider fusing small all-reduces (9 + new lever 6).
4. **Fix the SM120 sparse MLA hang** and turn adaptive verification back on.
5. **Re-tune gmu** as a joint KV/Engram tradeoff, not a KV-only knob.

The single highest-leverage change is **getting Engram resident in unified memory**, whether via FP4, codebook, or a hot-row cache. Everything else is secondary. The bimodality is almost certainly a symptom of Engram page-cache thrash, and fixing that fixes both the mean and the variance.

I'm least confident about the Engram keying scheme (content vs position) and the exact DSpark acceptance math. If you can share those, I can sharpen new lever 5 and the DSpark diagnosis.