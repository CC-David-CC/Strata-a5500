# Q8 expert reuse with duplex exchanges

Experimental branch `perf/q8-duplex-expert-reuse`, based on the measured
`perf/q8-duplex-exchanges` branch. Target: llm-60, RTX PRO 6000 Blackwell
Workstation Edition 96 GB, Ryzen 7950X, 128 GB RAM, full Unsloth Q8_0 and FP16 KV.
Main is unchanged. No new throughput result is claimed yet.

The earlier Q8 reuse experiment (`6ef9268`) used fixed placement, int8 KV, and
`--pcie-frac 0`; almost all missed-expert time was CPU computation. This branch
retests the same opt-in weight-fragment reuse on the current adaptive duplex
path, with the default GPU share of missed experts. The current fused SwiGLU
and grouped-launch improvements are preserved.

The current `--pcie-mode auto` uses a GPU copy kernel to read missed experts
from mapped host memory into VRAM staging, then computes them. The existing
`--pcie-mode direct` instead lets the grouped kernels read those mapped weights
directly. Combining direct reads with reuse may avoid staging writes/reads,
but uncoalesced PCIe reads or repeated requests can make it slower. Measure it.

## Invariants and gates

- Model bytes, selected experts, arithmetic/reduction order and KV precision
  are unchanged. All switches remain opt-in.
- Rebuild the branch with ccache; compare scalar-format-preserving Q8 kernels
  at four shapes, empty/partial groups, and scattered output destinations.
- Compare mapped-host and VRAM weights bit-for-bit, including group-grid widths
  1, 4 (the current PCIe path), and the resident default.
- Replay captured graphs after changing weights and activations for both
  placements. Run Compute Sanitizer memcheck.
- First screen component timing for singleton and shared-expert groups. Then
  use same-binary plain/MTP/n-gram/combined controls at 32K; expand promising
  cases to 128K and reversed-order repeats.

The fixture rotates eight independent weight sets (>600 MiB) and reverses
off/on order. Its mapped test includes PCIe-read cost, but excludes the model's
host work, adaptation and MTP drafting. It cannot establish a model speedup.

`STRATA_DECODE_TIMING=1` now also records exact missed-expert group counts and
the logical minimum weight payload when all layers have equal-sized blobs.
That estimate is distinct from hardware PCIe/DRAM transactions, and does not
include adaptive-cache exchanges or repeated direct reads. A heterogeneous
blob layout reports zero for the unsupported byte estimate.
