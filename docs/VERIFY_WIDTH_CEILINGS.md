# Verification width and graph setup diagnostics

This branch tests the Q4 full-expert model on llm-60 (RTX PRO 6000 Blackwell
96 GB, 128 GB system RAM). Controlled width measurements are recorded below.
It builds on the output-boundary fix and the checked forced-rollback oracle.

There are four real decoding paths: serial, MTP, prompt/history n-gram, and
MTP plus n-gram. A separate perfect-proposal control measures verification
capacity when prediction costs almost nothing and every proposal is correct.
Its proposals come from a previously saved answer to exactly the same prompt.
The target model still evaluates every position, selects outputs and verifies
the proposal. This is an upper-bound experiment, not an implementable predictor
or a model quality score. Do not label oracle throughput as n-gram throughput.

## Controls

The serving path accepts these diagnostic environment settings:

- `STRATA_DIAG_WINDOW_LIMIT=1..spec`: limit actual verification width without
  changing allocated buffers. Also bounds the number of n-gram proposals.
  MTP draft work is controlled separately with `--mtp-max-t`.
- `STRATA_VERIFY_ORACLE_WINDOW=1..spec`: width of known-answer oracle proposals
  when `--spec-oracle` is supplied. The ordinary first window and output/EOS
  boundary can still be shorter. Defaults to the allocated width.
- `STRATA_VERIFY_ORACLE_LOG=0`: suppress the diagnostic line for every oracle
  window during throughput runs. The target's ordinary acceptance totals stay
  available. The rollback diagnostic keeps its original logging by default.
- `STRATA_PREPARE_VERIFY_GRAPHS=1`: capture/upload reachable verification
  widths and the commit graph after prompt processing, before decode timing.
- `STRATA_PREPARE_MTP_GRAPHS=1`: capture/upload reachable MTP catch-up rounds
  and allowed draft steps there, using the request's sampling mode.
- `STRATA_GRAPH_CAPTURE_LOG=1`: log first captures of MTP rounds and steps as
  well as the existing verifier capture messages.

Graph preparation records and uploads execution descriptions; it does not
launch target/draft computation or advance model state. Outstanding commit
work is drained first. Setup milliseconds are logged and included in prompt
and total request time. An apparent decode-only gain from moving setup cannot
be described as an end-to-end gain. Preparation is a serving-path diagnostic;
the CLI does not currently apply these preparation environment switches.

## Measurement plan

Hold verifier allocation at eight. Compare T=1, 2, 3, 4 and 8, with identical
64K prompts and output budgets. For oracle controls, require full acceptance
and exact output equality. Real MTP tests report both fixed confidence zero
(to expose the requested width) and the ordinary 0.5 policy. Real n-gram width
is a cap: missing/weak matches can make actual windows smaller. Report the
window histogram, accepted/offered drafts, committed tokens, preparation time,
decode/effective throughput and memory use. Repeat in reverse order.

Before timing, compare prepared and lazy configurations against the target
state checks, including output limits and forced oracle rejection. For traffic,
collect warmed ranges, retain all verifier and drafter graph-capture events,
and reject mismatched replay trajectories. T=2 and T=3 must be separate rows.

The conditional bandwidth ceiling is measured traffic per committed token
divided into the GPU bandwidth assumption. It changes with width, proposal
accuracy, data reuse and workload. Comparing 245 token/s for serial with 504
for one MTP sample does not establish a universal limit for either algorithm.

Eight is the present implementation limit, not a proven optimum. An extension
must audit fixed arrays, graph tables, per-token scratch, grouped-expert slots,
MMVQ dispatch, recurrent-state snapshots and rollback before using T=16 or
larger. A larger shape must pass arithmetic and committed-state checks before
its performance is compared. A smaller optimum remains a valid result.
# Oracle EOS accounting

The first full sweep stopped on a harness assertion after an otherwise exact
T=2 prose answer: 793 proposals counted as committed out of 794 offered. The
last proposal was discarded by the natural EOS boundary. The corrected oracle
harness caps the request at the known reference length, so its final window
cannot propose past the known stop. This extra knowledge belongs only to the
oracle ceiling experiment. Real proposal paths keep their original output
budget. The engine binary and emitted reference answer are unchanged. Both
the requested budget and the actual engine limit are recorded.

