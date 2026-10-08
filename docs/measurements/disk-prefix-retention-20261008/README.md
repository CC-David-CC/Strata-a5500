# Disk-only shared-prefix retention: generic engine reproduction

On integration **#1489, commit `b299af0e8fc9f7ee1792c63a155707cc166ae7e4`**, an
8,191-token reference prefix is reused across changing questions, then lost from
automatic reuse after an unrelated request. Explicitly restoring the original
base snapshot immediately reuses all 8,191 tokens again.

This reproduction calls Strata's native engine through its public Python engine
adapter. It contains **no downstream profile wrapper**. It reproduces with MTP
off/on and with `strata_prefix: {"tokens": 8191}` pinning off/on. This establishes
that the observed loss does not require MTP or downstream profile handling.
Latest upstream main and the proposed #1529 fix have not been tested here.

| Configuration | Automatic return: reused tokens | Automatic prompt work | Explicit RESTORE | Prompt work after RESTORE | Reused after RESTORE |
|---|---:|---:|---:|---:|---:|
| No MTP, unpinned | 0 | 1,657.2 ms | 314.0 ms | 123.0 ms | 8,191 |
| No MTP, pinned | 0 | 1,699.1 ms | 318.1 ms | 124.8 ms | 8,191 |
| MTP, unpinned | 0 | 1,614.4 ms | 306.1 ms | 97.9 ms | 8,191 |
| MTP, pinned | 0 | 1,647.1 ms | 325.3 ms | 100.7 ms | 8,191 |

These are single diagnostic observations per configuration, not statistical
performance claims. The prompt-work column after restore excludes RESTORE itself;
both costs are shown separately. Generated output was capped at 128 tokens; the
return/control requests stopped naturally after 97 tokens.

## Sequence

1. Prefill a generic Python reference, explicitly SAVE its base snapshot, then
   park it with an unrelated one-token request.
2. Send eight requests with the same reference and changing 100-token question
   content. They reuse the base; the last still reports 8,191 cached tokens.
3. Send an unrelated short question about correlation and causation.
4. Return to the unchanged reference with a new Python-review question.
   **Actual: zero cached tokens. Expected: reuse the retained shared prefix.**
5. Explicitly RESTORE the base snapshot and repeat the same review question.
   Actual: all 8,191 prefix tokens are reused; only 21 prompt tokens are read.

The automatic disk budget is 4,096 MiB. Just before the miss, logs report
**2,941 MiB without MTP / 3,009 MiB with MTP** in nine files and one older copy
dropped. After parking the unrelated request, usage is **3,167 / 3,235 MiB**.
The miss therefore occurs below the configured disk budget. The logs suggest
examining snapshot supersession and retained checkpoint depth, but do not by
themselves prove the cause. #1529's root-checkpoint retention is relevant follow-up.

## Reproduce

Use a valid Strata JSON config selecting the model, pack, tokenizer, native
binary, and backend. The probe replaces only its cache directory/budget and
MTP options. Use a new output directory and leave several GiB beyond the engine's
4 GiB minimum disk reserve. The probe deletes its own completed session payloads,
retaining logs and metrics. No service or model files are modified.

```sh
python tools/disk_prefix_retention_probe.py \
  --source /path/to/Strata \
  --config /path/to/strata-iq3_xxs.json \
  --output /tmp/prefix-retention-probe \
  --mtp /path/to/mtp/rt
```

Omit `--mtp` to run only the two no-MTP cases. Add `--resume` only to continue
an interrupted probe in the same directory. One initial MTP-pinned attempt hit
the filesystem free-space reserve before SAVE; completed cases were preserved,
temporary snapshots reclaimed, and that case rerun successfully. The final
`rows.json` contains only the **52 completed diagnostic generations**.

Hardware/config: RTX PRO 6000 Blackwell 96 GB; ISTA IQ3_XXS; INT8 KV; 32K allocated
context; prefill `auto:8192`; temperature zero; suffix drafts disabled; MTP off
or `--spec 4 --mtp ...`. Same model/build across all cases, warm filesystem cache.

- [Runnable probe](../../../tools/disk_prefix_retention_probe.py)
- [Summary](summary.json), [raw timings](rows.json), [completion receipt](complete.json)
- Engine logs: [off/unpinned](off-unpinned/engine.txt), [off/pinned](off-pinned/engine.txt),
  [MTP/unpinned](mtp-unpinned/engine.txt), [MTP/pinned](mtp-pinned/engine.txt)
- Each configuration's `explicit-restore.json` records the successful native RESTORE.

The successful controls also provide narrow MTP-enabled SAVE/RESTORE evidence
for #1489. They are not a complete Responses lifecycle or model-quality test.
