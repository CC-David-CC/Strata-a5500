# Experimental Q8 GPU cache allocation results

An experimental configuration branch of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for the engine belongs to upstream and its contributors. The upstream
license is retained; main is untouched.

**RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X, 128GB RAM.
Full Unsloth **Q8_0, FP16 KV, native 32K/128K prompts + 1,024 output tokens**.
This compares configurations of the same measured engine; it adds no inference
kernel change relative to this fork's copy-grid baseline.

## Larger secondary cache

Four to sixteen entries per layer, with unchanged primary residency:

| Input / mode | Coding gain | Editing gain |
|---|---:|---:|
| 32K / plain | +1.20% | +2.36% |
| 32K / mtp | +1.58% | +4.34% |
| 128K / plain | +1.05% | +1.98% |
| 128K / mtp | +1.42% | +3.19% |

Tokens and recorded work matched exactly. The 32K gains repeated in both test
orders; 128K has one pair per mode. All fifteen follow-up configurations and
22 lifecycle requests passed. The report also retains initial measurements,
n-gram/combined results, effective throughput and memory use.

Spending the same spare VRAM on more primary experts is a competing path; it
changes CPU/GPU arithmetic placement and sometimes output/work. Those results
are qualified separately.

## More primary experts at 32K

The larger 16,560-primary/four-secondary MTP configuration reached **145.68
tok/s coding and 127.46 editing**, versus 135.38/118.23 with 15,472 primary
experts: **+7.61% / +7.80% generation**, and **+9.47% / +9.46% including
prefill**. It uses an additional 5,418.75MiB of expert storage and had 2,000MiB
free at the lowest GPU sample (1,440MiB in the engine startup report).

This is one qualified pair: coding first differed at output token 120;
editing output matched, but recorded work differed for both. It was tested
at 32K only. No answer-quality equivalence or confidence interval is claimed.
The 32K lifecycle gate does not establish 128K checkpoint coverage.

See the **[complete measured matrix and limits](docs/Q8_CACHE_BUDGET.md#complete-allocation-comparison)**.
Use upstream Strata for standard installation and support.
