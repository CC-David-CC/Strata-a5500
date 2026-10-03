# Forced rejection sweep

This diagnostic branch extends the existing `--spec-oracle` token-file option
to serving. A frozen serial continuation supplies proposals only. The normal
target model still produces logits, verifies the proposal, and commits the
accepted prefix. It never copies expected tokens into target output.

With an oracle, `STRATA_VERIFY_REJECT_DEPTH=-1` keeps every proposal intact.
Values 0 through `spec-2` deliberately replace that draft token with a different
in-vocabulary token in each sufficiently wide window. This exercises rejection
at the first draft and at each later depth. The oracle and injection are absent
from ordinary runs. Per-window diagnostics report offered width, accepted depth
and whether injection occurred, so a test cannot pass without reaching its case.

The state harness's `--oracle-sweep --caps 17 --verify-window 8` runs a serial
reference, then replay with MTP enabled. It compares output, consumed length and
valid target KV/recurrent/PLE/history hashes, excluding stale/unconsumed cells
and MTP-only state. Repeat with `--reject-depth -1,0,...,6` as separate runs.
The branch includes the output-cap/EOS fix; GPU checks are pending.

This is a controlled rollback test, not a speed benchmark or a test of natural
draft quality. It does not yet cover cancellation, stochastic target sampling,
parallel requests, or every context length.
