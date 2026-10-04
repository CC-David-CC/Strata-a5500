# Experimental Q8 admission by layer

An experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch tests letting early layers run while adaptive expert transfers for
later layers finish. It keeps the same selected experts and waits for each
affected layer's complete transfers before publishing its CPU/GPU expert plan.
It retains RAM ownership rotation and drains every request boundary.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth **Q8_0, FP16 KV**, native context.
`STRATA_EXCHANGE_LAYER_ADMISSION=1` is experimental and off by default.
The initial path requires one GPU, unsplit host-planned verification, fully
pinned resident expert exchanges and ownership rotation/duplex enabled.

**First native 32K-input/1K-output MTP comparison:** coding **135.0 ? 144.6 tok/s
(+7.1%)**, editing **119.0 ? 124.4 (+4.6%)**, with identical tokens, measured work
and transfer payloads. Effective throughput improved **3.4% / 2.3%**.
This is one pair; repeatability and 128K results are pending.

All **33 lifecycle requests** and component/sanitizer/build checks passed.
The earlier test-harness failure and its correction remain in the report.
All four 32K modes finished: plain gained 3.1%/2.7%; n-gram alone lost 1.9%/6.0%,
and combined gained 5.0%/1.7% with changed work. Preserve the earlier n-gram
configuration. Reverse-order MTP and 128K tests are queued. This branch has not
yet been published.

See [hypothesis, state and validation](docs/Q8_LAYER_ADMISSION.md) and
[the measured parent](docs/Q8_MISS_FETCH_GEOMETRY.md).
Main is untouched and the upstream license is retained. For standard
installation and support, use [upstream Strata](https://github.com/Niko1221/Strata).

The reversed-order 32K MTP repeat also matched tokens/work/counters: coding
136.42 -> 144.43 tok/s (+5.87%), editing 119.30 -> 124.36 (+4.23%).
Native 128K tests are running; no 128K result is claimed yet.
