"""Explanations and editable starting points for every page."""
CHOICES = [
    {'label': 'A', 'description': 'A request to fix a software bug'},
    {'label': 'B', 'description': 'A question about using the software'},
    {'label': 'C', 'description': 'A request to change the documentation'},
]
GROUPS = [
    {'name': 'Inspect first', 'answers': ['read the failing test', 'inspect the error log']},
    {'name': 'Change something', 'answers': ['edit the parser', 'restart the service']},
]
SOURCES = [
    {'id': 'S1', 'text': 'Strata serializes model execution. A client disconnect sends STOP and drains engine output before the next request.'},
    {'id': 'S2', 'text': 'A FastAPI example can serve static HTML and pass authenticated requests to an existing inference server.'},
    {'id': 'S3', 'text': 'The recipe uses two eggs and one cup of flour. Bake until golden.'},
]
BLOCKS = [
    {'id': 'B17', 'location': 'page 2, line 4', 'text': 'The engine stops generation when'},
    {'id': 'B18', 'location': 'page 2, line 5', 'text': 'the client disconnects, then drains pending output.'},
    {'id': 'B19', 'location': 'page 2, figure 1 caption', 'text': 'Figure 1. A request moves through the engine queue.'},
    {'id': 'B20', 'location': 'page 2, paragraph 3', 'text': 'The diagram below shows the request queue and cancellation path.'},
]


def page(id, title, eyebrow, simple, detail, defaults, features, next_gate):
    return dict(id=id, title=title, eyebrow=eyebrow, simple=simple, detail=detail,
                defaults=defaults, features=features, next_gate=next_gate)


