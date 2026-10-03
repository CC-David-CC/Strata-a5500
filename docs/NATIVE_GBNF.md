# Native grammar contribution

This branch starts at the passing stateless Responses checkpoint
`96092670da0dc3c1cfcce99bb90a3e6ca25ae1d9`. The
[Responses guide](RESPONSES.md) documents the experimental route, installation,
replay key and tested local Codex profile. Responses remains disabled by default;
enable it with `--experimental-responses` or `"experimental_responses": true`.

## G0: persistent target-only generation

In the existing server configuration's `args` array, use `"--spec", "1"` and
remove the `"--mtp", "..."` pair. Keep the model, tokenizer, expert profile,
prefill, GPU and other ordinary server settings. No new server is needed:

```text
python -m serve.server --engine strata --config strata-local.json
```

`--serve --spec 1` uses one-position verification and selection in the existing
native decoder. It loads no MTP weights and produces no suffix proposals. The
default suffix setting applies only to speculative serving. An explicitly
positive `--suffix-draft`, `--mtp`, positive `--mtp-max-t`, `--coupled-draft` or
`--spec-oracle` conflicts with this mode and is rejected before model loading.
Use `--no-coupled-draft` if the machine has enabled coupled drafting through
`STRATA_SPEC_COUPLED`.

Keep `--conversation-cache-mib 0` (the default). Parked conversations currently
need MTP KV state. Live prompt-prefix reuse and the ordinary `--prompt-cache`
checkpoints work without MTP. The server retains its existing request queue,
cancellation, output draining and engine restart behavior.

Engine `INFO` diagnostics report `decode_mode=target`, `spec=1`, `lookup=0`,
`mtp_loaded=0` and `mtp_vram_mib=0.0`, along with the originally requested spec
and suffix values. A speculative startup still uses `--spec T` (`T >= 2`) and
`--mtp DIR`; there is no automatic fallback from speculation to target-only.

The G0 qualification uses an RTX 4090 and the Coder IQ1_M model on Linux/CUDA.
Its [cursor audit](gbnf-evidence/G0/CURSOR.md) explains the pending feedback
token. Windows native, HIP and multi-GPU execution need their own qualification.
The Windows Python API regression suite is separate from native hardware tests.

## G1: native grammar library

The optional native library is disabled at build time by default. Prepare its
pinned dependencies once, then enable it in the existing build:

```text
python tools/prepare_xgrammar.py --out build/xgrammar
cmake -S . -B <native-build> <existing-native-options> -DSTRATA_ENABLE_GBNF=ON -DSTRATA_XGRAMMAR_DIR=<absolute-prepared-directory>
cmake --build <native-build> --target strata grammar_native_test
```

Choose a new dependency directory if an incomplete or different pin exists.
CMake/server startup does not download dependencies. See the
[backend decision](gbnf-evidence/G1/grammar-backend-decision.md) for supported
syntax, licenses and resource limits, and the [native test report](gbnf-evidence/G1/REPORT.md)
for the parser, recursive grammar, tokenizer-byte and sanitizer results.

G1 provides compilation and private matcher state. It does not yet enable the
`grammar` HTTP request field or constrain model selection.

## Remaining grammar gates

G2 enforces legality before native selection. G3 connects the raw `grammar` extension to both HTTP
adapters. G4 adds inspection and state-derived application contracts. G5
qualifies constrained MTP/suffix execution; G6 recovery is deferred.

G0 alone does not enable the `grammar` request field. JSON Schema, JSON-object
enforcement and standard custom-tool Lark syntax are outside this contribution.
Existing unconstrained structured-output behavior is separate from native GBNF.
