# Q8 resident adaptation — complete immediate experiment history

Evidence for the [draft integration branch](https://github.com/CC-David-CC/Strata-a5500/tree/draft/q8-resident-adaptation).
The [main report](https://github.com/CC-David-CC/Strata-a5500/blob/draft/q8-resident-adaptation/docs/Q8_RESIDENT_ADAPTATION.md)
explains the 24.5–28.2% rotation gain and the separate upstream comparison.

**Hardware/model:** RTX PRO 6000 Blackwell Workstation 96 GB, Ryzen 9 7950X,
128 GB RAM; Unsloth Qwen3.8-Flash-Next Q8_0 experts/PLE, compatibility BF16
small projections and Q5_K head, FP16 KV. The Q8 comparisons use 32,768 input
tokens, 1,024 forced output tokens, MTP T4, one request and physically locked
PLE. Smaller Q2 runs are lifecycle/default-path checks, not the Q8 speed claim.

## Files

- [`summary.json`](summary.json): readable timings, counters, configuration
  cases, source/binary hashes, output hashes and pairwise comparisons.
- [`experiment-history.tar.gz`](experiment-history.tar.gz): original retained
  JSON results, full input/output token arrays, logs, plans, build/coordinator
  scripts and benchmark harnesses for the five studies below.
- [`history-manifest.json`](history-manifest.json): per-file SHA-256 and sizes;
  source archive hashes identify the builds whose source is preserved in Git.
- [`verify_evidence.py`](verify_evidence.py): offline archive-integrity check,
  recomputation of both headline gains and equality checks on token IDs,
  measured work and exchange counters. No GPU or model required.

```bash
python verify_evidence.py
```

## Study order

1. `async-locked-20261005`: upstream PR #876 plus Q8 PLE reader; default-off
   parity and standalone async screen. Preserves differing output/work.
2. `adaptation-combined-20261005`: blocking rotation+duplex, async+rotation,
   and the first async+rotation+duplex combination. Preserves the regression.
3. `adaptation-layer-20261005`: per-layer admission, Q2 lifecycle gates and
   32K Q8 off/on comparisons; output/work differences remain visible.
4. `adaptation-no-rotation-20261005`: enables the fixed-RAM per-layer commit
   path. Six reversed-order Q8 cases isolate rotation, with the headline
   exact-token/work pairs. Includes Q2, CTest and explicit GPU ownership checks.
5. `adaptation-publication-20261005`: fresh upstream-plus-reader versus full
   stack A/B/B/A, default-off parity, and three CUDA memcheck fixture logs.

The reports record all case outcomes, not only successful speedups. Some
older pair labels say `default-path parity` even for an enabled admission
comparison; inspect the explicit flags, `require_token_equality`, actual
`tokens_identical` and `work_identical` fields. Only the two rotation pairs
claim observed exact token/work equality for Q8.

## Provenance and scope

Upstream base: `6f32ec070f23ced9f50e704d854d775da52591ab`.
Full integration code: `07ff95bed2889453d4fca3d45cd86765234d0b29`.
Fresh reference: main plus reader only, `18d3da487f82c8e7b5d8e91f6fdd8c75972182f1`.
All seven implementation commits, including Hardin22 / Francesco Albano's
original async commit, are retained in both branches. Earlier duplex
validation and unlocked-PLE experiments are also available in the
[prior archive](https://github.com/CC-David-CC/Strata-a5500/tree/test/duplex-q8-integration/bench/results/2026-10-05-duplex).

Download-manifest model hashes are provenance from the retained model
download; these runs do not rehash the full 188 GB of model files per request.
Binary hashes are checked by the harness. Startup is excluded; final async
ownership drains are included in decode time. Host-copy payload accounting
is not a measurement of hardware DRAM transactions. Fixture sanitizer results
are not full-model sanitizer results. Two repetitions are not a confidence
interval or a broad quality evaluation.
