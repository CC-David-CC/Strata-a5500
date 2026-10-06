# Replay the ordinary timings

These scripts use Strata's private native stdin/stdout protocol. They do not
start an HTTP listener. Use an idle RTX PRO 6000 Blackwell 96GB and an environment
with Strata's Python requirements installed.

Build the stock engine from `1cbcacbcae2953f3be9edc46369f0c875bc6ab8b` and the
combined engine from this branch. The combined build uses the default-OFF
DeepGEMM option turned ON and the pinned external headers described in
[the component build instructions](../../q8-deepgemm-tail/README.md#build-and-use).
GGML was pinned to `3cf03257`; CUDA architecture was `120`; build type was Release.

Copy this directory into a writable experiment directory. Edit `plan.json` to
point to the three GGUF sets, compatibility packs and MTP pack already on your
machine. Keep the profile hash in [client provenance](../client-provenance.json)
if comparing against these measurements. No model files are supplied here.

Set these environment variables to your paths:

```sh
export PYTHON_BIN=/path/to/venv/bin/python
export STRATA_CLIENT_SOURCE=/path/to/Strata
export STOCK_ENGINE=/path/to/stock-build/strata
export COMBINED_ENGINE=/path/to/combined-build/strata
```

Example matched pair:

```sh
"$PYTHON_BIN" case.py q8-i32768-mtp-stock
"$PYTHON_BIN" case.py q8-i32768-mtp-combined
"$PYTHON_BIN" analyze_matrix.py .
```

Run labels sequentially. `plan.json` lists all 48 points and their activation
flags. Each case creates a new result directory and refuses to overwrite one.
The result includes exact input count, token IDs, work counters, engine hash,
CPU ticks, activation checks and timings. The analyzer retains the first token
difference and every work-counter difference.

The published timings used an earlier frozen Python client, whose relevant
file hashes are recorded separately. The publication checks use the Python
client from the combined branch. Do not describe a new replay using a different
client/build as the original measurement series.

The runner requests exactly 1,024 output tokens, temperature zero, thinking off,
and a deliberately unavailable EOS ID. It checks a short arithmetic function;
it does not execute or score the long generated module. Prompt/conversation
reuse is disabled. The first matrix holds prefill chunks at 8,192; separate 16K
prefill and blocking-refill profiles are in the configuration/evidence files.
