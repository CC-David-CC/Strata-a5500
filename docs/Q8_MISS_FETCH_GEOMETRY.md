# Q8 miss-copy concurrency experiment

Experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0, FP16 KV, native 32K and 128K.

## Observation motivating the change

The first 32K MTP pair with four secondary-cache slots per layer used runtime
`bcacb884`. Upload overlap changed editing from 113.67 to 115.29 output tokens/s,
with identical output and recorded work. Mean host wait for GPU progress fell
14.59 to 12.85 ms/window, while CPU expert time rose 13.45 to 14.46 ms/window.
Full-window time fell 34.38 to 33.90 ms. Coding was essentially tied.

Evidence: [parent MTP request records and paired analysis](benchmarks/q8-miss-fetch-geometry-parent-20261004.json).

These are first paired observations from the parent overlap branch. The host
wait interval is not GPU idle time. Memory contention is a hypothesis; these
logs do not measure host DRAM traffic or prove the mechanism. Stage profiling
and a hardware-counter capability probe are separate jobs.

## Intervention and invariants

Both the ordinary miss copy and the secondary-cache fill launch 384 blocks of
256 threads. `STRATA_MISS_FETCH_BLOCKS` sets the block count from 1 through 4096
at graph capture; absence preserves 384. The same setting controls both copies.

Only launch concurrency changes. The grid-stride loops retain the full copy
extent, 16-byte accesses, source/destination addresses and complete-fill/tag
publication dependencies. Primary placement, CPU/GPU assignment, expert math,
token policy and FP16 KV remain fixed. Captured overlap and the secondary cache
keep independent switches. No DMA or driver-callback path is added.

Lower concurrency could reduce contention with CPU expert reads or resident
GPU kernels. It could also lengthen uploads enough to lose overall. Copy time
alone cannot choose the winner; measure matching-work request time and the CPU,
resident-kernel and exposed fetch/join intervals together.

## Validation and selection

Component gates passed the original 384-block default and explicit 1/32/96/384 configurations with
the actual 5,222,400-byte expert, small/tail shapes, captured serial/overlap paths,
cache eviction/bypass, complete-byte output, source immutability and guards.
Memcheck/initcheck passed at 32/96/384, and invalid values were rejected.

After these gates and the parent stage profile, select a small full-model
comparison. Keep serial and overlap, cache off/on and all decoding modes as
separate paths. Require exact plain/MTP tokens and recorded work; qualify n-gram
work changes. Repeat useful gains, then extend them to native 128K. No result
from the parent branch establishes a gain for this block-count change.

Runtime `7db4414` built with binary SHA-256
`96c16a3a64ccc4d1583242c1cf5838b5d32186fdbbea9d055a8040b560fdd4b7`.
There were 20 full component cases per setting, 100 total across the default
and four explicit block counts. All six sanitizer runs reported zero errors.
Five invalid values exited with the expected error. These component gates
preceded the full-model comparisons reported below.

Evidence: [complete gates and fixture logs](benchmarks/q8-miss-fetch-geometry-components-20261004.json).

## Measured GPU interval tradeoff and selected model screen

The corrected parent GPU profile (`bcacb884` runtime, `096742c` harness) used
32K input + 1K output with four secondary-cache slots/layer. Tokens and recorded
work matched. Summing GDN/QSA stage timestamps, overlap changed editing's
resident-expert interval from 4.93 to 16.44 ms/window while staging/exposed join
fell 13.08 to 0.68 ms. Coding changed 4.18 to 8.71 ms and 5.17 to 0.19 ms,
respectively. These are instrumented intervals; the fork/concurrent work is
inside the resident-expert interval, so individual kernel slowdown is unproven.

The initial unprofiled model screen used 384, 96 and 32 copy blocks,
each in serial and overlapped modes. Every arm used the same component-tested
`7db4414` binary, MTP, 32K input + 1K output, FP16 KV, four secondary slots/layer,
15,472 primary slots and PCIe fraction 0.55. Exact tokens/work are required.
The completed initial comparisons and their follow-up are below.

Evidence: [parent stage profile and semantic comparison](benchmarks/q8-miss-fetch-geometry-parent-gpu-profile-20261004.json).

## Initial model factorial completed

All six arms / 12 requests completed on the same `7db4414` binary above.
Every request reached 1,024 output tokens. All output tokens, recorded work,
secondary-cache hit/upload counts and primary-exchange payload matched the
384-block serial control exactly. Decode expert file reads stayed zero.

