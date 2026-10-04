# Ordered sampler experiments

This branch adds an explicit sampler chain to the existing native serving loop.
It starts at `work/logprobs-675`, commit
`2243cb1c5b1a87270731d8b8a76e4af001f96f97`. The educational Control Lab is a
separate consumer of this dependency. No fetch, rebase or changes to the original
checkouts were needed.

The three starting recipes are Min-P before temperature, Top-N-Sigma before
temperature, and XTC before temperature. They select from the full vocabulary,
after an optional native grammar mask. This is a **CPU reference selector after
Strata's existing native GPU forward pass**. It copies the raw row to the host;
it does not run a second model or another HTTP endpoint. The existing GPU
sampler is unchanged when `strata_sampler` is absent.

## Run a recipe

Build the branch's native binary using your existing Strata build configuration.
For native GBNF/JSON also follow [the logprobs build guide](LOGPROBS.md).
Run the existing Python server with that binary in its config. Query `/props`:
`strata_capabilities.samplers` must be `ordered-host-v1`.

Send this body to `POST /v1/chat/completions` with your usual authentication:

```json
{
  "model": "x",
  "messages": [{"role": "user", "content": "Give one concise alternative implementation of a bounded retry loop."}],
  "max_tokens": 64,
  "reasoning_effort": "none",
  "seed": 675,
  "logprobs": true,
  "top_logprobs": 5,
  "strata_sampler": {
    "chain": ["min_p", "temperature"],
    "min_p": 0.05,
    "temperature": 1.5,
    "inspect": true
  }
}
```

Save it as `request.json`. Windows PowerShell:

```powershell
$base = 'http://127.0.0.1:8080'
Invoke-RestMethod "$base/v1/chat/completions" -Method Post -ContentType 'application/json' -Body (Get-Content request.json -Raw)
```

Ubuntu:

```bash
curl http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' --data-binary @request.json
```

If your server requires a key, include its usual Bearer authorization header.
Use loopback or an authenticated LAN server as described in [AI setup](AI_SETUP.md).
The profile works without logprobs; omit `inspect` or set it false in that case.
`stream:true` uses the same selection and per-token data as the final JSON view.

Replace just the profile for the other two recipes:

```json
{"chain":["top_n_sigma","temperature"],"top_n_sigma":2.0,"temperature":1.5,"inspect":true}
```

```json
{"chain":["top_k","min_p","xtc","temperature"],"top_k":16,"min_p":0.04,"xtc_probability":0.12,"xtc_threshold":0.15,"temperature":0.9,"inspect":true}
```

## What the operators mean

| Operator | Exact action on the currently eligible logits |
| --- | --- |
| Grammar | First: native matcher determines the allowed token IDs. Identity mask without a grammar. |
| `min_p` | Keep logits at least `max + log(min_p)`; zero disables. |
| `top_n_sigma` | Keep logits at least `max - n × population_stddev`; zero disables. Compute statistics over current finite eligible logits, including the tail. |
| `top_k` | Keep the largest k logits, breaking ties by token ID. Zero keeps all candidates, with no hidden 64-token limit. |
| `top_p` | Keep the shortest descending prefix whose normalized mass reaches p, always keeping one token. |
| `xtc` | With the configured gate probability, discard all but the least likely token above the threshold; keep the tail. Fewer than two qualifying tokens makes it a no-op. |
| `temperature` | Divide surviving logits by a strictly positive temperature. |

Each operator appears at most once; every profile includes temperature. Parameters
must match the named operators exactly. Values are checked before streaming
headers. The explicit profile replaces server-default sampling settings; mixing
legacy top-level sampling fields with it is an error. `seed` remains top-level;
positive seeds are reproducible at identical logits, masks and generated positions.
Separate counter-based draws control the XTC gate and final categorical draw.
This is not llama.cpp RNG compatibility or a promise of identical GPU logits
across different execution paths.

The definitions were checked against the pinned
[llama.cpp sampler implementation](https://github.com/ggml-org/llama.cpp/blob/3cf03257f219afbe7334045ff7c6a06ac68c627d/src/llama-sampler.cpp),
the [Top-N-Sigma paper](https://arxiv.org/abs/2411.07641), and the
[original XTC proposal](https://github.com/oobabooga/textgen/pull/6335).
These recipes are hypotheses about useful exploration, not a demonstrated ranking
of coding quality. Grammar-first placement means Sigma measures the legal set;
this can differ substantially from filtering the full vocabulary before grammar.

## Inspect the distinction between preference and selection

With `inspect:true` and `logprobs:true`, each scored content token gains a
`strata_sampling` extension containing:

- the selected token's probability in the **final sampling distribution**;
- candidate count and entropy in nats after each operator;
- final top 20 token IDs, bytes and selection probabilities;
- host selection time, excluding the device-to-host copy and forward pass.

The existing `logprob` and `top_logprobs` stay the **raw target full-vocabulary
log-softmax before grammar and sampling**. A forced answer can have sampling
probability 1 and tiny raw model probability. Neither measures objective truth.
Final top-20 entries can omit probability mass; the reported stage entropy and
support are computed from the entire surviving set, not reconstructed from them.

## Boundaries and next gate

This profile runs one target row per step and bypasses MTP/suffix proposals for
that request, including on a speculative server. The next ordinary request uses
its configured decoding path. Grammar state, commit, STOP/draining, prompt cache
and engine ownership remain with the existing service and native driver.
Native GBNF and strict JSON constrain generated answer content as before.

The new profile supports Chat text requests. Images, custom stops, server MCP,
logit bias, injected reasoning wrap-up and mixed legacy settings are rejected.
DRY, dynamic temperature and Mirostat are not native operators in this version;
the lab may explore explicitly labeled simulations of those ideas. They are not
silently accepted as engine capabilities.

The next optimization gate is an equivalent GPU full-vocabulary selector with
same-tensor numerical tests, measured transfers/kernel cost, and a separately
qualified speculative path. HTTP latency alone is not a hardware roofline.

See [the qualification receipt](sampler-evidence/RECEIPT.md) for tested hardware,
commands, limitations and evidence. Host numerical tests can be compiled alone:

```bash
g++ -std=c++17 -O2 -UNDEBUG -Iinclude src/program/ordered_sampler_test.cpp -o ordered_sampler_test
./ordered_sampler_test
python -m pytest -q serve/test_sampling.py serve/test_logprobs.py
```
