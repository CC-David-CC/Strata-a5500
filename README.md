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

**Component validation found a fixture read of unused sparse-plan entries.**
Complete-byte cases and memcheck passed, but initcheck rejected that read;
the model benchmark did not run. The fixture now inspects only the initialized
counts and active entries. Sanitizer validation is pending again; the engine
and kernels are unchanged by this fixture correction. No model speed gain is
claimed. The inherited copy-grid gains do not establish that compaction helps.

See [invariants and required tests](docs/Q8_COMPACT_MISS_FILLS.md), and the
[inherited copy-grid measurements](docs/Q8_MISS_FETCH_GEOMETRY.md).
Main is untouched and the upstream license is retained. For standard
installation and support, use [upstream Strata](https://github.com/Niko1221/Strata).
