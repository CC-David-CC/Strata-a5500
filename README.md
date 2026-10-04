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

**Prepared, not yet measured.** See the [diagnostic and limits](docs/Q8_CACHE_ROUTING.md).
The inherited [copy-grid results](docs/Q8_MISS_FETCH_GEOMETRY.md) belong to a
different measured intervention. Main is untouched.
