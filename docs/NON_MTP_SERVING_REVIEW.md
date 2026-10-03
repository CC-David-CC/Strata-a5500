# Serving with or without an MTP drafter

Current base: **upstream 0.1.34**. See the
[2026-10-02 rebase checks](benchmarks/2026-10-02-upstream-sync-serving.md).
The performance tables and fleet/context matrix below were measured on **0.1.33**,
at the exact source commits listed. They remain historical evidence.

This is the shared serving split requested in [#323](https://github.com/Niko1221/Strata/pull/323)
and [#336](https://github.com/Niko1221/Strata/pull/336), based on upstream
**0.1.34, `1678de3`**. Strata, its expert cache and MTP are the work of
[Niko1221/Strata](https://github.com/Niko1221/Strata).

The fleet matrix, eight serving identity/replay gates and selected context
follow-ups completed. The initial allocation failure and natural-stop partial
success are retained in the evidence below.

## What changes

- `--serve` can start without `--mtp`. Draft binding, prefill, restoration,
  sampling and generation are guarded; the main model verifies one token at a time.
- Live-prefix reuse still works. Cross-conversation snapshots retain draft state,
  so use `--conversation-cache-mib 0` when the drafter is absent.
- `Verifier::set_pcie_enabled` omits empty graph stages when the expert source
  supplies no GPU-visible host aliases. A request's `pcie_frac=0` alone cannot
  disable the path: later requests may change that fraction.
- Prompt-tail profiling samples are separated from generated-token samples.
- The existing identity checker is updated for the current server lifecycle,
  and a reproducible MTP comparison harness is included.

Hardware support and optional performance kernels are separate contributions.
MTP is selected when the engine starts; this patch adds no per-request switch.

## Start the server without MTP

Build this branch for your GPU, then copy your working run config to
`config.no-mtp.json`. Keep its model, tokenizer and hardware settings. Set `exe`
to the absolute path of the newly built `strata` executable. In its `args` array:

1. Remove `"--mtp"` and the following directory value.
2. Set `"--spec", "2"` and `"--conversation-cache-mib", "0"`, replacing any
   existing values. Two is the allocation minimum; verification uses one token
   without a drafter. Live-prefix reuse remains available.

Restart the server using Strata's Python environment:

```sh
python -m serve.server --engine strata --config config.no-mtp.json --host 127.0.0.1 --port 8080
```

The existing config with `--mtp DIR` still starts with MTP. To restore it, stop
the server and restart with that original config. There is no automatic mode
selection and no new build-time opt-in. The PCIe graph fix applies automatically
when the expert source has no GPU-visible host aliases.

To verify the selected mode with the benchmark helper, use
`python tools/bench_mtp_modes.py --config config.no-mtp.json --output result-no-mtp --mode off`.
Its `READY mtp=False` line and saved launch arguments identify the drafter-free
run. See the reproduction section for controlled comparisons with MTP enabled.

## Measurements and correctness

[Full matrix, settings and retained failures](benchmarks/2026-10-01-serving.md).

Tested engine: `dea58f12e0536eb03a4bd8c2266a38ffbd9d0e28`.
The RX 5500 XT uses combined validation tree
`1dd175d3fa4b4013f3e17c34628337de5f0176ba`, containing this patch and the separate
community hardware support. It has no experimental performance kernels.

GSQ-RCO IQ3_S, Q8 KV, greedy text requests are tested at 8192, 32768 and 65536
input tokens with up to 4096 output tokens. Context allocations are 13312,
37888 and 70656. The matrix includes actual output lengths, prefill, first-token
time, generation rate, total completion time and effective throughput.

Completed RTX PRO examples at 64K input:

| Task | Actual output | MTP off generation | MTP on generation | Off total | On total |
|---|---:|---:|---:|---:|---:|
| Code | 2213 tokens | 104.79 tok/s | 222.72 tok/s | 30.80 s | 19.56 s |
| Prose | 1756 tokens | 104.56 tok/s | 159.66 tok/s | 26.33 s | 20.61 s |

The 4090 also completed all three lengths without a drafter. MTP is faster for
these longer RTX PRO and 4090 answers. On smaller cards the tradeoff includes
extra draft prefill and reduced expert-cache space; the matrix retains slower
cases and failures as well as improvements.

The RX 5500 XT short code request produced **the same 125 output token IDs** in
both modes. Without MTP it took **96.44 s**, versus **111.47 s** with MTP: a
**13.48% reduction in completion time**, despite slower generation
(11.63 versus 15.52 tok/s). Prefill was 85.69 versus 103.41 s. This is a measured
case where the new serving mode is useful.

For fresh 64K requests on the P4 and RX 5500 XT, removing the drafter also reduced
total completion time. Their outputs differed, so the full matrix includes
actual token counts and effective throughput. These observations do not imply
that MTP should be disabled on every machine or workload.

The identity gate compares output token IDs, authoritative state fingerprints,
resolved settings, known answers and live-prefix reuse across eight requests
per arm. It uses threshold 0, separately from throughput's MTP4/threshold 0.5.
CUDA, modern HIP and pageable resident HIP coverage are tracked separately.
These local checks complement the maintainer's broader gate.

Completed identity coverage:

| Platform | Gate | Result |
|---|---|---|
| RTX PRO / CUDA | Upstream versus serving; independent non-MTP replay | Pass |
| RX 7900 XTX / HIP 7 | Upstream versus serving, mapped and pageable resident experts; non-MTP replay | Pass |
| RX 5500 XT / HIP 5.7 | Hardware-only versus combined serving with pageable experts; non-MTP replay | Pass |
| RTX 4090 / CUDA | Per-request PCIe fraction 0 / 0.55 switching | Pass |

Each gate compares eight requests per arm. An independent non-MTP replay checks
determinism and state/known-answer consistency; upstream cannot serve that mode.
It is distinct from the upstream-versus-candidate MTP comparison.

All six hosts completed long code/prose requests at 8K, 32K and 64K input,
with both modes. The RTX 3070's initial 64K MTP-on allocation failed; the
documented 1148 MiB reserve retry passed. Its separate Q8 KV-streaming test
completed 128K input plus 4096 output with EOS stopping suppressed. The natural
128K request stopped normally at 3893 tokens and remains a partial success.

The separate **non-MTP 128K-input code request** completed normally:
131072 input tokens, 136192 allocated context, **2288 output tokens at
25.28 tok/s**, 362.25 s prefill, 452.80 s total, and 5.05 effective tok/s.
Minimum sampled free VRAM was **865 MiB**. This uses Q8 KV streaming with
32768 resident cells and the same 1148 MiB reserve. Its generated TTLCache class
passed the functional checks. The MTP-on capacity runs used counting, so their
generation rates are not a matched-workload comparison with this code request.

These are single-request results. The largest demonstrated full input is 128K
on the RTX 3070; a maximum context limit was not established. On the RX 5500 XT,
the largest full input tested with this serving/hardware combination is 64K.

### Small starting prompt with a larger allocation

The RX 5500 XT also completed the long code task with **8192 input tokens and
70656 allocated context tokens**, without Q8 KV streaming:

| Mode | Actual output | Prefill | Generation | Total |
|---|---:|---:|---:|---:|
| MTP off | 2133 | 92.50 s | 12.31 tok/s | 265.74 s |
| MTP on | 2518 | 162.76 s | 15.40 tok/s | 326.32 s |

Minimum sampled free VRAM was 381.16 MiB across the pair. The larger allocation
changes the memory available for expert caching and prompt buffers, so the
original 8K/13312-allocation results should not be presented as this workload.
Output lengths differ; these are observed completion times for each answer.

An additional RTX 4090 regression test starts a pinned host-expert source at
`--pcie-frac 0`, then alternates request-level fractions 0 and 0.55 without
restarting. Both upstream and candidate performed positive PCIe expert work on
the enabled requests and none on the disabled requests. All eight requests had
identical output tokens, state hashes, prefix reuse and known answers between
the engines. The test uses 1024 GPU expert slots to exercise cache misses:

```sh
# Config: --expert-cache 1024 --pcie-frac 0, with a pinned expert arena.
python tools/conversation_cache_disabled.py --config config.json \
  --upstream /path/to/upstream/build/strata --candidate /path/to/branch/build/strata \
  --output pcie-switch-results --spec 4 --paragraphs 32 \
  --pcie-sequence 0 0.55 --run
```

Model startup is excluded from request time. Throughput requests have no prefix
reuse or conversation snapshots; the OS file cache is not reset. Different
MTP modes may produce different output lengths. The generated TTLCache class is
checked against independent functional cases; this is not a model-quality score.

## Reproduce

Build upstream `aeb35be` and this branch with the same toolchain and pinned GGML.
The tested GGML revision is `3cf03257f219afbe7334045ff7c6a06ac68c627d`.

```sh
python tools/conversation_cache_disabled.py --config config.json \
  --upstream /path/to/upstream/build/strata --candidate /path/to/branch/build/strata \
  --output identity-results --spec 4 --paragraphs 32 --run

python tools/bench_mtp_modes.py --config config.json --output result-64k \
  --input-tokens 65536 --output-tokens 4096 --workload long \
  --mode both --cases coding writing
```

The throughput config must include `--mtp DIR` and at least 70656 allocated
context tokens; the harness removes `--mtp` for the off arm. Keep `--spec 2`
when manually starting without MTP: the allocation minimum is two although the
actual verification window is one token. On the RX 5500 XT, apply the same
community hardware support to both identity-comparison arms.

The combined AMD validation commit is local. Its exact source tree can be
recreated from the published contribution commits, without another public branch:

```sh
git switch -c local-serving-gfx1012 dea58f12e0536eb03a4bd8c2266a38ffbd9d0e28
git merge --no-edit 4a6c47ef837e999f428a0740ecf769daa66fbe15
git rev-parse 'HEAD^{tree}'
# 02937409c68bcdd8b4bd58c4a39da919aab44ef1
```

The JSON evidence includes actual launch arguments and environment overrides.
Replace `${HOME}` and the recorded build/model paths for your installation.
The engine snapshot above predates later test/documentation-only commits;
its C++ implementation is unchanged by those commits. Source manifests and
binary hashes identify the measured builds.
