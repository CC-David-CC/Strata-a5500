# Native grammar contribution

This branch starts at the passing stateless Responses checkpoint
`96092670da0dc3c1cfcce99bb90a3e6ca25ae1d9`. The
[Responses guide](RESPONSES.md) documents the experimental route, installation,
replay key and tested local Codex profile. Responses remains disabled by default;
enable it with `--experimental-responses` or `"experimental_responses": true`.

For a small real-model demonstration, see the [14-case live test](gbnf-evidence/live-demo/REPORT.md)
and its [plain-text request/result receipt](gbnf-evidence/live-demo/GBNF_DEMO.txt).
The same prompt produced ordinary prose without a grammar and `color=blue;count=1`
with a grammar, in both target-only and MTP modes. The recorded checks also cover
Responses JSON/SSE, Chat JSON, Unicode, token limits and invalid grammar rejection.

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

G1 provides compilation and private matcher state. G2 enforces native masks
through the same persistent target-only decoder; see its
[real model and sampler report](gbnf-evidence/G2/REPORT.md).

## G3: raw grammar through both HTTP APIs

Build with GBNF enabled as above, use the target-only configuration (or the G5
speculative configuration below), and start
the existing server. For Responses, also install its Python requirements, set
the replay key and enable `--experimental-responses` as described in the
[Responses guide](RESPONSES.md). Chat Completions needs no Responses flag.
Both use the same native constraint argument and decoder. A build without GBNF
rejects grammar requests; it does not download or enable a backend at runtime.

The engine's existing `INFO` diagnostics must advertise `grammar=gbnf-v2`.
The HTTP service checks that version, verifies the tokenizer byte table against
the native vocabulary, and compiles the request before sending success headers.
An older engine or an unsupported configuration is rejected explicitly. The server
does not change its configured inference mode to accommodate a request.

