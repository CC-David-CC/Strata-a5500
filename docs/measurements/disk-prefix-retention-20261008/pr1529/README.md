# PR #1529: disk-only return still misses

Applying #1529 to the #1489 integration did **not** resolve this fixture's
automatic shared-prefix retention failure. All four configurations still reused
zero tokens after switching away, while explicit RESTORE recovered all 8,191
reference tokens. All 52 generations completed, and all five selected native
cache/session test executables passed.

| Configuration | Automatic return: reused | Prompt work | Explicit RESTORE | Prompt work after RESTORE | Reused after RESTORE |
|---|---:|---:|---:|---:|---:|
| No MTP, unpinned | 0 | 1,665.4 ms | 325.1 ms | 126.7 ms | 8,191 |
| No MTP, pinned | 0 | 1,712.2 ms | 330.6 ms | 126.3 ms | 8,191 |
| MTP, unpinned | 0 | 1,601.7 ms | 309.5 ms | 100.7 ms | 8,191 |
| MTP, pinned | 0 | 1,669.5 ms | 329.7 ms | 100.5 ms | 8,191 |

These are single diagnostic observations, not latency percentiles. Prompt work
after RESTORE excludes the separate RESTORE cost. Output was capped at 128 tokens;
the return and restore-control requests ended naturally at 97 tokens. The model,
settings and probe were held fixed relative to the [baseline](../README.md).
Automatic cache usage before returning remained below the 4,096 MiB budget:
3,167 MiB without MTP and 3,235 MiB with MTP. There were no free-space failures.

## Candidate and scope

- Base: #1489, `b299af0e8fc9f7ee1792c63a155707cc166ae7e4`.
- Patch: #1529, `daff41701df36ff48e35c3c32bb99f2738542ef2` from
  `konijiwa110/Strata:conv-disk-tier`, cherry-picked cleanly onto that base.
- Tested source: `86ce4287` on local branch `bench/test-1529-on-1489`.
- Binary SHA-256: `19b6a52e31dbce46ac9c413627214b9852e120694ffdffb23e824859fe752e11`.
- llm-60, RTX PRO 6000 Blackwell 96 GB, CUDA 13.2, ISTA IQ3_XXS,
  INT8 KV, 32K allocated context, prefill `auto:8192`, temperature zero,
  suffix draft disabled, disk-only automatic cache. MTP off/on and pinning off/on.
- The public engine adapter is used directly; no downstream profile wrapper.
- This tests the proposed patch on #1489, not the original PR branch as a whole
  or latest upstream main. RAM-tier eviction was not exercised by this fixture.

## Why the disk-only path needs separate investigation

In this candidate, #1529's new `conversation_spill_trim_checkpoints()` retains
the shallowest and deepest checkpoints for `spill_async()` after RAM eviction.
The direct disk-only path instead uses `session_save_checkpoints()`, which still
saves one checkpoint, then `spill_streamed()`. It does not call the new helper.

There is also a concrete supersession mismatch worth testing next:
`disk_save_live()` writes the selected `disk_checks` but calls
`drop_superseded()` with the original, potentially larger `checks` chain.
That can describe checkpoints which the new file does not actually contain.
Logs again show an older snapshot removed before the miss. This is a code-level
hypothesis, not yet a proven root cause or a validated additional fix.

The successful explicit restores mean callers can continue using an explicit
base/conversation snapshot restore as the tested workaround. They do not establish
that automatic disk-only profile switching retains the desired prefix.

## Evidence

- [Summary](summary.json), [raw request timings](rows.json),
  [completion receipt](complete.json), [source and binary receipt](campaign.json).
- [Five passing native test executables](unit-tests.txt).
- Engine logs: [off/unpinned](off-unpinned/engine.txt),
  [off/pinned](off-pinned/engine.txt), [MTP/unpinned](mtp-unpinned/engine.txt),
  [MTP/pinned](mtp-pinned/engine.txt).
- [Runnable probe](../../../../tools/disk_prefix_retention_probe.py).

Disposable session payloads were removed after each case. Normal serving remains off.
