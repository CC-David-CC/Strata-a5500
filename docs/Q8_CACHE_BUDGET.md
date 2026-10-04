# Q8: spend spare VRAM on duplicates or primary experts

Experimental configuration branch of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Hardware: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM. Full Unsloth Q8_0, FP16 KV, native RoPE. No inference code changes.

## Evidence and competing explanations

The first 32K capacity screen found that 16 secondary entries per layer improved
MTP coding from 135.45 to 137.72 tok/s (+1.67%) and editing from 118.23 to 122.93
(+3.98%) versus four entries, with identical output and recorded work. These
were initial pairs; the repeated results are recorded below. Secondary upload payload fell from
36.93 to 31.00GB for coding and 79.23 to 62.80GB for editing; primary exchanges
were unchanged. All initial capacity modes have now completed; their full artifact is linked below.
[MTP records and resource measurements](benchmarks/q8-cache-capacity-mtp-32k-20261004.json).

A previous equal-memory comparison added 192 primary slots and improved
editing by 2.59% once, but placement/work differed. This makes larger primary
residency a useful competitor: it can avoid CPU computation and uploads.
Secondary duplicates avoid repeated uploads without changing the CPU/GPU split.
The faster use of the same VRAM is an empirical question.
[Earlier primary-capacity comparison](benchmarks/q8-primary-plus192-prior-20261004.json).

## Configurations

Each expert is 5,222,400 bytes. Secondary storage covers 48 layers.

| Configuration | Primary experts | Secondary entries/layer | Expert storage relative to baseline | Planned contexts |
|---|---:|---:|---:|---|
| Baseline | 15,472 | 4 | 0 | 32K, 128K |
| Duplicate cache | 15,472 | 16 | +2,868.75MiB | 32K, 128K |
| Equal-memory primary | 16,048 | 4 | +2,868.75MiB | 32K, 128K |
| More primary at 32K | 16,560 | 4 | +5,418.75MiB | 32K only |

The first three keep the same combined expert allocation where indicated.
The fourth uses additional headroom available at 32K; it is not an equal-memory
comparison. Do not silently shrink a requested cache to make an arm fit.
The expected full RAM complement is respectively 45,342, 42,473 and 39,923MiB
for the three primary capacities. PLE must remain locked and expert file reads
must remain zero. Measure actual sampled VRAM/RAM use, not just this budget.

## Gates and measurements

1. Build the new branch with ccache. Require exact engine binary identity with
   the completed capacity component gate: 24 byte cases, full-size eight/sixteen
   entry copies in serial/overlap paths, and memcheck/initcheck passes. Reusing
   those component results is conditional on identical engine bytes.
2. Test four lifecycle arms: plain/MTP with four versus sixteen secondary
   entries, at 32K and fixed primary capacity. Check normal requests, STOP,
   following requests, MTP checkpoint switching/restoration and state hashes.
   Enforce full placement and locked PLE before the first prompt.
3. Fifteen fresh-engine arms, coding then editing, 1,024 committed output
   tokens. At 32K MTP run secondary16 first, equal-memory primary and baseline4;
   also reverse plain16/four. At 128K test four/sixteen entries
   in all four modes, plus equal-memory primary with MTP. The primary placement
   screen is MTP-only; this does not establish primary-placement performance
   for the other modes.
   Run the most aggressive 32K primary allocation last, so an allocation failure
   there does not prevent collecting the native128K capacity comparisons.
4. Require exact tokens/work for plain and MTP unchanged-primary four/sixteen
   comparisons. N-gram and combined runs retain any output/work differences
   as qualified observations; they do not pass that exact-work gate.
   Primary placement changes which implementation computes an expert, so retain
   first differing tokens, speculative work, routing/cache counts and timings.
   Do not describe placement-dependent comparisons as equal-work kernel gains.
5. Record output and effective throughput, sampled resource minima, CPU expert
   time, exposed transfer waits, primary D2H/H2D and secondary uploads. Extend
   useful configurations to the other modes after this screen.

All arms keep copy32 overlap, ownership rotation, duplex transfers, PCIe fraction
0.55, native context and FP16 KV. This branch does not enable compact fills or
per-layer admission: those remain independently measured candidates.

Status: fresh byte-identical build and all 22 lifecycle requests passed.
The 32K MTP placement triple, reversed plain pair and first full native128K
MTP pair have completed below; other 128K modes and primary placements are
still running. Both the duplicate-cache and primary-cache designs
remain alternatives; a smaller upload count alone is not a speedup.


## Lifecycle harness correction before execution

The first budget queue was stopped while waiting for the GPU, before any
attempt or engine started. A separate per-layer run exposed an eager Python
`dict.get` default accessing the legacy `ways` field despite an explicit
variant list. The same helper is corrected here before requeueing. Explicit
and legacy plans plus empty/null/object rejection were checked locally; no
engine source changed. The fresh queue must still pass byte-identical build,
normal/STOP/checkpoint checks and the planned throughput comparisons.


## Build and lifecycle gate passed

The frozen `3745a0d` branch built successfully with ccache, producing exactly
the capacity engine bytes:
`96c16a3a64ccc4d1583242c1cf5838b5d32186fdbbea9d055a8040b560fdd4b7`.
The prior complete-byte/sanitizer evidence hash was checked before admitting
this build. Worker ASan/UBSan and TSan also passed in the fresh build stage.

All four lifecycle arms completed and exited cleanly:

| MTP | Secondary entries/layer | Requests | Covered |
|---|---:|---:|---|
| Off | 4 | 3 | Normal, stop at 16 delivered tokens, following request |
| Off | 16 | 3 | Same sequence, compared with four entries |
| On | 4 | 8 | Above plus five checkpoint/switch/restore requests |
| On | 16 | 8 | Same sequence, compared with four entries |

