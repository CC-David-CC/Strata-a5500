# Q8 secondary cache and CPU assignment diagnostic

Experimental diagnostic branch of [Niko1221/Strata](https://github.com/Niko1221/Strata),
derived from this fork's measured copy-grid path. Hardware: RTX PRO 6000
Blackwell Workstation Edition 96GB, Ryzen 7950X, 128GB RAM. Full Unsloth Q8_0,
FP16 KV, native 32K input + 1,024 output for this diagnostic.

## Question

The host planner chooses CPU versus PCIe groups from primary residency and a
fixed PCIe fraction. The later GPU cache lookup can avoid a transfer for
GPU-assigned groups, but it does not reconsider CPU-assigned groups. Some CPU
work might therefore use weights already present in the secondary GPU cache.
The completed census below measures that frequency before adding a host cache
snapshot or changing expert placement.

`STRATA_MISS_ROUTE_TRACE=1` records the existing distinct expert IDs, assignment
and token count at each layer. It changes no assignment, routing, arithmetic or
cache policy. It is off by default. Trace logging adds overhead, so traced
throughput is not a performance result. Plain and MTP output and recorded work
must match the earlier untraced sixteen-entry configuration.

## Measurements and falsifiers

Replay the existing per-layer cache with 0, 4, 8 and 16 entries. Validate the
actual sixteen-entry replay against the GPU's cumulative hit/upload/bypass and
byte counters at **every request boundary**, plus independent per-request PCIe
group/byte accounting. Keep caches across coding then editing, as the engine
does; never assume a fresh editing cache.

For CPU-assigned groups, count weights present before current GPU fills and
the subset still present after those fills. The latter excludes entries that
would be evicted before a potential GPU consumer. Both are opportunities under
the unchanged trace, not predictions after changing execution. Report groups,
token entries, request and layer breakdowns. A small opportunity parks the idea;
a mismatch with device counters invalidates the replay.

Any later implementation would need explicit cache publication/lifetime
dependencies and cancellation/checkpoint tests. Moving CPU work to the GPU can
change reduction arithmetic, token decisions and future speculative work;
it cannot be advertised as an identical-work kernel gain. More GPU work can
also slow current GPU computation despite avoiding uploads. Only a measured
whole-request gain would justify adoption.

## Can primary refills reuse a secondary GPU copy?

The same capture enables the existing `STRATA_EXCHANGE_TRACE=1` flag. It logs
committed primary ownership exchanges. At those boundaries the replay checks
whether each incoming expert already has an immutable secondary GPU copy.
The combined trace changes neither cache policy nor refill behavior.

The parser requires contiguous exchange counters, valid within-layer pairs,
consistent primary ownership and complete verification-window boundaries.
At every request footer, the traced committed count must equal the engine's
reported cumulative count. Report available copies and payload bytes for the
actual sixteen-entry cache, with zero/four/eight-entry trace projections.

These are **committed exchanges**, not all enqueued H2D copies. A delayed
commit can appear under the following request's footer; a final uncommitted
refill is excluded. The opportunity count is not a throughput prediction.

If the count is large enough, a separate opt-in implementation could choose a
GPU source for that primary refill. It would need full-byte identity checks,
an explicit source lifetime until the D2D completes, the existing victim-D2H
dependency, unchanged primary placement and separate D2D/H2D counters. The
current whole-batch admission is a simple initial boundary; a later per-layer
version must also keep its secondary source from being evicted by the next
layer lookup. A copy saved is useful only if the measured request improves.

## Preparation before the capture

Diagnostic code and seven parser/replay tests pass locally. They include
corrupted exchange counters, ownership, request footers and boundary rejection.
The first queue was superseded while waiting, before any build or request,
to include this existing exchange trace in the same four diagnostic requests.
Native build and model measurements followed as recorded below. Main and public
services are unchanged.


## Native census complete

All four diagnostic requests completed: native 32,768 input + 1,024 output,
40,960 allocated, FP16 KV, 15,472 primary experts, sixteen secondary entries
per layer and PCIe fraction 0.55. Full RAM/locked-PLE guards passed, with zero
expert file reads. Plain and MTP coding/editing tokens and recorded work
matched their untraced controls exactly. The trace timings are not speed results.

All seven replay tests passed on the local machine and llm-60. The native
ccache build and worker ASan/UBSan/TSan gates passed. The measured engine hash
is `af916cd05037851ee89a8838cb9da0527c260e2698ce8689ecff844a11ca5a85`, source
`53df1c0b1ec8aa143182892ff53d2b3943ac6bdb`.

| Mode / task | CPU expert groups | Already cached before fills | Still cached after current fills | Cached primary promotions / committed | Potential refill bytes, GB |
|---|---:|---:|---:|---:|---:|
| Plain / Coding | 20,015 | 4,911 (24.54%) | 24.05% | 1,570/2,992 | 8.20 |
| Plain / Editing | 36,134 | 8,374 (23.17%) | 22.42% | 2,052/3,174 | 10.72 |
| MTP / Coding | 13,782 | 3,647 (26.46%) | 25.63% | 2,195/3,775 | 11.46 |
| MTP / Editing | 21,900 | 4,961 (22.65%) | 20.93% | 2,709/4,154 | 14.15 |

The actual sixteen-entry replay matched GPU hit/upload/bypass/byte counters
and independent logical PCIe group/byte accounting at every request boundary.
The committed-exchange trace also matched each request footer's cumulative
exchange count. The raw artifact retains per-layer and zero/four/eight-entry
projections as well as the actual-capacity result.

Across coding plus editing, **58.74% of plain promotions (18.92GB)** and
**61.85% of MTP promotions (25.61GB)** had secondary GPU copies. These are
committed promotions; pending final refills are excluded, and delayed commits
can appear under the next request's footer. The weights could potentially
supply a D2D refill without changing placement, but that path is not implemented
by this diagnostic.

The CPU opportunity is also large enough to test. Its current staging plan
has sixteen groups, so a candidate must preserve existing GPU assignments and
respect remaining group capacity. Moving CPU work changes arithmetic placement
and can alter tokens and future routing; these counts do not promise the same
realized fraction after enabling it.

A prospective shared mechanism is a 3,072-byte snapshot of all cache tags
(48 layers x16 entries x4 bytes) copied on the verifier stream before its
existing end-of-window synchronization. This could avoid a new per-layer
round trip. Its overhead, source lifetime and snapshot correctness still need
component and model tests. Neither opportunity above is a measured speed gain.

[Native build, full request records and validated census](benchmarks/q8-cache-routing-census-20261004.json).
