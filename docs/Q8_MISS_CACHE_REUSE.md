# Q8 read-only GPU miss cache: diagnostic

Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0, FP16 KV, native RoPE. Main is unchanged.

Retaining recently promoted experts in RAM showed very little potential to
avoid their later writebacks in the initial 32K traces. A read-only GPU cache
of repeatedly uploaded misses is a different candidate: it may avoid repeated
H2D without changing primary residency or the existing CPU/GPU split.

`STRATA_MISS_TRACE=1` records the actual distinct experts selected for PCIe
execution at each layer/group. It changes no arithmetic or placement. The
analyzer verifies trace byte totals against the engine's logical payload
counters and replays global LRU capacities and separate per-layer caches.
Group members reserve their slots until all consumers finish; excess requests
use the existing uncached staging path in the simulated policy.

The first measurement will use MTP at 32K with 1,024 output tokens, coding then
editing, and check tokens/work against the existing same-binary math path.
Reported timings are diagnostic. Projected saved upload bytes are not a speed
claim. Extra GPU capacity must be checked at native 128K before implementation.

Proposed implementation, if reuse justifies it: separate immutable GPU copies
with per-slot expert tags. The GPU must validate and finish a fill before
publishing a tag. Keep tags separate from KV/recurrent/speculative state;
rejected drafts cannot leave a falsely valid cache entry. Never overwrite a
slot still consumed by a captured graph. A discarded secondary copy always
has an authoritative copy in the existing primary GPU/RAM/file hierarchy.
These lifecycle rules require explicit component and full-model checks.
