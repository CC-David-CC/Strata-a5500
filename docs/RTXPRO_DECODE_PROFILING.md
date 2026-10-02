# RTX PRO decode profiling

Branch `perf/q4-single-token` starts from the measured full-expert baseline
`3fcea83` (engine code `29cbc02`). The companion branches `perf/q4-mtp-window`,
`perf/q8-hybrid`, and `perf/q8-mtp-window` start from that same baseline. They
are independent experiments; main and the community contribution branches are
unchanged. The host-use window ends at 2026-10-03 10:50:47 UTC.

CUDA builds include optional capture boundaries in the CLI and server decode
loops. Set `STRATA_PROFILE_DECODE_SKIP=16` and
`STRATA_PROFILE_DECODE_COUNT=16` to capture windows 16 through 31, counting from
zero after prefill. The default count is zero: no profiler calls or added CUDA
synchronization occur. HIP builds make no CUDA profiler calls.

Run the existing benchmark under Nsight Systems with:

```
nsys profile --trace=cuda --sample=none --cpuctxsw=none \
  --cuda-graph-trace=node --capture-range=cudaProfilerApi \
  --capture-range-end=stop --output=UNIQUE_PATH python tools/bench_mtp_modes.py ...
```

Use one workload/request per capture. A scope guard closes an active capture on
EOS, cancellation, or an early return. Start/stop synchronize the device only in
the opted-in diagnostic. Treat its rates as instrumented, never as a candidate
throughput result. Unprofiled companion requests use the same binary with both
environment variables absent. Keep the profiler report and its exact config,
source commit, binary hash, prompt hash, and GPU clocks with the observations.

The user accepts IEEE arithmetic variation and different correct answers.
Record token equality as a diagnostic; judge arithmetic candidates by finite
values, error measurements against the same weights, and independent task
correctness checks. A 99% token-match rate does not mean 99% task accuracy.
Packed data readers must still decode the source bytes correctly. Do not change
the model's experts, routing rule, quantization, or MTP verification policy as a
substitute for a scheduling/kernel improvement.
