# Frozen Q8 LAN test configuration

**Optimization is paused.** This branch freezes the tested llm-60 setup,
keeps competing configurations and reports speed and resource savings separately.

- **[Complete matrix and branch status](docs/Q8_FROZEN_MATRIX.md)**
- **[All 536 completed observations](docs/Q8_FROZEN_ALL_MEASUREMENTS.md)**, including controls and diagnostics
- **[LAN connection, validation and rollback](deploy/q8-lan-20261004/README.md)**
- [Bandwidth-saving alternative](docs/Q8_GPU_REFILLS.md): **61.85% fewer primary refill RAM-upload bytes**

The LAN endpoint uses the per-layer engine described below, **MTP on, n-gram
off**, with 139,264 allocated positions and FP16 KV. HTTP authentication,
completion, streaming, FIFO queuing and disconnect recovery passed over LAN.
The API key is stored outside the repository. Main is unchanged.

## Resource saving is an independent win

GPU refills reduced primary refill uploads from **41.4084 GB to 15.7978 GB**
across two 32K-input/1K-output MTP requests, replacing **25.6106 GB** with
GPU-local copies. Primary victim writebacks remained. Reversed-order tests
repeated the saving and approximately 1-2% generation gains with exact matched
output/work. This is primary refill payload, not total PCIe traffic or measured
energy. The large byte saving remains useful even with a small speed gain.

That alternative uses its own engine and sixteen secondary slots per layer.
It is not combined with the faster scheduling path below. Combined layer/refill
and cached-CPU model tests are paused and unvalidated. N-gram qualifications,
negative results, 48 measured profiles and source/binary hashes are in the matrix.

## Selected engine: admit completed expert transfers by layer

A small experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Credit for Strata, its kernels and serving engine belongs to upstream and its
contributors. The upstream license is retained.

Instead of waiting for all adaptive expert transfers, let early layers execute
after their own transfers finish. Keep the same selected experts, arithmetic,
cache capacity and transfer bytes; publish each layer only after its completion
event. Every request boundary drains pending exchanges.

**RTX PRO 6000 Blackwell Workstation Edition 96 GB**, Ryzen 7950X, 128 GB RAM.
Full Unsloth **Q8_0, FP16 KV, native RoPE**. 32K or 128K input plus 1,024 output;
allocated context is input + 8,192. Fixed 15,472 primary slots, four secondary slots
per layer, PCIe fraction 0.55, copy grid 32 with overlap and locked RAM/PLE.

## Measured MTP gains

| Input / order | Coding: control -> per-layer tok/s | Gain | Editing: control -> per-layer tok/s | Gain |
|---|---:|---:|---:|---:|
| 32K / first | 135.01 -> 144.56 | +7.07% | 119.00 -> 124.43 | +4.56% |
| 32K / reversed | 136.42 -> 144.43 | +5.87% | 119.30 -> 124.36 | +4.23% |
| 128K / first | 137.64 -> 145.06 | +5.39% | 113.66 -> 118.45 | +4.22% |

These MTP pairs matched all output tokens, measured work, primary transfer bytes
and secondary-cache counters. The reversed 32K effective-throughput gain was
2.2% for each task; 128K was 0.93% coding/0.88% editing. Effective throughput
includes prefill. The 128K numbers have one pair and no confidence interval.

All four modes completed at both input lengths. Plain gained about 2.5-3.1%.
N-gram alone regressed at 32K (1.9% coding/6.0% editing); it and combined mode
can change timing-dependent speculative work. Their full rates, effective
throughput and first token differences are in the report. Keep configurations
separate; this branch is not a universal default.

All component byte/ownership checks, ASan/UBSan, TSan, CUDA memcheck/initcheck,
native build and 33 lifecycle requests passed. The lifecycle suite covers 32K
normal/STOP/following requests and MTP checkpoint restoration; 128K coverage
here is the full-mode throughput/token/work comparison.

**Opt-in, off by default:** `STRATA_EXCHANGE_LAYER_ADMISSION=1`, with ownership
rotation, duplex exchange and completion waits enabled. Initially restricted
to one GPU, unsplit host-planned verification and pinned resident experts;
peer/remote consumers, device planning and router lookahead are rejected.

[Full results, source identity, invariants and reproduction](docs/Q8_LAYER_ADMISSION.md).
The engine source is `ac398f5e`; later commits add documentation and evidence.
For standard installation, use [upstream Strata](https://github.com/Niko1221/Strata).
