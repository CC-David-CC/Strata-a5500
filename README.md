# Experimental Q8 GPU refills

A small experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata),
testing refills from immutable secondary GPU copies on an **RTX PRO 6000 Blackwell
Workstation Edition 96GB**, with 128GB RAM, full Unsloth Q8_0 and FP16 KV.

**Native build, byte/sanitizer checks and all 33 lifecycle requests passed.**
Control, metadata-only and GPU-refill runs matched tokens, measured work and
main-model state checks, including STOP and MTP checkpoint restoration.
Actual GPU-to-GPU copies occurred; primary victim writebacks stayed unchanged.
First 32K-input/1K-output MTP pair: **+1.64% coding / +1.50% editing**
generation throughput, with matching tokens and measured work. Primary refill
RAM uploads fell 61.85%; primary victim writebacks remained. This is a first
pair, not a repeated or 128K claim. All four 32K modes completed: plain gained
0.74%/0.51%, combined MTP+n-gram gained 1.32%/1.51%, with matching tokens/work.
N-gram alone changed work and lost 1.95% coding / 0.08% editing.
Reverse-order repeats and native 128K pairs are queued.

The change copies cache tags at an existing synchronization point, then substitutes
GPU-to-GPU copies for eligible repeated RAM-to-GPU uploads. Primary victim writebacks
are preserved. Both new options default off.

See [design, invariants and validation plan](docs/Q8_GPU_REFILLS.md).
All original Strata credit and license terms remain applicable.
