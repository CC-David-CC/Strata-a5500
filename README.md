# Experimental Q8 GPU refills

A small experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata),
testing refills from immutable secondary GPU copies on an **RTX PRO 6000 Blackwell
Workstation Edition 96GB**, with 128GB RAM, full Unsloth Q8_0 and FP16 KV.

**Prepared, not yet benchmarked.** Native correctness and throughput tests are queued
only after the source is frozen. No speedup is claimed here yet.

The change copies cache tags at an existing synchronization point, then substitutes
GPU-to-GPU copies for eligible repeated RAM-to-GPU uploads. Primary victim writebacks
are preserved. Both new options default off.

See [design, invariants and validation plan](docs/Q8_GPU_REFILLS.md).
All original Strata credit and license terms remain applicable.
