# Experimental duplex resident exchanges

`STRATA_EXCHANGE_DUPLEX=1` changes how the **single-request serving path** exchanges
experts between the GPU cache and the resident RAM complement. It is off by
default. It does not select resident RAM, change a preset, rank different experts,
change quantization, or save transfer bytes.

Use it with an existing configuration that explicitly requests
`--resident-budget-gib N` (or `--resident-experts`). Export the environment variable
before starting that configuration. The startup log must say
`duplex resident exchanges enabled`; otherwise the original sequential path is
used. The normal arena remains available. In the Q2 comparison below it was faster
and held more expert data in RAM than the resident configuration.

The experiment requires CUDA, one GPU, fully pinned resident and exchange buffers,
and the ordinary fixed cache. Helper GPUs, batch slots, elastic VRAM, pageable
buffers and other backends retain sequential copies. A batch containing an expert
already duplicated in RAM also uses the original path. The non-serving `generate`
path is unchanged. There is no dependency on exchange-buffer rotation.

## Ordering and ownership

Previously, a batch copied every eviction D2H, waited on the host, then queued its
H2D refills. Duplex queues evictions on a separate stream. Each refill waits for
that slot's eviction event, so opposite-direction copies for different slots can
overlap without overwriting unread data.

Before publishing the evicted experts to CPU readers, the adapter still waits for
all evictions. The existing `adapt_ev` then guards refill completion and
`commit_exchanges()`. Incoming RAM bytes cannot be overwritten or reassigned before
their H2D copies finish. Submission errors and early teardown drain both streams;
the borrowed fill stream and all buffers must remain alive until then. Slots are
unique within a batch, and batches are not submitted concurrently.

The diagnostic's copy and payload counters are **cumulative submitted exchanges**.
Payload is D2H plus H2D; an exchange copies the same number of bytes in either arm.
A final submitted batch may still await ownership admission when request statistics
are printed. Its submitted count can therefore exceed the committed resident count.

## Validation

Base: upstream `6f32ec070f23ced9f50e704d854d775da52591ab`.
Code: `513395defe59fdf6abc74f7fbf0f0b50f57662a0`.

- `file_expert_source_test` and `duplex_exchange_test` passed on an RTX PRO 6000
  Blackwell Workstation Edition 96 GB, Ryzen 9 7950X, 128 GB RAM, Linux, CUDA 13.2,
  driver 595.91.07. The duplex fixture also passed on an RTX 4090 with CUDA 13.3.
- The fixture checks every eviction/refill byte and preserves incoming data for
  1, 127, 1,382,400 and 5,222,400-byte blobs; 1, 4, 16 and 96 slots; repeated AB/BA
  orders; invalid lists; close/reopen; and early close with both directions queued.
- Compute Sanitizer memcheck reported zero errors. The fixture passed ASan/UBSan
  with `ASAN_OPTIONS=detect_leaks=0:protect_shadow_gap=0`; the default ASan shadow
  gap prevented CUDA initialization on this machine. Leak detection was not run.
- Seven Q2 model comparisons passed exact output-token and recorded-work equality:
  upstream versus flag-unset in both arena and resident modes; arena/pageable
  fallback; resident MTP and target-only A/B; and cancellation followed by another
  request. Work checks include expert hits, offloads and MTP acceptance counts.

The native GSQ-RCO Q2_0 gate used 8,192 input + 512 output tokens for the main arms,
1,024 + 256 for pageable fallback, and cancellation at 128 tokens followed by a
512-token request. It used FP16 KV, 40,960 allocated context, 12,000 GPU expert
slots, no prompt reuse, and greedy decoding. Target-only uses the upstream serving
path with `--mtp-max-t 1`; it still loads the MTP weights. The cache cap deliberately
exercises exchanges on this 96 GB card. An EOS sentinel forces each output budget;
this is a scheduling test, not a quality evaluation.

### Isolated copy time

Eight alternating AB/BA pairs; medians on the RTX PRO 6000. Timing excludes data
initialization and byte verification. These are transfer times, not model speedups.

