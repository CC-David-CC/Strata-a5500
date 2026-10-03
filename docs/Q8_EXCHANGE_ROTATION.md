# Q8 expert exchange buffer experiment

Branch: `perf/q8-exchange-buffer-rotation`.
Target: llm-60, NVIDIA RTX PRO 6000 Blackwell Workstation Edition **96 GB**,
Ryzen 9 7950X, 128 GB installed RAM. Full Unsloth Q8_0, FP16 KV.

**Status: model comparisons completed. Plain decoding and MTP improved in two
paired runs with exact outputs and matching work counters.** N-gram and combined
coding outputs diverged; those paths need first-divergence diagnosis before
accepting an exact-output claim. All fixture and memory checks passed.

## The change

The resident RAM mode keeps the experts absent from the GPU cache. Promoting
expert A frees its RAM slot; evicting expert B first copies B from VRAM into a
temporary host buffer. The original commit copies B again into A's former RAM
slot. This experiment adopts B's temporary buffer as its resident storage and
recycles A's former RAM slot as the next eviction buffer.

Enable with `STRATA_EXCHANGE_ROTATE=1`. Unset or `0` retains the original copy
path. The RAM and exchange allocations keep their original lifetime owners;
expert ownership moves by atomic slot IDs into an immutable table of host and
CUDA device addresses. Background router lookahead reads those IDs safely. The model
weights, resident expert count, cache replacement policy and quantization stay
the same. The GPU-to-host eviction transfer is still required.

This first implementation accepts **equal-size expert blocks with the entire
resident complement pinned and mapped**. Partial pinning, pageable memory and
mixed block sizes explicitly fall back to the copy path. The maximum exchange
capacity must be reserved before rotation is initialized; later growth is
rejected because the original exchange allocation may contain live experts.
Existing serve/generate callers reserve their maximum once before inference.

## Correctness contract

- The D2H eviction finishes before the evicted expert is published for readers.
- Existing CPU completion and H2D completion waits precede ownership commit.
- Every resident expert and spare has exclusive ownership of one buffer.
- CUDA aliases move with host pointers. No alias is reconstructed from a stale
  offset into the original RAM allocation.
- Staged overrides, file fallback, `blob`, `copy_blob`, prefetch, pin checks and
  device address lookups resolve the same committed storage.
- No transfer wait, residency publication order, stream lifetime or kernel
  arithmetic changes. Invalid commit metadata fails closed.

The counter `host memcpy bytes avoided` counts payload bytes. Avoiding an N-byte
copy removes an N-byte CPU read and N-byte CPU write at the software level; it
does not itself establish measured DRAM traffic or an end-to-end speedup.

## Validation and measurement

`exchange_storage_test` exercises 12,304 ownership transitions, odd sizes,
unaligned host addresses, actual Q8-sized blocks, distinct device aliases,
repeated reuse, invalid commits, guards and exact bytes. Run under ASan/UBSan.

`file_expert_source_test --rotation-gpu` exercises the real source API and CUDA
transfers with copy, rotation, and pageable fallback: staged reads, promotion,
eviction, host copies, CUDA alias reads, disk fallback, growth rejection,
close/reopen and byte equality. Run under Compute Sanitizer memcheck.

`tools/run_q8_exchange_rotation_fleet.py` joins the private fleet GPU queue:

1. Component tests, source API tests and GPU memory checks.
2. Old binary versus new binary with rotation disabled, 8K input/256 output.
3. Rotation off/on for serial, MTP, n-gram and combined modes, **64K input +
   1,024 output**, 73,728 allocation, FP16 KV, coding then editing requests with fresh prompt state. The adaptive expert cache
   persists between those two requests, identically in the comparison arms.
4. Fixed 16,400 GPU slots for serial/n-gram and 16,192 for MTP/combined; automatic
   CPU/PCIe split, 96 adaptive swaps, completion waits enabled, ESP disabled.
5. Exact token IDs, first divergence, resource telemetry, copy counters and
   unprofiled decode speed. Reverse-order repeat for any exact-output candidate
   with a first-run task improvement of at least 3%.

A semantic mismatch remains a failed gate for that path, even if throughput
increases. The storage fixtures and model comparison answer different questions;
both are required before accepting the change. Public serving is unaffected.

## Initial validation, 2026-10-03

Engine source `1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c` built successfully on
llm-60 (CUDA SM120 Release). Binary SHA-256:
`d14ed6b69a1814ce4b5c08932a47d6921a55fa0aa8dea50427ccf0782d1ad997`.

