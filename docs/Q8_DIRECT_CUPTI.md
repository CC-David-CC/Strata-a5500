# Direct Q8 counter collection

Local diagnostic branch `diag/q8-cupti-user-range`, based on the tested ownership
engine `1a50d913`. No engine sources or model kernels are changed. Hardware:
RTX PRO 6000 Blackwell Workstation Edition 96 GB, 128 GB RAM, Linux, CUDA 13.2.

Nsight Compute 2026.1.1 rejected repeated static graph launches in a small
app-range fixture. Fresh graph instances fixed that fixture, but the full Q8
probe still blocked inside its first `cudaGraphLaunch`, before the requested
range. The unprofiled fresh-graph model matched the frozen engine's 128 output
tokens; the profiled run was released by the existing watchdog. No model
counter result was accepted. The dependent 64K matrix did not run.

This alternative uses a private `LD_PRELOAD` library that implements only
`cudaProfilerStart` and `cudaProfilerStop`. Those existing opt-in range markers
initialize the installed CUPTI range API, collect one user range in one pass,
and write the evaluated byte counters plus raw counter/config images. It does
not intercept graph launch, replace graphs, replay model work, control clocks
or change model precision. The shared CUDA runtime is required.

The API sequence follows NVIDIA's installed `range_profiling` sample and
[CUPTI documentation](https://docs.nvidia.com/cupti/main/main.html).
Only the three requested metrics are scheduled: DRAM read bytes, DRAM write
bytes and L2 transaction bytes. Multiple passes, dropped ranges, invalid values
and missing capture are rejected. A fresh process is required per capture.

## Gates

`tools/profile_q8_cupti_fixture.py` builds the library and a bounded fixture
under the private fleet queue. Each shape runs with and without the library:

- A small static graph with a mapped CPU/GPU handshake.
- A static graph with 4,096 marker nodes plus handshake and payload nodes.
- A 512 MiB read/modify/write payload. Two captured launches nominally move
  2 GiB; a declared 0.5–1.5 ratio allows L2 residency/deferred writeback while
  detecting missing or incorrectly scaled counters.

Every output word and marker count must be correct, with zero watchdog
interventions. After fixture success, a short model capture must match its
unprofiled control before attempting native 64K measurements.

Counters may be device scoped, so the runner yields to foreign GPU processes.
Profiled timings are not throughput evidence. CPU/PCIe constraints remain
separate from a GPU-only conditional bandwidth ceiling.

## Fixture result, 2026-10-03

All six control/profile cases passed on source `06d5f4fc`: every output word and
marker count matched, with zero watchdog interventions. Each direct capture
used one pass and one range with zero dropped ranges. The large-payload test
measured 1,073,826,048 DRAM read bytes and 1,058,195,712 write bytes: **99.28%**
of the nominal 2 GiB. Small payloads mostly stayed in L2, as expected.

The measured library SHA-256 is
`47d059ca1cc9040caf2247ff5fd6620eb460c0fe5125cf3397f5b19e41012450`.
`tools/profile_q8_cupti_model.py` verifies that library and the frozen ownership
binary, then compares an 8K/128-output capture against the just-completed 8K
control. Only after equality does it attempt the native 64K/512-output matrix.

## Real Q8 results, 2026-10-03

The short 8K/128-output probe passed: every output token and recorded work
counter matched its unprofiled control. The four native 64K cases then finished
successfully. The original frozen engine and its static graphs were retained.
Each capture used one pass, one range, no replay and zero dropped ranges.

Hardware: RTX PRO 6000 Blackwell Workstation Edition **96 GB**, Ryzen 9 7950X,
128 GB system RAM, NVIDIA driver 595.91.07, CUDA 13.2.86. Model: full Unsloth
Qwen3.8-Flash-Next **Q8_0**, FP16 KV, native RoPE. Each fresh engine received
65,536 input tokens and produced the requested 512 output tokens, with 73,728
positions allocated. These are additional traffic measurements, not the 1M
ownership off/on comparison.

Ownership rotation and completion waits were enabled in every arm. Expert
placement was automatic CPU/PCIe, with 96 adaptive swaps and a 56 GiB RAM
expert budget; the PLE table was in RAM. No case read experts from files.
There were 16,400 GPU expert slots without MTP and 16,192 with MTP. Verification
capacity was eight, MTP maximum T was four, and the suffix draft setting was
three where enabled. ESP was off. The differing cache capacities and adaptive
speculation make these configuration comparisons, not a single-variable MTP
experiment.

| Configuration / task | Unprofiled output tok/s | Effective output tok/s | Sampled DRAM GB / committed token | GPU-only conditional ceiling, tok/s |
| --- | ---: | ---: | ---: | ---: |
| Plain / coding | 72.68 | 23.80 | 8.2869 | 198.7 |
| MTP / coding | 117.58 | 26.77 | 4.3074 | 382.4 |
| N-gram / editing* | 72.97 | 23.82 | 3.8526 | 427.5 |
| MTP + n-gram / editing | 68.63 | 23.03 | 3.4640 | 475.5 |

GB is decimal. Effective throughput includes prefill and request wall time,
excluding engine startup. Speed comes only from the unprofiled controls.
The ceiling is **1,647 GB/s divided by sampled DRAM GB per committed token**,
using the earlier measured streaming bandwidth on this GPU. It omits CPU
expert execution, PCIe, synchronization and other limits; it is not an
achievable whole-engine speed prediction.

All four profiles reproduced their own control's complete 512-token output.
Plain, MTP and combined also reproduced all recorded work counters. *N-gram
had 447 versus 445 drafts offered, 233,302 versus 232,640 cache hits, 255,560
versus 254,637 lookups, and 38,426 versus 38,227 RAM blob reads under capture.
Its output equality passed, but its work equality did not. Its traffic is
valid for that captured execution; no matched speed/traffic fraction is
reported. These counters alone do not identify the cause of the schedule
change.

There is one control/profile pair per configuration, with no reverse-order
repeat or confidence interval. Coding and editing are different prompts.
Plain and MTP coding first differed from each other at output token index 288
(zero based); equality above is profile versus its own control, not across
decoding modes. The editing outputs matched across the two suffix modes.
Token and aggregate work equality do not establish per-step state or logit
equivalence.

### Capture boundaries and interpretation

Every 64K capture covered decode windows 32 through 47. Speculation committed
different numbers of tokens in those windows:

| Configuration | Committed count at start / end | Tokens in range | DRAM read bytes | DRAM write bytes |
| --- | ---: | ---: | ---: | ---: |
| Plain | 32 / 48 | 16 | 129,269,047,552 | 3,321,371,648 |
| MTP | 78 / 129 | 51 | 211,511,863,808 | 8,167,668,736 |
| N-gram | 110 / 163 | 53 | 186,064,848,640 | 18,122,789,888 |
| MTP + n-gram | 155 / 224 | 69 | 216,075,765,760 | 22,941,421,312 |

These are different output-position ranges. Multiplying the sampled traffic
by full-request control throughput gives a **proxy**, not measured continuous
bandwidth utilization: 36.6% of the conditional ceiling for plain, 30.8% for
MTP, and 14.4% for combined. N-gram's work mismatch excludes that proxy.
The two-window 8K probe is only a compatibility gate and is excluded from this
table and the 64K ceiling claims.

The data supports lower GPU traffic per committed token with speculation in
these samples. It also shows that lower traffic alone does not guarantee a
faster request: combined editing had less traffic per committed token but a
slower unprofiled control than n-gram editing. CPU work, transfers and waits
need their own critical-path measurements before attributing the remaining
gap to GPU kernel bandwidth. Counter collection itself changed no engine
kernel and supplies no new optimization speedup claim.

### Reproduction and evidence

- Engine source: `1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c`.
- Engine SHA-256: `d14ed6b69a1814ce4b5c08932a47d6921a55fa0aa8dea50427ccf0782d1ad997`.
- Library/fixture source: `06d5f4fce19cf53767f74c2cc7dc10512fff9d62`.
- Model runner source: `75c24a4af2f95e7fe389af23ab33be11398e4b8f`.
- [Compact measurements and checks](../bench/results/2026-10-03-q8-direct-cupti/summary.json).
- Raw archive: `q8-direct-profiling-evidence-20261003.tar.gz`, 189 files,
  230,856 compressed bytes. SHA-256:
  `792ec5e55aa891e60d275ea3588e96a07d2f36eeebdbb305618f7b26d71ffc89`.

The raw archive is retained on llm-60 under `~/fleet-downloads/` and in the
local fleet evidence folder, with matching SHA-256. It includes successful
CUPTI counters, config images, commands, outputs and logs, plus the failed
Nsight model probe and skipped dependent run. No weights are archived. The
GPU was idle after completion; no reboot, public service or other host was
changed.