| Expert bytes | Slots | Sequential ms | Duplex ms | Reduction |
|---|---:|---:|---:|---:|
| 1,382,400 (Q2) | 4 | 0.416 | 0.316 | 24.1% |
| 1,382,400 (Q2) | 16 | 1.579 | 1.076 | 31.9% |
| 5,222,400 (Q8) | 4 | 1.483 | 1.083 | 27.0% |
| 5,222,400 (Q8) | 16 | 5.858 | 3.867 | 34.0% |

### Repeated Q2 requests

Two matched pairs per cell, in AB then BA order; 1,024 generated tokens per request.
Rates below are total tokens divided by total decode time across those two runs.
Total seconds include prompt processing and decode, excluding model startup.
All 16 pairs matched token IDs and recorded work. MTP uses one proposal (`--spec 2`);
suffix drafting is disabled. The remaining configuration is the gate's above.

| Input | Mode | Task | Sequential tok/s | Duplex tok/s | Change | Total seconds, off to on |
|---|---|---|---:|---:|---:|---:|
| 8K | Target-only | code | 101.5 | 103.1 | +1.58% | 15.07 to 14.91 |
| 8K | Target-only | editing | 112.0 | 113.1 | +0.95% | 14.14 to 14.05 |
| 8K | MTP | code | 146.1 | 150.1 | +2.78% | 11.99 to 11.80 |
| 8K | MTP | editing | 156.0 | 158.7 | +1.73% | 11.56 to 11.45 |
| 32K | Target-only | code | 103.0 | 102.3 | -0.67% | 30.17 to 30.24 |
| 32K | Target-only | editing | 108.2 | 106.9 | -1.21% | 29.71 to 29.83 |
| 32K | MTP | code | 147.0 | 150.7 | +2.53% | 27.20 to 27.02 |
| 32K | MTP | editing | 147.0 | 150.0 | +2.04% | 27.21 to 27.07 |

This supports a small MTP benefit in these requests, not a universal speedup.
Target-only 32K did not improve. Two pairs are a small sample, and prefill dominates
much of the total time. The full arena held 31.64 GiB of expert data in RAM versus
16.19 GiB here; the 8K/512 gate measured about 160 tok/s with the full arena, faster
than either resident arm. Resident RAM is a storage tradeoff, not a faster default.

### Q8 integration: correctness and memory-lock diagnostic

A separate validation branch combines this change with the opt-in Q8 PLE reader
and exchange-buffer rotation. The initial **12 Q8 comparisons** passed exact token
and recorded-work equality: eight in the first suite and four with a wider MTP policy.
This includes a real 131,072-token input, target-only decode, rotation disabled,
and a cancellation followed by another request. Together with the Q2 checks above,
there are 35 matching comparisons across 72 requests.

The Q8 fixture uses the Unsloth Q8_0 experts and PLE table with an existing
compatibility dense pack and a Q5_K head. It has 15,472 GPU expert slots (75.25 GiB),
a 44.28 GiB pinned RAM complement, FP16 KV, 139,264 allocated context, and 1,024-token
prefill chunks. Each normal request generates 1,024 tokens. The reader is enabled
with `STRATA_EXPERIMENTAL_Q8_PLE=1`; rotation is on unless the case says otherwise.

**The initial Q8 timing pairs are not a repeatable speed claim.** For transparency, these
are the completed repeated 32K-input measurements (off/on output tok/s):

| MTP policy | Task | First pair | Reverse-order pair |
|---|---|---:|---:|
| T2 | code | 63.80 / 108.70 | 62.61 / 60.93 |
| T2 | editing | 63.04 / 116.48 | 56.46 / 65.83 |
| T4 | code | 72.36 / 71.75 | 70.50 / 137.25 |
| T4 | editing | 73.16 / 65.44 | 67.54 / 67.69 |

