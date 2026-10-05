# Duplex exchange validation, 2026-10-05

Supporting evidence for the opt-in CUDA resident-exchange experiment in
[`perf/duplex-transfers-only`](https://github.com/CC-David-CC/Strata-a5500/tree/perf/duplex-transfers-only).
The [report](https://github.com/CC-David-CC/Strata-a5500/blob/perf/duplex-transfers-only/docs/DUPLEX_EXCHANGES.md)
describes its scope, ordering, results and limitations. Strata is by
[Niko1221 and contributors](https://github.com/Niko1221/Strata).

## What passed

RTX PRO 6000 Blackwell Workstation Edition 96 GB, Ryzen 9 7950X, 128 GB RAM,
Linux, CUDA 13.2, driver 595.91.07. The standalone transfer fixture also passed on
an RTX 4090 with CUDA 13.3. It checks eviction/refill bytes and early teardown;
Compute Sanitizer memcheck and ASan/UBSan passed as described in the report.

| Suite | Requests | Exact token/work comparisons |
|---|---:|---:|
| Q2 defaults, fallbacks, target-only, MTP, cancellation | 14 | 7 |
| Q2 repeated 8K/32K coding and editing | 32 | 16 |
| Q8 T2, target-only, rotation-off, 128K and cancellation | 18 | 8 |
| Q8 wider MTP, repeated 32K coding and editing | 8 | 4 |
| Q8 locked-table diagnostic, repeated 32K coding | 4 | 2 |
| Total | 76 | 37 |

The cancelled request itself is a protocol/lifetime check; the paired equality
check applies to the following complete request. These results are not a model
quality evaluation or proof of all possible state interleavings.

## Performance interpretation

- Two AB/BA pairs per Q2 cell: MTP improved 1.7-2.8%. Target-only 32K regressed
  0.7-1.2%; the report retains both improvements and regressions.
- The isolated Q8-sized 4/16-slot transfer batches took 27.0/34.0% less time.
  This measures transfer latency, not model throughput or fewer bytes.
- Initial Q8 pairs varied substantially between repetitions. They validate token/work
  equality, but do not support a large repeated Q8 speed claim.
- The Q8 fixture has Q8_0 experts/PLE and a compatibility dense pack with a Q5_K
  head. Its RAM lookup table failed to lock under the test launcher's limit.
- A separate screen of [PR #876](https://github.com/Niko1221/Strata/pull/876)
  (Francesco Albano / Hardin22) captured heavy reclamation/swapping and unstable
  flag-disabled timings. This diagnostic does not establish that every timing
  difference has the same cause. Its asynchronous outputs can differ, and are
  not included in the duplex equality checks above.

### Locked-table diagnostic

Raising only the diagnostic launcher's memlock limit allowed the 50.66 GiB lookup
table to lock successfully. With the same Q8 binary, model and settings, two AB/BA
pairs of 32,768 input + 1,024 output tokens measured:

| Order | Sequential tok/s | Duplex tok/s | Decode gain | Total seconds, off to on |
|---|---:|---:|---:|---:|
| AB | 129.72 | 136.65 | +5.35% | 60.81 to 62.59 |
| BA | 128.70 | 136.93 | +6.39% | 60.86 to 60.41 |

Tokens and recorded work matched in both pairs. Aggregate decode rate was
129.21 to 136.79 tok/s (+5.87%). Prefill dominated: mean total time was
60.836 to 61.503 seconds, with no consistent end-to-end gain. This is a limited
coding result, with MTP T4, FP16 KV and suffix drafting off. Remaining swap-ins
and major faults mean it is not a claim that all paging was eliminated. No
global memory limits or service settings changed. The report gives full settings.

## Files and reproduction

- `raw-results.tar.gz`: exact plans, raw input/output token IDs, complete logs,
  build/test logs, binary hashes and the model runner actually used.
- `provenance.json`: SHA-256 hashes and build-machine/service metadata. Compiled
  binaries, source tarballs and model weights are hashed where recorded but not
  included in the archive.
- `summary.json`: all pair comparisons and the archive hash.
- `q2-summary.json`, `copy-summary.json`: derived numerical summaries.
- `fixture-4090.json`: matching fixture source hashes and the second GPU receipt.
- `separate-async-memory-screen.json.gz`: the later #876 screen's token results,
  process counters, Linux memory-pressure counters, GPU snapshots and settings.
- `locked-duplex-results.tar.gz`: completed locked-table diagnostic, including
  process-local limit launcher, actual runner, plan, raw tokens, logs, process and
  system counters, binary hashes, and an individual-file hash manifest.
- `locked-summary.json`: derived locked-table timing and memory-counter summaries.

Unpack `raw-results.tar.gz`, read a suite's `result.json` and its corresponding
plan, and follow the report's build commands. The plans preserve the exact host
paths used; adjust checkout, model, MTP, pack and profile paths for your machine.
Keep settings fixed within each A/B pair. Q8 T4 also changes the proposal
probability threshold, so T2 versus T4 is a policy comparison, not width alone.

Upstream base: `6f32ec070f23ced9f50e704d854d775da52591ab`.
Clean duplex code: `513395defe59fdf6abc74f7fbf0f0b50f57662a0`.
Q8 test integration: `21b5487a6615b49daafff1bf3c06f55f7525e19c`.
The integration includes the reader and rotation prerequisites; the duplex
contribution itself has neither as a code dependency.
