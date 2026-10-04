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

**Component, sanitizer and build gates passed; model validation is pending.**
The first lifecycle attempt stopped before loading a model because of a
test-harness configuration bug. The harness is corrected; no inference code
changed in that correction, and no model correctness or speed pass is claimed.
The inherited copy-grid branch's measured gains do not establish a gain here.

See [hypothesis, state and validation](docs/Q8_LAYER_ADMISSION.md) and
[the measured parent](docs/Q8_MISS_FETCH_GEOMETRY.md).
Main is untouched and the upstream license is retained. For standard
installation and support, use [upstream Strata](https://github.com/Niko1221/Strata).