## Measured widths (2026-10-03)

Full Unsloth **UD-Q4_K_XL**, int8 KV, 65,536 actual input tokens and 73,728
allocated context. All arms allocate eight verifier positions. The engine is
`8591dc7`; the EOS-aware harness is `70ca7c2`. Graph preparation is enabled in
every arm and included in prompt/request time. Prompt and conversation reuse
are disabled. Real MTP uses minimum draft probability **0.0** to expose the
width limit; these are not measurements of the usual 0.5 policy.

[The evidence JSON](benchmarks/q4-verify-widths-20261003.json) contains 95
observations, command arguments, environment, prompt/output/binary hashes,
acceptance and window histograms, timings, and raw-file hashes. Every observation
passed its exact-output and committed-count checks against the frozen answer.
These are performance and smoke tests on synthetic workloads, not quality scores.
The unchanged engine passed earlier state/rollback gates; the speed runs did not
collect a new per-step state trace.

### Real predictors: 1,024-token screen

Output tok/s; one observation per cell. Larger windows improve editing but hurt
MTP on code and prose. A width chosen from this screen needs a matched repeat.

| Path / workload | T=1 | T=2 | T=3 | T=4 | T=8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MTP / code | 99.55 | 164.59 | 194.97 | 209.57 | 194.47 |
| MTP / prose | 98.22 | 144.01 | 156.82 | 151.74 | 108.03 |
| MTP / editing | 101.78 | 175.86 | 219.53 | 254.14 | 284.48 |
| N-gram / code | 103.94 | 113.84 | 115.93 | 115.99 | 115.84 |
| N-gram / prose | 103.47 | 103.66 | 103.68 | 103.72 | 103.57 |
| N-gram / editing | 104.78 | 176.95 | 219.72 | 249.99 | 329.84 |
| MTP + n-gram / code | 99.48 | 165.29 | 194.08 | 209.94 | 192.13 |
| MTP + n-gram / prose | 98.23 | 144.23 | 157.26 | 151.79 | 107.80 |
| MTP + n-gram / editing | 101.74 | 176.00 | 219.59 | 254.50 | 302.49 |

### Selected widths: completed ABBA repeats

Fresh engine per request, two observations per arm, 4,096-token requested limit.
Prose stopped naturally at **1,588 tokens** and editing at **1,238** in every arm;
these are not 4,096-output-token measurements. Each compared group emitted an
identical token stream. The incomplete pre-pause group is excluded; all four
observations in each group below were run after resuming.

| Path / workload | Width change | Output tok/s, before -> after | Effective output tok/s, before -> after |
| --- | --- | ---: | ---: |
| MTP / prose | 4 -> 3 | 153.80 -> 158.51 | 77.03 -> 78.30 |
| MTP / editing | 4 -> 8 | 255.67 -> 283.64 | 81.32 -> 83.65 |
| N-gram / editing | 4 -> 8 | 249.59 -> 330.34 | 80.70 -> 87.65 |
| MTP + n-gram / prose | 4 -> 3 | 153.48 -> 158.39 | 76.72 -> 77.94 |
| MTP + n-gram / editing | 4 -> 8 | 255.34 -> 300.25 | 81.11 -> 84.99 |

Effective rate divides emitted tokens by measured prompt plus generation time,
excluding engine startup. For n-gram editing, wall request time fell from
15.35 to 14.13 seconds. Sampled peak VRAM across the repeat phase was 85,531 MiB;
minimum available host RAM was 116.27 GiB. No foreign GPU process was observed.

### Known-answer oracle: verification capacity

Output tok/s, mean of two observations in reversed width order. Both proposed
tokens and the stop position are supplied from the saved answer. These numbers
measure verifier capacity and cannot be presented as usable generation speed.

| Workload | T=1 | T=2 | T=3 | T=4 | T=8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code | 104.25 | 183.22 | 239.85 | 285.88 | 391.95 |
| Prose | 103.91 | 183.19 | 239.61 | 285.23 | 391.98 |
| Editing | 104.78 | 182.13 | 236.53 | 280.63 | 383.37 |

All oracle outputs matched, with full proposal acceptance. There is no 400+
tok/s observation in this set. Widths beyond eight belong to the separate
`perf/q4-wide-verify24` experiment; its results are not implied by this table.
