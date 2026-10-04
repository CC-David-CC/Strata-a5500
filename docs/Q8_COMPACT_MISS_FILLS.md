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

This correction changes the fixture only. A fresh initcheck pass is still
required to confirm the diagnosis; there is no accepted model result yet.
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
