# Experimental Q8 host and PCIe optimization

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata, the model engine and its existing kernels belongs to the upstream
project and its contributors. This branch adds opt-in host scheduling experiments
and overlapping expert transfers. It is not an upstream release.

## Measured result

On an **NVIDIA RTX PRO 6000 Blackwell Workstation Edition, 96 GB**, with a
Ryzen 9 7950X and 128 GB RAM, duplex expert copies improved **MTP decode throughput
by 5.6?7.2% in the reversed-order comparisons below**, on top of buffer ownership
rotation. These are full **Unsloth Qwen3.8-Flash-Next Q8_0** tests with **FP16 KV**
and native RoPE. Each request generated 1,024 tokens.

| Actual input / task | Ownership baseline | + Duplex copies | Decode gain |
|---|---:|---:|---:|
| 32,768 / coding | 121.77 tok/s | 130.51 tok/s | +7.18% |
| 32,768 / editing | 105.53 | 112.21 | +6.33% |
| 131,072 / coding | 124.95 | 131.93 | +5.58% |
| 131,072 / editing | 100.30 | 106.12 | +5.80% |

Every output token and recorded work counter matched within these comparisons.
Both arms used the same binary, fixed 15,472 GPU expert slots, 75.25 GiB of GPU
expert storage and a 44.28 GiB pinned RAM complement. The candidate ran before
the control in these repeats. Initial control-before-candidate measurements
also improved. Prefill-inclusive gains are smaller; see the complete report.

**[Results, effective throughput, correctness limits and next experiments](docs/Q8_HOST_CRITICAL_PATH.md)**

## What changes

- `STRATA_EXCHANGE_DUPLEX=1`: overlap opposite-direction copies for different
  expert slots. A slot is overwritten only after its outgoing bytes are saved.
- `STRATA_ADAPT_WORKER=1`: retain one adaptive worker. Alone, this did not produce
  a material speed improvement. CPU placement remains a separate experiment.
- `STRATA_HOST_TIMING=1`: report host waits, copy bytes and related timings.

The optimized path requires one GPU and a pinned resident expert complement.
Tests use `STRATA_EXCHANGE_ROTATE=1` and `STRATA_ADAPT_NOWAIT=0`; all required
completion waits remain. These optimization switches default off. Other
placements retain the existing exchange path. HIP execution was not tested.

Plain, MTP, n-gram and combined modes were measured separately. N-gram policy
choices can change with timing: some coding outputs differed, and matching
editing output sometimes required different work. Those rows are qualified in
the report, not presented as exact-work kernel gains.

This branch preserves the upstream license. For the main project, installation
and supported configurations, use **[upstream Strata](https://github.com/Niko1221/Strata)**.
