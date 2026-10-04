"""Pure calculations and application rules. No HTTP or model execution here."""
from __future__ import annotations

import itertools
import json
import math


def logsumexp(values):
    values = list(values)
    if not values or any(not math.isfinite(x) for x in values):
        raise ValueError("Expected nonempty finite log probabilities")
    largest = max(values)
    return largest + math.log(math.fsum(math.exp(x - largest) for x in values))


def normalized_weights(logps):
    total = logsumexp(logps)
    return [math.exp(x - total) for x in logps]


def distribution_stats(weights, levels=None):
    if len(weights) < 2 or any(not math.isfinite(p) or p < 0 for p in weights):
        raise ValueError("Need at least two nonnegative weights")
    if not math.isclose(math.fsum(weights), 1, abs_tol=1e-8):
        raise ValueError("Weights must sum to one")
    ordered = sorted(weights, reverse=True)
    n = len(weights)
    result = {
        "top_weight": ordered[0], "margin": ordered[0] - ordered[1],
        "peakedness": (ordered[0] - 1 / n) / (1 - 1 / n),
        "entropy_bits": -math.fsum(p * math.log2(p) for p in weights if p),
    }
    if levels is not None:
        if len(levels) != n or any(not math.isfinite(x) for x in levels):
            raise ValueError("One finite numeric value per level is required")
        mean = math.fsum(p * x for p, x in zip(weights, levels))
        result.update(expected_score=mean, variance=math.fsum(p * (x - mean) ** 2 for p, x in zip(weights, levels)))
    return result


def literal_grammar(strings, *, max_literals=16):
    if not strings or len(strings) > max_literals or len(set(strings)) != len(strings):
        raise ValueError(f"Use 1..{max_literals} distinct literal answers")
    if any(not s or len(s.encode('utf-8')) > 256 or '\0' in s for s in strings):
        raise ValueError("Answers must have 1..256 UTF-8 bytes and no NUL")
    return 'root ::= ' + ' | '.join(json.dumps(s, ensure_ascii=False) for s in strings)


def validate_groups(groups):
    if not 2 <= len(groups) <= 4:
        raise ValueError("Use two to four finite grammar groups")
    seen, names = set(), set()
    for group in groups:
        if not group['name'] or group['name'] in names:
            raise ValueError("Grammar groups need unique names")
        names.add(group['name'])
        if not 1 <= len(group['answers']) <= 4:
            raise ValueError("Each group needs one to four literal answers")
        for answer in group['answers']:
            literal_grammar([answer])
            if '\n' in answer or '\r' in answer:
                raise ValueError("Answers cannot contain newlines; the lab appends one common terminator")
            if answer in seen:
                raise ValueError("Overlapping groups would double-count a path; assign each answer once")
            seen.add(answer)
    return groups


def score_content(reply, expected=None):
    choice = reply['choices'][0]
    entries = (choice.get('logprobs') or {}).get('content')
    if entries is None:
        raise ValueError("This Strata server did not return content logprobs")
    content = choice['message'].get('content') or ''
    if bytes(b for e in entries for b in e['bytes']) != content.encode('utf-8'):
        raise ValueError("Scored bytes do not reproduce the exact answer")
    if expected is not None and content != expected:
        raise ValueError(f"Incomplete constrained answer: expected {expected!r}, got {content!r}")
    if not entries:
        raise ValueError("No visible answer tokens were scored")
    for e in entries:
        if not math.isfinite(e['logprob']) or e['logprob'] > 0:
            raise ValueError("Invalid selected-token logprob")
    total = math.fsum(e['logprob'] for e in entries)
    return {"text": content, "tokens": entries, "token_count": len(entries),
            "logprob": total, "path_probability": math.exp(total),
            "mean_logprob": total / len(entries), "finish_reason": choice['finish_reason']}


def top_row_distribution(reply, labels):
    """Only exact single-token byte matches; an absent label stays unknown."""
    entries = (reply['choices'][0].get('logprobs') or {}).get('content') or []
    if not entries:
        raise ValueError("Missing first-token scores")
    row = entries[0]
    available = {bytes(t['bytes']): t['logprob'] for t in row['top_logprobs'] if t.get('bytes') is not None}
    available[bytes(row['bytes'])] = row['logprob']
    values = [available.get(label.encode('utf-8')) for label in labels]
    missing = [label for label, lp in zip(labels, values) if lp is None]
    if missing:
        return {"complete": False, "missing": missing, "raw_logprobs": values}
    return {"complete": True, "missing": [], "raw_logprobs": values,
            "weights": normalized_weights(values), "reported_label_mass": math.fsum(math.exp(x) for x in values)}


STATES = ['unread', 'inspected', 'edited', 'verified', 'done']
ACTIONS = {
    'inspect': 'Read the file and its failing test',
    'edit': 'Fix the off-by-one bug',
    'test': 'Run the small verification suite',
    'finish': 'Mark the task complete',
    'ask': 'Ask for missing information',
}


def allowed_actions(state):
    if state not in STATES:
        raise ValueError("Unknown controller state")
    return {
        'unread': ['inspect', 'ask'], 'inspected': ['edit', 'ask'],
        'edited': ['test', 'edit', 'ask'], 'verified': ['finish', 'inspect'], 'done': [],
    }[state]


def advance_state(state, action):
    if action not in allowed_actions(state):
        raise ValueError(f"{action} is not allowed while {state}")
    return {'inspect': 'inspected', 'edit': 'edited', 'test': 'verified',
            'finish': 'done', 'ask': state}[action]


def admissible_graph(edges):
    outgoing, incoming, caption_targets = {}, {}, set()
    for e in edges:
        a, b = e['source'], e['target']
        if a == b:
            return False
        if e['relation'] == 'caption':
            if a in caption_targets:
                return False
            caption_targets.add(a)
        else:
            if a in outgoing or b in incoming:
                return False
            outgoing[a] = b
            incoming[b] = a
    for start in outgoing:
        visited, current = set(), start
        while current in outgoing:
            if current in visited:
                return False
            visited.add(current)
            current = outgoing[current]
    return True


def reconstruct_graph(edges, threshold=0.5):
    """Exact bounded subset search; objective is utility, NOT a joint probability."""
    if len(edges) > 12 or not 0 < threshold < 1:
        raise ValueError("The inspectable solver supports at most 12 edges and a threshold inside (0, 1)")
    for e in edges:
        if not 0 <= e['weight'] <= 1 or not math.isfinite(e['weight']):
            raise ValueError("Invalid edge weight")
    best, best_utility, feasible = [], 0.0, 0
    for mask in itertools.product((False, True), repeat=len(edges)):
        selected = [e for e, yes in zip(edges, mask) if yes]
        if not admissible_graph(selected):
            continue
        feasible += 1
        utility = math.fsum(e['weight'] - threshold for e in selected)
        if utility > best_utility:
            best, best_utility = selected, utility
    return {"selected": best, "utility": best_utility, "feasible_subsets": feasible,
            "evaluated_subsets": 2 ** len(edges), "threshold": threshold,
            "objective": "sum(edge weight - threshold), not a calibrated joint probability"}
