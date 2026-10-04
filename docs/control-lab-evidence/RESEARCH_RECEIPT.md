# Research Control Lab qualification

Branch: **`work/control-lab`**. Worktree:
`C:/Users/dflanag3/Documents/fleet/strata-control-lab`.
The exact implementation checkpoint is in [RESEARCH_CHECKPOINT.txt](RESEARCH_CHECKPOINT.txt).
Implementation: **`bb28ac8b6bfcfc78dcd01ca55a0d8f178599ee02`**.
The [source manifest](research-source-manifest.json) pins the tested lab files.
The [final artifact audit](research-final-audit.json) verifies all 230 recording
hashes and 31 source hashes against committed Git blobs and checks the local gallery.

Logprobs base: `2243cb1c5b1a87270731d8b8a76e4af001f96f97`.
Sampler dependency: **`450285f3c90748057a02648345e6c3973519a710`**, merged with
`11db33b05f860e345723981d0a2d1e13e7427734` after separate native qualification.
The sampler implementation itself is `dbdfda4aafe306c6c7da47eac8106d6bcd45636c`.
The original checkouts remain intact. No fetch, reset, stash or rebase was used.

The sampler branch is published at
[work/samplers](https://github.com/CC-David-CC/Strata-a5500/tree/work/samplers).
This receipt does not assert that the separate lab branch has been published.

## Responsibilities

- The optional FastAPI client now has a 25-page gallery, local fonts and assets,
  search, category filters, reduced-motion controls and a responsive interface.
- `research.py` owns bounded experiments over the existing authenticated Strata
  HTTP API. It never owns model execution, GPU scheduling, native cancellation,
  prompt caching or the inference lifecycle.
- `control_math.py` owns explicit game, plant, utility, information and scoring
  calculations. Model observations and code-owned constraints remain distinct.
- `research_catalog.py` and `research_ideas.py` hold plain explanations, technical
  limits, next gates and eight unimplemented experimental protocols.
- `research.js` renders token-stage inspection, trace playback, game boards,
  controllers, graphs and assumption dials. Its motion is illustrative, not
  claimed GPU/thread telemetry. The final-result trace controls send no model commands.
- Exact-request replay remains SHA-256 keyed. A changed prompt without a recording
  fails visibly. Native records, analytical fixtures and unimplemented proposals
  are labeled separately. The original eleven-page suite remains available.

There are no additional `serve/` or native-engine changes in this lab expansion.
The separately reviewed sampler dependency supplies the new native features.
FastAPI and python-chess are optional lab dependencies, not engine requirements.

## Native evidence

Capture and qualification: **October 4, 2026 UTC**, using **llm-49 only**.
No requests used llm-60 or r730. The Windows client reached a loopback native
server through SSH. Native configuration: Linux, RTX 4090, CUDA 13.3.73,
Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M, int8 KV, context 4096, prefill 256,
expert cache 6000, mmap experts, adaptation disabled, prompt cache 2,
conversation cache 0 and target-only serving.

New capture binary SHA-256:

```text
99890d1dd54a53ac8b1af3b3a9c4dde06282a88bdfdc472efff6f13a381c37d6
```

[Native source/binary identity](../sampler-evidence/identity.json),
[sampler qualification](../sampler-evidence/RECEIPT.md) and
[the independent full-row oracle](../sampler-evidence/oracle.json) establish the
engine used here. Its raw-logit diagnostic recording was disabled during lab use.
The oracle's maximum probability/statistic error was about `6.66e-14` against
independent FP64 arithmetic on the same native tensor, within the `1e-9` tolerance.

There are **230 canonical native request recordings**: 101 foundation requests
and 129 research requests. The [manifest](research-recordings-manifest.json)
pins each file's LF-normalized Git bytes and capture time. Successful preliminary duplicate captures
were archived outside the public replay set, so the replay files agree with the
completed scenario receipts. The original foundation records were preserved.

| Research workload | Native requests | Evidence |
| --- | ---: | --- |
| Six ordered profiles, two GBNF hybrids, strict JSON hybrid | 9 | [samplers.json](samplers.json) |
| Tic-tac-toe against exact minimax | 14 | [tictactoe.json](tictactoe.json) |
| Six chess labels plus the complete legal UCI grammar | 7 | [chess.json](chess.json) |
| Three toy poker hands | 9 | [poker.json](poker.json) |
| Six-step simulated cooling loop | 24 | [thermal.json](thermal.json) |
| Four-job dependency schedule | 12 | [scheduler.json](scheduler.json) |
| Three context variants and an identical-request pair | 8 | [context.json](context.json) |
| Three semantic probes over three reports | 18 | [observer.json](observer.json) |
| Six disclosed truth fixtures and a label swap | 14 | [calibration.json](calibration.json) |
| Analytic information gain followed by a native action | 4 | [information.json](information.json) |
| Five valid scene programs, two labels each | 10 | [search.json](search.json) |

The sampler sandbox, cost frontier and possibility tree make zero inference
requests. Their formulas, synthetic inputs or assumed engineering quantities
are disclosed in the UI and JSON. The cost frontier also reads actual native
selection timings; those timings exclude GPU row copy and forward execution.

Useful counterexamples were retained. The recorded tic-tac-toe policy loses to
minimax; all moves remain legal. The chess UCI request selects a legal stalemate
while the six-letter shortlist prompt favors a mating move. Those prompts and
representations differ. Their contrast is not a calibration or chess-strength
benchmark. Toy poker utilities assume the exact disclosed opponent policy.
The cooling shield is exact only for its disclosed one-step simulated dynamics.

## Validation

[Python output](research-python-tests.txt): **83 passed**, with one recorded
Starlette TestClient deprecation warning. [Environment](research-environment.json)
pins the Python packages. The tests include all 25 page replays, original API
and lifecycle boundaries, all 5,478 reachable tic-tac-toe states, minimax symmetry,
thermal action bounds, exact toy utilities, Bayes/information identities, proper
scoring rules, dependency order, native chess legality and GBNF/JSON sampler receipts.

**59 headless browser checks passed** across these complementary runs:

| Suite | Checks | Evidence |
| --- | ---: | --- |
| Original pages under the new shell | 28 | [results](research-foundations-browser/results.json) |
| Research pages, nine recipes, all controls/exports, gallery, phones and reduced motion | 23 | [results](research-browser/results.json) |
| Live edited prompt, nine native recipes including GBNF/JSON, stop and next ordinary request | 3 | [results](research-live-browser/results.json) |
| Completed pages which make zero model requests | 5 | [results](research-browser/zero-request-results.json) |

Offline qualification used a separate lab with `STRATA_BASE_URL=http://127.0.0.1:1`.
The research test first confirmed a live connection failure, then replayed every
research page successfully. It blocked and recorded external browser requests;
none occurred. Desktop size was 1500×1060; mobile size was 390×844. Console errors
were empty in the main suites. Screenshots were inspected, including the index,
native sampling, game boards, thermal loop and mobile layouts.

The live browser exported [nine native runs with an edited prompt](research-live-browser/samplers.json)
and [the ordinary request after stop](research-live-browser/next-ordinary-request.json).
These additional live checks are separate from the 230 default replay fixtures.
Browser success is not used as a substitute for the sampler's native numerical,
speculative-restoration and cancellation/draining qualification.

Commands, from the checkout root using the lab environment's Python:

```text
python -m pytest examples/control_lab -q
python -m examples.control_lab.capture --base-url http://127.0.0.1:18765 --page samplers --output evidence/my-samplers
python -m examples.control_lab.check_browser --base-url http://127.0.0.1:8877 --output evidence/foundations-browser
python -m examples.control_lab.check_research_browser --base-url http://127.0.0.1:8877 --expect-offline --output evidence/research-browser
python -m examples.control_lab.check_empty_receipts --base-url http://127.0.0.1:8877 --output evidence/empty-receipts
python -m examples.control_lab.check_research_live --base-url http://127.0.0.1:8876 --output evidence/live-browser
```

Port 8877 was the deliberately disconnected lab; port 8876 was configured to
reach native Strata. These are two optional client processes, not two inference
servers. `capture --page` can select any experiment; omitting it captures all
live-capable built-in configurations. Do not run the live checker against a
disconnected lab and interpret that expected connection failure as an engine bug.

## Limits and next gates

- Three priority native sampler families are supported. DRY-like sequence
  penalties, entropy temperature and expected-surprise feedback are teaching
  models. Native DRY/DynaTemp/Mirostat are not advertised.
- Ordered sampling is a CPU reference after the existing GPU forward pass;
  profiled requests disable speculation for that request. GPU porting and
  speculative profiles require the same-tensor oracle and rollback qualification.
- State replacement is demonstrated through ordinary requests. Arbitrary KV or
  recurrent-state rewriting and token-acknowledged grammar replacement are not implemented.
- Finite grammar-group scores cover measured token paths, with explicit
  terminators where used. They are not exact mass over every tokenization,
  arbitrary infinite grammar or unseen EOS event.
- These are disclosed small applications and counterexamples, not large held-out
  benchmarks, calibrated truth estimates, chess/poker strength, closed-loop
  stability proofs, actual OS automation or measured hardware rooflines.
- Unusual applications in the possibility tree are falsifiable research designs.
  Each needs its verifier, baseline and evaluation budget before implementation.

The next native performance gate is GPU selection with identical operator/RNG
semantics, measured row-copy/kernel cost and ordinary-request regression checks.
The next control gate is held-out state perturbations with direct-state and
ordinary-controller baselines. See the [experiment tree](../CONTROL_LAB_ROADMAP.md).
