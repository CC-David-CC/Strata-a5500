# Experimental GR and MMVQ alternatives

Current base: **upstream 0.1.34**. See the
[2026-10-02 rebase checks](benchmarks/2026-10-02-upstream-sync-experimental.md).
The performance tables and fleet/context matrix below were measured on **0.1.33**,
at the exact source commits listed. They remain historical evidence.

This is a contribution to [Niko1221/Strata](https://github.com/Niko1221/Strata),
based on 0.1.34 (`1678de3`). Strata's model support, expert cache and MTP are
upstream work. This patch changes two optional kernel launch paths.

Validation completed on all six fleet GPUs. Both alternatives remain opt-in.
The RTX PRO results below were measured from the focused source tree, not the
larger archived branch that was used during investigation.

## Changes

- `STRATA_GR_DOWN_MAX4=1` specializes per-thread token storage for windows of
  at most four tokens. It preserves upstream's block size, tile selection,
  accumulation order and plain/split/staged choice. Larger windows retain the
  existing implementation. The parity test requires bitwise-identical outputs.
- `STRATA_MMVQ_WARP1=1` maps one warp to a dense MMVQ output row. This avoids
  a reduction between warps. Floating-point association changes, so numerical
  parity is checked with a declared relative-L1 limit of `1e-5`; exact output
  tokens are not promised. The observed use case is the consumer RX 5500 XT 8GB.

Both options are off by default. They do not change weights, quantization,
expert selection, or the MTP acceptance threshold. Test options individually.

This branch contains no hardware-enablement or non-MTP serving changes. To test
the RX 5500 XT, combine it with `contrib/gfx1012-community`. Non-MTP serving is
the independent `contrib/non-mtp-serving` contribution. Combined test commits
are identified explicitly in the results.

## Enable an option for serving

Build this branch for your GPU. For example, with a CUDA toolchain installed
on Linux and an RTX 4090 (`89`; choose your GPU's architecture):

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DSTRATA_ENABLE_HIP=OFF -DCMAKE_CUDA_ARCHITECTURES=89
cmake --build build --target strata --parallel 4
```

For AMD, use the [HIP source-build instructions](AMD_HIP.md#build). Set the run
config's `exe` to the absolute path of that build's `strata` executable. The
alternatives are compiled into this branch; both runtime switches default to
zero (off).

In your existing run config, merge these keys into its `env` object to test GR
max4 alone. Keep all other config and environment entries:

```json
{
  "env": {
    "STRATA_GR_DOWN_MAX4": "1",
    "STRATA_MMVQ_WARP1": "0"
  }
}
```

For one-warp MMVQ alone, use `"STRATA_GR_DOWN_MAX4": "0"` and
`"STRATA_MMVQ_WARP1": "1"` instead. Start or restart with Strata's Python
environment and your edited config:

```sh
python -m serve.server --engine strata --config config.json --host 127.0.0.1 --port 8080
```

The server passes `env` to the native engine on both Windows and Linux. Config
values override inherited shell variables. For a Linux shell-only trial, when
the config does not already set these keys:

```sh
STRATA_GR_DOWN_MAX4=1 STRATA_MMVQ_WARP1=0 \
  python -m serve.server --engine strata --config config.json --host 127.0.0.1 --port 8080
```

Set both config values to `"0"` and restart to disable the alternatives. Restart
after every change because engine initialization and captured GPU graphs retain
the selected paths. For GR max4, the measured setting is `--spec 4`; windows
larger than four continue to use the existing implementation.

Check that `exe` names this branch's build and inspect the `args` and `env`
recorded by `tools/bench_mtp_modes.py` when verifying a trial. An upstream binary
does not implement these switches. Use the [reproduction checks](#reproduction)
for numerical validation; `STRATA_BENCH_ALLOW_ROUNDING` is only a test tolerance
switch and is not needed to serve requests.

## RTX PRO result at 64K input

[Full matrix, settings and build identities](benchmarks/2026-10-01-experimental-kernels.md).

Tested source: `99ec97520a2f3462e26770296aa1d569da629d48`.
Hardware: RTX PRO 6000 Blackwell 96GB, Ryzen 9 7950X, about 61 GiB usable RAM.
GSQ-RCO IQ3_S, Q8 KV, MTP4 at threshold 0.5; 65536 input tokens, 70656 allocated
context, up to 4096 output tokens. All 24576 experts fit the GPU in every arm.
These requests produced exactly the same output token IDs across the comparisons.

Untouched upstream ran before and after the candidate. Its mean is shown:

| Task | Actual output | Upstream generation | GR max4 generation | Generation gain | Upstream total | GR max4 total |
|---|---:|---:|---:|---:|---:|---:|
| Code | 2213 | 223.37 tok/s | 228.15 tok/s | 2.14% | 19.49 s | 19.32 s |
| Prose | 1756 | 160.21 tok/s | 164.07 tok/s | 2.41% | 20.50 s | 20.27 s |

Prefill remains about 9.5 seconds, so completion-time reductions are only 0.89%
and 1.08%. The focused branch with both options disabled measured 223.42 tok/s
for code and 160.36 tok/s for prose, within the two upstream observations.

Three additional default/max4 pairs, alternating order, reproduced the generation
gain. Each pair used the same binary and settings apart from the flag:

| Pair | Code default / max4 | Code gain | Prose default / max4 | Prose gain |
|---|---:|---:|---:|---:|
| 1 | 224.60 / 228.57 tok/s | 1.77% | 160.93 / 164.38 tok/s | 2.14% |
| 2 | 222.73 / 228.28 tok/s | 2.49% | 159.81 / 164.16 tok/s | 2.72% |
| 3 | 222.82 / 227.67 tok/s | 2.17% | 159.67 / 163.81 tok/s | 2.59% |

This is a small measured generation improvement on this workload and card.
Other architectures and the one-warp MMVQ path are reported below.

## RX 5500 XT one-warp MMVQ result at 8K input

Consumer Radeon RX 5500 XT **8GB**, Ryzen 5 3600, 56 GB installed RAM, HIP 5.7.1.
The combined hardware/serving/performance tree is `d37c41f`, with only
`STRATA_MMVQ_WARP1=1` enabled for the candidate. GSQ-RCO IQ3_S, Q8 KV, MTP4 at
threshold 0.5; 8192 input, 13312 allocated context, up to 4096 output.

The default path ran before and after the candidate. A and B generated identical
token sequences. The candidate generated different sequences and lengths:

| Task | A / B generation | Candidate generation | Gain versus A/B mean | Default / candidate output | Default mean / candidate total |
|---|---:|---:|---:|---:|---:|
| Code | 16.17 / 16.32 tok/s | 16.95 tok/s | 4.35% | 2688 / 2673 | 269.86 / 260.51 s |
| Prose | 13.06 / 13.09 tok/s | 13.52 tok/s | 3.41% | 1453 / 1601 | 210.96 / 218.57 s |

This is one A/B/A experiment. The prose completion took longer because it
generated more tokens; this is not an identical-output completion-time gain.
The generated code's TTLCache class passed the independent functional checks.
Those checks do not establish equivalent quality across tasks.

## Other GR max4 observations

These are single default/max4 pairs with **8192 input + exactly 512 counting
tokens**, 9728 allocated context, MTP4/threshold 0.5. They are a different
workload from the long code/prose tables. Output tokens matched within each pair.

| GPU | Default | GR max4 | Observed generation difference |
|---|---:|---:|---:|
| RTX 4090 24GB | 135.11 tok/s | 135.51 tok/s | +0.30% |
| RTX 3070 8GB | 44.37 tok/s | 44.35 tok/s | -0.03% |
| Tesla P4 8GB, one card | 23.64 tok/s | 24.05 tok/s | +1.74% |
| RX 7900 XTX 24GB, mapped experts | 19.36 tok/s | 17.91 tok/s | -7.48% |

These single pairs do not establish small gains. The RX 7900 XTX result is a
reason to retain its default path. No architecture-wide default is changed.

## Numerical validation

- GR max4: bitwise parity for windows 1 through 8, all three hyper-connection
  paths, pending-write and injection combinations, on all six GPUs.
- Default MMVQ: 182 real-tensor/column cases, including the native output
  projection, matched the single-column oracle bitwise on all six GPUs.
- RX 5500 XT one-warp MMVQ: all 182 cases passed the declared relative-L1
  limit of `1e-5`; the largest observed value was **1.29335e-7**. The seven
  output-projection column cases were included. The test caps individual
  tensor size at 1 GiB and tests supported native quantizations.

The output-projection coverage expansion is test-only commit `ac28acb`.
Its committed source was checked against its SHA256, linked against the tested
engine libraries, and run on every host. The engine binaries stayed unchanged;
both test and engine identities are recorded in the evidence. Kernel arithmetic
order can change token choices, so numerical parity is not an exact-token or
general answer-quality guarantee for the one-warp alternative.

## Reproduction

Use upstream's build instructions for the relevant GPU with
`-DSTRATA_BUILD_TESTS=ON`, then build `strata`, `gr_roofline`, and `mmvq_roofline`.

```sh
./build/gr_roofline
./build/mmvq_roofline /path/to/IQ3_S-shard-1.gguf --all-shapes
STRATA_MMVQ_WARP1=1 STRATA_BENCH_ALLOW_ROUNDING=1 \
  ./build/mmvq_roofline /path/to/IQ3_S-shard-1.gguf --all-shapes
```

`tools/bench_mtp_modes.py` uses a local model config and fixed prompt token IDs.
Use `--mode on` on this independent branch. Testing `--mode off` also requires
the serving contribution. For example, allocate at least 70656 context tokens
in the config, and run:

```sh
python tools/bench_mtp_modes.py --config config.json --output result-64k \
  --input-tokens 65536 --output-tokens 4096 --workload long \
  --mode on --cases coding writing
```

The matrix includes actual output lengths, prefill, first-token time,
generation rate, total completion time, effective throughput and correctness
checks. Model startup is excluded; the OS file cache is not reset. These are
execution measurements and functional smoke tests, not model-quality scores.

The RX 5500 XT validation also needs the community hardware patch. Its private
combined commit is `d37c41fa5bf5b7af0f08d1d8601ff021d77835a4`; recreate the exact
tree from the three published contribution commits:

```sh
git switch -c local-focused-gfx1012 99ec97520a2f3462e26770296aa1d569da629d48
git merge --no-edit dea58f12e0536eb03a4bd8c2266a38ffbd9d0e28
git merge --no-edit 4a6c47ef837e999f428a0740ecf769daa66fbe15
git rev-parse 'HEAD^{tree}'
# b72c14af85f910a519e9b5a43153be3fb6a202f3
```

The private commit's metadata differs from a locally recreated merge; the tree
hash identifies the source files. The RX 5500 XT kernel comparison uses 8192
input tokens and long code/prose outputs in baseline/warp1/baseline order.

The JSON also records the environment flags used for each arm. Replace
`${HOME}` and local model/build paths before reusing its configurations.
