# Logprobs qualification receipt

Implementation checkpoint: **`28cedda46d5d96e5fedf8a729ddbcd1c6a8d533b`**.
Branch: `work/logprobs-675`.
Worktree: `C:\Users\dflanag3\Documents\fleet\strata-logprobs`.
Base: upstream main `99f3dbd0b21d1401b3769e0c0d963913607f380b`, verified before
starting this independent attempt. Qualification ran October 3–4, 2026 UTC.

The new worktree leaves the Responses and GBNF worktrees intact. There was no
fetch, reset, stash or rebase. The build used an exported source tree on llm-49;
it did not switch another server checkout's branch. All owned test servers were
stopped afterward; the RTX 4090 returned to 9 MiB used.

## What changed

- Native persistent serving advertises `logprobs=raw-v1`. An opt-in, bounded `LP`
  record carries an output index, token ID, channel, selected raw logprob and 0–20
  alternatives. The ordinary `T` path remains when scores are disabled.
- The existing verifier's target row supplies a full-vocabulary FP64 normalizer.
  No extra inference pass is run to obtain selected/top-N scores. Output retention
  uses the same EOS/budget/acceptance boundary as model-state commitment.
- The service preserves typed metadata through tokenizer/parser alignment; JSON
  and SSE share `openai_chunks`. Authentication, FIFO, STOP and draining remain
  the existing service mechanisms. Old engines fail preflight.
- Native GBNF/JSON support was selectively reused, without the Responses adapter.
  Scored Chat `response_format` uses native constraints and mandatory full schema
  validation. It never repairs/reformats scored text. Existing unscored Chat's
  legacy structured-output behavior was not replaced.
- Opt-in server diagnostics distinguish MTP draft probabilities, target proposal
  scores and retained target output. They include rejected proposals, sequence
  sums, evaluated length, acceptance and EOS inclusion. These are diagnostics,
  not additional standard Chat fields.

Reuse source: `work/gbnf` at **`0c087036f59bedee17a2de6bef46b238236bc37e`**.
Ported responsibilities are persistent target-only serving, native compiler and
vocabulary/masks, scoped reasoning/tool constraints, bounded JSON compilation,
retained speculative prefixes, their tests, and the relevant Python adapter
methods. No Responses routes, storage, Codex profile or unrelated hardware work
was imported. The JSON validator was separated from Responses transport imports.

## Environment and identity

Linux inference: llm-49 / r4090, one RTX 4090 with 24,564 MiB, CUDA 13.3.73,
GCC 15.2, Release build, CUDA architecture 89. Model: local
Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M, INT8 KV, context 4096, prefill 256, mmap experts,
configured expert cache 6000, prompt cache 2, conversation-cache MiB 0,
adapt-swaps 0. Target mode uses `--spec 1` and no MTP. MTP uses `--spec 4`;
suffix adds `--suffix-draft 3`. Coupled uses `STRATA_SPEC_COUPLED=1`, temperature
0.8, seed 675, top-p 0.95, top-k 20. Other matrix modes use temperature zero.

Final grammar-enabled binary SHA256:
`6ea58d8eec0dafe24642eb6d9fa124ae1a31dfb5237529986231a999beb7423d`.
The earlier first-token prototype has SHA256
`392d84c48c9acca97397849abb0a08b8d1dcaeb44c592a591453754e6acfafc0`.
The [identity record](native/identity.json) includes full SHA256 hashes of both
model shards, expert profile, tokenizer assets and the final binary. Original
source was exported without `.git`; the commit above records the qualified code.

Grammar dependency: `xgrammar-0.2.8-strata-budget1-json1`, prepared by the committed
helper, with source and patch hashes checked by CMake. GGML source pin:
`3cf03257f219afbe7334045ff7c6a06ac68c627d`.

## Commands and results

Portable Python regression run on Windows:

```sh
python -m unittest serve.test_detok serve.test_lifecycle serve.test_logprobs serve.test_mcp serve.test_monitor serve.test_security serve.test_server serve.test_structured -q
```

**214 tests ran: 209 passed, 5 skipped** because their optional tokenizer fixtures are
absent. After the final parser-buffer change, the focused logprobs/detokenizer run
ran **27 tests: 22 passed, 5 skipped**. Synthetic score fixtures are explicitly labeled;
MockEngine never advertises real model probabilities.

Native build/test commands used the existing pinned dependency directories:

```sh
cmake -S source -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DCMAKE_CUDA_ARCHITECTURES=89 -DSTRATA_ENABLE_CUDA=ON -DSTRATA_ENABLE_GBNF=ON -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_BUILD_TESTS=ON -DSTRATA_GGML_DIR=/path/to/pinned/llama.cpp -DSTRATA_XGRAMMAR_DIR=/path/to/pinned/xgrammar
cmake --build build --target strata logprobs_test grammar_native_test grammar_speculation_test serve_input_test grammar_inspection_test grammar_speculation_gpu_test --parallel 8
ctest --test-dir build -R '^(logprobs_test|grammar_native_test|grammar_speculation_test|serve_input_test|grammar_inspection_test|grammar_speculation_(split|one_block|old))$' --output-on-failure
```

**All 8 native checks passed.** This includes an independent long-double oracle,
ties, extreme logits, selected/proposed IDs outside top-N, non-finite rejection,
grammar prefix/retention cases and all three GPU sampler variants. The grammar-off
build also compiled and returned scores in real JSON/SSE requests. Re-enabling
grammar restored the same final binary hash.

