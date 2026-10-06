# Community concurrency measurements on RTX PRO 6000 Blackwell

Measured on 2026-10-05/06 by [CC-David-CC](https://github.com/CC-David-CC).
Seven Flash-Next model/quant variants, 64K/128K actual input per request,
512 output tokens, FP16 KV. **118 completed cohorts / 800 requests / 409,600
committed output tokens.** Most configurations have one observation.

Measured source is the **experimental fork at `cd9fcca`**; current unmodified
upstream main was not benchmarked here. Engine changes are reviewed separately
in [#969](https://github.com/Niko1221/Strata/pull/969).

## Hardware and software

- RTX PRO 6000 Blackwell Workstation Edition, 96 GB VRAM, 400 W limit;
  Ryzen 9 7950X; 128 GB installed RAM; WD_BLACK SN8100 2 TB NVMe.
- Ubuntu 24.04.5 LTS, NVIDIA driver 595.91.07, CUDA toolkit 13.2.86.
  Software inventory captured on 2026-10-06 after testing; PCIe generation
  during inference was not recorded.
- Source build [cd9fccafd7b693734b7cd400f61d6bce2b7b74bc](https://github.com/CC-David-CC/Strata-a5500/tree/cd9fccafd7b693734b7cd400f61d6bce2b7b74bc),
  CUDA architecture 120. Source/binary/harness hashes are in the linked receipts.
- One benchmark engine at a time; no other GPU compute workloads.

## Configuration and timing

- Greedy sampling, thinking disabled, text only; no vision or n-gram speculation.
  Prompt reuse/conversation caching disabled. Every saved request actually reads
  65,536 or 131,072 tokens and generates 512 tokens.
- Shared weights and private states; prefill finishes before the measured common
  decode interval. Model loading is excluded from cohort time.
- Non-MTP uses up to eight physical verification rows. Grouped MTP proposes one
  token per request and verifies up to four requests/eight rows per window.
  Larger logical populations rotate through bounded windows.
- The fork includes concurrent MTP/waves, PDL/graph branches and Q8 support.
  Grouped decode uses the initial expert profile; it does not launch the optimized
  solo asynchronous-adaptation rounds. Allocated slots and active requests differ.
- Exact GGUF filenames, custom packs/profiles, launch arguments, environment,
  synthetic prompts, per-request timings and memory telemetry are in the pinned
  archive. Expert/PLE placement is also recorded per cohort in the CSV.

## Results

Cells are aggregate committed **decode / effective tok/s**. Effective includes
all prefill. These are combined output rates, not per-stream rates or speedup
factors over upstream. Both table columns allocate eight sessions.

### 65,536 input + 512 output; eight active requests

| Model | Non-MTP | Grouped MTP |
|---|---:|---:|
| GSQ IQ3_S | 299.2 / 26.26 | 280.3 / 26.00 |
| GSQ IQ3_XXS | 308.4 / 27.00 | 288.1 / 26.78 |
| GSQ Q2_0 | 320.9 / 28.88 | 298.8 / 28.57 |
| Pruned Coder IQ1_M | 244.0 / 28.74 | 226.7 / 28.30 |
| Unsloth UD-IQ1_M | 308.2 / 22.28 | 287.9 / 22.07 |
| Unsloth UD-Q4_K_XL | 248.5 / 18.28 | 237.6 / 18.14 |
| Unsloth Q8_0 | 67.9 / 3.82 | 68.4 / 3.82 |

![64k measurements](https://raw.githubusercontent.com/CC-David-CC/Strata-a5500/453310bce60466301e25cb69e77a142a17880605/bench/concurrency-20261005/64k/overview.png)

### 131,072 input + 512 output; eight active requests

| Model | Non-MTP | Grouped MTP |
|---|---:|---:|
| GSQ IQ3_S | 290.6 / 13.53 | 275.2 / 13.44 |
| GSQ IQ3_XXS | 298.8 / 13.98 | 281.0 / 13.85 |
| GSQ Q2_0 | 311.3 / 14.89 | 290.6 / 14.77 |
| Pruned Coder IQ1_M | 238.6 / 15.03 | 222.8 / 14.92 |
| Unsloth UD-IQ1_M | 299.4 / 11.25 | 282.6 / 11.20 |
| Unsloth UD-Q4_K_XL | 156.5 / 5.22 | 152.2 / 5.00 |
| Unsloth Q8_0 | 48.4 / 1.53 | not measured |

![128k measurements](https://raw.githubusercontent.com/CC-David-CC/Strata-a5500/453310bce60466301e25cb69e77a142a17880605/bench/concurrency-20261005/128k/overview.png)

## Failures and limits

- At 128K, two Q8 MTP attempts with 52.5 GiB requested GPU expert cache finished
  N=2 and failed during N=4 with `ERR verify: batch instantiate: out of memory`.
  Failed attempts are excluded from the successful CSV and retained in the archive.
- With a 40 GiB cache, Q8 MTP completed N=2 at **29.3 / 1.27** and N=4 at
  **38.7 / 1.29**, about 9.7 decode tok/s per stream on average. N=8 was deferred
  when testing stopped. This placement differs from Q8 non-MTP and does not isolate
  the effect of MTP. Q8 process swap was observed; sampled peaks are in the CSV.
- At 128K, reserving sixteen Q4 sessions reduced requested expert cache from
  52.75 to 24 GiB. With eight active requests, rates fell from **156.5 / 5.22**
  to **63.1 / 2.12**. The sixteen-active-request point was skipped by the recorded
  projected stream-rate threshold. Later 2K-output workloads were deferred.
- Some partially resident outputs differ across concurrency counts; causes are
  unclassified. No confidence intervals, answer-quality score, complete matched
  stock-control matrix or GPU sanitizer campaign is claimed.

## Data and reproduction

- [results.csv](results.csv): 118 successful cohorts. Rates are tok/s; durations
  seconds; expert/RAM cache GiB; sampled VRAM/swap MiB. `aggregate_decode_tok_s`
  uses the common steady interval; `aggregate_effective_tok_s` is all committed
  output divided by full cohort time. `summed_prefill_seconds` is summed engine
  prompt time. Loading is excluded; missing fields are empty.
- [64K evidence](https://github.com/CC-David-CC/Strata-a5500/blob/453310bce60466301e25cb69e77a142a17880605/bench/concurrency-20261005/64k/README.md) and [128K evidence](https://github.com/CC-David-CC/Strata-a5500/blob/453310bce60466301e25cb69e77a142a17880605/bench/concurrency-20261005/128k/README.md):
  JSON case/cohort labels match the CSV. Token hashes/differences, TTFT, latency,
  draft acceptance, failure receipts, exact configuration and raw-result hashes.
- [Harness, prompts, model plans and setup](https://github.com/CC-David-CC/Strata-a5500/blob/453310bce60466301e25cb69e77a142a17880605/bench/concurrency-20261005/README.md): use the measured
  fork source, input `65536` or `131072`, output `512`, and the archived placement.
- [Complete archive pinned at `453310b`](https://github.com/CC-David-CC/Strata-a5500/tree/453310bce60466301e25cb69e77a142a17880605).
  This PR stores only this summary and compact CSV; historical code, JSON, logs
  and plots stay in the contributor fork. Images above load from that pinned fork.

Credit: [Niko1221/Strata](https://github.com/Niko1221/Strata),
[rkcth #846](https://github.com/Niko1221/Strata/pull/846),
[Hardin22 #904](https://github.com/Niko1221/Strata/pull/904), and
[#947](https://github.com/Niko1221/Strata/pull/947).
