# Fully resident batch decoding: doorbell fix

This is a small bug-fix branch based on upstream `6f32ec0`. The implementation
changes one file, `src/core/verify.cpp`, with five added and three removed lines.
It adds no serving feature, configuration option, speculative policy or cache policy.

## Failure and change

The fully resident verifier graph does not ask the CPU to execute missed experts.
The batch host paths nevertheless waited for one expert-work doorbell per layer.
Those doorbells are absent on this path, so a batch could stall.

The batch path also gathers its PLE rows before launching the graph. Its lookup
ready flag must therefore be set for the fully resident graph's PLE gate.

The patch:

- Sets the initial lookup-ready flag to one when `all_resident_` is true.
- Sets the CPU expert-work step count to zero in `run_slot_rows` for that case.
- Makes the corresponding step-count change in `batch_launch`.

The graph still executes and the existing CUDA completion/commit handling remains.
When `all_resident_` is false, these expressions retain their previous values.

## Completed testing

The same code change was built and exercised in integration commit `66b9474`,
which also contains the Q8 adaptation and PDL/graph work. This is evidence for the
integrated fix; it is **not a fresh build of this standalone branch**.

Hardware: RTX PRO 6000 Blackwell Workstation 96 GB, existing 400 W limit, Linux.
All experts were GPU-resident; KV was FP16, allocated context 16,384 tokens.
Each request actually read 8,192 input tokens and generated 512 output tokens.
Prompt reuse was disabled. The five models were:

- GSQ-RCO IQ3_S
- GSQ-RCO IQ3_XXS
- GSQ Q2_0
- Pruned Coder IQ1_M
- Unsloth UD-Q4_K_XL

For each model, one solo MTP T4 request and two simultaneous target-only requests
completed: 15 requests total. The paired requests exercised all-resident batching.
This establishes completion for that screen; it is not a speedup claim or a
claim of cross-policy token equality. An IQ1 transfer was active during this
historical screen, so its timings are retained as observations, not controlled
performance evidence.

[Compact receipt: model names, input/output counts, binary hashes, output-ID
hashes and source-result hash](../bench/results/2026-10-05-all-resident-batch/screen-summary.json)

## Remaining before marking ready for review

- Build and run the isolated upstream-plus-fix branch, with a timeout-bounded
  two-request reproducer and a partially resident control.
- Add a focused regression check for the all-resident batch completion contract.
- Run applicable GPU sanitizer and cancellation/recovery checks on that build.
- Check the `batch_launch` pipeline path separately; multi-GPU execution has not
  been exercised by the completed screen.

The contribution is intentionally a draft while these checks remain. Larger
concurrency and grouped MTP experiments are separate branches.
