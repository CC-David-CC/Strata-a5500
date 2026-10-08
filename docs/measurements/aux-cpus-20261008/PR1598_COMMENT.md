Independent Linux results on four systems, using this PR's helper-placement logic ported onto #1489. Full method, raw requests, affinities and tables: [evidence branch](https://github.com/CC-David-CC/Strata-a5500/tree/bench/p4-aux-cpus-1598/docs/measurements/aux-cpus-20261008).

- R730, two/three Tesla P4s: no convincing decode gain (median paired changes -0.58% to 0.00% across automatic and reserved-core settings). 8K prefill was unchanged. Host involuntary preemptions nevertheless fell sharply: three-card auto, median 5,700 → 129 during the 8K request.
- RTX PRO 6000 Blackwell: median paired decode change 0.00%; 8K TTFT approximately 1.32 → 1.31 s.
- RX 7900 XTX / HIP: decode -1.12% automatic / -0.10% reserved-core. Preliminary 8K TTFT 15.29 → 14.24 s automatic, 15.54 → 14.14 s reserved-core.
- RTX 4090: decode -7.06% automatic / -1.04% reserved-core; the automatic off/off control itself varied +4.69%. Preliminary 8K TTFT 4.43 → 3.29 s automatic and 3.79 → 2.82 s reserved-core. Host RAM is small relative to the mmap model; file-cache effects remain a confounder.

CUDA and HIP builds and selected CPU/API checks passed. Fourteen campaign jobs completed, 622 HTTP requests including warmups, zero request errors. Each candidate configuration has 12 alternating decode pairs, three off/off control pairs, two pairs per fresh-prefill size, and four cached-8K pairs. The prefill sample is too small for a firm speedup claim.

These are ISTA IQ3_XXS, INT8 KV, 128-token replies, solo serial serving, MTP disabled. This differs from the PR's two-stream MTP workload. Adaptive expert placement was enabled, and some outputs changed in off/off controls too; this is not a bitwise-parity claim. Original-binary controls are labeled separately in the evidence.

The placement mechanism works on these CUDA/HIP hosts, but fewer preemptions did not imply faster P4/Blackwell decode here. Keeping this opt-in makes sense; the 4090/HIP prefill observations deserve more repetitions with controlled file-cache conditions.
