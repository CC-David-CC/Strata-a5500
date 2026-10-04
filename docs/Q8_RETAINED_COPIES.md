# Q8 retained RAM copies and overlap experiments

Local experimental branch `perf/q8-retained-expert-copies`, based on the measured
duplex path. Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB,
Ryzen 7950X, 128GB RAM. Full Unsloth Q8_0, FP16 KV, native RoPE. Main is unchanged.

## First measurement: how many writebacks could be avoided?

Weights are immutable. A GPU expert whose original bytes remain in RAM can be
evicted without copying its bytes back. The current compact RAM representation
deliberately keeps only the GPU cache's complement, so most evictions require a
D2H transfer. Buffer rotation already removes the later host memcpy; it does
not eliminate that D2H copy.

`STRATA_EXCHANGE_TRACE=1` records completed ownership exchanges to the engine log.
The default is off. This first commit changes no placement, transfers or math.
Traced-run timing is diagnostic and must not be advertised as a speed result.

`tools/analyze_q8_retained_copies.py` replays the real sequence with 0, 0.25, 0.5,
1, 2, 4 and 8 GiB of additional retained RAM copies. It reports avoided D2H
payload. FIFO retains recently promoted experts; a separately labeled oracle
uses future evictions to indicate optimistic potential. Neither predicts TPS.
It checks batch continuity, ownership transitions, bounds and simultaneous
eviction dependencies. The existing temporary exchange buffers are additional.

The next runtime experiment will retain incoming RAM buffers by ownership,
recycling an older redundant buffer when needed. It must preserve the original
GPU expert placements, bytes, admission dependencies and authoritative RAM
copy of every nonresident expert. Eviction of a duplicate must never discard
the sole live copy. This is a design to test, not an implemented speedup yet.

RAM capacity is bounded. About 119.5 GiB of experts plus 50.7 GiB of PLE data
cannot all be retained in this host's approximately 124 GiB usable RAM.
Runtime headroom must be checked after loading, not during a restart between
test arms. A bounded copy cache is the initial target.

## Other overlap opportunities

| Path | Candidate | Existing behavior or limit |
|---|---|---|
| Miss fetch | Transfer while resident experts compute | Current kernel-copy path fetches after resident math. DMA exists but has a documented historical stall issue; test in isolation or use a captured, explicitly dependent transfer path. |
| Adaptive exchange | Admit each layer when its copies are ready | Current admission waits for the whole batch. CPU readers and cache ownership must obey per-layer readiness too. |
| Verification | CPU experts for group A while GPU processes group B | Existing `--spec-split` path; upstream calls it exact but slower in its earlier study. Needs current-Q8 measurement before a benefit claim. |
| Prefill | Next expert uploads during current math | Already uses a staging ring/copy stream. Measure gaps before changing depth or scheduling. |
| Prefetch | Use prior/draft routes to fetch probable experts early | Only a prediction of memory demand; actual routing and speculative acceptance remain authoritative. Wrong guesses waste bandwidth. |

Prioritize retained-copy replay and then a bounded runtime cache. Keep a small
read-only GPU cache of repeated misses as a separate competitor: its originals
stay in RAM, but it consumes GPU capacity and can displace useful resident experts.
Measure plain, MTP, n-gram and combined separately; repeat useful gains at 128K.
