# Q8 CPU / PCIe miss balance

Configuration experiment on llm-60: RTX PRO 6000 Blackwell Workstation Edition
96GB, Ryzen 7950X, 128GB RAM, full Unsloth Q8_0, FP16 KV and native RoPE. Based
on the measured duplex branch and its component-validated Q8 instrumentation.
Main is unchanged. No new speedup is claimed before the model test completes.

## Evidence motivating the test

With 15,472 expert slots, adaptive ownership rotation, duplex exchanges and
automatic PCIe fraction 0.55, the current 32K MTP control measured:

| Workload | Tokens/window | CPU experts/layer/window | PCIe experts/layer/window | CPU work/window | Total/window |
|---|---:|---:|---:|---:|---:|
| Coding | 3.23 | 0.91 | 0.52 | 6.98 ms | 25.03 ms |
| Editing | 3.91 | 1.74 | 1.29 | 13.89 ms | 34.92 ms |

These are host timing categories, not GPU hardware counters. Source
`b926ad75744f20652e940db9141900bc91f1b48f`, engine SHA-256
`22d90a60f002a38833c44c4834d082a400540c8fb5c84c80997594075a02d2ee`.

`expert_pool_dispatch_multi` computes the PCIe share as
`(nmiss * pcie_num) >> 8` for each layer/window. With a fraction below one,
a single distinct miss therefore goes to the CPU. The observed GPU share
of missed experts is lower than the nominal 0.55, particularly when there
are only one or two misses. Eliminating that CPU work could be more valuable
than the tied result from grouped Q8 weight reuse.

## Intervention

Use the same binary with `--pcie-frac 1 --pcie-mode auto`, leaving Q8 weight
reuse off. Send eligible pinned-RAM misses to the existing GPU staging path,
subject to its existing staging capacity. This is a placement configuration,
not a new kernel. Keep 15,472 resident slots, FP16 KV, model bytes, native
context, ownership rotation, duplex transfers, MTP parameters and stopping
policy fixed.

First screen plain, MTP, n-gram and combined at 32,768 actual input tokens,
40,960 allocation, 1,024 output tokens, coding then editing. Each arm starts a
fresh engine. Compare to the same-binary controls from the preceding matrix.
Record first token divergence, work/acceptance changes, CPU expert counts,
logical PCIe payload, transfer timing, RAM/VRAM and any expert file reads.

Moving expert arithmetic from CPU to GPU can change floating-point rounding.
Do not describe changed token streams or work as an exact-output kernel gain.
If the GPU-only placement helps, bracket the split, repeat promising cases in
reversed order, and test 128K. The all-four-mode scope remains intact.

Falsifier: additional PCIe and GPU computation cost outweighs the removed CPU
work, or correctness/state failures appear. Actual link counters and timelines
will test that explanation; nominal fraction alone is insufficient evidence.
