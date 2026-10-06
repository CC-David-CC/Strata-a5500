# Focused publication checks

These checks passed on the measured RTX PRO; see the compact publication results.
They are correctness checks, not additional headline speed observations.

## Component memory/lifetime checks

Build these targets from this branch: `duplex_exchange_test`,
`layer_exchange_test`, `readonly_miss_cache_fixture`, `gpu_refill_fixture`,
`pdl_parity`. The exchange fixtures include early close/drain, delayed later
layers, repeated owner rotation, invalid whole-batch submission, source-byte
immutability and destination guards.

The queued command uses:

```sh
compute-sanitizer --tool memcheck --error-exitcode 99 --leak-check full /path/to/target
```

Add `--quick` for `readonly_miss_cache_fixture`. Set `STRATA_DF_PDL=1` for the
PDL check. Memcheck checks the exercised memory accesses; it is not a proof of
all global-memory scheduling, all model states or all supported hardware.

## Model checks

As in [timing reproduction](../reproduce/README.md), copy `case.py` and
`plan.json` to a writable directory, edit assets and set the engine/client
variables. Also set `COMBINED_OFF_ENGINE` to a build with
`-DSTRATA_DEEPGEMM_TAIL=OFF`.

The thirteen labels cover stock/combined default-off parity for all three models,
compiled-DeepGEMM-OFF parity for Q8, and cancellation at 7, 19 and 65 observed
tokens. Every cancellation must finish as `cancel` before the 2,048-token cap,
leave the engine alive, and allow the next arithmetic request to pass. The next
full request must read its complete prompt and emit all 512 requested tokens.

Fully resident Q4/IQ3_S also require exact next-request token parity with their
pre-cancellation reference. Dynamic Q8 placement can change arithmetic, so its
next-request difference is recorded rather than used as a state-digest proof.
No internal KV/recurrent/history digest is collected by these model checks.
The two extra Q8 controls test stock adaptive placement and fixed combined
placement; only the fixed placement control requires exact post-STOP tokens.

## DeepGEMM dispatch boundaries

`dg_dispatch_test.cpp` links against the measured `libstrata_dg_tail.a` and
CUDA runtime/driver libraries. It exercises 23 selector boundaries, including
the two losing large-tail shapes, signed extremes, capacity/null rejection and
default-off construction. It launches no expert product on its invalid-input
checks. This complements the real-tensor stage checks; it does not replace them.
