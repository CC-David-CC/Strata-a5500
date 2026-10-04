# Educational control lab: experiment tree

The first release goal is a clear, working lab. All eleven pages run on committed
native receipts; live pages use the existing Strata API. This branch starts at
`work/logprobs-675` commit `2243cb1c5b1a87270731d8b8a76e4af001f96f97`.
The independent logprobs contribution can be reviewed without the lab.

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
|   +-- multiple semantic probes ..... implemented in scene and graph pages
|   +-- calibration / abstention ..... next: held-out labels, Brier/ECE, coverage
|   +-- label/permutation sensitivity  next: preserve meanings, permute labels
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
|   +-- token-acknowledged steering .. separate endpoint/rollback design, not here
|   +-- actual OS execution .......... outside this educational first release
|
+-- compose observations in code
|   +-- independent source ranking .. implemented; HTTP concurrency shown honestly
|   +-- immutable document graph ..... implemented; bounded exact subset optimizer
|   +-- JSON scene + code checks ..... implemented; text probes + human rendering view
|   +-- larger graph/search loop ..... next: sparse proposals, budget, quality metric
|   +-- observer/controller learning . next: logged state/action/outcome evaluation
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
