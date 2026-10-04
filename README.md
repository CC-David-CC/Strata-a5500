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

**The 32K MTP capacity gain repeated:** sixteen versus four secondary entries
improved coding +1.58% and editing +4.34% in reversed order, with exact tokens,
recorded work and primary exchange bytes. Initial gains were +1.67%/+3.98%.
Plain also repeated (+1.20% coding /+2.36% editing, versus +1.05%/+2.65%
initially), with exact tokens/work. Fresh build and all 22 normal/cancel/
checkpoint requests also passed.

The same extra weight-storage budget spent on primary experts reached
139.16 tok/s coding /121.50 editing, versus 137.51/123.36 for the larger
secondary cache. That placement changes output/work; details and effective
throughput are in the report. Native128K and the remaining
configurations are still running. These pairs have no confidence intervals.
See [memory budgets, invariants and required measurements](docs/Q8_CACHE_BUDGET.md).

The fresh build matches the previously tested engine bytes. Lifecycle checks
passed before the new throughput tests; placement-dependent output differences remain
visible in the report. Use upstream Strata for standard installation/support.
