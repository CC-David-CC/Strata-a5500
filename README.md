# Experimental Q8: about 20% faster MTP through buffer ownership

An experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata, its model support, kernels and serving engine belongs to the
upstream project and its contributors. This branch tests a small change to how
RAM buffers are reassigned when the adaptive GPU expert cache swaps experts.

**Measured on an NVIDIA RTX PRO 6000 Blackwell Workstation Edition, 96 GB VRAM,
Ryzen 9 7950X, and 128 GB installed RAM.** Full Unsloth
**Qwen3.8-Flash-Next Q8_0**, FP16 KV, native RoPE, **65,536 input + 1,024 output
tokens**, 73,728 allocated context. Engine test base: Strata 0.1.38.

## Measured results

**MTP decode improved 17-24% across coding and editing in two paired runs per
task, with identical output tokens and matching work counters.** Plain decoding
improved about 8%. Reverse-order repeats are included below.

Two values in a cell are the first run and reverse-order repeat. Rows marked
`*` have only the first paired measurement.

| Mode / task | Original copy, tok/s | Buffer ownership, tok/s | Paired gains |
| --- | ---: | ---: | ---: |
| Plain / coding | 70.07; 70.00 | 75.39; 75.64 | +7.6%; +8.1% |
| Plain / editing | 57.51; 57.43 | 61.93; 62.06 | +7.7%; +8.1% |
| MTP / coding | 112.62; 107.49 | 131.87; 132.53 | +17.1%; +23.3% |
| MTP / editing | 88.81; 86.73 | 107.64; 107.56 | +21.2%; +24.0% |
| N-gram / coding * | 70.64 | 76.31 | +8.0% * |
| N-gram / editing * | 88.42 | 108.14 | +22.3% * |
| MTP + n-gram / coding * | 107.91 | 131.06 | +21.5% * |
| MTP + n-gram / editing * | 88.30 | 106.45 | +20.5% * |

**\* Provisional:** coding first differed at token index 415 for n-gram and 95
for combined mode. Editing tokens matched, but the preceding coding requests
left different adaptive cache histories. These rows have not passed the full
exact-output gate or a reverse-order repeat. Diagnosis is queued; the coding
rates are not equivalent-output speed comparisons.

These are output-generation rates. Including prompt processing, MTP effective
throughput improved **5.8-8.0% for coding** and **8.4-9.3% for editing**.
Startup is excluded. Two pairs are evidence for these requests, not a confidence
interval or a promise of the same gain on other workloads or hardware.

## What changed

Previously, an evicted expert travelled GPU -> temporary RAM -> resident RAM.
The final step copied the whole expert again. This branch makes the temporary
buffer become that expert's resident buffer, then recycles the promoted
expert's former RAM buffer. It changes ownership metadata instead of copying
the bytes a second time.

The GPU-to-RAM eviction transfer and completion waits remain. Model weights,
quantization, KV precision and expert-cache capacity are unchanged. The MTP
coding-plus-editing pair avoids **37.85 GB of RAM-copy payload**.

**Opt-in, off by default:** add this environment variable to an otherwise
working Strata launch:

```sh
export STRATA_EXCHANGE_ROTATE=1
```

Unset it, or set it to `0`, to use the original copy path. The first implementation
requires uniform expert-block sizes and a fully pinned/mapped RAM complement.
Unsupported layouts explicitly retain the copy path. Only the hardware and
configuration above have full-model measurements in this branch.

## N-gram results are provisional

The first n-gram editing pair improved **88.4 -> 108.1 tok/s (+22.3%)** with
identical tokens. Coding improved **70.6 -> 76.3 tok/s**, but first diverged at
output token index **415**, so that pair is not an exact-output speed claim.
Combined MTP + n-gram also had a coding divergence, at index **95**.

The suffix policy uses measured timings to select verification batches. Those
choices changed between runs; first-divergence diagnosis is queued. The prior
coding request also changes editing's cache history. These paths have not
passed the full exact-token gate or a reverse-order performance repeat.

## Evidence and limits

- 12,304 ownership transitions passed ASan/UBSan byte, alias and lifetime checks.
- Real CUDA source-API transfer checks passed; Compute Sanitizer memcheck: **0 errors**.
- The new build with rotation disabled matched the old binary on the 8K gate.
- All eight plain/MTP task pairs matched output tokens, cache hits, lookups,
  RAM reads, proposed drafts and accepted drafts.
- This is a throughput/correctness experiment, not a model-quality benchmark.

[Full report, conditions and limitations](docs/Q8_EXCHANGE_ROTATION.md) ?
[Machine-readable results](bench/results/2026-10-03-q8-buffer-rotation/summary.json) ?
[Implementation](include/strata/core/exchange_storage.hpp) ?
[Upstream installation instructions](https://github.com/Niko1221/Strata#readme)

Benchmark engine source: `1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c`.
Subsequent commits add benchmark tools, results and documentation.
The original [license](LICENSE) is retained.
