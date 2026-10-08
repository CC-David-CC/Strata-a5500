# Independent Linux CUDA/HIP checks for #1598

Moving helper threads away from worker cores sharply reduced host involuntary
context switches, but **did not give a convincing decode gain on these systems**.
R730 two-/three-P4 prefill was also unchanged. Short prefill probes on the 4090
and RX 7900 XTX suggest a benefit worth repeating with tighter filesystem-cache
controls. This does not contradict the PR author's different hardware/workload.

The PR's logic was ported as `6273bb8e` onto integration #1489 (`b299af0`), not
tested as a pristine checkout of its head. The harness is in
[`tools/aux_cpus_bench.py`](../../../tools/aux_cpus_bench.py). All four builds and
their selected CPU/API checks passed. All 14 campaign jobs exited successfully:
**622 HTTP requests including warmups, zero request errors**.

| Hardware / helper placement | Median paired decode change | 8K TTFT off → on |
|---|---:|---:|
| 2 P4, automatic spare CPU | -0.29% | 39.228 → 39.286 s |
| 3 P4, automatic spare CPU | -0.58% | 43.887 → 43.901 s |
| 2 P4, reserved physical core | -0.29% | 39.315 → 39.275 s |
| 3 P4, reserved physical core | 0.00% | 43.923 → 44.050 s |
| RTX 4090, automatic | -7.06% | 4.427 → 3.291 s |
| RTX 4090, reserved core | -1.04% | 3.792 → 2.819 s |
| RTX PRO 6000 Blackwell, automatic | 0.00% | 1.316 → 1.305 s |
| RTX PRO 6000 Blackwell, reserved core | 0.00% | 1.326 → 1.318 s |
| RX 7900 XTX / HIP, automatic | -1.12% | 15.285 → 14.236 s |
| RX 7900 XTX / HIP, reserved core | -0.10% | 15.543 → 14.136 s |

Each decode entry uses 12 alternating off/on pairs (six code, six prose),
plus three off/off control pairs per configuration. There are only **two pairs
at each prefill length**, and four cached-8K pairs: prefill numbers are preliminary,
not a tail-latency study. Decode changes are medians of paired ratios; the TTFT
columns are separate arm medians. They are not interchangeable estimators.

On three P4s, 8K host involuntary preemptions fell from a median **5,700 to 129**
with auto placement, yet TTFT stayed **43.89 to 43.90 s**. Fewer preemptions alone
therefore did not establish a throughput improvement here. On the 4090 the auto
off/off decode control itself moved about **+4.69%**; available host RAM is small
relative to the model, and mmap/file-cache effects remain a confounder. Do not
present the 4090 prefill gain or decode loss as a stable universal effect.

Configuration: unchanged ISTA IQ3_XXS, INT8 KV, native `--spec 2` without MTP
weights, suffix drafting disabled, temperature 0, reasoning none, 128 output
tokens. Fresh-prefill requests disabled conversation checkpoints and checked
zero cache reuse. Short code/prose, 1K/8K fresh input, and cached 8K were measured.
Hardware is R730 dual E5-2697 v3 with two x16 P4s and one x8 P4; RTX 4090 24 GB;
RTX PRO 6000 Blackwell 96 GB; RX 7900 XTX 24 GB. This is solo serial serving,
not the PR author's two-stream MTP configuration.

The original-binary rows are separate baseline controls. Their `on`/`off` arm
labels are harness labels only: they do not enable this patch. Adaptive expert
placement was enabled; some generated outputs differed even in off/off controls.
This is not a bitwise parity or answer-quality-equivalence claim.

## Inspect and reproduce

- [Derived summary](summary.json)
- [R730 raw requests and summaries](r730-results.json)
- [4090 raw requests and summaries](llm-49-results.json)
- [Blackwell raw requests and summaries](llm-60-results.json)
- [HIP raw requests and summaries](llm-79-results.json)

Use `python tools/aux_cpus_bench.py --help` for the build/config inputs and
repeat counts. Keep one same-binary off/on campaign separate from original-binary
controls, retain warmups and off/off controls, and record host CPU affinity.

Suggested feedback on [#1598](https://github.com/Niko1221/Strata/pull/1598):
the Linux placement mechanism built and ran on CUDA and HIP here; retaining its
opt-in default makes sense. The P4/Blackwell results show no measured decode win,
while the 4090/HIP prefill observations merit a larger controlled follow-up.
