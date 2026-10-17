# Qwen3.6 Q4 on one Tesla P4, 2026-10-17

One Tesla P4 (sm_61, 7,680 MiB reported VRAM), dual Xeon E5-2697 v3, 251 GiB RAM, Linux,
NVIDIA driver 580.178.04, CUDA 12.0.140, GCC 12.4. GPU 0 and its NUMA socket were used;
the other two P4s remained idle. `--pool-workers 14` was requested; the engine reported 15 CPU threads.

Model: Unsloth `Qwen3.6-35B-A3B-MTP-GGUF`, `UD-Q4_K_XL`, revision
`5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, 22,853,663,008 bytes. Model/binary hashes and
per-request timings and responses are in [results.json](results.json).

Source: 0.1.45, `477ac13cbe8e582c20484871ce459d20d82df09d`. All runs include the separate
CUDA 12.0 host half-bit debug-print compile fix. The automatic-recovery run additionally includes
this PR's memory patch. HIP was not compiled.

## Allocation failure and recovery

At `--max-context 8192 --prefill auto`, the default packed copies left 1.16 GiB free after
engine buffers. Startup failed allocating `E.stage[b]`: [failed log](default-oom.txt).
The manual `STRATA_Q8_PACKED=0` workaround loaded successfully.

The automatic fix starts with packed copies enabled and gives back 1.78 GiB for hybrid staging:
[working log](automatic-mtp2.txt). It then uses the same 16/256 expert slots per layer,
18.75 GiB of pinned host expert memory, and 1.10 GiB of staging as the manual workaround.
Peak sampled GPU use was 6,871 MiB; summed server/engine RSS was 41.17 GiB, including file-backed
model mappings. This does not establish a minimum RAM requirement.

## Throughput

Medians; three short requests (40 prompt tokens), two long requests (3,945 prompt tokens),
128 generated tokens each. One warmup and one arithmetic smoke request per engine start are excluded.
All timed prompts had zero reused tokens. Temperature and presence penalty were both zero.

| Configuration | MTP drafts | Short prompt / decode tok/s | 3,945-token prompt / decode tok/s |
| --- | ---: | ---: | ---: |
| Manual packed-copy disable | 0 | 93.6 / 31.2 | 262.5 / 21.8 |
| Manual packed-copy disable | 2 | 95.6 / 34.2 | 255.8 / 18.65 |
| Automatic memory recovery | 2 | 90.4 / 39.2 | 257.35 / 20.0 |

Rates are engine timings, excluding startup and client overhead. These are sequential smoke runs,
not an order-balanced performance study; the memory patch makes no speedup claim. MTP was exercised
(draft proposals/acceptances are in the logs), helped short decode and hurt decode after the long prompt
in this sample. It did not improve prefill. All seven automatic-recovery responses matched the manual
MTP-2 responses byte for byte. The arithmetic response was `42` in every arm. This is not a quality study.

## Reproduce

Build the CUDA engine using [OLDER_GPUS.md](../../../docs/OLDER_GPUS.md), selecting CUDA 12 and
sm_61. Export `STRATA_CHECKOUT`, `STRATA_ENGINE`, `QWEN36_GGUF`, and `BENCH_OUTPUT` as absolute paths.
Extract the tokenizer into `$BENCH_OUTPUT/data/packs/qwen36-q4`:

```sh
"$STRATA_CHECKOUT/.venv/bin/python" "$STRATA_CHECKOUT/tools/strata_tokenizer.py" \
  --gguf "$QWEN36_GGUF" --out "$BENCH_OUTPUT/data/packs/qwen36-q4"
BENCH_Q8_PACKED=auto BENCH_MTP=2 "$STRATA_CHECKOUT/.venv/bin/python" benchmark.py
```

`BENCH_Q8_PACKED=0 BENCH_MTP=0,2` reproduces the manual comparison. The harness binds NUMA node 0,
uses GPU 0 and localhost port 18445, runs the bounded suite and stops its server afterward.
No full 8K prompt, vision, multi-GPU, other backend, other quant, or long-duration test was run.
