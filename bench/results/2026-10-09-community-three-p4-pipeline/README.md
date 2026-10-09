# 3x Tesla P4: 23.0 -> 28.6 tok/s with exact pipeline output

Measured 2026-10-09 by CC-David-CC. On 4,096-token prose, median decode rose from
**23.000485 to 28.606868 tok/s (+24.375063%)** with two-window pipelining.
All 32 requests matched their serial token reference.

The speedup comes from [#1656](https://github.com/Niko1221/Strata/pull/1656).
Both measured arms include the minimal commit guard in
[#1674](https://github.com/Niko1221/Strata/pull/1674), extracted from the earlier
three-P4 work in [#1154](https://github.com/Niko1221/Strata/pull/1154)
([original guard](https://github.com/Niko1221/Strata/commit/dd7045d4b6a5143b73477b56c21b58bf3d6fa140)).
This report contains measurements and reproduction files only.

## Results

Three measured repetitions per arm, same corrected binary and expert placement.
The output cap was 256 tokens; code ended naturally at 125 tokens.

| Workload | Prompt tokens | Generated tokens | Serial tok/s | Pipeline tok/s | Gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prose | 4,096 | 256 | 23.000485 | 28.606868 | +24.375063% |
| Prose | 512 | 256 | 23.377928 | 29.103477 | +24.491258% |
| Code | 512 | 125 | 25.461878 | 43.067806 | +69.146224% |
| Count | 512 | 256 | 26.400734 | 46.913942 | +77.699384% |

4K prose median whole-request latency was **33.755897 -> 31.510369 seconds**,
a **6.652252%** reduction. Prompt processing accounts for roughly 22.6 seconds
of that request and is separate from decode throughput.

| Workload / mode | Decode tok/s median [min, max] | Prompt tok/s median [min, max] | TTFT s median [min, max] | Request s median [min, max] |
| --- | --- | --- | --- | --- |
| 4096:prose / serial | 23.000485 [22.972827, 23.007307] | 181.020272 [180.823684, 181.406699] | 22.692373 [22.646491, 22.718453] | 33.755897 [33.725810, 33.785710] |
| 4096:prose / pipeline | 28.606868 [28.555812, 28.618701] | 181.692365 [181.430805, 181.827060] | 22.607528 [22.591687, 22.641144] | 31.510369 [31.475004, 31.527005] |
| 512:prose / serial | 23.377928 [23.374940, 23.458476] | 96.121353 [96.119549, 96.180940] | 5.386180 [5.383820, 5.386711] | 16.276122 [16.240525, 16.278369] |
| 512:prose / pipeline | 29.103477 [29.071748, 29.117048] | 96.112331 [95.665172, 96.170101] | 5.386492 [5.383687, 5.414537] | 14.121002 [14.120118, 14.158734] |
| 512:code / serial | 25.461878 [25.415803, 26.174722] | 94.869277 [94.846430, 94.920282] | 5.456266 [5.454276, 5.457760] | 10.304331 [10.174642, 10.316185] |
| 512:code / pipeline | 43.067806 [43.036667, 43.267567] | 94.827107 [94.292713, 94.865761] | 5.458766 [5.456955, 5.491578] | 8.302593 [8.287056, 8.335273] |
| 512:count / serial | 26.400734 [26.364844, 26.409722] | 96.693169 [96.607419, 96.704127] | 5.354930 [5.354434, 5.361491] | 14.997424 [14.989655, 15.005422] |
| 512:count / pipeline | 46.913942 [46.540377, 47.175896] | 96.229749 [96.115940, 96.560048] | 5.382042 [5.361631, 5.387979] | 10.760163 [10.755231, 10.822083] |

All per-run floating-point values are in [results.json](results.json), with
medians, ranges, and the three values per metric in [summary.json](summary.json).
Six decimal places above preserve calculation results from the engine's reported
timings; they do not imply that level of measurement precision.

## Hardware and software

- Dell PowerEdge R730xd; GPUs 0, 1, 2: Tesla P4, 7,680 MiB each, Pascal `sm_61`.
  PCIe widths x16/x8/x16; 75 W power limits. Active link generation was not recorded.
- Two Xeon E5-2697 v3 CPUs (28 physical cores total), AVX2, no AVX-512;
  251.773 GiB OS-visible RAM. Storage type was not recorded.
- Ubuntu 24.04, Linux `7.0.0-31-generic`; NVIDIA driver `580.178.04`;
  CUDA compiler `12.0.140`, GCC 12, CMake Release.
- No competing GPU inference jobs. GPUs were returned to idle after testing.
- Engine `0.1.41`; measured source is #1656 head `06abdfa50aef6e5068869bc7552fafa5e99b7b9d`
  plus exactly the `verify.cpp` guard published as
  [this #1674 commit](https://github.com/CC-David-CC/Strata-a5500/commit/9e67094a981225d4dc581a0229caf8525878e97a).
  Both PRs are based on `fb58e0dbc8399662c0e47c76578c6e878b14f6cf`. The measured worktree was uncommitted;
  its diff SHA-256 and executable SHA-256 are retained in `results.json`.
- CUDA Release build passed with `STRATA_ENABLE_CUDA=ON`,
  `STRATA_EXPERIMENTAL_SM60=ON`, `CMAKE_CUDA_ARCHITECTURES=61`,
  `STRATA_BUILD_TESTS=ON`. Dependency revision is recorded in `assets.json`.

## Model and settings

Qwen3.8-Flash-Next-GSQ-RCO **IQ3_XXS**, from the installed ISTA pack:

- `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf`: 47,039,860,096 bytes.
- `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf`: 28,800,138,432 bytes.

The exact model repository revision and full GGUF hashes were not recorded.
[assets.json](assets.json) records hashes for the tokenizer, expert profile,
MTP dense weights, MTP experts, draft vocabulary, and pack metadata.

Full launch arguments and environment are in [config.json](config.json) and the
first line of [engine.log](engine.log). Local directories have been replaced
with `/path/to/...` placeholders; measured settings and numerical data are unchanged.

- Layer split `19,37`; int8 KV; context limit 40,960; resident KV 32,768;
  RoPE scaling off; PLE in RAM; stage weights trimmed.
- Expert cache and prefill `auto`; 7,699 GPU expert slots / 12,807 MiB reported
  at startup, a 40,925 MiB shared host expert arena, 1,024 MiB VRAM reserve per card.
  These are allocation/startup values, not sampled peak memory measurements.
- 27 physical CPU workers, NUMA interleave across both sockets; 64 GiB memlock allowance.
- MTP `--spec 2 --spec-min-p 0.5`; suffix drafting off; greedy temperature 0;
  reasoning disabled in the chat template; vision disabled.
- Static placement: `--pcie-frac 0 --adapt-every 0`, `STRATA_IQ_MT_MIN=1`.
  `STRATA_ATTN_MERGE_V2=1`, `STRATA_SHARED_ARENA_REUSE=1`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Prompt and conversation caches disabled. No calibration or experimental
  speed-projection pass was run for this comparison.

## Method and reproduction

One engine process was launched with `--pipeline-windows 2`. The existing debug
switch selected `pw=0` (serial) or `pw=2` (pipeline) before each request, keeping
the binary, split, allocations, and expert placement identical. The first code
serial/pipeline pair was warmup and excluded from speed statistics. Each workload
then had three measured pairs, reversing order for the middle pair. Six control
requests forced rollback or disabled guesses. The recorded plan includes the
exact order of all 32 requests.

Every prompt was fully processed with **zero reused tokens**. Model loading is
excluded. Decode tok/s is generated tokens / engine `decode_ms`; prompt tok/s is
fresh prompt tokens / engine `prompt_ms`. TTFT is measured in the local Python
driver from request start until its first token ID, and whole-request time until
completion. Whole-request time includes small driver postprocessing overhead.

[results.json](results.json) contains the exact input token IDs, output token IDs,
decoded output, plan, engine timing fields, draft acceptance, and equality results.
Prompt tasks are merging sorted Python lists, Linux performance-diagnosis prose,
and counting consecutive integers, padded with maintenance notes to 512 or 4,096
tokens. Exact token arrays avoid tokenizer/template regeneration differences.

[run.py](run.py) is the measurement driver adapted to accept paths and reuse those
published prompt arrays. The request loop and timing boundaries are retained.
It additionally compares rerun output with the published serial reference.
Prepare a checkout of #1656 and cherry-pick the guard from #1674, then build:

```bash
git fetch https://github.com/Niko1221/Strata.git refs/pull/1656/head
git checkout --detach 06abdfa50aef6e5068869bc7552fafa5e99b7b9d
git fetch https://github.com/CC-David-CC/Strata-a5500.git fix/pipeline-one-token-commit
git cherry-pick 9e67094a981225d4dc581a0229caf8525878e97a
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=61 -DSTRATA_ENABLE_CUDA=ON \
  -DSTRATA_EXPERIMENTAL_SM60=ON -DSTRATA_BUILD_TESTS=ON \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-12 \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++-12 -DCMAKE_C_COMPILER=/usr/bin/gcc-12
cmake --build build --target strata -j12
```

Use a separate checkout for the build and keep this report directory available.
Copy `config.json` to `config.local.json` and replace every `/path/to/...` value
with your paths. Use a unique shared-arena path. Install the checkout's Python
dependencies and use its Python environment. With a 64 GiB memlock allowance,
choose 27 physical CPU IDs across both sockets in `CPU_IDS` and run:

```bash
numactl --cpunodebind=0,1 --interleave=all taskset -c "$CPU_IDS" \
  python run.py --config config.local.json --out /path/to/new-run
python verify_results.py
```

The original build reused a local dependency checkout at
`3cf03257f219afbe7334045ff7c6a06ac68c627d` through
`FETCHCONTENT_SOURCE_DIR_STRATA_LLAMACPP`. Preserve that revision when reproducing.
Do not reuse a live serving process or overwrite these published result files.

## Correctness and limits

All **32 fixed-build requests** matched their serial reference: two warmups,
24 measured requests, and six controls. The 512-token cases also matched the
original unmodified serial output. Forced rollback exercised 62 / 157 / 128
rollbacks for code / prose / counting. There were no crashes or OOMs.

The initial uncorrected pipeline failed exact prose token equality. Repeated
512-token prose diverged at zero-based output index 95 in all three measured
repetitions. The exact parent also reproduced the issue with two stages, so it
predates #1656. The global `STRATA_ONE_TOKEN_COMMIT=0` diagnostic restored equality;
#1674 confines the guard to pipelined verifiers. [correctness.json](correctness.json)
retains those diagnostic token streams and original serial references. Diagnostic
arms are separate from this report's fixed-build speed comparison.

Equality on these inputs is not a broad answer-quality claim. This run did not
test Q8, sampled decoding, images, suffix drafting, dynamic expert adaptation,
concurrent serving, contexts above 4K, HIP, or SYCL. No inference-state byte comparison
or task-specific functional test was run for this 32-request suite. The public
replay adaptation was syntax-checked; the recorded GPU measurements used its
original host-specific driver.