```sh
python tools/qualify_logprobs.py --config target.json --output evidence/target
python tools/qualify_logprobs.py --config mtp.json --output evidence/mtp
python tools/qualify_logprobs.py --config suffix.json --output evidence/suffix
STRATA_SPEC_COUPLED=1 python tools/qualify_logprobs.py --config coupled.json --output evidence/coupled --temperature 0.8
python tools/qualify_logprobs.py --config suffix.json --output evidence/examples --examples-only
python tools/qualify_logprob_edges.py --config suffix.json --output evidence/edges
```

| Qualification | Result / evidence |
| --- | --- |
| Baseline issue reproduction | JSON/SSE accepted scores but omitted them; [baseline response](native/baseline/json-response.txt). This used base Python with the existing GBNF binary, so it isolates the API omission and is not an upstream-native performance baseline. |
| Target-only, MTP, suffix enabled, coupled MTP | 24 HTTP requests each: **96 passed**, including intended 400s. [Target](native/target/results.json), [MTP](native/mtp/results.json), [suffix configuration](native/suffix/results.json), [coupled](native/coupled/results.json). |
| Published example files | **All 10 ran successfully**, plus two repetition requests. [Results](native/examples/results.json), [router](native/examples/router-response.txt), [tool call](native/examples/tool-call-response.txt), [tool result](native/examples/tool-result-response.txt). |
| Actual suffix verification | **7 suffix windows** in the separate edge trace. The initial suffix-enabled matrix selected MTP windows, so it alone did not qualify suffix scoring. [Receipt](native/edges/oracle.json). |
| Disconnects | Real disconnect during decode and during prefill; the next request returned its own valid scored `A` after draining. [Responses](native/edges/disconnects.json). |
| Selected token outside reported alternatives | GBNF forced `Z` while raw top five omitted it. The selected token still received its raw score. [Example](native/examples/grammar-response.txt). |
| JSON/reasoning/tools | Full schema and object validation, Unicode, native thinking budget, returned function call and subsequent tool-result input. [Thinking + JSON](native/examples/reasoning-json-response.txt). |

The protocol tests cover malformed/missing/duplicate scores, ordering, DONE counts,
old-engine preflight, strict option types, UTF-8 fragments, literal unfinished tags,
hidden reasoning/tools, explicit parser-boundary failure, auth and feature-off
behavior. The existing security/lifecycle suite covers the shared protections.

## Numerical evidence and replay limit

```sh
STRATA_LOGPROBS_TRACE=/absolute/path/trace.jsonl STRATA_LOGPROBS_RAW=/absolute/path/raw.bin python -m serve.server --engine strata --config strata.json
python tools/check_logprob_rows.py evidence/mtp --output evidence/mtp/oracle.json
```

Against the **same recorded raw target tensors**, Python's independent
`math.fsum` FP64 calculation matched within **2.132e-12 logprob**. The three
matrix captures checked 662 retained rows and 464 proposed-token rows, including
36 rejected/post-rejection rows. Sequence sums were checked separately.
[MTP oracle](native/mtp/oracle.json), [coupled oracle](native/coupled/oracle.json).
The edge capture added 68 retained and 55 proposal rows, including suffix work.

An independent target-only replay of three candidate-prefix rows preserved the
top decision and had a largest absolute probability difference of **1.892e-5**.
It was **not numerically identical**: one low-probability candidate changed by
**0.4347 in logprob**, from -12.36169 to -12.79640. The initial 0.05 logprob
tolerance failed. The receipt retains that failure and uses a separate 1e-4
absolute probability bound for cross-path replay; the strict same-tensor reducer
check was not relaxed. Re-prefilling generated context and changing native
window/cache paths can differ. [Exact comparison](native/edges/teacher-forced.json).

This independently evaluates the proposed prefix, not a corrected continuation.
Do not interpret this qualification as a promise that cached, cold, target-only
and speculative executions always return identical logits.

## Measured cost

Three alternating warmed pairs, 40 output tokens each, target-only, diagnostics
off: median native decode time **2771.4 ms without scores**, **2828.8 ms with
scores**: about **2.1%** in this small experiment. Same output token choices.
The transfer is 993,280 bytes per scored row for this 248,320-token vocabulary.
This supports keeping the simple CPU reducer for the qualified configuration;
a compact GPU reduction is deferred. This is not a broad throughput benchmark.

## Public artifacts and remaining gates

[All text requests/responses/traces as a ZIP](native-receipts.zip) retain the full
matrix without hundreds of expanded files in the source tree. Selected readable
receipts are linked above. Raw tensor files are reproducible test outputs;
their hashes are recorded, but the hundreds of megabytes of tensors are not
committed. There are no links to private server files or missing online artifacts.

Supported release scope: n=1, text input/output, target logprobs with optional native
grammar/JSON, returned client-owned function tools and ordinary reasoning boundaries.
Images, custom stop strings, logit bias, server MCP/legacy functions with scores,
Python-injected thinking wrap-up and mixed hidden/visible token boundaries are
explicitly unsupported. Native scored JSON requires its build capability and
mandatory validator. Draft top-N and a candidate-scoring HTTP endpoint are not
implemented. Draft/proposal scores currently use the server diagnostics.

Windows Python/API fixtures passed; Linux CUDA inference was qualified. Windows
native, HIP and multi-GPU inference were not qualified here. No universal Codex or
cross-backend probability-equivalence claim is made.

Next independent gate: review/publish this branch, then implement the separately
flagged [grammar steering design](../GRAMMAR_STEERING_PLAN.txt). Per-token grammar
updates are planned, not an implemented feature of this endpoint.
