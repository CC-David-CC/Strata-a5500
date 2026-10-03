# Experimental stateless Responses adapter

This branch adds a bounded `POST /v1/responses` profile over Strata's existing
service. It is disabled by default. It does not change native inference, MTP,
model loading, or the legacy Chat Completions structured-output path.

Enable it when starting an existing configured server:

```sh
python serve/server.py --engine strata --config strata-model.json --experimental-responses
```

Use the path of your actual model config in place of `strata-model.json`.
Alternatively, add `"experimental_responses": true` at the top level of that
config. The CLI flag enables it even if the config says false; the effective
value is resolved once at startup. No per-request experimental field is needed.
When disabled, the route returns 404 and starts no Responses store or workers.

A CPU-only example, without a model download:

```sh
python serve/server.py --engine mock --script "Hello." --experimental-responses
```

The existing API key, Host/Origin checks and CORS configuration protect the route.
For SDK clients use the same base URL and API key as the other Strata endpoints:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8095/v1", api_key="your-strata-api-key")
response = client.responses.create(
    model="qwen3.8-flash-next",  # use a model ID advertised by /v1/models
    input="Say hello.",
    store=False,
    max_output_tokens=128,
)
print(response.output_text)
```

## Capability profile

R1 supports text messages, per-request instructions, explicit `store:false`,
plain text output, bounded metadata, temperature/top-p, and output limits.
Reasoning defaults to off; the only accepted explicit request is
`reasoning={"effort":"none"}`. Unknown behavior-changing parameters are errors.
Request bodies are bounded to 4 MiB; input context must fit the existing service.
Configured sampling defaults remain in effect when a request omits them.

| Capability | Policy |
|---|---|
| Full text/message history | Supply in `input`, including content-bearing returned messages and IDs. |
| Server storage | Explicit `store:false` required; omitted or true is rejected. |
| `previous_response_id`, conversation storage, ID-only references | Unsupported; no history is inferred from GPU cache. |
| Retrieve/delete/cancel/background | Not implemented. Disconnects use existing cancellation/draining. |
| `text.format` | Omitted or `{"type":"text"}` only. |
| JSON Schema / JSON-object generation | Excluded; no strict enforcement claim or object-only fallback. |
| Streaming | R2 gate; rejected until that phase passes. |
| Function calls | R3 gate; rejected until that phase passes. |
| Reasoning summaries/encryption, image/audio, hosted tools, compaction, WebSockets | Unsupported; rejected. |
| Raw GBNF | Rejected until a separate native grammar contribution passes its gates. |

To continue, append the previous response's complete `output` items and the new
user message to your supplied history. Resend any instructions you still want.
Responses and runtime handles are request-local; no parent record exists to mutate.
The optional existing API monitor can retain its usual bounded diagnostics in
memory. That is not Responses storage or a conversation continuation mechanism.

## Ownership and tests

`serve/responses.py` validates capabilities and owns one request-local assembler.
It consumes `Service.run()` semantic events below HTTP serialization. Final JSON
and typed lifecycle/output events come from that same assembler. Token fragments
are appended to incremental buffers; serialization does not rewrite their text.
The handler issues commands and sends snapshots. Existing service admission,
loading, cancellation, draining and metrics remain authoritative for execution.

```sh
python -m unittest serve.test_responses -v
```

This is not a universal Codex compatibility claim. The pinned Codex 0.160.0
initial request asks for excluded reasoning representations and a tool namespace.
See the [R0 client capture and blocker report](responses-evidence/R0/REPORT.md).
SDK and mock tests do not prove a real Codex tool/edit/result loop or native
grammar enforcement. GBNF work cannot start before a passing R4 checkpoint.

Protocol references: [Responses](https://developers.openai.com/api/reference/resources/responses),
[typed streaming](https://developers.openai.com/api/docs/guides/streaming-responses),
[function calling](https://developers.openai.com/api/docs/guides/function-calling).
