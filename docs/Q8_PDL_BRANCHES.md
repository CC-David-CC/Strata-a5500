# Q8 integration: PDL and independent graph branches

Fork integration for **CC-David-CC/Strata-a5500**, based on
`draft/q8-resident-adaptation` at `a8802eb`.
The kernel and graph implementation is **Francesco Albano / Hardin22's work in
[upstream PR #904](https://github.com/Niko1221/Strata/pull/904)**. This branch
preserves his authorship and extracts PDL plus graph branches. David's additions
are the opt-in defaults, an activation message, tests on this Q8 configuration,
and this report. This PR targets our fork's adaptation branch.

## Focused branch results

**RTX PRO 6000 Blackwell Workstation Edition, 96 GB VRAM; Ryzen 9 7950X;
128 GB system RAM; CUDA 13.2, native sm_120.** Model: Unsloth
Qwen3.8-Flash-Next Q8_0 experts and PLE, compatibility BF16 small projections
and Q5_K output head. Target and draft KV are FP16.

Actual **32,768 input + 1,024 output tokens**, greedy, **MTP T4**, one request.
Combined PDL+branches decode change: **+1.69% / +2.45%** in off/on and on/off pairs.
Full-request time reduction: **+0.22% / +0.26%**. Both combined pairs have identical output token IDs and recorded work.

| Case, chronological order | Output tok/s | Prefill seconds | Request seconds |
| --- | ---: | ---: | ---: |
| r0-off | 141.146 | 52.920 | 60.191 |
| r0-both | 143.538 | 52.911 | 60.060 |
| branches | 143.153 | 52.919 | 60.087 |
| pdl | 140.890 | 52.909 | 60.191 |
| r1-both | 144.663 | 52.941 | 60.034 |
| r1-off | 141.204 | 52.922 | 60.188 |

`both` means `STRATA_DF_PDL=1 STRATA_DF_BRANCH=1`; `off` omits both flags.
The two individual-feature cases are single measurements between the combined
pairs. Do not add their percentage changes or treat this small screen as a
general speed guarantee. Preserve any losses shown in the table.

Standalone PDL measured **140.890 tok/s (-0.18%)**; graph
branches measured **143.153 tok/s (+1.42%)**, against
the first focused control. The initial +0.54% PDL-only result was not reproduced
as a standalone gain here. PDL remains an independent opt-in experiment;
the combined result does not establish that it adds a repeatable benefit over
graph branches alone.

The prompt has repeated maintenance-note filler followed by a coding task;
the exact input IDs are archived. An unreachable EOS sentinel forces the
requested output length. These are throughput tests, not answer-quality scores.
Each case starts a fresh engine. Startup is excluded from request time; final
adaptation/ownership drains are included in decode time. Allocated context is
139,264 tokens, distinct from the actual 32,768-token input.

The cache is explicitly fixed at **15,472 experts (75.25 GiB)**, with a 56 GiB
resident-RAM budget and physically locked Q8 PLE. Async adaptation, rotation,
duplex copies and per-layer admission remain enabled in every Q8 case.
No prompt reuse or suffix/n-gram drafts. This screen does not retest 128K input,
Q8 target-only throughput, concurrent requests, HIP or another GPU architecture.

## Validation and provenance

- Eight component tests passed: exchange storage, file expert source, duplex,
  per-layer admission, MMVQ, PDL, BF16 GEMV and Q4 KV parity.
- PDL normal and single-predecessor modes passed; 200 graph replays matched.
- CUDA Compute Sanitizer **memcheck and initcheck: zero errors** on PDL parity.
- Fixed-placement Q2 model gates passed: previous/default build parity,
  enabled/default MTP parity, and enabled/default target-only parity.
  These short Q2 runs are correctness gates; their timings are archived and
  are not used as Q8 performance evidence.
- Model-level output equality is observed for the recorded comparisons;
  it is not a proof of all intermediate states or all workloads.

Tested source: `70ed61f158f0ef6364557cc1ba8d1ab03178d2f1`. Engine SHA-256: `3e52d8c534b271025c50b8b301c5090685abfbf77750230cad65e9b590d8ec74`.
The source was archived from the committed branch before building; later
commits only add documentation. PDL requires supported native sm_90+ code
and CUDA 12.3+ APIs; this build was CUDA 13.2 / sm_120.

**[Immutable evidence, exact token IDs, logs, plans and verifier](https://github.com/CC-David-CC/Strata-a5500/tree/1c76a5ac315f98815dda25c7e3f9ac5478eadda4/bench/results/2026-10-05-q8-pdl-branches)**.
Run `python verify_results.py` in that evidence directory to check its hashes,
request counts, output equality, recorded work including transfer counters,
and recompute the comparisons. Plans and `run.py` contain the exact build and
launch arguments; replace the host-specific model paths when reproducing.

## Enable or disable

Both features are **off by default in this fork integration**. With the same
model and adaptation launch arguments:

```bash
export STRATA_DF_PDL=1 STRATA_DF_BRANCH=1
```

For the control, omit both environment variables or set both to `0`.
`STRATA_DF_PDL=2` restricts PDL to single-predecessor graph edges; it passed the
component check but is outside this focused Q8 timing matrix.
Graph branches do not activate in split/batch verifier windows or under
`STRATA_VERIFY_PROFILE`; use the ordinary timing path for this comparison.
The off path retains #904's kernel refactoring and copy-kernel substitution;
it is validated separately from the prior binary, not claimed byte-identical.

This extraction contains no fused PLE post-ops or Q4 KV batching from #904.
Those were separate variables in the initial screen below.

## Initial full-#904 screen that motivated the extraction

This earlier source was `3232bef`, with all of #904 compiled in. One run per
case, same Q8/FP16 32K+1K configuration; every output token and recorded work
counter matched. These numbers belong to that earlier build.

| Configuration | Output tok/s |
| --- | ---: |
| published | 140.542 |
| off | 141.349 |
| pdl | 142.114 |
| branches | 143.673 |
| ple | 140.297 |
| all | 143.760 |
| single-edge-all | 144.376 |

PDL alone was +0.54%, graph branches +1.64%, and fused PLE -0.74% against
that build's 141.349 tok/s control. The focused branch above is the new
measurement of the selected pair; it does not inherit those percentage claims.
The parent adaptation results are documented separately in
[Q8_RESIDENT_ADAPTATION.md](Q8_RESIDENT_ADAPTATION.md).