The standalone ownership fixture passed all **12,304 exchanges** under
AddressSanitizer and UndefinedBehaviorSanitizer, including concurrent metadata
readers, exact resident bytes, alias pairs, buffer reuse and malformed commits.
The CPU fixture and compiler overlapped the separate retrieval quality
check, with bounded memory/CPU use; that check's timing is not a controlled speed
comparison. No GPU benchmark overlapped the compilation.

Evidence: `~/fleet-downloads/rtxpro-exchange-cpu-check-20261003` and
`~/fleet-downloads/rtxpro-exchange-build-ahead-20261003`.

The real CUDA source-API fixture subsequently passed all 64 exchanges in each
of three configurations: pinned copy, pinned rotation, and requested rotation
with pageable fallback. Exact bytes, CUDA alias reads, staged transfers, disk
fallback and close/reopen checks passed. Compute Sanitizer memcheck reported
**0 errors**. These source-API fixtures use 1,382,400-byte blocks, so their commit
timing is not a full-model Q8 speed measurement. The CPU fixture separately
includes Q8's 5,222,400-byte expert blocks.

The old `080891d` binary and the new `1a50d91` binary with rotation disabled
produced identical 256-token outputs at 8K input. The remaining comparison
enables rotation at 64K input using the model's native RoPE settings, without
YaRN extension. Evidence:
`~/fleet-downloads/rtxpro-q8-exchange-rotation-20261003-r2`.

## Model results, 2026-10-03

Same hardware, full Unsloth Q8_0 and FP16 KV, native RoPE, **65,536 input +
1,024 output tokens**, 73,728 allocated context. Each pair differs only by the
rotation setting. Controls and candidates run in opposite orders in the repeat.
All requests reached the output budget; startup is excluded from request time.

| Mode/task | Copy, first tok/s | Rotation, first | Copy, repeat | Rotation, repeat | Paired decode gains |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain coding | 70.07 | 75.39 | 70.00 | 75.64 | +7.6%, +8.1% |
| Plain editing | 57.51 | 61.93 | 57.43 | 62.06 | +7.7%, +8.1% |
| MTP coding | 112.62 | 131.87 | 107.49 | 132.53 | +17.1%, +23.3% |
| MTP editing | 88.81 | 107.64 | 86.73 | 107.56 | +21.2%, +24.0% |

These eight task pairs matched every output token. Cache hit counts, lookups,
RAM blob reads, proposed drafts and accepted drafts also match within each pair.
Two pairs are evidence for these workloads, not a confidence interval or a
universal speed claim. The MTP copy control varied between runs; both results
are reported.

The plain request pair avoids 5,354 copies / **27.96 GB** of memcpy payload;
MTP avoids 7,247 copies / **37.85 GB**. These are cumulative across coding and
editing, not per token. Rotation keeps the GPU eviction and promotion transfers.
It removes the subsequent RAM-to-RAM copy. It does not duplicate all experts in
RAM, change weight values, or skip synchronization.

### Suffix paths: results with unresolved coding divergence

| Mode/task | Copy tok/s | Rotation tok/s | First differing output index |
| --- | ---: | ---: | ---: |
| N-gram coding | 70.64 | 76.31 | 415 |
| N-gram editing | 88.42 | 108.14 | None |
| MTP + n-gram coding | 107.91 | 131.06 | 95 |
| MTP + n-gram editing | 88.30 | 106.45 | None |

These paths did **not** pass the full exact-token gate and were not promoted
for the reverse-order performance repeat. N-gram coding first changes the
docstring word `expiry` to `deadline`; later differences are not counted as
independent events. Window counts and draft choices differ. Timing-driven draft
policy decisions are a hypothesis for the divergence, not a proven explanation.
The preceding coding requests also leave different adaptive cache histories
for editing, so the editing gains need independent confirmation.

`tools/trace_q8_exchange_policy.py` records window position/width and ordered
expert IDs with the frozen engine, including a copy-versus-copy repeat. Its
instrumented rates will not be used as throughput claims. The existing serving
routing dump stores placeholder weights; it cannot establish route-weight,
logit-margin or committed-state equality.

Machine-readable [result summary](../bench/results/2026-10-03-q8-buffer-rotation/summary.json)
includes exact source/binary hashes, per-request prefill and decode timings,
effective throughput, token-stream digests, counters and comparison results.
