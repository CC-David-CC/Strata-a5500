# Experimental ordinary-RoPE to YaRN 4x session migration

Strata already supports starting an engine with YaRN. This feature adds an
explicit conversion of a saved ordinary-RoPE session into **approximate YaRN
history**, avoiding a fresh prefill of every saved token. It does not make the
result equivalent to computing the entire conversation under YaRN.

No default changes. The feature requires `--experimental-rope-yarn4-cache` on
both the source and target engine, with `STRATA_ROPE_TABLE=1` in both engine
environments. The default analytic fast-math caches are rejected: their angles
can differ from the table coefficients. It is experimental, limited to text-only
single-GPU FP16 KV with MTP and batching off, and requires
`--conversation-cache-mib 0`. CUDA and HIP share one host converter. The SYCL
engine's separate entry point does not expose this operation.

## Use the existing session endpoint

Build this branch's native engine first and set the configuration's `exe` to
the absolute path of that new `build/strata` binary. In an existing **single-GPU** server
configuration, keep the model paths and tokenizer, remove `--mtp <path>` from
the engine's `args`, and replace conflicting KV/context/RoPE options with:

```text
--experimental-rope-yarn4-cache --kv fp16 --conversation-cache-mib 0
--max-context 262400 --rope-scaling none
```

Save that configuration as `source.json`. Start it with the existing Python
environment (add your normal API-key option if needed):

```sh
export STRATA_ROPE_TABLE=1
python -m serve.server --engine strata --config source.json \
  --slot-save-path ./sessions --port 8080
```

For `target.json`, copy the same configuration, keep the experimental flag, and
replace the last line of engine arguments with:

```text
--max-context 1048832 --rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 262144
```

These capacities include headroom; allocating 1M is not a claim that migration
has been tested through a full 1M continuation. The initial probe below uses
only 4K before attempting larger allocations.

After a source chat has completed, save it:

```sh
export API=http://127.0.0.1:8080
curl "$API/slots/0?action=save" \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"filename":"ordinary.sess"}'
```

Stop the source server. Start the target using the same command with
`--config target.json`, then migrate:

```sh
curl "$API/slots/0?action=migrate_yarn4" \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"filename":"ordinary.sess","source_context":262400}'
```

`source_context` is the source engine's **allocation capacity**, not the number
of saved tokens or an inferred trained-context size. The target capacity may
grow; other state-affecting settings must match. Ordinary-source knobs must be
the engine's resolved ordinary defaults, with the same frequency base as the
target. Unsupported profiles are refused by the session fingerprint.

The source file is retained. The result is written atomically as
`ordinary.sess.yarn4`, then restored through the normal session validation path.
An existing destination is refused. Success reports
`"approximate_migrated_history": true`; later SAVE and RESTORE preserve this
provenance. Duplicate conversion is refused.

Continue through `/v1/chat/completions` with the **full recorded conversation
plus the new user message**, `"max_tokens":128`, and `"temperature":0`. Keep
`STRATA_ROPE_TABLE=1` in the target engine environment as well. Keep
the same tokenizer, chat template, and thinking setting. The restored prefix
is reused where it matches; the server still needs the canonical history in
the request. This endpoint does not add a new conversation-ID API.

The native protocol equivalent is:

```text
MIGRATE_YARN4 <source-allocation-capacity> <source-session-path>
```

This is **not an in-place change of a running engine's RoPE configuration**.
GPU graphs are built for the target at startup. Do not sample cached logits
computed under ordinary RoPE: replay the boundary token(s) under the target
first. The supplied probe saves a prefix ending one token before the prompt
boundary, verifies the saved token receipt, then processes that boundary token
before generating a reply.

## What is converted

The converter uses the backend's actual post-RoPE key representation and YaRN
frequency ramp. Only the existing table-coefficient execution path is supported;
its opt-in setting is recorded in the experimental session fingerprint. For each NEOX key pair it applies the source-to-target rotation
and key-side magnitude ratio once. Non-rotary key components stay unchanged.
Paged FP16 main keys, completed FP32 pooled indexer keys at their block-start
positions, and position-zero spare/dead indexer keys are covered.

Values, recurrent GDN state, PLE state, unrotated raw tails, canonical tokens,
and absolute positions are retained. Deeper-layer values and recurrent state
still reflect the original attention computations. **Coordinate correctness
does not establish continuation quality.** Exact replay from canonical tokens
is the fallback when approximation is unacceptable.

The supported geometry is the current Qwen4exp hybrid QSA/GDN layout: 24 query
heads, 2 KV heads, head dimension 256, and 64 rotary dimensions. Other layouts,
layer splits, multimodal state, MTP, BF16, quantized KV (INT8, rotated INT8,
Q4_0 and K8V4), and inconsistent model/settings are refused.

## Integrity, memory, and compatibility

Both engines fingerprint all model-file bytes in experimental mode. This is
Strata's 64-bit integrity fingerprint, not a cryptographic authenticity claim.
It costs a full model read on the first session operation; the result is
cached for the process. Normal mode retains its existing sampled identity.
Sessions written without the experimental identity mode are incompatible.

The host converter stages only changed key/indexer buffers before committing;
it does not require a second GPU KV pool. Reading the source and staging it
still require substantial RAM. Admission conservatively reserves twice the
session read estimate plus 4 GiB; the mainline restore subsequently reads the
converted session into host memory. Insufficient resources fail explicitly.
A device-transfer failure during native restore stops the engine rather than
continuing from partially replaced state.

Ordinary session saves keep format v1. Migrated saves use v2 and preserve source
and target configuration fingerprints plus the initial migrated prefix length.
Older engines reject v2. Model files must not change while the engine is running.
Without the experimental flag, ordinary session fingerprints and v1 format are
unchanged. Normal inference settings are unchanged.
The necessary MTP-off save/restore fix omits the unallocated draft layer;
MTP-enabled session layout is unchanged.

## Tests and reproduction

The deterministic FP64 oracle is independent of the converter. It covers the
requested absolute positions through 262143, nonzero offsets, YaRN frequency
regions, FP16 rounding, non-rotary dimensions, attention scores and outputs.
Session tests cover incompatibility, failure atomicity, unchanged values,
provenance, save/reload, and duplicate conversion. HTTP tests exercise the
explicit operation and refusal responses.

```sh
cmake -S . -B build -DSTRATA_ENABLE_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DSTRATA_BUILD_CONVERSATION_TESTS=ON
cmake --build build -j8 --target strata rope_cache_migration_test rope_parity
ctest --test-dir build --output-on-failure -R 'rope_cache_migration_test|rope_parity'
python -m unittest serve.test_slots
python tools/bench_rope_migration.py --config strata.json \
  --output /tmp/new-migration-probe --compare
```

The probe sets `STRATA_ROPE_TABLE=1` on every execution path and records all failures, exact output text and per-position distributions
using an opt-in bounded diagnostic (`STRATA_MIGRATION_LOGITS`, enabled alongside
`STRATA_LOGPOS`). It compares fresh YaRN, converted ordinary state, exact YaRN
replay, and ordinary RoPE at a larger allocation. Quality differences are
measurements, not automatic pass/fail thresholds. Do not confuse a configured
1M capacity, a fresh 1M YaRN run, and migration followed by continuation to 1M.
The last of these remains unverified. No automatic switching policy is proposed.

Measured CUDA/HIP lifecycle checks and timing/quality differences are documented
in the [migration report](../bench/results/2026-10-09-rope-cache-migration/README.md).
