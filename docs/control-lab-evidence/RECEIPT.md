# Initial eleven-page Control Lab qualification receipt

This is the historical first checkpoint. See [the research expansion receipt](RESEARCH_RECEIPT.md) for the current 25-page gallery and sampler dependency.

Branch: **`work/control-lab`**. Worktree:
`C:\Users\dflanag3\Documents\fleet\strata-control-lab`.

Base: **`2243cb1c5b1a87270731d8b8a76e4af001f96f97`**, the pushed
`work/logprobs-675` checkpoint. The original worktree remains intact. The exact
lab implementation commit is recorded in [CHECKPOINT.txt](CHECKPOINT.txt).

Native capture and browser qualification: **October 4, 2026 UTC**.

## Changed responsibilities

- `examples/control_lab/core.py`: pure numerical calculations, finite literal
  grammar construction, state transitions and bounded graph selection.
- `client.py`: authenticated client calls to the existing Chat API, typed local
  progress, incremental SSE collection, and exact-request native replay.
- `catalog.py` / `scenarios.py`: educational explanations and the eleven small
  experiments. State, graph and scene logic belong to the demo application.
- `app.py` / `static/`: loopback FastAPI UI, request validation, error and
  cancellation handling, accessible controls, diagrams, token inspection and
  downloadable receipts.
- Tests and capture tools: separate synthetic mathematical/transport cases,
  replayed native evidence, real native capture, and actual browser workflows.

No changes to `serve/`, native C++/CUDA/HIP, MTP, tokenizer, inference scheduling,
existing API authentication or engine cancellation. Optional lab dependencies
are separate from the normal Strata requirements.

## Native evidence

The [initial capture report](initial-capture-results.json) contains **101 completed native HTTP
requests** across 25 experiment configurations: ten live-capable pages, all
four controller states, the ten original wire examples, and three fast probes.
The eleventh page replays the original native speculation diagnostics.

Each file in [recordings/](recordings/) contains the complete request, response,
native provenance, UTC capture time and measured request duration. Filenames
start with the canonical request's SHA-256. The UI fails on a recording miss;
there is no synthetic fallback. Summary files such as [candidates.json](candidates.json),
[graph.json](graph.json), [scene.json](scene.json) and [performance.json](performance.json)
preserve the derived result and its underlying calls.

The native [identity record](native-identity.json) pins the binary and serving
source. The Python service was exported from the exact base commit into a new
isolated directory on llm-49. The native executable is the previously qualified
grammar-enabled artifact, SHA-256:

```text
6ea58d8eec0dafe24642eb6d9fa124ae1a31dfb5237529986231a999beb7423d
```

Its Qwen model, tokenizer and build qualification are in the base branch's
[identity](../logprobs-evidence/native/identity.json) and
[native receipt](../logprobs-evidence/RECEIPT.md). The lab does not rebuild or
modify that engine. The five key serving Python files' hashes were compared
against this worktree and match exactly.

Native configuration: RTX 4090, driver 595.91.07, Linux, Qwen3.8-Flash-Next IQ1_M,
int8 KV, context 4096, prefill 256, configured expert cache 6000, mmap experts,
prompt cache 2, conversation cache 0, adaptive swaps 0, `spec=1`, no MTP.
The Windows client used an SSH tunnel to loopback HTTP. Test traffic did not use
llm-60 or r730. Model loading is excluded from the per-request timings; the first
Choice call still incurred a cold prompt/cache path.

Representative native results:

- Finite grammar groups: approximately 99.866% of the measured candidate-path
  weight favored inspecting first. The best listed phrase's raw path mass was
  only about 0.523%; the UI shows why these are different numbers.
- Controller: `inspect → edit → test → finish`, with legal grammars derived at
  each state. All four native actions respected the application transition rule.
- Graph: retained the sentence-continuation and caption-attachment links while
  preserving all source text and uncertain edges.
- Scene: native schema-constrained JSON, explicit code checks, three semantic
  features per candidate and a separate browser-only human visual judgment.
- Fast one-row probes: roughly 0.91–0.95 seconds each in this capture. Full
  multi-call workflows are slower; no universal latency or cost claim is made.

## Python and browser validation

[Python test output](python-tests.txt): **59 passed**. These check stable
log-space arithmetic; missing labels; selected tokens outside top-N; exact UTF-8
bytes; finite-group overlap; conditional score calculations; illegal transitions;
globally admissible graph selection; strict HTTP validation; native replay;
changed-input replay misses; all ten wire cases; error propagation; and
request-local cancellation cleanup. A separate extreme-score fixture verifies
that legal-action conditioning remains stable when its raw mass underflows.

One dependency warning is recorded: Starlette deprecates its current `httpx`
TestClient integration. The tested runtime works; this is not hidden as a clean
warning-free run. [Environment versions](environment.json) pin what was used.

[Browser results](browser/results.json): **29 checks passed**, no page errors.
Headless Chromium exercised every page, all three fast/raw display modes,
four controller transitions, candidate token inspection, JSON download, all
ten wire cases, a changed-input error followed by reset, live cancellation
followed by a clean next request, and seven layouts at a 390-pixel mobile width.
Desktop and mobile screenshots were visually inspected; see
[preview](browser/preview.png), [controller](browser/controller.png),
[graph](browser/graph.png) and [mobile](browser/mobile.png).

Commands, from the lab checkout with its virtual environment active:

```sh
python -m examples.control_lab.capture --base-url http://127.0.0.1:18765
python -m pytest examples/control_lab/test_core.py examples/control_lab/test_app.py -q
python -m examples.control_lab --port 8876
python -m examples.control_lab.check_browser --base-url http://127.0.0.1:8876 --live
git diff --check
```

Native capture is separate from browser replay. The browser result is not
presented as 29 additional native accuracy tests. The recorded timings remain
the original native timings, not the speed of reading a JSON file.

## Limitations and next gate

This is an educational client application. The OS controller is simulated,
semantic scores are uncalibrated, and text-only scene probes do not evaluate
pixels. One finite token path per literal is scored; arbitrary/infinite grammar
language mass, alternative tokenizations and EOS probability are not supplied.
Independent source requests still enter the existing single-engine queue.

Native per-token grammar steering, score gathering for arbitrary candidate token
IDs in one pass, GPU reduction, prefix-trie batching and hardware roofline work
are future experiments in the [roadmap](../CONTROL_LAB_ROADMAP.md). The original
draft/target/replay numerical paths remain distinct. No universal Jev, Codex,
hardware, accuracy or cost superiority is claimed.

The next gate is user review of the educational workflow, then selection of one
measured optimization or control experiment. The independent logprobs branch
does not require merging this lab.
