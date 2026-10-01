# AMD HIP support and performance evidence

This opt-in Linux `gfx1100` backend supersedes the initial support in
[PR #94](https://github.com/Niko1221/Strata/pull/94). It retains HIP runtime and
wave32 integer-dot compatibility, native mmap layout validation, and MTP, then
adds HIP MMQ, optional calibrated dense hipBLASLt GEMM, native prefill batching,
and the host-memory / SSD paths used by the measured configuration. HIP blocking
expert uploads use one reusable pinned staging buffer, including prompt-cache
refills, to avoid repeated pageable-source registrations.

## Reproduce the configuration

Build instructions are in [AMD_HIP.md](AMD_HIP.md). Use the repository-pinned
llama.cpp dependency; do not silently substitute another revision. Build with
`STRATA_PREFILL_MMQ=ON` and use these runtime variables for the measured arm:

```sh
export STRATA_PREFILL_MMQ=1
export STRATA_HIPBLASLT_TUNING="$PWD/tools/hip/gfx1100-hipblaslt-100100.txt"
export STRATA_PREFILL_RING=96
export STRATA_IO_THREADS=32
```

The supplied table is calibrated for gfx1100 and hipBLASLt version 100100.
It is not a universal ROCm tuning table. The runtime guards architecture,
library version and actual shape/stride/workspace requirements, falling back
when a table entry is unavailable or incompatible. HIP MMQ is opt-in at runtime. Default CUDA selection is preserved.

Measured engine configuration: Orca Flash Next IQ3_XXS, native pack plus matching
GGUF/tokenizer/template, `--mmap-experts --resident-cpu-experts`, fixed ranked
`--expert-profile`, `--expert-cache auto`, `--prefill 8192`, `--spec 4`,
`--spec-min-p 0.5`, matching MTP runtime, `--max-context 262144`, `--kv int8`,
`--kv-resident 32768`, `--pool-workers 15`, `--adapt-every 0`, `--pcie-frac 0`,
and `--vram-reserve-mib 1024`. Keep PLE on SSD.

`--resident-cpu-experts` copies the complement of the static GPU cache to ordinary
RAM. It requires mmap and a fixed expert profile. The slots the prompt path may
borrow keep their experts in RAM too as far as the budget below allows (the rest
use the mapped fallback while borrowed and for their refill), and adaptive swaps
(`--adapt-every`) exchange experts between VRAM and the RAM copy without reading
the file. The copy is pageable; `--resident-experts` (CUDA, chosen by setup)
page-locks it and uses 4 GiB of headroom. Allocation needs sufficient available RAM;
on Linux this option requires readable standard cgroup-v2 mounts. For each
finite cgroup ancestor, the guard credits only `inactive_file` after subtracting
`file_dirty` and `file_writeback`, capped by current usage; it remains bounded by
the ancestor limit and host `MemAvailable`, with 8 GiB headroom. This accounts
for reclaimable clean file cache but cannot reserve memory against concurrent
system or process allocations.
The POSIX PLE path issues direct reads through a configurable worker pool.

Use a dedicated idle server, restart it between arms, and capture its engine log:

```sh
python3 tools/hip/bench_prefill.py \
  --model MODEL_NAME --url http://127.0.0.1:8080 \
  --engine-log /path/to/engine.log --label candidate --output candidate.json
```

The script uses the same synthetic source prompts and request order as the
reported measurements: a small warmup, then 140/280/140/280 functions, with one
follow-up after each fresh prompt. It enforces zero reused tokens for the fresh
prompts and records prefill, decode, wall time and stop reason. It requires the
unbuffered log to contain exactly one completed timing record per request. The
128-token output cap is intentional for throughput measurement, not task success.
Never use cancelled-request timing lines as throughput evidence.

## Final revision benchmark

Measured on 2026-09-29, source revision `9568e78da663e6b224ab96d57baf450717b36e73`.
HIP executable SHA-256: `705f5925a788bc227bad72abfb5466032e0879d752fea9afc3eb32051b35182b`.
The control and candidate below were both measured anew in this session; no
historical benchmark values are mixed into the table. The control binary SHA-256
is `4522d4937ca4a41ca294d31b60df8c2bc4df5b7a6caf65eaad10c036e08491f7`;
its source was an existing local runtime snapshot rather than a clean upstream commit.
Both arms use an RX 7900 XTX 24 GiB / gfx1100, Ryzen 9 7950X3D,
64 GiB installed RAM, Fedora-family Linux, ROCm 7.1 and a 272 W GPU cap.
Other model services are stopped for measurement and restored afterward.
Sampling: temperature 0, top-k 1, top-p 1, min-p 0, seed 42, reasoning disabled.

| Fresh request, execution order | Control prefill t/s | Candidate prefill t/s | Candidate output t/s | Candidate request wall time |
| --- | ---: | ---: | ---: | ---: |
| 4,210 tokens, first use | 240.0 | 447.5 | 55.5 | 11.729 s |
| 8,830 tokens, first use at this size | 484.8 | 873.7 | 55.7 | 12.420 s |
| 4,210 tokens, warmed | 457.2 | 901.1 | 56.7 | 6.937 s |
| 8,830 tokens, warmed | 478.9 | 966.5 | 59.2 | 11.314 s |

Each request generated exactly 128 tokens and finished at the intentional length
cap. All four fresh prompts had zero reused KV tokens. Fresh-prompt prefill was
1.80–2.02x the freshly measured existing AMD runtime; fresh-request wall time was
40–46% lower. This is a comparison with our existing HIP runtime, not unmodified
upstream, which does not provide this backend. The candidate also completed four
cached follow-ups in 2.95–3.26 seconds. Those follow-ups are not apples-to-apples
prefill comparisons: cache reuse differs with generated text and checkpoint
selection. Full sanitized measurements are in
[the fresh-run JSON](benchmarks/2026-09-29-gfx1100.json).

Before this revision, an intermediate package missing the HIP upload staging
buffer stalled on the 8,830-token request and was rejected. Restoring staging
allowed the complete sequence above to finish. That failed attempt is not
included in the throughput table. No watchdog limit was raised to obtain these
results.

Zero KV reuse is not equivalent to a cold filesystem cache. First-use speed
and warmed speed are reported separately. Individual observations do not
establish confidence intervals or a general rate at every context length.

## Correctness and quality limits

Both HIP and CUDA executables built from the measured source revision. CUDA was
compile-checked, not performance-tested by this run. The selected HIP CTest suite
passed **29/29** with the tuning table enabled, including expert-upload readback,
asynchronous handoff, QSA, MMQ, Lt GEMM, KV streaming and PLE reading. The excluded
`ple_parity` requires an external fixture; `platform_memory_test` requires a
larger locked-memory limit than the test account provides. Separately, three
real IQ3_XXS PLE matrix graph replays passed, and the POSIX direct-file test passed
queued reads, short EOF, wake, close/drain and reopen checks.

Development checks passed eight MMQ numerical comparisons, four actual Lt GEMM
comparisons, and native QSA/indexer/embedding parity including tail states,
chunk continuation and image overrides. Real quantized MMQ relative L2 error
was approximately 0.0026 against raw-FP32/dequantized-weight reference, reflecting
Q8 activation arithmetic; this is not bitwise numerical equivalence.

End-to-end coding quality is not established by these numerical checks or capped
throughput requests. Validate completed tasks with independent runtime tests; this
contribution makes no broad answer-quality or agentic-reliability claim.

The changes do not claim better model reasoning, verified full-context behavior,
end-to-end vision validation, Windows HIP, other AMD architectures, or mixed
AMD/NVIDIA execution. Existing CUDA multi-GPU code remains present but is not
validation of HIP multi-GPU support.

## Attribution and rejected experiments

The measurements above were taken before this backend was rebased onto engine 0.1.24. The PR's own batched
embedding gather and QSA indexer append (adapted from
[PR #108](https://github.com/Niko1221/Strata/pull/108), commit
`acd487233c0bbe2217a6881c5bb43f8a283b0de5`) were dropped in the rebase: 0.1.24 already does both on every
backend, bit-exact (C-2, C-4). #108's optional GDN parallel/split path is not included. Existing upstream MMQ orchestration is retained and enabled for
HIP with AMD architecture identification and the correct backend compilation.

Static 16K chunks, expanded FP16 expert tuning, and a 192-slot ring did not offer
a consistent end-to-end win in the evaluated workload. The table includes only
the selected 30 dense-shape rows. Microkernel speedups alone were not sufficient
to select a configuration. No increase in GPU power cap was used.

## RX 5500 XT 8 GB (RDNA1)

**Hardware: AMD Radeon RX 5500 XT, 8 GB VRAM, consumer GPU, gfx1012 / wave32.**
The machine's local SSH alias was `a5500`. It is **not an NVIDIA RTX A5500**.
These are RX 5500 XT measurements, not results for another card with a similar
name. The runtime identified `AMD Radeon RX 5500 XT` and 8,573,157,376 available
VRAM bytes in total (7.984 GiB after the device reservation).

Measured September 30, 2026 (America/New_York) on a Ryzen 5 3600, 56 GB installed
DDR4 at 1866 MT/s (about 54.8 GiB usable), Ubuntu 24.04, HIP 5.7.1 / clang 17,
hipBLAS 0.54 / rocBLAS 2.47 and a WD Blue SN550 NVMe SSD. Model:
**Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S**, text only. The PLE shard stays on NVMe;
the CPU experts use mmap-backed file cache and a bounded adaptive GPU cache.

### Revision and method

- Upstream base: `30ec18ec7094550fcc594fd948220d511d80464e` (Strata 0.1.30).
- Measured branch revision: `a94081db395398651e52cde5c6f458e3d0376928`, clean worktree.
- Executable SHA-256: `8b50864e1043ded44f2f948879df1886d1b59e7c1b2a6767aa270fa6d21d68c7`.
- Unmodified llama.cpp / ggml dependency: `3cf03257f219afbe7334045ff7c6a06ac68c627d`.
- **Every request: 8,192 input tokens. Allocated context: 9,216 tokens. Output
  limit: 512 tokens.** Coding and writing stopped naturally at the lengths below.
- Temperature 0, thinking disabled, Q8 KV, one request at a time; no prompt KV
  reuse, suffix drafts, conversation snapshots, vision, or profiling instrumentation.
- MTP-off requests ran first, then MTP-on in a fresh process, in the table order.
  The same frozen input IDs were used across modes. OS file cache was not cleared;
  this is not a controlled cold-storage test. Each table cell is one observation.
- Runtime settings: `--mmap-experts --expert-cache auto --prefill auto
  --pool-workers 5 --adapt-every 8 --adapt-swaps 64 --pcie-frac 0
  --vram-reserve-mib 768`. MTP uses `--spec 4 --spec-min-p 0.5`; off uses `--spec 2`
  solely for verifier allocation, with no drafter loaded.

Full measurements, output text, prompt hashes, startup times, first-token times,
engine settings and smoke-check outcomes are in
[the sanitized JSON](benchmarks/2026-09-30-gfx1012.json). Reproduce with
[`tools/hip/bench_rdna1.py`](../tools/hip/bench_rdna1.py) and the
[RX 5500 XT configuration example](../tools/hip/rx5500xt-iq3s.example.json).

### Results: MTP off and on

Effective output tok/s = actual output tokens / complete request wall time,
including prefill. Model startup is reported separately in the JSON. Output
token counts include the model's stop token when present.

| MTP | Task | Output tokens | Prefill tok/s | Prefill seconds | Output tok/s | Total seconds | Effective tok/s | Accepted/offered drafts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Off | Counting | 512 | 97.71 | 83.84 | 11.35 | 128.96 | 3.97 | - |
| Off | Coding | 125 | 100.22 | 81.74 | 10.45 | 93.71 | 1.33 | - |
| Off | Writing | 232 | 100.10 | 81.84 | 10.17 | 104.64 | 2.22 | - |
| On | Counting | 512 | 80.25 | 102.09 | 16.81 | 132.55 | 3.86 | 384/384 |
| On | Coding | 125 | 82.89 | 98.83 | 15.30 | 107.01 | 1.17 | 94/94 |
| On | Writing | 232 | 82.47 | 99.33 | 10.91 | 120.60 | 1.92 | 127/205 |

MTP improved generation speed by about **48% for counting, 46% for code, and 7%
for prose** in these runs. It did not reduce total time for these fresh 8K
requests: the extra prefill time outweighed the decode saving at these output
lengths. Automatic prefill selected 4,096-token chunks without MTP and 2,048
with MTP. The GPU expert cache was 2,783 MiB / 1,410 slots without MTP, versus
1,890 MiB / 957 slots with MTP; startup free VRAM was 714 and 700 MiB respectively.
Those free-VRAM figures are startup observations, not measured minimum headroom.

Counting and this merge function had 100% draft acceptance; the prose case
accepted 127/205 drafts (62%). Counting speed should not be presented as general
writing speed. These numbers do not measure cached follow-ups or longer outputs.

### Checks actually performed

- Branch build succeeded on the RX 5500 XT host.
- **16/16 focused GPU tests passed** in 19.34 seconds: `hip_prefill_gemm`,
  `hip_expert_cache_staging`, `hip_intrinsics`, `hip_handoff`,
  `hip_native_qsa_score`, `hip_prefill_native_batch`, `shared_expert_parity`,
  `gr_parity`, `gdn_parity`, `sampler_parity`, `quantize_act_parity`,
  `router_top10_parity`, `bf16_gemv_parity`, `qsa_parity`, `kv_q8_parity`,
  and `kv_stream_parity`.
- Real IQ3_S expert checks at layers **0, 8, 24, 40 and 47 passed**, with zero
  failures, using the CPU/float/GPU comparisons in `native_expert_parity`.
- All six 8K requests completed. Both counting outputs were consecutive
  integers starting at 1. The two code outputs were identical; both passed six
  merge cases covering empty/asymmetric inputs, duplicates, negative integers,
  and preservation of the input lists.
- Both writing outputs exceeded the requested 120-160 words (186 whitespace
  words each). Their timings are valid throughput measurements; this is an
  instruction-following miss, not a passed quality check.

The focused tests are not the entire project suite. There is no new CUDA build
or other-GPU validation in this contribution. The 9,216-token allocation is not
a maximum-context result. See the [code/configuration distinction](AMD_HIP.md#what-changed-and-what-is-configuration)
for the scope of the port and the unchanged llama.cpp dependency.
