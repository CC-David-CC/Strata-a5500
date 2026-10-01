# Strata: experimental Tesla P4 support

This is David's **`strata-p4` branch** of a small hardware-support fork of
**[Niko1221/Strata](https://github.com/Niko1221/Strata)**. Credit for Strata,
its expert cache, model support, and MTP implementation belongs to upstream.
This branch adds experimental CUDA support for the **NVIDIA Tesla P4, 8 GB,
Pascal sm_61**. It is separate from the
[RX 5500 XT branch](https://github.com/CC-David-CC/Strata-a5500/tree/feat/gfx1012-hip).
The fork's `main` is not changed by this work. This is not an upstream release.

## What changed

- Explicit opt-in build/runtime support for sm_61 with CUDA 12.x.
- A bounded FP32 cuBLAS prefill path for Pascal, preserving BF16's range.
- Numerical tests, launch configurations, and measurements on a real P4.

These results are **our modified native Strata engine**, not a separate stock
Strata result that beat the port. The stock runtime rejects the P4. Existing
DP4A kernels, adaptive expert caching, and MTP are upstream features reused here.
This branch also includes the earlier AMD contribution on which it was based.

## Tested hardware and model

- **One Tesla P4 8 GB** in a Dell PowerEdge R730xd; ECC enabled, 7,680 MiB exposed.
- Two Xeon E5-2697 v3 CPUs; **256 GiB installed RAM** (about 251 GiB usable).
- GPU 0 and NUMA node 0; 13 CPU expert workers. The other two P4s were idle.
- **Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S**, text only, Q8 KV.
- 46.84 GiB resident CPU expert arena; model n-gram table mapped on the host.
- CUDA 12.0 / GCC 12. No power-limit, clock, or ECC changes.

## Measured speed

Each request used **8,192 input tokens**, at most **512 output tokens**, and
**9,216 allocated context**. Coding and writing stopped naturally. One observation
per task/configuration; no prompt KV reuse. Startup time is excluded.

| Task | Configuration | Output tokens | Prefill tok/s | Output tok/s | Total seconds | Effective tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Counting | Strata, MTP off | 512 | 128.02 | 13.76 | 101.20 | 5.06 |
| Coding | Strata, MTP off | 125 | 127.55 | 13.17 | 73.72 | 1.70 |
| Writing | Strata, MTP off | 233 | 127.30 | 13.01 | 82.27 | 2.83 |
| Counting | Strata, MTP on, baseline | 512 | 87.93 | 21.26 | 117.25 | 4.37 |
| Coding | Strata, MTP on, baseline | 125 | 87.99 | 18.85 | 99.74 | 1.25 |
| Writing | Strata, MTP on, baseline | 232 | 87.85 | 14.31 | 109.48 | 2.12 |
| Counting | Strata, MTP on, tuned cache | 512 | 88.08 | **22.09** | 116.19 | 4.41 |
| Coding | Strata, MTP on, tuned cache | 125 | 88.24 | **20.24** | 99.02 | 1.26 |
| Writing | Strata, MTP on, tuned cache | 233 | 88.10 | **14.94** | 108.59 | 2.15 |
| Counting | Stock llama.cpp b11118 control | 512 | 84.64 | 7.87 | 161.73 | 3.17 |

Effective tok/s = output tokens / complete request wall time. **MTP improves
generation speed but makes these fresh 8K requests slower overall**, because
its prefill is slower. Counting is particularly favorable to speculation;
22 tok/s should not be described as typical prose speed. The llama.cpp control
used identical counting input token IDs and weights, with dense work on GPU
and all 48 layers' experts on CPU; this compares complete configurations.

The tuned MTP cache used 1,511 MiB. Minimum free VRAM sampled once per second
was **261 MiB**. Longer contexts, simultaneous requests, and three-P4 scaling
have not been validated by this port.

## Validation and reproduction

Nine focused CUDA tests, nine prefill numerical cases, and real IQ3_S expert
checks at five layers passed. Counting was consecutive; each generated merge
function passed six functional cases. Writing exceeded the requested word
limit, and one baseline sample contained a factual error. These are throughput
and correctness smoke tests, **not intelligence or coding benchmark scores**.

- [Build instructions, methodology, and full timings](docs/DETAILS.md#experimental-tesla-p4-pascal-sm_61)
- [Raw results, source revision, executable hash, and outputs](docs/benchmarks/2026-09-30-sm61.json)
- [Baseline configuration](tools/cuda/p4-iq3s.example.json)
- [Tuned MTP configuration](tools/cuda/p4-iq3s-mtp-tuned.example.json)

Replace the example paths with your own. Use the documented manual CUDA 12.x
build; the generic upstream installer is not the validated P4 installation path.
This remains experimental support. Upstream documentation and licensing remain
in the repository; see [the original project](https://github.com/Niko1221/Strata).
