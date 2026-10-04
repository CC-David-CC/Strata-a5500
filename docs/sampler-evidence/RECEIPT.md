# Ordered sampler qualification

Implementation: `dbdfda4aafe306c6c7da47eac8106d6bcd45636c` on `work/samplers`.
Base: `2243cb1c5b1a87270731d8b8a76e4af001f96f97` (`work/logprobs-675`).
Local worktree: `C:/Users/dflanag3/Documents/fleet/strata-samplers`.
Only llm-49 was used for native testing. The original checkouts were left intact.

## Responsibilities changed

- The native serving driver optionally selects a token from its existing raw
  target row using an ordered CPU reference profile before commit and feedback.
- A pure selector owns filters, deterministic draw lanes and stage statistics.
- The HTTP boundary validates the capability and rejects incompatible profiles
  before streaming. Typed receipts attach to the same scored content tokens in
  JSON and SSE. Raw target logprobs retain their existing meaning.
- The existing service owns model execution, serialization, grammar phases,
  caching, cancellation and engine-output draining. No inference scheduler or
  web framework was added.

## Environment and results

Native: RTX 4090, Linux, CUDA 13.3.73, GCC 15.2, release build, architecture 89.
Model: Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M, int8 KV, context 4096, prefill 256,
mmap experts, adaptation disabled. Windows Python 3.13 was the HTTP client.
[Source and binary hashes](identity.json) identify the tested artifact.

| Gate | Result / evidence |
| --- | --- |
| Python HTTP/service/structured/lifecycle suite | 169 tests, 139 subtests passed; final sampler-only rerun: 16 tests, 24 subtests passed |
| Analytical CPU selector | Full vocabulary, exact probabilities, operator order, mask boundaries, masked NaN, XTC singleton, validation and 20,000 reproducible draws passed |
| Existing CUDA sampler paths | Split, one-block and legacy parity passed |
| Native grammar regressions | Grammar compiler and grammar sampler passed; separate GPU speculation test passed 1,728 fixed-logit/counter cases |
| Actual target-only HTTP | [15 cases](http/result.json): six ordered profiles, six grammar combinations, strict JSON, SSE, selection without logprobs |
| Actual MTP/coupled/suffix-configured HTTP | [The same 15 cases](spec/result.json); ordered profiles use target-only selection |
| STOP/draining and next request | [Target-only](target/lifecycle.json) and [speculative configuration](spec/lifecycle.json) passed |
| Ordinary speculation restored | [Native trace](spec/native-trace.jsonl) contains proposal rows after the ordered request; [server config](spec/server-config.json) records spec 4, coupled MTP and suffix 4 |
| Independent FP64 oracle | [Full-row comparison](oracle.json), six captured vocabulary rows, tolerance 1e-9 |

The full-vocabulary oracle compares raw log-softmax, all stage candidate counts
and entropies, final selected probability and final top probabilities. It uses
independent Python arithmetic on the exact captured FP32 tensor. These are
arithmetic checks, not claims about model calibration or task intelligence.

The model output differed between some target-only and speculative-server
configurations. Different native execution shapes can change logits; no seed-only
cross-path identity is claimed. The ordered operator semantics remain the same.

## Reproduction commands

```text
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude src/program/ordered_sampler_test.cpp -o ordered_sampler_test
./ordered_sampler_test
cmake --build build -j 12 --target strata ordered_sampler_test sampler_parity logprobs_test grammar_native_test grammar_sampler_test grammar_speculation_gpu_test
ctest --test-dir build -R "^(ordered_sampler_test|sampler_parity|sampler_parity_one_block|sampler_parity_old|logprobs_test|grammar_native_test|grammar_sampler_test)$" --output-on-failure
./build/grammar_speculation_gpu_test
python -m pytest -q serve/test_sampling.py serve/test_logprobs.py serve/test_server.py serve/test_lifecycle.py serve/test_structured.py
python tools/test_ordered_samplers_native.py --base-url http://127.0.0.1:18765 --output evidence/http
python tools/check_sampler_lifecycle.py --base-url http://127.0.0.1:18765 --output evidence/lifecycle
python tools/check_sampler_oracle.py docs/sampler-evidence/first-rows.bin.gz docs/sampler-evidence/http/result.json --output evidence/oracle.json
```

[CTest output](native-tests.txt), raw JSON/SSE response files next to each HTTP
result, and the compressed [six-row tensor fixture](first-rows.bin.gz) are retained.
Native diagnostic environment variables were used only while recording evidence;
the educational lab runs without writing raw logit tensors on every request.

## Limitations and next gate

This is a CPU selection reference, with one vocabulary-row transfer per generated
token. `selection_ms` reports host selection only; it excludes row copy, inference
and queue time. Inspection itself computes stage statistics. See the actual per-
case costs in the oracle and receipts; this is not an optimized GPU roofline.

Only Linux NVIDIA native execution was qualified; Windows was the client. DRY,
DynaTemp, Mirostat and sampled speculative verification with the new chain are
not implemented. The ordinary existing speculative path remains available on
requests without the profile. Next: use this tested dependency in the educational
Control Lab, then qualify any GPU optimization against these same-tensor fixtures.
