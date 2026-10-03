# Commit only the emitted speculative prefix

The serving and CLI speculative loops previously committed the full accepted
prefix before clipping the emitted tokens at the output limit or EOS. Correct
printed tokens could therefore hide extra consumed state. This matters when a
serving session is reused for a later request.

On the RTX PRO 6000 Blackwell, the frozen `1c0c2bb` engine with Unsloth
UD-Q4_K_XL, int8 KV, an 8192-token prompt and four-token MTP windows reproduced
the problem. At output limits 3, 4, 7, 9 and 15, serial and MTP emitted identical
tokens but MTP's consumed length exceeded `prompt + output - 1`. For example,
the three-token cap left length 8196 instead of 8194. The target KV, recurrent,
PLE and history fingerprints consequently differed. Caps 1, 2, 5, 6, 8 and 17
matched in that particular sequence. This diagnostic has no throughput claim.

The fix bounds verification by the remaining output budget, then truncates the
accepted prefix at its first emitted EOS before committing it. Both loops use
the same rule; the CLI applies EOS clipping only when its stop-EOS setting is
enabled. The model weights, routing, per-token arithmetic and verifier remain
unchanged. The final emitted token remains the next input, as in serial decoding.

`tools/bench_state_boundaries.py` compares serial and MTP output and target state
at short caps. `--eos-id` and `--caps` also permit a reference token to act as an
early EOS inside a verified window. Stale cells beyond the consumed length and
MTP-only state are recorded separately, not mistaken for target committed state.
Fixed-engine GPU validation is pending. These checks do not establish every
cancellation, rollback or concurrent serving property.