Send one additional field, `grammar`, containing UTF-8 GBNF source with a `root`
rule. This is a **Strata extension**, not an OpenAI standard field. With the
official Python SDK, use `extra_body`:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8095/v1", api_key="your-strata-api-key")
response = client.responses.create(
    model="qwen3.8-flash-next",
    input="Return a boolean.",
    store=False,
    reasoning={"effort": "none"},
    max_output_tokens=32,
    extra_body={"grammar": 'root ::= "true" | "false"'},
)
print(response.output_text)
```

For Chat Completions, send `messages`, `reasoning_effort="none"` and
`max_tokens=32` to `client.chat.completions.create`, with the same `extra_body`.
Set `stream=True` on either call for streaming. Complete request bodies and their
pieces are in [Responses](gbnf-examples/responses.txt),
[Chat Completions](gbnf-examples/chat-completions.txt) and
[recursive Unicode](gbnf-examples/recursive-unicode.txt) examples.

The initial G3 profile is single-GPU target-only text generation with the
gpt2/qwen35 tokenizer and standard end controls. The rendered prompt must end at
the Qwen answer-only boundary with thinking explicitly disabled. Requests with
tools, generated reasoning, summaries, custom stop strings, images or simultaneous
JSON requirements are rejected. Grammar source is bounded to 8192 UTF-8 bytes,
output to 8192 tokens and 65536 native bytes; compilation/matcher work has the
[G1 limits](gbnf-evidence/G1/grammar-backend-decision.md). No arbitrary grammar
file path, registry, Lark or JSON converter is exposed.

Chat sampling uses the existing bounded native sampler: `top_k` accepts 1..64;
zero means its existing 64-candidate cap. Seeds use unsigned 64-bit values.
Temperature, top-p, min-p and penalties retain their native order after grammar
legality. Unsupported logit bias, log probabilities, multiple choices and
unknown constrained-profile fields are rejected. Unconstrained Chat behavior
remains separate. Constrained Chat also rejects `stream_options`: the existing
Chat serializer includes usage in its final choice chunk, rather than the
optional separate usage-only chunk. Responses uses its own documented final
response usage object.

The native matcher alone advances on selected tokens. HTTP content bypasses the
marker parser, so literal `<think>` or `<tool_call>` text is preserved. Typed SSE
and final JSON contain the same concatenated text. At a token limit or disconnect,
a partial UTF-8 character stays buffered: JSON cannot represent incomplete UTF-8
bytes. It is never replaced or repaired, and its consumed tokens still count in
usage. A length limit reports `incomplete` (Responses) or `length` (Chat), even if
the visible prefix happens to be accepting. Successful completion requires the
native matcher to select an allowed end control. Post-header failures use the
existing API error lifecycle; they do not become successful completions.

See the [G3 qualification and measured overhead](gbnf-evidence/G3/REPORT.md).
Raw grammar qualification does not extend the separately tested Codex tool
profile: grammar cannot be combined with tools or thinking at this checkpoint.

## G4: local inspection and application contracts

The [inspection guide](GBNF_INSPECTION.md) provides Mermaid diagrams, plain-text
native observations and a bounded application-side example. It uses frozen
revisions and current permissions to reject stale candidates before effects.
Grammar syntax alone does not authorize an action. The
[G4 report](gbnf-evidence/G4/REPORT.md) records native matcher, sanitizer and real
model evidence, including an incomplete but readable command that the client
refuses to apply. Inspection is an explicit local debug operation, with no new
HTTP or native-pipe endpoint.

## G5: constrained MTP and suffix execution

Keep the same Python server, API flag, request body and grammar-enabled build.
To enable MTP, use the existing native configuration's `args` entries:

```text
"--spec", "4", "--mtp", "<your-existing-MTP-directory>", "--suffix-draft", "0"
```

Use `"--suffix-draft", "3"` to enable the existing suffix policy. Add
`"--coupled-draft"` for coupled proposals on sampled requests; use
`"--no-coupled-draft"` for argmax proposals. The server never disables these
settings to accommodate a grammar request. `--spec 1` remains the reference
mode of the same decoder and requires no draft weights. Native GBNF is still
off by default at build time; Responses is still off by default at server startup.
The existing suffix policy can enlarge the maximum window (`--spec 4` plus
suffix lookup uses a maximum of 6 here); `INFO` records requested and effective
settings. This is independent of the number of reachable rows in a particular
grammar-constrained window.

The matcher builds each row's legal-token mask from a tentative proposal prefix.
An illegal draft keeps the row that can replace it and removes its descendants.
An end-token proposal has no following row. Existing target selection determines
which proposals survive by exact token equality. A single retained count governs
model commit, emitted output, grammar progress and draft catch-up; it is bounded
before commitment by remaining output and EOS. The final emitted token remains
pending model feedback and is not consumed twice by the matcher.

`STRATA_TRACE=1` adds native `SPEC` observations: selected proposal source,
coupled mode, proposed/reachable rows, retained count, illegal/end proposal and
window duration. Ordinary draft-offered statistics count the valid verifier
input drafts; the trace separately exposes proposals removed before verification.
Grammar work spent on discarded proposals still counts against its request budget.
There is no automatic acceleration recovery or unmasked retry.

The [G5 report](gbnf-evidence/G5/REPORT.md) pins the exact model, build, correctness
matrix and latency results. Fixed-logit tests require exact selected tokens.
Actual model logits can differ with GPU graph shape, even when seed, masks,
history and expert placement match. Native numerical diagnostics are reported
separately; a seed alone is not a promise of bitwise model parity.

For explicit local numerical investigation, `STRATA_GRAMMAR_LOGITS=<local-file>`
buffers raw head rows, legal masks, histories and counters, then writes once
after generation. It is an environment-only diagnostic, not an API parameter.
The bound is 32 rows per request and 128 per process, with at most 262144 logits
per row; truncation is explicit in the file and rejected by the audit tool.
Keep it off for performance measurements. The
[audit tool](../tools/grammar_numerical_audit.py) retains legal scores and hashes,
full-vocabulary deviations, greedy margins and explicitly approximate float64
CDF boundaries. It does not infer grammar branch probabilities.

## Remaining scope

G6 recovery is deferred. The user
selected Mermaid/plain text for G4, so actual Code Visualizer ProgramModel
integration is not performed or claimed.

JSON Schema, JSON-object
enforcement and standard custom-tool Lark syntax are outside this contribution.
Existing unconstrained structured-output behavior is separate from native GBNF.
