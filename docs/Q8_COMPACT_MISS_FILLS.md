# Q8 secondary-cache upload compaction

Branch `perf/q8-compact-miss-fills`, based on the fork's measured copy-grid
branch and [Niko1221/Strata](https://github.com/Niko1221/Strata).
Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM, full Unsloth Q8_0 and FP16 KV.

## Evidence and intervention

The measured four-slot-per-layer cache avoided 1,945 of 24,188 uploads in the
32K MTP coding/editing pair, or 8.04%. Cache hits avoid RAM reads, but the fill
kernel still iterates through `group_count * expert_bytes / 16` positions.
Each hit position calculates its group/offset and skips the copy. An all-hit
group still visits the entire range. Smaller copy grids increase the number
of loop iterations per thread, so this is a concrete remaining source of work.

`STRATA_Q8_COMPACT_MISS_FILL=1` records upload indices in the existing plan
kernel. The fill kernel visits only those indices. Its loop remains a complete
16-byte grid-stride copy of every actual miss. A miss that bypasses the small
cache still needs an upload and is included. The ordinary template remains
available and is the default. The plan adds a fixed 64-entry index list and a
count; arena alignment still applies. No additional kernel or synchronization
is introduced, and no physical read/write savings are claimed for this change.

The extra index read and plan writes could outweigh the skipped iterations.
The component experiment and full model comparison, rather than the existence
of redundant instructions alone, decide whether to keep it.

## Invariants

- Preserve group order, source/destination addresses and all expert bytes.
- Reserve existing hits before replacements; retain the same LRU decisions.
- Upload all misses, including cache-capacity bypasses.
- A cache key becomes valid only after the complete fill kernel finishes.
- Join the upload branch before expert consumers; retain their buffer lifetimes.
- Preserve primary expert placement, CPU/GPU split, arithmetic and output policy.
- Reject malformed flag values; absent or `0` keeps ordinary traversal.

## Required validation

The component fixture uses independent complete-byte comparisons, guarded
destinations, immutable RAM sources and null RAM pointers for actual hits.
It covers empty/all-hit/all-miss/mixed groups, hit reservation, eviction,
staging bypass, graph replay, serial/overlap, abandoned fills and full
5,222,400-byte experts with cache capacities 0/4/16. Small/tail cases also use
capacity 1. The prepared gate runs both templates at 32/384 blocks, then
Compute Sanitizer memcheck/initcheck at 32, plus invalid-flag rejections.

A separate fixed-plan microbenchmark measures only fill traversal, using real
expert size and groups of 1/4/16 with varying misses. It checks every copied
byte and untouched hit destination after replay. Off/on/on/off ordering is
recorded. These timings exclude planning, publication and model computation
and cannot establish a model speedup.

After component gates and the CUDA build, use the same new binary for native
32K + 1,024-output coding/editing comparisons in plain, MTP, n-gram and combined
modes. Hold primary slots at 15,472, secondary slots at four per layer, copy
blocks at 32, overlap on, PCIe fraction 0.55 and ownership/duplex enabled.
Check default-off against the earlier binary as well. Exact plain/MTP tokens
and recorded work are required; timing-sensitive n-gram changes remain visible.
Extend useful paths to native 128K and repeat before a speed claim or push.

## First component gate and fixture correction

Source `2762f5a` compiled the fixture and kernels. All four ordinary byte-test
runs (compact off/on at 32/384 blocks) passed, as did memcheck off/on and
initcheck off. Initcheck on failed with 17,740 reported host API access
errors. The runner stopped before microbenchmarks, engine build or model tests.

The fixture copied all 1,544 bytes of `ReadonlyMissCachePlan` to the host even
though only its counts and active fill-index prefix were inspected. Unused
array entries are deliberately unwritten scratch, so the copy itself reads
uninitialized bytes. The corrected fixture copies only the initialized counts
and active prefix. Device scratch remains uninitialized: zeroing the whole
plan would hide accidental kernel reads beyond the valid prefix.

This correction changes the fixture only. The corrected gate below confirms
the initcheck diagnosis; the failed run did not reach model testing.
The failed run and its logs remain in
[the rejected fixture evidence](benchmarks/q8-compact-fill-rejected-fixture-20261004.json).


## Corrected component gate completed

The fixture-only correction passed all 88 complete-byte cases, memcheck and
initcheck with compact traversal both off and on (four zero-error sanitizer
runs), and the three malformed-flag rejections. The device plan was not
zero-filled to hide unused-entry reads. The earlier failed run is preserved
above. The CUDA engine built successfully with ccache; model testing follows.

Fill-only microbenchmark: 32 blocks, 5,222,400 bytes/expert, off/on/on/off order.
Each number averages two batches of 64 graph replays. No planning, publication,
expert arithmetic or prefill is inside these times. No model speedup or
confidence interval is established by this table.

| Expert groups | Actual misses | Ordinary fill us | Compact fill us | Fill time reduction |
|---:|---:|---:|---:|---:|
| 1 | 0 | 6.17 | 2.06 | +66.65% |
| 1 | 1 | 198.67 | 198.77 | -0.05% |
| 4 | 0 | 18.43 | 2.04 | +88.91% |
| 4 | 1 | 213.63 | 198.79 | +6.95% |
| 4 | 2 | 395.81 | 393.45 | +0.60% |
| 4 | 4 | 783.30 | 783.32 | -0.00% |
| 16 | 0 | 67.55 | 2.05 | +96.97% |
| 16 | 1 | 261.97 | 198.68 | +24.16% |
| 16 | 8 | 1571.40 | 1563.20 | +0.52% |
| 16 | 16 | 3122.58 | 3122.27 | +0.01% |

[Complete gates, sanitizer logs, build and microbenchmark samples](benchmarks/q8-compact-fill-components-20261004.json).


## First full-model screen: all four modes

All eight arms (16 requests) completed: full Unsloth Q8_0, FP16 KV, native
32,768 input tokens + 1,024 committed output tokens, with 40,960 allocated.
Primary capacity was 15,472 experts; the full 45,342MiB RAM arena and locked
lookup table passed the startup guard. No expert file reads occurred.
Secondary capacity was four slots per layer, with 32-block overlapped fills,
PCIe fraction 0.55, ownership rotation and duplex transfers unchanged.

The existing approximately two-second monitor observed minimum free VRAM of
7,378MiB and available host RAM of about 19.85GiB, with no foreign GPU
process recorded. These are sampled minima, not bounds on unsampled transients.

These are one ordinary/compact pair per mode in the same binary, not repeated
gains or confidence intervals. Plain and MTP tokens, recorded work, primary
exchange bytes and secondary upload counts matched exactly. Their default-off
arms also matched the earlier binary's tokens and recorded work. N-gram uses
timing-sensitive policy; its request/work qualifications are shown separately.

| Mode | Coding ordinary -> compact tok/s | Change | Editing ordinary -> compact tok/s | Change |
|---|---:|---:|---:|---:|
| MTP | 133.52 -> 135.39 | +1.40% | 118.33 -> 118.15 | -0.15% |
| Plain | 74.60 -> 74.70 | +0.13% | 63.09 -> 63.12 | +0.04% |
| N-gram* | 78.82 -> 79.63 | +1.03% | 111.33 -> 113.03 | +1.52% |
| MTP + n-gram* | 134.36 -> 136.05 | +1.26% | 116.69 -> 116.78 | +0.08% |

*N-gram comparisons are not automatically equal-work kernel measurements:

| Mode / task | First differing output token (zero-based) | Recorded work matches | Logical copy payload/counts match |
|---|---:|---|---|
| N-gram / coding | none | no | no |
| N-gram / editing | none | no | no |
| MTP + n-gram / coding | 311 | no | no |
| MTP + n-gram / editing | none | no | no |

Effective throughput, all prompt/output tokens, exact-work checks, per-window
host timings and copy counts are retained in the evidence below. The isolated
fill timings establish that hit traversal can be cheaper; this model screen
alone does not establish that it caused a small end-to-end timing change.
Reverse ordering and native 128K validation remain pending before a broader
performance claim. Keep ordinary traversal as the default and an alternative.

[Full model records and qualified comparisons](benchmarks/q8-compact-fill-model-32k-20261004.json).


## Reversed 32K pair and native 128K: no repeated gain

The four follow-up arms (eight requests) completed using the same measured
engine bytes and placement. Every request generated 1,024 output tokens; the
full RAM/locked lookup guard passed and no expert file reads occurred. Both
pairs matched tokens, recorded work, primary exchange payload and secondary
hit/upload/bypass counts exactly. Approximately two-second samples recorded
no foreign GPU processes. Timings below are generation rates.

| MTP pair | Coding ordinary -> compact tok/s | Change | Editing ordinary -> compact tok/s | Change |
|---|---:|---:|---:|---:|
| 32K, compact first | 135.04 -> 134.80 | -0.174% | 118.16 -> 118.43 | +0.231% |
| 128K, ordinary first | 136.62 -> 136.11 | -0.373% | 112.44 -> 112.41 | -0.030% |

The initial +1.40% coding observation did not repeat. Keep this option off for
the measured four-entry secondary cache. Faster isolated fill traversal did
not establish a sustained whole-model benefit. There are no confidence
intervals or blanket equivalence claims from these pairs.

The complete scope is 24 throughput requests: all four modes at 32K initially,
then a reversed 32K MTP pair and one native 128K MTP pair. This does not claim
128K plain/n-gram coverage for compaction. The earlier n-gram output/work
qualifications remain part of the report. The code and negative evidence stay
available as an alternative; a substantially higher cache-hit workload could
justify revisiting it, but would require a new measured comparison.

[Follow-up raw records, exactness/copy checks and resource samples](benchmarks/q8-compact-followup-20261004.json).
