# Verification width and graph setup diagnostics

This branch tests the Q4 full-expert model on llm-60 (RTX PRO 6000 Blackwell
96 GB, 128 GB system RAM). It does not claim a measured speedup yet.
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
