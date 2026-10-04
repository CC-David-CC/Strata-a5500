# Educational control lab: experiment tree

The first release is an educational control lab: **25 pages**, an offline gallery,
230 native request recordings, three explicitly analytic instruments and a
20-branch possibility tree. Live pages use the existing Strata API. This branch starts at
`work/logprobs-675` commit `2243cb1c5b1a87270731d8b8a76e4af001f96f97`.
Its tested `work/samplers` dependency is `450285f3c90748057a02648345e6c3973519a710`.
The independent logprobs and sampler contributions can be reviewed without the lab.

No finite plan exhausts every possible controller or optimization. This is an
explicit tree of the useful mechanisms and their next falsifiable experiments.
An unmeasured optimization is not described as an achieved capability.

```text
state + question + answer definitions
|
+-- numerical observation
|   +-- one target row / top-N ........ implemented; missing labels unknown
|   +-- complete one-token labels .... implemented; one native call per label
|   +-- ordinal expectation .......... implemented; explicit rubric values
|   +-- multiple semantic probes ..... scene, graph and three-channel observer
|   +-- calibration / abstention ..... teaching Brier/coverage; held-out data next
|   +-- label/permutation sensitivity  native label-swap fixture; broader suite next
|
+-- branches of possible output
|   +-- finite literals .............. implemented; conditional token scores
|   +-- finite disjoint groups ....... implemented; logsumexp over measured paths
|   +-- shared-prefix trie ........... next: native prefix/KV reuse, same scoring
|   +-- teacher-forced batches ....... next: expose a distinct scored replay path
|   +-- bounded grammar expansion .... next: explicit horizon and residual mass
|   +-- unbounded grammar probability  unresolved; no exact-language claim
|
+-- control with hard rules
|   +-- legal action per state ....... implemented; one completed request per step
|   +-- native GBNF output ........... existing engine feature, exercised here
|   +-- strict native JSON ........... existing engine feature, exercised here
|   +-- games and planning ........... tic-tac-toe, legal chess, toy poker, scheduler
|   +-- plant feedback ............... simulated thermal loop + one-step shield
|   +-- state replacement ............ native appended/replaced/structured prompts
|   +-- arbitrary KV/recurrent edit .. not implemented; correctness design first
|   +-- token-acknowledged steering .. separate endpoint/rollback design, not here
|   +-- actual OS execution .......... outside this educational first release
|
+-- compose observations in code
|   +-- independent source ranking .. implemented; HTTP concurrency shown honestly
|   +-- immutable document graph ..... implemented; bounded exact subset optimizer
|   +-- JSON scene + code checks ..... implemented; text probes + human rendering view
|   +-- bounded program search ....... six candidates, code checks, utility dial
|   +-- active inspection ............ analytic likelihoods + native next action
|   +-- observer/controller learning . probe vectors implemented; learned policy next
|
+-- sampling as a control algorithm
|   +-- Min-P then temperature ....... native reference, reverse-order comparison
|   +-- Top-N-Sigma then temperature . native reference, full eligible vocabulary
|   +-- XTC then temperature ......... native reference, independent RNG lane
|   +-- grammar / JSON hybrids ...... native mask followed by the ordered sampler
|   +-- DRY-like / entropy / surprise  teaching models only; native implementations next
|   +-- GPU / speculative profiles .. not implemented; preserve the numerical oracle
|
+-- cost and computational path
    +-- target-only .................. new native suite and latency page
    +-- MTP draft / target verify ..... original native receipts, distinct scores
    +-- suffix target verification ... original native receipts; no suffix prior
    +-- coupled draft distribution ... original receipts; post-sampling label
    +-- independent replay ........... original receipt, expected numerical drift
    +-- GPU score gather/reduction ... next: bytes moved, kernel time, numerical oracle
    +-- native batch/prefix sharing ... next: throughput vs memory and queue latency
    +-- adaptive lookahead ........... next: acceptance, verified work, rollback cost
    +-- hardware roofline ............ requires counters; not achieved by HTTP timing
```