| Copy blocks | Scheduling | Coding output tok/s | Editing output tok/s | Change vs 384 serial: code / edit |
|---:|---|---:|---:|---:|
| 384 | Serial | 131.93 | 113.66 | +0.00% / +0.00% |
| 384 | Overlap | 133.75 | 115.86 | +1.38% / +1.93% |
| 96 | Serial | 132.99 | 114.48 | +0.81% / +0.72% |
| 96 | Overlap | 134.03 | 117.04 | +1.59% / +2.97% |
| 32 | Serial | 132.66 | 115.68 | +0.55% / +1.78% |
| 32 | Overlap | 133.87 | 118.50 | +1.47% / +4.26% |

The 32-block overlap candidate reached 118.50 editing tok/s versus 113.66 for
the original serial control (+4.26%). Holding overlap enabled, changing 384 to 32
blocks improved editing from 115.86 to 118.50 (+2.28%); coding was essentially
unchanged (133.75 to 133.87). Ninety-six blocks gave slightly higher coding than
32, but that difference is only 0.12%, not an established advantage.

This initial screen supports retaining both 32-block serial and overlap paths.
Repeat in reversed order and extend native 128K; screen plain/n-gram/combined
separately. These finite sequential pairs have no confidence intervals yet.
Lower launch concurrency helped measured request time, but this alone does
not identify which memory/scheduling resource was limiting overlap.

[Complete model records](benchmarks/q8-miss-geometry-model-20261004.json) and
[same-work comparisons, effective throughput and host timing](benchmarks/q8-miss-geometry-analysis-20261004.json).

## Reversed 32K MTP comparison completed

The candidate ran first, then 32-block serial, then the original 384-block
serial control. Every arm again reached 1,024 output tokens for coding and
editing. Tokens, recorded speculative work, secondary hit/upload counts and
primary D2H/H2D payload all matched, including between the two candidate runs.
This uses the same `7db4414` binary and unchanged configuration above.

| Setting | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---:|---:|---:|---:|
| 384 blocks, serial | 132.52 | 113.46 | 65.47 | 61.01 |
| 32 blocks, serial | 133.82 | 115.99 | 65.75 | 61.70 |
| 32 blocks, overlap | 134.88 | 118.34 | 66.04 | 62.45 |

Against 384-block serial, the candidate gained **1.78% coding / 4.31% editing**
on generation. Against 32-block serial, overlap gained **0.79% / 2.02%**.
Effective throughput includes each request's prefill and generation; it
excludes engine loading. These are paired finite tests, not confidence bounds
or claims about every prompt. The reverse ordering supports the direction of
the initial result while keeping both serial and overlap as useful alternatives.

Editing's mean host wait for GPU progress fell 14.45 to 12.26 ms/window while
CPU expert work rose 13.60 to 14.41 ms/window. Whole-window time fell 34.45 to
33.03 ms. Host waiting is not GPU idle time. The measurements still do not
identify the contended resource; separate valid traffic profiling is needed.

[Complete reversed-triple records and correctly oriented comparisons](benchmarks/q8-miss-geometry-reverse-20261004.json).

## Native 128K MTP comparison completed

Each request supplied 131,072 input tokens and generated all 1,024 requested
outputs, with 139,264 allocated context, native RoPE and FP16 KV. The runtime,
primary and secondary slot counts and PCIe policy stayed fixed. Output tokens,
recorded work, secondary-cache counts and primary exchange payload matched
across all three arms. Expert file reads remained zero during decode.

| Setting | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---:|---:|---:|---:|
| 384 blocks, serial | 133.72 | 107.75 | 25.72 | 24.62 |
| 32 blocks, serial | 134.91 | 110.09 | 25.77 | 24.74 |
| 32 blocks, overlap | 136.52 | 112.38 | 25.84 | 24.85 |

The combined change gained **2.09% coding / 4.30% editing** on generation.
Holding 32 blocks fixed, overlap added **1.19% / 2.08%** over serial. Effective
throughput improved **0.48% / 0.91%** versus the original serial control;
prefill dominates more of total request time at this length. This is one 128K
triple, alongside the separate repeated 32K evidence, not a confidence bound.

[Complete native128K MTP records and comparisons](benchmarks/q8-miss-geometry-128k-mtp-20261004.json).

