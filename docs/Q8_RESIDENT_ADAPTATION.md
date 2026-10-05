# Q8 resident adaptation: 24.5–28.2% faster decode from rotation

**Experimental integration draft for [Niko1221/Strata](https://github.com/Niko1221/Strata).**
Measured on **llm-60: NVIDIA RTX PRO 6000 Blackwell Workstation Edition, 96 GB VRAM,
Ryzen 9 7950X, 128 GB RAM**. The model is **Unsloth Qwen3.8-Flash-Next Q8_0**:
Q8_0 experts and PLE lookup table, compatibility BF16 small projections and a
Q5_K output head. KV is FP16. This result is for Q8, not the upstream README's
IQ3_S/RTX 5070 example.

## The headline result

With **async adaptation + duplex transfers + per-layer admission enabled**,
changing only `STRATA_EXCHANGE_ROTATE=0` to `1` produced:

| Repetition | Rotation off, output tok/s | Rotation on, output tok/s | Decode gain | Decode seconds, off → on | Full request seconds, off → on |
| --- | ---: | ---: | ---: | ---: | ---: |
| A → B | 113.224 | 140.979 | **+24.513%** | 9.0440 → 7.2635 | 61.980 → 60.192 |
| B → A | 111.568 | 142.975 | **+28.151%** | 9.1783 → 7.1621 | 62.108 → 60.124 |

Both pairs generated **the same 1,024 token IDs**, with the same recorded work:
697/872 MTP drafts accepted/offered, 555,439/570,047 expert cache hits/lookups,
18,559 RAM blobs, 6,913 offloaded operations, zero expert file reads,
82 adaptation rounds and 3,449 exchanged experts. There was no first differing
output token. This is observed equality for these requests, not a proof that
every asynchronous execution has identical intermediate states.

The two rotation pairs were part of a six-case reversed-order run, using the
same binary and a fresh engine for each case. The measured prompt was a
32,768-token coding request, with exactly 1,024 output tokens; one request at a
time; greedy decoding; MTP T4; FP16 KV; no suffix/n-gram drafts; no prompt reuse.
`--max-context 139264` was the allocated capacity, **not the input length**.
Startup/model loading is excluded from request timing. Final ownership drains
are included in decode time.

The full request improved by **2.88% and 3.19%**, because reading the prompt
took about 52.9 seconds. The 24.5–28.2% headline is a **decode-throughput gain
over rotation off in this combined stack**. The upstream comparison below is
a separate measurement.

## Comparison with upstream Strata

| Pair | Main + Q8 reader, output tok/s | Full stack, output tok/s | Decode gain | Full request seconds, baseline → stack | Token/work equality |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 106.058 | 141.830 | **+33.73%** | 62.581 → 60.152 | Different; first token index 906 |
| 2 | 106.775 | 141.671 | **+32.68%** | 62.604 → 60.153 | Different; first token index 906 |

These baseline-versus-stack runs compare complete configurations. Any token/work differences above prevent treating that gain as the same-work rotation ablation.

Unmodified upstream `6f32ec0` does not accept this Q8 PLE tensor. The runnable
baseline is **that exact main plus only the Q8 PLE reader, commit `18d3da4`**
([PR #865](https://github.com/Niko1221/Strata/pull/865)). It has none of async
adaptation, rotation, duplex or per-layer admission. Both engines use the same
model, GPU/RAM budgets, physically locked PLE, prompt, stopping policy and
build configuration. This isolates the combined adaptation changes without
claiming stock main already supports the full Q8 configuration.

## Actual 128K input follow-up

The same `07ff95b` code and verified binary completed **131,072 input tokens +
1,024 output tokens** with all four adaptation features active, MTP T4 and
FP16 KV. This was actual input length; no prompt tokens were reused.

| Measurement | Result |
| --- | ---: |
| Decode throughput | **141.115 tok/s** |
| Prefill | 213.195 s |
| Generation | 7.2565 s |
| Request wall time | 220.487 s |
| Effective output / request wall time | 4.644 tok/s |
| Model startup, excluded above | 122.344 s |

The request finished at its requested length without a reported inference or
allocation error. This is one longer-input result, not a new rotation or
upstream speedup comparison at 128K.

A separate 4K editing request was cancelled after 128 delivered tokens (the
engine reported 135 generated positions as in-flight work drained). The next
request completed all 512 tokens at 134.021 tok/s. A fresh engine completed the
same prompt at 126.972 tok/s, but outputs first differed at token index **43**
and measured work differed. This establishes operational recovery, **not exact
state equivalence or a speedup**. Persistent cache/adaptation history and
CPU/GPU arithmetic placement are possible explanations; this test does not
exclude cancellation-state contamination. A placement-controlled comparison
or state-digest trace remains necessary.

**[Raw follow-up evidence, token IDs, logs and hash manifest](https://github.com/CC-David-CC/Strata-a5500/tree/f5064b483cc3fd7ed89760255cb4ddbf1a8643ae/bench/results/2026-10-05-q8-resident-adaptation/followup-128k)**.
The complete three-case job exited zero in 628.8 seconds.

## Why rotation helps here

The existing resident-RAM path uploads an incoming expert and downloads the
evicted expert to a staging buffer, then copies the staging bytes into the
incoming expert's old RAM allocation. Rotation changes ownership instead:
the staging allocation becomes resident and the old resident allocation
becomes the next staging buffer. Host pointers and mapped device aliases move
together; the allocations remain alive until the source closes.

Each measured Q8 expert occupies **5,222,400 bytes** (4.98 MiB). Across 3,449
exchanges, rotation removes **18,012,057,600 bytes of host `memcpy` payload**
per request. Counting each logical read and write would be twice that number;
neither number is a hardware measurement of DRAM transactions. Recorded
D2H+H2D payload remains **36,024,115,200 bytes** in both arms. This result
does **not** claim that rotation eliminates PCIe transfers.

Resident placement in this test:

| Component | Placement |
| --- | --- |
| 15,472 cached experts | 75.25 GiB in GPU cache |
| Remaining 9,104 experts | 44.28 GiB in pinned, mapped system RAM; 56 GiB budget |
| Q8 PLE lookup table | 50.66 GiB, physically locked in system RAM |
| Dense path, FP16 KV, workspace | Remaining GPU capacity |

All 24,576 experts remain available. The Q8 GGUF download is six shards,
188,225,033,248 bytes; no expert pruning is introduced by this branch.

## How we reached this result

These are separate experiments, not percentages to multiply. Most schedule
changes alter CPU/GPU placement timing and can change floating-point outcomes,
output tokens and speculative work. Those comparisons are marked explicitly.

| Stage | Observed output tok/s | Interpretation |
| --- | --- | --- |
| Standalone async #876, main + Q8 reader | 106.06–107.40 → 112.24–115.26 | +5.83–7.32%; output/work differed at token index 625 |
| Rotation + duplex, blocking adaptation | 137.57–137.68 | Strong simpler alternative; keep as an independent option |
| Async + rotation, no duplex | 136.76–137.18 | No gain over the blocking rotation+duplex configuration |
| First async + rotation + duplex integration | 127.50–128.66 | Regression: whole-batch readiness waits serialized progress |
| Add per-layer admission to that integration | 127.67–129.25 → 140.97–141.21 | +9.25–10.42%; output/work differed at token index 218 |
| Async + duplex, no rotation; add per-layer admission | 108.24–108.51 → 111.57–113.22 | +2.82–4.61%; output/work differed |
| Same async + duplex + per-layer stack; add rotation | **111.57–113.22 → 140.98–142.97** | **+24.51–28.15%; identical output IDs and recorded work in both pairs** |

Earlier duplex-only work recorded repeatable **+5.35%/+6.39% decode** gains
with physically locked PLE and identical tokens/work, but no consistent
full-request gain. Those results, copy fixtures and early unlocked-PLE runs
are retained in the [duplex report and archive](https://github.com/CC-David-CC/Strata-a5500/tree/test/duplex-q8-integration/bench/results/2026-10-05-duplex).
Unlocked-PLE results varied with paging/reclaim and are not used for this headline.

## Dependencies, attribution and review order

Strata is [Niko1221's project](https://github.com/Niko1221/Strata). This branch
is a fork experiment built on current main `6f32ec070f23ced9f50e704d854d775da52591ab`.
It retains the seven logical implementation commits and the original author
of async adaptation:

| Commit | Change | Origin / review role |
| --- | --- | --- |
| `7d188aa` | Opt-in async adaptive tier | **Francesco Albano / Hardin22**, [PR #876](https://github.com/Niko1221/Strata/pull/876); preserved original commit |
| `a9daa44` | Q8 PLE reader | Cherry-pick of `18d3da4`; [PR #865](https://github.com/Niko1221/Strata/pull/865) |
| `59fa041` | Resident exchange rotation | Cherry-pick of `18a30ad`; [PR #864](https://github.com/Niko1221/Strata/pull/864) |
| `c71f73c` | Opt-in duplex copies | Cherry-pick of `513395d`; [focused duplex branch](https://github.com/CC-David-CC/Strata-a5500/tree/perf/duplex-transfers-only) |
| `d5ec4f1` | Reconcile async ownership and duplex boundaries | Integration; drain ownership before request completion |
| `fb62dbe` | Per-layer readiness/admission | Integration; wait for the required layer instead of the entire batch |
| `07ff95b` | Fixed-RAM commit path for per-layer admission | Enables a meaningful rotation-off ablation |

This draft is an **integration review and evidence package**, dependent on
the focused reader/rotation/async work above. It does not replace those PRs or
ask for another copy of their code to be merged. The maintainer can select the
focused changes first, then review the remaining integration/admission commits.
This branch's README banner is for fork review and can be omitted when
extracting an upstream patch.

## Enable and reproduce

Every new behavior remains opt-in. Resident RAM is an explicit use case;
upstream presets are unchanged. The tested combination is CUDA, one GPU,
fixed expert cache, fully pinned/mapped resident complement, and host planning.
It is not a multi-request or helper-GPU result.

```bash
export STRATA_EXPERIMENTAL_Q8_PLE=1
export STRATA_EXCHANGE_ROTATE=1
export STRATA_EXCHANGE_DUPLEX=1
export STRATA_ASYNC_LAYER_ADMIT=1
export STRATA_VERIFY_DEVICE_PLAN=0
export STRATA_ADAPT_NOWAIT=0

# Add these to the existing prepared Q8 model/pack/mtp/profile arguments:
# --adapt-async 1 --adapt-every 4 --adapt-swaps 96 --adapt-decay 0.7
# --resident-budget-gib 56 --expert-cache 15472 --pcie-frac -1
# --spec 8 --mtp-max-t 4 --spec-min-p 0.5 --suffix-draft 0 --kv fp16
# --max-context 139264 --prefill 1024 --no-prefill-borrow
# --vram-reserve-mib 2048 --ple-io ram --ple-row-cache 1048576
# --prompt-cache 0 --conversation-cache-mib 0
```

The evidence includes full argument arrays, source/binary/model hashes,
synthetic prompt token IDs, output token IDs, counters, build logs and the
Python private-serving benchmark harness. The harness forces exactly 1,024
output tokens with an EOS sentinel; that is a benchmark policy, not a serving
recommendation. It checks the startup message `PLE table locked in RAM` and
fails if locking did not succeed. Configure sufficient process memlock limits
for this experiment; a log saying merely prefaulted is insufficient.

Build: Release, GCC 13.3, CUDA 13.2, SM120, driver 595.91.07, native experts,
tests enabled; ggml `3cf03257f219afbe7334045ff7c6a06ac68c627d`.

```bash
cmake --build build --target strata file_expert_source_test \
  exchange_storage_test duplex_exchange_test layer_exchange_test
ctest --test-dir build \
  -R '^(file_expert_source_test|exchange_storage_test|duplex_exchange_test|layer_exchange_test)$' \
  --output-on-failure
./build/file_expert_source_test --rotation-gpu
compute-sanitizer --tool memcheck --error-exitcode 86 ./build/layer_exchange_test
compute-sanitizer --tool memcheck --error-exitcode 86 ./build/file_expert_source_test --rotation-gpu
compute-sanitizer --tool memcheck --error-exitcode 86 ./build/duplex_exchange_test
```

## Validation and draft limits

- All four ownership/transfer CTest fixtures passed on the measured source.
- Explicit GPU source fixture passed 64 exchanges per mode: fixed pinned,
  rotated pinned, and requested rotation with pageable fallback. Partial
  admission preserved both early and later owners' CPU/GPU bytes.
- Per-layer fixture checks delayed later layers, byte equality, guards,
  repeated ownership cycles and boundary draining.
- Fresh CUDA memcheck runs of **layer readiness, file-source rotation and
  duplex fixtures each reported zero errors**. These are fixture checks,
  not a full-model Compute Sanitizer run.
- Q2 integration checks passed flags-off parity, cancellation followed by
  another request, target-only generation and fallback. A fresh reader-only
  upstream comparison also passed exact flags-off token/work parity.
- The Q8 rotation ablations above each completed the full 32K + 1K request.
- Earlier standalone reader validation matched 1,059 Q8 PLE probes and batch
  reads against ggml; earlier standalone ownership ASan/UBSan checks are
  linked in the respective reader/rotation/duplex reports.

Remaining before promoting the whole integration from draft: broader prompts
and run counts (including more 128K cases), Q8 cancellation/state-differential
coverage of all async boundaries, and review
of interactions with other pipelined adaptation changes. Full-model routing,
KV/recurrent-state hashes and Nsight DRAM transactions were not collected for
the headline pairs. The two repetitions are not a confidence interval or an
answer-quality evaluation. AMD, Windows GPU execution and multiple concurrent
requests are not validated for this combined path.

## Evidence and history

**[Immutable evidence archive and readable summary](https://github.com/CC-David-CC/Strata-a5500/tree/8c473b947c5076edd39539bc5d69c082b237842b/bench/results/2026-10-05-q8-resident-adaptation)** (commit `8c473b947c5076edd39539bc5d69c082b237842b`). Contains all five immediate study histories, original scripts/logs/input-output token arrays, file hashes, fresh upstream baseline and sanitizer logs. Run `python verify_evidence.py` in that folder to check archive hashes and both headline comparisons without a GPU.

The implementation history is retained on this branch. Larger raw archives
are linked separately so the upstream code review need not carry generated
token arrays, logs and earlier experimental work as source changes.

Earlier research remains available in the fork as context, with its own
models, flags and measurement limitations. It is not substituted for the
fresh comparisons above:

- [Original Q8 buffer-ownership experiment](https://github.com/CC-David-CC/Strata-a5500/tree/experimental/rtxpro-q8-buffer-ownership)
- [Exchange-rotation research and native Q8 parity history](https://github.com/CC-David-CC/Strata-a5500/tree/perf/exchange-rotation-mvp)
- [Earlier duplex experiments](https://github.com/CC-David-CC/Strata-a5500/tree/perf/q8-duplex-exchanges)
- [Earlier per-layer admission experiments](https://github.com/CC-David-CC/Strata-a5500/tree/perf/q8-layer-admission)
- [LAN configuration/evidence freeze](https://github.com/CC-David-CC/Strata-a5500/tree/freeze/q8-lan-20261004)
