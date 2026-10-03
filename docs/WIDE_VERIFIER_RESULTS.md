# Wide verifier: correctness results

Measured 2026-10-03 on llm-60, **RTX PRO 6000 Blackwell Workstation Edition,
96 GB VRAM and 128 GB installed RAM**, using full Unsloth UD-Q4_K_XL and int8 KV.
The inference source is `9f7fdeb`; `4a5e201` and `71e3f8a` change the HC test
fixture only. The model executables were hashed before and after those test
changes and remained identical.

## HC test input ordering

The first capacity-24 gate failed the HC direct-versus-single and graph-versus-
direct comparisons. Its initial pageable host copies used the default stream,
followed by computation on a nonblocking stream without an explicit dependency.

An alternating ten-run comparison changed only that dependency:

| Fixture | Passes | Failures |
| --- | ---: | ---: |
| Historical | 8 | 2 |
| Default-stream copies explicitly completed first | 10 | 0 |

This supports an input-ordering problem in the fixture. No inference arithmetic
or tolerance was relaxed. The expanded fixture tests every width 1 through 24;
plain and staged HC variants passed parity, memcheck, initcheck and synccheck.
An earlier diagnostic racecheck timed out and is not reported as a pass.

## Model and kernel gates

[The evidence summary](benchmarks/q4-wide-state-gates-20261003.json) records
checks, binary hashes and hashes of the preserved raw archives.

- MMVQ, wide BF16, IQ, grouped S2 and HC arithmetic fixtures passed their parity
  tests and Compute Sanitizer memcheck.
- The grouped S2 fixture also passed racecheck and synccheck.
- Real MTP versus serial state checks passed at widths **8, 12, 16, 18 and 24**,
  using output caps immediately below, at, above and beyond a complete window.
- At width 24, full oracle acceptance and forced rejection at each draft depth
  **0 through 22** passed. Tail/rejection checks at 12, 16 and 18 passed too.
- All **32 state test groups** passed: emitted tokens, consumed positions, and
  valid KV, recurrent, lookup and history state matched the serial reference.
- The capacity-8 control and capacity-24 build matched output and committed
  target state when both executed width 8.

State tests used **8,192 input tokens and 16,384 allocated context**. Their state
hash instrumentation invalidates throughput measurements. These checks do not
claim exhaustive floating-point, concurrency or cross-hardware correctness.

The separate **65,536-input-token** oracle and real-predictor throughput sweep
is running. No speed above the previously measured eight-position capacity is
claimed by this report yet. Known-answer oracle results must remain separate
from usable MTP or n-gram generation rates.