## Gates for a follow-up optimization

| Branch of work | Establish first | Compare next | Passing evidence |
| --- | --- | --- | --- |
| GPU score gather | Same raw logits, normalizer and selected token | CPU row copy versus compact GPU gather | Same-tensor numerical oracle plus transfer and kernel timings |
| Complete labels in one pass | Arbitrary requested token IDs and explicit omissions | One row versus repeated forced labels | Distribution deltas, label coverage, end-to-end latency |
| Candidate prefix sharing | Same prompt and candidate tokenization | Naive repeated requests versus trie replay | Exact conditioning, cancellation, memory, measured speed |
| Native batching | Independent contexts and existing engine ownership | Query concurrency versus actual native batch | Queue latency, tokens/second, no cross-request contamination |
| State grammar steering | Explicit token acknowledgement and committed-prefix boundary | Target-only first; speculation later | Stale commands, STOP/drain, no output after terminal state |
| Graph reconstruction | Human-labeled edges and hard format rules | Local threshold versus global selection | Structural accuracy, retained alternatives, immutable source bytes |
| Scene search | Syntax/geometry checks and human judgments | Generator alone versus measured search | Quality per model call and per second; text/pixel evaluator separation |
| Semantic calibration | Separate train/validation/test outcomes | Prompt, label order, temperature, model variants | Proper scoring rules and coverage/error curves |
| Speculation policy | Distinct draft and target semantics | Window size, MTP, suffix and target-only | Acceptance, total verified work, committed output and latency |
| Native GPU samplers | Exact host reference and counter-RNG contract | Same tensors, same profile, GPU selection | Full-support probabilities, selected IDs, operator order, transfer and kernel time |
| Cache-aware state replacement | Valid prefix and recurrent-state snapshot | Append, replace, re-prefill and safely reused prefix | Byte-identical state inputs, numerical tolerance, isolation and measured recomputation |
| Closed-loop controllers | Explicit dynamics, delays and admissible set | Model observer versus direct-state or ordinary controller | Regret, violations, oscillation, cost and held-out disturbances |

## Deliberately unusual experiments

The possibility tree includes eight inspectable protocols: musical tension,
proof-tactic allocation, compiler rewrites, circuit sketches, transactional
workflows, paraphrase-invariant observers, adversarial legal actions and adaptive
token budgets. Each names a hypothesis, intervention, ordinary baseline,
measurement and failure condition. These are original experiment proposals,
not a claim that their systems are implemented or that the model outperforms
domain tools. Their data lives in
[`research_ideas.py`](../examples/control_lab/research_ideas.py), and the UI
keeps the unimplemented label visible.

The useful pattern is a checkable outer world, an explicit state, a bounded
proposal language and an honest outcome metric. An implausible proposal can be
valuable if it exposes a missing assumption; a clever animation alone is not
evidence. Cache intervention, mid-generation steering and speculative sampler
feedback each require a separate native design and qualification gate.

An engineering roofline needs measured workload bytes and operations together
with sustained bandwidth/compute for the actual kernels. The latency page is a
starting frontier: it tells us where to look, not that the hardware ceiling was
reached. Keep quality, calibrated task outcomes and arithmetic reproducibility
as separate measurements.

## First-release boundaries

The lab is an optional loopback FastAPI client with local static assets. It
does not replace Strata's service, authentication, queue, scheduler, GPU process,
tokenizer or native constraint engine. It does not execute arbitrary generated
programs or real OS actions. The state controller previews a simulated transition
and the user applies it before the next model request.

The finite-group page measures one emitted token path for each supplied literal,
with a common visible terminator. It rejects duplicate/overlapping literals.
General language probability, alternative tokenizations and EOS mass require
additional machinery and are not hidden behind the word “grammar.”
