# Concurrent-serving research snapshot

**Update: [the full 64K initial screen is archived here](64k/README.md).**

This folder supports the focused `contrib/concurrent-mtp-waves` draft. The engine
used for the historical 32K/64K matrix is `cd9fcca`, immediately before this
evidence commit. It includes other experiments and is not the minimal PR diff.
Research continues; this folder is a dated snapshot, not a claim that all tests
or contexts have finished.

**Q4 at actual 32K input + 512 output per request:** grouped MTP reached
**275.8 aggregate decode tok/s with eight requests**, **35.7 effective tok/s**.
Hardware: RTX PRO 6000 Blackwell Workstation 96 GB, 400 W, Ryzen 9 7950X,
128 GB RAM, FP16 KV. These are committed output rates across all streams.

- `research-receipt.json`: completed 32K and initial IQ3 64K cohorts, compact
  timings, memory observations, token hashes and first-divergence records.
- `reproduce.py` and `client_helpers.py`: the timing harness with configurable
  source/model/output paths. They retain the original prompt construction and
  committed-token accounting. Path configuration was generalized for this archive;
  this is not a claim that its file hash equals the historical harness hash.
- `plans/`: synthetic task text and model launch templates. No weights, credentials
  or private prompts are included. Set the four path variables below.

## Run the focused comparison

Use the Python environment installed by Strata, with the model, native pack and
MTP runtime already prepared. Build the focused branch normally. `ROOT` below
is that checkout, and `ARCHIVE` is this folder from the research checkout.
The GPU must be free of other compute work. RAM PLE needs a sufficient locked-memory
limit; configure that through the system's normal account limits before running.

```bash
ROOT=/path/to/focused-strata-checkout
ARCHIVE=/path/to/research-checkout/bench/concurrency-20261005
export PACK=/path/to/q4-native-pack
export NATIVE=/path/to/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf
export MTP=/path/to/mtp/rt
export PROFILE="$ROOT/data/expert-profile.bin"
export STRATA_BENCH_SOURCE="$ROOT"
export STRATA_BENCH_ENGINE_ROOT="$ROOT"
export STRATA_BENCH_EXE="$ROOT/build/strata"
export STRATA_BENCH_OUTPUT="$PWD/concurrency-results"

python "$ARCHIVE/reproduce.py" --model unsloth_q4 --policy mtp \
  --input 32768 --output 512 --capacity 8 --counts 2,4,8 \
  --placement full --cache-gib 71.75 --ple-mode ram --label q4-32k-mtp
python "$ARCHIVE/reproduce.py" --model unsloth_q4 --policy nomtp \
  --input 32768 --output 512 --capacity 8 --counts 2,4,8 \
  --placement full --cache-gib 71.75 --ple-mode ram --label q4-32k-nomtp
```

Use a new label for every run; the harness refuses to overwrite an existing
case. It uses the engine protocol internally and opens no HTTP endpoint.
The historical integration also enabled PDL/independent graph branches from
Hardin22's PR #904. Reproducing that integration requires the research engine and
`STRATA_BENCH_PDL=1 STRATA_BENCH_GRAPH_BRANCHES=1`. The focused branch omits those
changes. Q8 additionally needs the reader from PR #865, present in the research
engine. For IQ3_S waves, change the model paths, use `--model iq3_s`,
`--cache-gib 46.86 --input 8192 --capacity 16 --counts 8,12,16 --policy nomtp`.

## Limits

These are screening observations. Higher slot counts rotate through eight
physical verifier rows; they do not increase kernel width. Effective throughput
includes all prefills. Q8 and reduced-cache Q4 token differences remain
unclassified, and Q8 showed process swap. No numerical-equivalence, answer-quality,
multi-GPU or GPU-sanitizer claim follows from successful request completion.
Most points have one observation. No repeat-validation jobs are scheduled in this
roofline branch; distinct context/output exploration continues separately.