T2 uses `--spec 2 --mtp-max-t 2` and the default probability threshold of zero.
T4 uses `--spec 8 --mtp-max-t 4 --spec-min-p 0.5`. These are separate policies,
not an isolated comparison of window widths. Suffix drafting is off in both.
The single 128K T2 pair measured 64.64 / 66.33 tok/s; it is subject to the same
timing limitation.

The logs show that `--ple-io ram` touched the Q8 lookup table but failed to lock
it. The SSH process's memory-lock limit was 16,764,923,904 bytes, below this table's
size. Later resource snapshots from a separate PR #876 screen show substantial
memory reclamation and swapping, including an inconsistent flag-disabled control.
This is a concrete measurement confound; it does not establish the cause of every
timing difference. The initial raw results remain available below.

#### Locked-table repeat: 32K coding, MTP T4

A separate diagnostic raised only its launcher's soft/hard memory-lock limit with
`sudo prlimit --pid <launcher-pid> --memlock=unlimited:unlimited`. It required
`PLE table locked in RAM` before each request; all four engines reported 50.66 GiB
locked. No engine code, model, placement, global limits or service settings changed.
Both arms used the same integration binary, the Q8 configuration above, and
`--spec 8 --mtp-max-t 4 --spec-min-p 0.5`. Suffix drafting was off.

Two pairs ran in AB then BA order, each with 32,768 input + 1,024 output tokens.
All output tokens and recorded work matched, including 698/858 accepted/offered
drafts and 6,587 offloads in every request.

| Pair | Sequential tok/s | Duplex tok/s | Decode gain | Total seconds, off to on |
|---|---:|---:|---:|---:|
| AB | 129.72 | 136.65 | +5.35% | 60.81 to 62.59 |
| BA | 128.70 | 136.93 | +6.39% | 60.86 to 60.41 |

Across both pairs, total output tokens divided by total decode time improved from
**129.21 to 136.79 tok/s (+5.87%)**. Mean decode time fell from 7.925 to 7.486 seconds.
Mean prefill was 52.911 versus 54.017 seconds, so mean total request time was
60.836 versus 61.503 seconds: **no consistent end-to-end gain**. These totals exclude
model startup. This supports a repeated decode improvement for this coding case,
not a claim about all tasks or 128K performance. There are only two pairs.

Locking the table did not eliminate all memory pressure. The first-token-to-end
system counters still recorded swap-ins and major faults; one run recorded
background reclamation. No direct reclamation or swap-outs occurred in those
decode intervals. These are system-wide counters, not per-engine attribution.
The diagnostic adds two equality checks, bringing the total to **37 comparisons
across 76 requests**. Its logs, launcher, resource snapshots and hashes are archived
separately from the original unlocked runs.

### Evidence

The [supporting validation archive](https://github.com/CC-David-CC/Strata-a5500/tree/test/duplex-q8-integration/bench/results/2026-10-05-duplex)
contains the exact plans, input/output token IDs, logs, work counters, binary and
source-archive hashes, component results, and the RTX 4090 fixture receipt. The
large raw data stays on that validation branch. This contribution contains the
scheduling change, its fixture, the small model runner, and this report.

## Reproduce

Build with the normal CUDA options and `-DSTRATA_BUILD_TESTS=ON`, then run:

```sh
cmake --build build --target strata file_expert_source_test duplex_exchange_test
ctest --test-dir build -R '^(file_expert_source_test|duplex_exchange_test)$' --output-on-failure
compute-sanitizer --tool memcheck --error-exitcode 71 build/duplex_exchange_test
build/duplex_exchange_test --bench
python tools/bench_duplex.py plan.json results-directory
```

The model runner takes explicit engine/model paths and cases in its plan JSON and
preserves raw input/output token IDs, arguments, binary hashes, timings and work
counters. Every arm uses a fresh engine. Keep the GPU and CPU free of competing
work; do not infer a model speedup from the copy fixture alone. Fully GPU-resident
experts have no exchanges to accelerate, and gains depend on exchange frequency,
cache warming, PCIe bandwidth and the rest of the request.
