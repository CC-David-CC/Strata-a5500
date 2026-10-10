# Disk-tier root retention: follow-up on the rebased branch

The root-retention explanation in [konijiwa110/Strata#1](https://github.com/konijiwa110/Strata/pull/1) was correct.
The current branch already saves a persistent root, and the previous proposal's replacement-file rule prevented
ordinary streamed turn-back cleanup. That rule is **not** in this candidate. `drop_superseded` is unchanged.

The remaining reproduced failure was serving **without MTP**: streamed save tried to capture an uninitialized
draft K/V ring and refused with `conversation snapshot: invalid K/V extent`. The candidate passes an absent
draft explicitly through snapshot capture, read limits, validation and restore, including persistent root saves.
The same optional-draft handling is applied to SYCL's existing session save/restore path.

## Source and scope

- Baseline: `konijiwa110/Strata:conv-disk-tier`, `42cb9558cc3bb0c794013cb11a9c42c7b2971298`.
- Current main at both fetches: `fb58e0dbc8399662c0e47c76578c6e878b14f6cf`; already an ancestor of that baseline.
- Candidate: `fix/disk-tier-optional-mtp`, `bdb3438ec9ffc05726839d3966726d726aa31dfb`.
- The optional-draft fix was adapted from `e6da7e11`; the broad retention patch was not ported.
- Seven changed code/test files. These measurement files live on a separate evidence branch, not the PR branch.
- Other private branching/bookmark and RAM-wait policy changes were not combined with this correction.

## Tests and an important correction to the old probe

The original workload uses an 8,191-token shared prefix, eight changing 100-token suffixes, unrelated requests,
an automatic return, and an explicit session restore control. Replies are capped at 128 tokens.
The legacy `*-pinned` arms requested a pin, but their warm-up prompt ended exactly at the pin, which the engine
correctly rejected. Their logs remain here for reproducibility; **they are not evidence of a successful pin**.

`probe_effective_pin.py` fixes the warm-up by appending a short request beyond the prefix. It checks for ignored
pins, asserts reuse of all 8,191 tokens, checks the persistent prefix save on streamed paths, restarts the engine,
and checks reuse again. No old measurements have been relabeled as successful pin tests.

Three modes are exercised, with MTP off and on:

| Mode | RAM budget / slots | Disk budget | Purpose |
|---|---:|---:|---|
| Disk only | Disabled | 4,096 MiB | Streamed saves and persistent roots |
| RAM + disk | 4,096 MiB / 1 | 4,096 MiB | Parking, eviction and asynchronous spills |
| RAM fallback | 1 MiB / 1 | 4,096 MiB | Force RAM refusal and the streamed fallback |

The original candidate matrix completed 156 generations. The corrected pinned/restart matrix completed another
84, with no save/restore failures or failed reuse assertions. A repeat added 13 more (253 candidate generations total).
The unchanged baseline failed both MTP-off disk-only saves;
its MTP-on runs already recovered the ordinary root (8,176 tokens) and the correctly pinned root (8,191 tokens).
No new retention predicate was needed for these workloads.

The new CPU regression writes two successive turns using `session_checkpoints_to_save`, so only the deepest
checkpoint reaches each file. It confirms that the old payload and sidecar are removed. Putting the old broad
rule back, while retaining the new prefix-entry guard, fails exactly this assertion; see `negative-test.log`.
The tests also check persistent root matching after reopening and both cleanup call shapes (with/without `keep`).

## Timing examples

Single observations from the corrected pin workload, on a warm filesystem cache. These are engine prompt-work
times, including cache handling; they are not isolated disk bandwidth, HTTP TTFT, or latency percentiles.
The candidate adds no MTP-on speed claim: the baseline's root preservation already works.

| Mode | MTP | Baseline automatic return | Candidate automatic return | Candidate reused tokens |
|---|---|---:|---:|---:|
| Disk only | Off | Save refused | 630.0 ms | 8,191 |
| Disk only | On | 605.1 ms | 598.9 ms | 8,191 |
| RAM + disk | Off | Not run | 257.6 ms | 8,191 |
| RAM + disk | On | 235.5 ms | 236.6 ms | 8,191 |
| RAM fallback | Off | Not run | 626.3 ms | 8,191 |
| RAM fallback | On | 605.9 ms | 599.7 ms | 8,191 |

## Build and correctness checks

- Full CUDA, HIP (`gfx1100`) and SYCL builds passed.
- Five CUDA-build host cache/session test executables passed; spill: 116 checks; validation: 1,068 checks.
- HIP-build host spill/validation tests passed. These are host tests, not HIP inference measurements.
- SYCL validation is compilation only. This does not claim the fork's disk-tier serving integration exists in SYCL.
- All 42 properly pinned baseline/candidate token comparisons matched, including restarts.
- All 38 automatic-versus-explicit/restart token comparisons matched, including the repeat runs.
- Compare integer token IDs only: `StrataEngine.generate` also yields `None` heartbeat events.
- Five of the first 122 baseline/candidate comparisons differed, all in the original MTP-on, unpinned forced-fallback
  arm. Repeating that arm changed the same five requests on the **unchanged baseline** (8/13 exact), and on the
  candidate (8/13 exact). The repeated baseline/candidate comparison was also 8/13 exact; total paired comparisons
  were 125/135 exact. This demonstrates run-to-run variation already exists on the baseline; it does not establish
  its cause or prove equivalence in every unpinned fallback request. See `repeat-status.json` and `summary.json`.
  The differing outputs are retained; do not infer universal bitwise reproducibility from functional cache passes.

## Machine and reproduction

RTX PRO 6000 Blackwell 96 GB, Ryzen 9 7950X, about 125 GiB RAM, WD Black SN8100 NVMe; Ubuntu 24.04.5,
kernel 7.0.0-34, NVIDIA 595.91.07, CUDA 13.2. See `hardware.json` and the configurations for details.
Model: ISTA-DASLab Qwen3.8-Flash-Next GSQ-RCO IQ3_XXS, two GGUF shards totaling 75,839,998,528 bytes.
INT8 K/V, 32,768 max context, `--prefill auto:8192`, temperature zero, suffix drafting disabled, MTP-on `--spec 4`.
Both builds use the same local model files, pack, tokenizer and expert profile. There are no model weights here.
The unused template spill-directory value in the published configs is a placeholder; the probes replace it with
their own output directory. Effective paths appear in the engine logs.

Builds used CMake with `STRATA_BUILD_CONVERSATION_TESTS=ON`; CUDA added `STRATA_ENABLE_CUDA=ON`,
`CMAKE_CUDA_ARCHITECTURES=120`, and `/usr/local/cuda-13.2/bin/nvcc`. HIP used `STRATA_ENABLE_HIP=ON`,
`CMAKE_HIP_ARCHITECTURES=gfx1100`, and `/opt/rocm`. SYCL configured the separate `sycl/` project with Intel
2026.1 `icx`/`icpx` after sourcing `/opt/intel/oneapi/setvars.sh`. Full `strata` targets were linked on each.

Install `regex` and `jinja2` in a Python environment. Adjust the model/toolchain paths in the supplied config,
then run (repeat with `ram` and `ram-fallback`; omit `--mtp` for an MTP-off-only run):

```sh
python probe_extended.py --source /path/to/Strata --config config.json \
  --output results --cache-mode disk --mtp /path/to/mtp/runtime
python probe_effective_pin.py --source /path/to/Strata --config config.json \
  --output pinned-results --cache-mode disk --mtp /path/to/mtp/runtime
```

Each probe writes rows, token events and engine logs, and deletes only its own disposable session files afterward.
This is an 8K-prefix regression study, not a long-context soak, multi-GPU test, cold-disk benchmark, power-loss
durability test, or proof of output equivalence for all cache formats and workloads.
