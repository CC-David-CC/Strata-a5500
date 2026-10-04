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
The frequency is not known yet. It must be measured before adding a host cache
mirror or changing expert placement.

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

## Status

Diagnostic code and seven parser/replay tests pass locally. They include
corrupted exchange counters, ownership, request footers and boundary rejection.
The first queue was superseded while waiting, before any build or request,
to include this existing exchange trace in the same four diagnostic requests.
No native build, model trace, CPU-cache-hit frequency, promotion-reuse frequency
or speed gain is claimed yet. The queued capacity and per-layer experiments
retain priority. Main and public services are unchanged.