PAGES = [
    page('choice', 'A question becomes a number.', '01 / MEASURE',
         'Give the model a situation and a few answers. See how strongly it prefers each answer.',
         'The fast path uses exact single-token labels in one raw target row. Missing top-N labels stay unknown. The complete path forces each label separately and normalizes its raw logprob. Neither path is calibrated by this demo.',
         dict(state='The save button crashes the app when the filename contains an emoji.', question='What kind of ticket is this?', choices=CHOICES, strategy='complete'),
         ['logprobs', 'GBNF', 'choice'], 'A native arbitrary-label score gather could replace repeated candidate calls. Test label permutations and calibration on held-out tickets.'),
    page('boolean', 'A useful, measurable “if”.', '02 / PROBE',
         'Ask one yes-or-no question. Your code decides what to do with the answer.',
         'This Noul-like probe is a normalized Yes/No label comparison on a generative model. The output is a semantic measurement feature, not a proven truth probability. Related probes may share errors.',
         dict(state='The customer says: please cancel my subscription at the end of this month.', question='Does the customer explicitly ask to cancel?', strategy='complete'),
         ['logprobs', 'GBNF', 'boolean'], 'Evaluate Brier score, calibration, and abstention against labeled examples before choosing a production threshold.'),
    page('score', 'A scale, with its whole shape.', '03 / SCORE',
         'Choose clear descriptions for low, medium, and high. See a rating and the alternatives behind it.',
         'The displayed continuous rating is the expectation of three explicit rubric values. It is not a separately predicted scalar. Spread and entropy remain visible.',
         dict(state='The application is unavailable to all customers and no workaround exists.', question='How severe is this incident?', strategy='complete', choices=[
             {'label': 'A', 'description': 'Minor inconvenience; normal work can continue', 'value': 0},
             {'label': 'B', 'description': 'Work is degraded; a workaround exists', 'value': 0.5},
             {'label': 'C', 'description': 'Work is blocked for everyone; no workaround', 'value': 1}]),
         ['logprobs', 'GBNF', 'rubric'], 'Compare ordinal calibration and ranking stability under paraphrases; keep the rubric fixed when comparing models.'),
    page('candidates', 'Compare whole paths, not just letters.', '04 / BRANCH',
         'Two grammars describe different plans. Score every listed sentence and see which group carries more weight.',
         'Each literal answer plus a newline is generated under its own grammar, using the same prompt. Sum conditional raw token logprobs, then log-sum-exp within each disjoint finite group. This covers one emitted token path per listed string, not every tokenization or an infinite grammar language. EOS is not included.',
         dict(state='A test failed after a parser change. The failure has not been read yet.', question='What should the developer do next?', groups=GROUPS),
         ['logprobs', 'GBNF', 'multi-token', 'finite groups'], 'A native prefix trie and teacher-forced batches can share common work. General grammar-language probability needs explicit truncation and unscored-mass bounds.'),
    page('controller', 'The model suggests. State decides.', '05 / CONTROL',
         'Fix a tiny bug one step at a time. You cannot finish before the test passes.',
         'The application derives a fresh legal grammar from the current state for each completed decision. It compares raw action-label scores, generates a legal action, then applies a pure transition. This is a simulated OS task with real model judgments; no shell command runs. It does not change grammar during a token stream.',
         dict(state='Fix an off-by-one bug in count_items, then verify it.', controller_state='unread', threshold=0),
         ['logprobs', 'GBNF', 'state machine'], 'A separate token-acknowledged steering endpoint could update grammar inside a generation; it requires cancellation and speculative rollback gates.'),
    page('rerank', 'Find the useful source.', '06 / RETRIEVE',
         'Ask the same relevance question about several sources. Keep the original text and sort the scores.',
         'Each source receives its own three-level relevance distribution. The scores are not a softmax across documents and are not statistically independent. Concurrent HTTP requests still enter Strata’s existing single-engine queue.',
         dict(question='How does Strata handle cancellation without corrupting the next request?', sources=SOURCES, parallel=1),
         ['logprobs', 'GBNF', 'reranking'], 'Measure full collection recall/latency. A native batched scoring path could share the query prefix; more HTTP concurrency alone does not create GPU batching.'),
    page('graph', 'Recover structure. Keep the words.', '07 / CONNECT',
         'The model weighs possible links between text blocks. Code chooses a legal graph without rewriting a word.',
         'A bounded exact subset solver maximizes sum(weight - threshold), enforces an acyclic reading chain and one target per caption, and preserves all rejected alternatives. The objective is application utility, not a product of supposedly independent correctness probabilities.',
         dict(threshold=0.5), ['logprobs', 'GBNF', 'graph solver'],
         'Larger documents need sparse candidate retrieval and an appropriate constrained optimizer; measure edge labels and final structural accuracy separately.'),
    page('scene', 'Generate. Check. Score. Look.', '08 / SEARCH',
         'Make a small scene, check its rules, compare a repaired candidate, and judge the drawing yourself.',
         'Native JSON Schema constrains the scene. Code checks geometry. A text-only semantic probe scores three properties of each candidate; it does not see the rendered image. Search chooses by a weighted measurement vector, while a human judges visual quality.',
         dict(state='A blue circle is left of a gold square, and they do not overlap.'),
         ['JSON Schema', 'logprobs', 'GBNF', 'semantic vector'], 'Scale to a bounded proposal/search loop and compare with human image judgments. Text probes cannot stand in for visual evaluation.'),
    page('wire', 'Open the engine’s answer.', '09 / INSPECT',
         'Watch tokens arrive. Click a token to see the alternatives. Open the exact request and response.',
         'The ten original contract examples cover plain scores, streaming, constraints, native JSON, reasoning and client-owned tools. Reasoning and tool envelopes are distinct from scored answer content. No incoming tool output is grammar-constrained.',
         dict(case='stream'), ['logprobs', 'GBNF', 'JSON', 'SSE', 'reasoning', 'tools'],
         'Test additional tokenizers and parser boundaries. Mixed visible/hidden token fragments fail explicitly instead of receiving invented substring scores.'),
    page('speculation', 'A proposal is not a verdict.', '10 / VERIFY',
         'See a draft token the target model rejected. Both numbers matter, but they answer different questions.',
         'These are original native diagnostic receipts. Draft probabilities and target verification use different heads and sometimes different vocabularies. Accepted output uses retained target rows. Suffix lookup has no draft probability distribution. Replay follows another numerical path.',
         dict(), ['MTP', 'suffix', 'draft / target', 'replay'],
         'Sweep lookahead versus acceptance and wall time before changing the policy. Draft top-N and live diagnostic HTTP endpoints are not implemented.'),
    page('performance', 'Measure the cost of each control.', '11 / MEASURE TIME',
         'Time plain output, scores, grammar, and JSON on the same server. Inspect every run.',
         'This is a latency frontier, not a claim of hardware roofline saturation. Request time includes queueing, network, prefill, decode and API overhead. Cache counters and engine timings are retained. A hardware roofline needs measured bytes, bandwidth, FLOPs and kernel time.',
         dict(repeats=3), ['logprobs', 'GBNF', 'JSON', 'latency'],
         'Profile the limiting kernels, bound memory/compute cost, then optimize one branch at a time. Keep target-only, MTP, suffix and replay measurements separate.'),
]
BY_ID = {p['id']: p for p in PAGES}
