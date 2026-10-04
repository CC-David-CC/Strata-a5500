# Q8 cache routing diagnostic

An experimental diagnostic fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its engine belongs to upstream and its contributors;
the upstream license is retained.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM, full Unsloth **Q8_0 with FP16 KV**.

This branch measures whether CPU-assigned experts already have usable copies
in the secondary GPU cache. It records assignments and replays cache state;
it does not redirect computation. Logging is opt-in and its timing is not a
speed benchmark. Actual GPU counters must validate the replay before using it.

It also joins the existing committed-exchange trace to count primary-cache
promotions whose bytes are already in the secondary GPU cache. That measures
the opportunity for a device-to-device refill; it does not implement one.

**Measured at 32K:** 23-26% of CPU-assigned expert groups already had copies in
this sixteen-entry GPU cache. Across coding/editing, 59% of plain and 62% of MTP
committed primary promotions also had GPU copies (18.9/25.6GB of potential
refill payload). Every cached CPU group in these traces fits in the remaining
staging slots without displacing existing GPU groups. This is an opportunity
census, **not a measured speedup**.

All four requests matched untraced tokens/work; GPU and committed-exchange
counters validated the replay. Seven replay tests and native build/sanitizer
gates passed. See the [census, exact scope and limits](docs/Q8_CACHE_ROUTING.md#native-census-complete).
The inherited [copy-grid results](docs/Q8_MISS_FETCH_GEOMETRY.md) belong to a
different measured intervention. Main is untouched.
