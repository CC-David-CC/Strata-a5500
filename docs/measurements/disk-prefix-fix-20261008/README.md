# Keep disk checkpoints until their replacement really contains them

Automatic shared-prefix return now recovers **8,191 tokens in all four diagnostic
cases**, with MTP and pinning independently off/on. Before this correction, all
four returns missed. All 52 generations completed in each campaign.

| Configuration | Reused before → after | Prompt work before → after | Ratio |
|---|---:|---:|---:|
| No MTP, unpinned | 0 → 8,191 | 1,665.4 → 627.4 ms | 2.65× |
| No MTP, pinned | 0 → 8,191 | 1,712.2 → 621.7 ms | 2.75× |
| MTP, unpinned | 0 → 8,191 | 1,601.7 → 598.7 ms | 2.68× |
| MTP, pinned | 0 → 8,191 | 1,669.5 → 604.3 ms | 2.76× |

These are single observations per case, not percentiles. The engine prompt-work
counter includes automatic parking/restoring; it is not HTTP time to first token
or isolated GPU prefill. Each return reads 21 new tokens rather than 8,212.
Replies were capped at 128 tokens and these returns stopped naturally at 97.
Filesystem caches were warm; cold-storage latency was not measured.

## Cause and correction

The streamed writer can omit a shared root checkpoint which still exists in the
live RAM chain. Supersession used that larger RAM chain to decide which old files
to delete, allowing the only disk copy of the root to disappear. Explicit RESTORE
from an independently saved base worked, but automatic return to the prefix failed.

When a replacement path is supplied, `drop_superseded()` now checks the indexed
replacement file's retained checkpoint lengths and live state as well as the
existing token/image compatibility checks. A missing or mismatched replacement
does not authorize deletion. Genuinely redundant snapshots can still be removed.
The path without a replacement argument is unchanged. Cache budgets still apply:
this does not promise unlimited retention or change capacity eviction.

## Validation and provenance

- CPU regression fails before the fix and passes afterward: **104 checks**,
  including a root omitted by the streamed writer, a changed suffix, restart
  reindexing, and deletion when a replacement really retains the root.
- All five selected cache/session test executables pass.
- The spill regression was also compiled and run on the exact review base
  (original #1529 plus this correction): [104 checks passed](review-unit.txt).
- Live hardware: llm-60, RTX PRO 6000 Blackwell 96 GB, CUDA 13.2,
  ISTA IQ3_XXS, INT8 KV, 32K allocated context, `auto:8192` prefill,
  temperature zero, suffix draft disabled, 4,096 MiB disk-only cache.
- Workload: 8,191-token reference, eight changing suffixes, an unrelated request,
  then a return with a new suffix; explicit RESTORE is a control.
- Live base: [#1489](https://github.com/Niko1221/Strata/pull/1489),
  `b299af0e8fc9f7ee1792c63a155707cc166ae7e4`, with the top commit from
  [#1529](https://github.com/Niko1221/Strata/pull/1529),
  `daff41701df36ff48e35c3c32bb99f2738542ef2`, applied as `86ce4287`.
  This correction was then applied to that integration for the live campaign.
  It does not claim a complete live validation of the original #1529 stack,
  latest main, HIP, multi-GPU, or the RAM-eviction tier.
- The review patch is based directly on `konijiwa110/Strata:conv-disk-tier`,
  so its diff contains only this correction, its regression, and this evidence.
  The existing disk-tier implementation remains the work of #1529 and its
  dependency authors. The tested #1489 integration provides the separate no-MTP
  session-save correction needed for the no-MTP live arms.

## Evidence and reproduction

- [Before/after counters](summary.json), [all fixed requests](rows.json),
  [completion receipt](complete.json), [fixed binary hash](binary.json).
- [Failing regression before correction](regression-before.txt),
  [passing regression](unit-regression.txt), [five test results](unit-tests.txt).
- Engine logs: [no MTP/unpinned](off-unpinned/engine.txt),
  [no MTP/pinned](off-pinned/engine.txt), [MTP/unpinned](mtp-unpinned/engine.txt),
  [MTP/pinned](mtp-pinned/engine.txt).
- [Original before-fix campaign](https://github.com/CC-David-CC/Strata-a5500/tree/bench/disk-prefix-retention-20261008/docs/measurements/disk-prefix-retention-20261008/pr1529).
- [Generic probe](../../../../tools/disk_prefix_retention_probe.py):
  `python tools/disk_prefix_retention_probe.py --source PATH_TO_STRATA --config CONFIG_JSON --output RESULTS --mtp MTP_RUNTIME`
  uses the supplied model configuration; no private profile or server wrapper.

Session payloads were disposable and removed after each case. Model weights and
private Codi code are not included.
