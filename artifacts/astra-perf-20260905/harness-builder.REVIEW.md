# Review handoff — adversarial review of worker `depths-harness-fix-20260905`

You are the REVIEWER, not the builder. Your single job: **find what the builder's report claims that the code does not actually do.** Assume the report is optimistic until proven otherwise.

## Inputs
- Original spec/handoff: `/home/jun/git/spark-bench/artifacts/astra-perf-20260905/harness-builder.md`
- Builder's report: `/home/jun/git/spark-bench/artifacts/astra-perf-20260905/harness-builder.REPORT.md`
- Builder's log: `/tmp/depths-harness-fix-20260905.log`
- Builder model: `venice/z-ai-glm-5-3` (you are `venice/qwen-3-8-2-4t-a95b`)
- Change surface (run these first): `git -C '/home/jun/git/spark-bench' log --oneline 4bc912877d9f0adfde29e0d4a993378a3ee9974b..HEAD; git -C '/home/jun/git/spark-bench' diff 4bc912877d9f0adfde29e0d4a993378a3ee9974b..HEAD --stat; git -C '/home/jun/git/spark-bench' status --short; git -C /home/jun/git/eva-core log --oneline de37815d44fd6e65649e732ff19937b82b185718..HEAD; git -C /home/jun/git/eva-core diff de37815d44fd6e65649e732ff19937b82b185718..HEAD --stat`

## Method
1. Read spec, then report. List every concrete claim in the report (files, tests, numbers, "verified" statements).
2. For each claim, verify it yourself with a real command (run the tests, run the script, query the DB read-only, grep the file). Do not trust log text.
3. Check the spec's "Hard constraints" section line by line for violations (forbidden files/tables/dirs touched, restarts performed, personal data).
4. Read the actual diff for correctness bugs the tests would not catch (error handling, off-by-one, silent fallbacks that hide failure, hardcoded paths, secrets).
5. Do NOT fix anything. Do NOT commit. Read-only except for writing your report.

## Report — write to `/home/jun/git/spark-bench/artifacts/astra-perf-20260905/harness-builder.REVIEW.REPORT.md`
First line exactly: `verdict: accept | accept-with-fixes | reject`
Then: claims table (claim → verified/false/unverifiable + receipt), constraint violations, bugs found (file:line), what must change before accept (if any), one-paragraph summary for the orchestrator.