## Rejected plain-decoding attempt and benchmark guard

The first 32K plain overlap attempt was rejected. Its startup clamped the RAM
complement from the intended **44.28 GiB / 9,104 experts** to **43.64 GiB /
8,973 experts**. INFO reported `arena_mib=44689` instead of `45342`. The coding
and editing requests then recorded 353 and 787 expert file reads, respectively.
Coding first differed at token index 120. This changed placement is a confound;
the attempt is not evidence of an overlap speed gain or a kernel correctness
failure. Its successful process exit alone is insufficient to accept it.

The valid serial controls and completed MTP comparisons remain recorded. The
rejected record and startup evidence are preserved in
[the placement investigation](benchmarks/q8-miss-geometry-rejected-placement-20261004.json).

The benchmark now supports an explicit expected INFO mapping and required
startup log patterns. These comparisons require the full RAM arena, fixed GPU
slots, FP16 KV and a locked lookup table before sending any prompt. A mismatch
closes the engine and records the observed configuration and resource limits;
it does not retry a failed output comparison or change memory policy. This is
a harness check. The engine under comparison remains the tested `7db4414`
binary. The completed guarded 32K results are below. All three remaining
modes at 128K need valid controls; their results are not implied by the MTP
measurements.

## Guarded 32K plain-decoding comparison completed

All three fresh arms passed the startup guard with the full 44.28GiB RAM
complement and a locked lookup table. Each generated 1,024 coding and 1,024
editing tokens. All tokens, recorded work, primary-exchange payload and
secondary-cache counts matched; expert file reads were zero. This supplies a
valid comparison for the setting rejected above, without discarding that record.

| Setting | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---:|---:|---:|---:|
| 384 blocks, serial | 74.21 | 62.38 | 47.24 | 42.42 |
| 32 blocks, serial | 74.47 | 62.81 | 47.32 | 42.62 |
| 32 blocks, overlap | 74.66 | 63.22 | 47.40 | 42.84 |

The combined change gained **0.61% coding / 1.34% editing** on generation in
this first valid triple. Prefill-inclusive gains were **0.35% / 1.00%**. Plain
decoding's gain is smaller than the separately measured MTP gain. This is one
fresh triple; it does not establish a confidence interval or a 128K result.

[Full startup checks, requests and paired analysis](benchmarks/q8-miss-geometry-plain-guarded-20261004.json).

## Guarded 32K n-gram and combined comparisons completed

All six arms passed full-residency/locked-table startup checks and completed
1,024 coding and 1,024 editing output tokens. Expert file reads stayed zero.
Each row uses the same `7db4414` binary, 32K input, FP16 KV and the placement
above. The n-gram policy is timing-sensitive: speculative work can change
when scheduling changes. These rows must retain that qualification.

| Mode | Setting | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---|---:|---:|---:|---:|
| N-gram | 384 blocks, serial | 78.76 | 107.04 | 49.02 | 59.12 |
| N-gram | 32 blocks, serial | 79.18 | 115.37 | 49.21 | 61.63 |
| N-gram | 32 blocks, overlap | 75.80 | 118.53 | 47.84 | 62.56 |
| MTP + n-gram | 384 blocks, serial | 131.85 | 111.48 | 65.26 | 60.43 |
| MTP + n-gram | 32 blocks, serial | 132.90 | 114.62 | 65.55 | 61.35 |
| MTP + n-gram | 32 blocks, overlap | 135.90 | 120.21 | 66.25 | 62.86 |

Versus 384 serial, n-gram overlap changed coding **-3.76%** and editing
**+10.73%**; combined overlap changed coding **+3.07%** and editing **+7.83%**.
These are single request pairs, with no confidence intervals. Editing output
tokens matched in every comparison, but n-gram accepted/offered counts and
expert work differed. Coding first differed at zero-based token index **316**
for n-gram overlap and **122** for combined overlap. No quality-equivalence
claim follows from these differences.

The 32-block serial combined coding pair did match tokens and recorded work
and improved **0.80%**. Other speculative comparisons changed recorded work,
even where tokens matched. All copy/cache counter differences are preserved
alongside token and speculation differences; these rows are not isolated
same-work copy-kernel measurements.

[Complete requests, startup evidence and qualified comparisons](benchmarks/q8-miss-geometry-32k-speculation-20261004.json).
