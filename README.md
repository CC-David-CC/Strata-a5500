# Experimental Q8 secondary GPU cache capacity

This is an experimental configuration branch of
**[Niko1221/Strata](https://github.com/Niko1221/Strata)**. Credit for Strata and
its existing engine belongs to upstream and its contributors. The license is
preserved. Main is untouched.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0 with FP16 KV. Compare 4, 8 and 16 duplicate GPU
cache entries per layer while retaining canonical RAM copies. The goal is to
avoid repeated uploads without adding secondary-cache eviction writebacks.

**Tests are pending; no new speed gain is claimed.** This branch changes test
coverage and configuration, with no new inference kernel or cache policy.

See **[the experiment, memory budget and required gates](docs/Q8_MISS_CACHE_CAPACITY.md)**.
Earlier copy-grid results remain in the inherited
[report](docs/Q8_MISS_FETCH_GEOMETRY.md); they are not capacity results.