All **11 paired comparisons** matched output tokens, recorded work and
main-model state fingerprints exactly, including cancellation and the request
after cancellation. No comparison needed the unequal-cancellation-work
qualification. All startup guards passed with full RAM residency, locked PLE,
FP16 KV, 15,472 primary experts and 40,960 allocated context; no expert file
reads occurred. These checks use 32K prompts. They do not establish 128K
lifecycle coverage or correctness for a different primary placement.

[Build identity, complete request records and state comparisons](benchmarks/q8-cache-budget-lifecycle-20261004.json).
The [complete initial 32K capacity screen](benchmarks/q8-cache-capacity-model-32k-20261004.json)
is also retained here, including plain and n-gram results and qualifications.
The fifteen-arm throughput follow-up proceeds after this gate; its results
remain separate from these functional checks.


## First follow-up MTP triple at 32K

All six requests below finished with 32,768 input + 1,024 output tokens,
40,960 allocated and FP16 KV. Full placement/locked-PLE guards passed and no
expert file reads occurred. These generation/effective rates exclude model
startup; effective throughput includes prompt processing. Coding ran before
editing in each fresh engine.

| Primary experts | Secondary entries/layer | Coding generation | Editing generation | Coding effective | Editing effective |
|---:|---:|---:|---:|---:|---:|
| 15472 | 16 | 137.51 | 123.36 | 66.55 | 63.75 |
| 16048 | 4 | 139.16 | 121.50 | 68.94 | 64.88 |
| 15472 | 4 | 135.38 | 118.23 | 66.13 | 62.35 |

For unchanged primary residency, running sixteen entries first and four last
gave **+1.58% coding / +4.34% editing**
for sixteen versus four. All tokens, recorded work and primary exchange bytes
matched. Secondary hit/upload counts changed as intended. This is the reversed
pair following the initial +1.67%/+3.98% capacity observations.

Spending the same extra 2.802GiB on 576 more primary experts instead of twelve
more secondary entries per layer gave **+1.20% coding /
-1.50% editing generation** relative to the larger
secondary cache. Throughput including prefill improved
**+3.59% / +1.77%** in this pair.

This placement comparison changes arithmetic placement and is qualified:

| Task | First differing output token, zero-based | Recorded work matches |
|---|---:|---|
| coding | 120 | no |
| editing | none | no |

Keep both uses of spare VRAM as alternatives: the primary placement changes
which experts the CPU computes, while the secondary cache removes repeated
uploads without changing that assignment. These first placement results do not
establish a universal winner or equivalent answer quality. Native128K, the
other capacity modes, and the more aggressive primary allocation are still
running or queued in the same suite.

[Full records, first divergence, work/copy counts and resource samples](benchmarks/q8-cache-budget-first-mtp32k-20261004.json).


## Reversed plain pair and both-order 32K summary

The reversed plain pair also passed full placement guards and all token/work
checks. At 32,768 input + 1,024 output (40,960 allocated, FP16 KV), four to
sixteen entries gave:

| Task | Four entries tok/s | Sixteen entries tok/s | Change |
|---|---:|---:|---:|
| coding | 74.61 | 75.50 | +1.20% |
| editing | 63.22 | 64.71 | +2.36% |

Primary residency, primary exchange bytes, tokens and recorded work matched.
Secondary hit/upload counts changed, as intended. The two orders now show:

| Mode / order | Coding gain | Editing gain |
|---|---:|---:|
| plain / ascending | +1.05% | +2.66% |
| plain / reversed | +1.20% | +2.36% |
| mtp / ascending | +1.67% | +3.98% |
| mtp / reversed | +1.58% | +4.34% |

Both modes improved in both orders. This supports a repeated gain for these
requests, not a confidence interval or a general workload guarantee. The
initial n-gram qualifications and primary-placement differences remain in
their respective sections. Native128K testing continues separately.

[Plain request records, timings/copy counts and both-order summary](benchmarks/q8-cache-budget-plain-repeat-20261004.json).


## First full native128K MTP capacity pair

All four requests completed with **131,072 input + 1,024 output tokens**, 139,264
allocated and FP16 KV. Each fresh engine ran coding then editing. Sixteen
secondary entries per layer fit with the same 15,472 primary experts, the full
44.28GiB RAM expert complement and locked PLE; expert file reads stayed zero.

| Task | Four entries generation | Sixteen entries generation | Change | Four entries effective | Sixteen entries effective |
|---|---:|---:|---:|---:|---:|
| coding | 136.49 | 138.43 | +1.42% | 25.82 | 25.89 |
| editing | 112.74 | 116.35 | +3.19% | 24.86 | 25.03 |

All rates are output tokens/s; effective includes prompt processing and excludes
model startup. Tokens, recorded work and primary exchange payload matched
exactly. Total secondary upload payload across coding and editing fell from
118.59GB to 96.58GB (18.56%); these are logical payload counts, not measured
hardware DRAM or PCIe transactions. The much smaller speed gain indicates that
the removed uploads were only part of the request's critical path.

The lowest two-second GPU free-memory sample was **1,862MiB** for sixteen
entries (four entries: 4,732MiB). The engine's startup free-memory report was
**1,302MiB** for sixteen entries. These are distinct observations from different
measurement points, not a claim that free memory never fell below 1,862MiB.
Sampled host available memory stayed at or above 20.07GiB, with no foreign GPU
process observed.

This is one completed 128K pair. The repeated result and lifecycle/state checks
above apply to 32K; 128K cancellation/checkpoint behavior has not been tested by
this pair. Plain, n-gram, combined and primary-placement 128K comparisons remain
in the running suite.

[Full 128K request records, copies, timing and resource evidence](benchmarks/q8-cache-budget-mtp128k-20261004.json).
