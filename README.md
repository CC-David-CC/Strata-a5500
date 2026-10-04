# Experimental Q8 upload compaction

A small experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch tests removing wasted GPU loop iterations from the secondary
expert-cache upload kernel. Hits already skip memory reads, but the existing
kernel still visits their weight ranges. An opt-in compact list makes it visit
only actual uploads, including staging bypasses. Copied bytes, cache policy,
expert computation and publication dependencies stay fixed.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth **Q8_0, FP16 KV**, native context. Enable with
`STRATA_Q8_COMPACT_MISS_FILL=1`; it is off by default.

**The first four-mode 32K model screen completed.** All eight arms reached
1,024 output tokens with full RAM residency and zero expert file reads.
Plain/MTP tokens and recorded work matched; n-gram qualifications and the
speed table are in the report. These are single pairs, with repeats and 128K
validation still pending. All 88 byte cases and four sanitizer runs passed;
the corrected fixture failure remains documented. Ordinary traversal stays
the default. No universal or repeated model speedup is claimed.

See [invariants and required tests](docs/Q8_COMPACT_MISS_FILLS.md), and the
[inherited copy-grid measurements](docs/Q8_MISS_FETCH_GEOMETRY.md).
Main is untouched and the upstream license is retained. For standard
installation and support, use [upstream Strata](https://github.com/Niko1221/Strata).
