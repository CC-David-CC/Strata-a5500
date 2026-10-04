# Experimental Q8 VRAM allocation comparison

An experimental configuration branch of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for the engine belongs to upstream and its contributors. The license
is retained and main is untouched.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0, FP16 KV and native 32K/128K contexts.

This branch compares using extra VRAM for a secondary cache of RAM experts
against more primary resident experts. The former avoids repeated uploads;
the latter can also reduce CPU work. It changes configuration and test
coverage, with no inference kernel or model-weight changes.

**Tests are pending.** The initial sixteen-entry capacity result motivates
this comparison; it is not a result for the new primary configurations.
See [memory budgets, invariants and required measurements](docs/Q8_CACHE_BUDGET.md).

The fresh build must match the previously tested engine bytes. Lifecycle checks
precede new throughput tests; placement-dependent output differences remain
visible in the report. Use upstream Strata for standard installation/support.
