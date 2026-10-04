"""Typed raw target scores, native transport validation and parser byte alignment."""
from collections import deque
from dataclasses import dataclass
import math

CAPABILITY = "raw-v1"


def validate_logprobs(req):
    enabled, count = req.get("logprobs"), req.get("top_logprobs")
    if enabled is not None and type(enabled) is not bool:
        raise ValueError("logprobs must be boolean or null")
    if count is not None and (type(count) is not int or not 0 <= count <= 20):
        raise ValueError("top_logprobs must be an integer from 0 through 20 or null")
    if count is not None and enabled is not True:
        raise ValueError("top_logprobs requires logprobs:true")
    if enabled is not True:
        return None
    if type(req.get("n", 1)) is not int or req.get("n", 1) != 1:
        raise ValueError("logprobs supports n:1")
    if req.get("stop") not in (None, []) or req.get("logit_bias") not in (None, {}):
        raise ValueError("logprobs does not support custom stop strings or logit_bias")
    if req.get("strata_mcp") or req.get("functions"):
        raise ValueError("logprobs supports client-owned function tools, not server MCP or legacy functions")
    if req.get("modalities") not in (None, ["text"]) or req.get("audio") is not None:
        raise ValueError("logprobs supports text output only")
    for key in ("max_tokens", "max_completion_tokens"):
        if req.get(key) is not None and type(req[key]) is not int:
            raise ValueError(key + " must be an integer")
    if req.get("max_tokens") is not None and req.get("max_completion_tokens") is not None:
        raise ValueError("use one output-token limit field with logprobs")
    return count or 0


@dataclass(frozen=True)
class Probability:
    id: int
    logprob: float


@dataclass(frozen=True)
class ScoredToken:
    index: int
    id: int
    logprob: float
    top: tuple[Probability, ...]
    channel: str = "raw"
    sampling: dict | None = None


def parse_score(line, index, count):
    """LP index channel token logprob count id:logprob ... (one bounded record)."""
    if len(line) > 2048:
        raise ValueError("oversized native logprobs record")
    try:
        parts = line.split()
        if len(parts) < 6 or parts[0] != "LP" or int(parts[1]) != index or int(parts[5]) != count:
            raise ValueError()
        if len(parts) != 6 + count or parts[2] not in ("raw", "answer", "reasoning", "tool", "control"):
            raise ValueError()
        pairs = [part.split(":") for part in parts[6:]]
        top = tuple(Probability(int(token), float(value)) for token, value in pairs)
        token = ScoredToken(index, int(parts[3]), float(parts[4]), top, parts[2])
        if token.id < 0 or not math.isfinite(token.logprob) or token.logprob > 0:
            raise ValueError()
        if len({p.id for p in top}) != len(top) or any(p.id < 0 or not math.isfinite(p.logprob) or p.logprob > 0 for p in top):
            raise ValueError()
        if any(a.logprob < b.logprob or (a.logprob == b.logprob and a.id > b.id) for a, b in zip(top, top[1:])):
            raise ValueError()
        if any(p.id == token.id and p.logprob != token.logprob for p in top):
            raise ValueError()
        return token
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid, missing or out-of-order native logprobs record") from None


def probability_json(tokenizer, token, selected=False):
    try:
        raw = tokenizer.token_bytes(token.id)
    except (IndexError, KeyError, ValueError):
        raise ValueError("native logprobs token is outside the tokenizer vocabulary") from None
    kinds = getattr(tokenizer, "token_types", None)
    special = kinds is not None and kinds[token.id] != 1
    return {"token": raw.decode("utf-8", errors="replace"), "logprob": token.logprob,
            "bytes": None if special and not selected else list(raw)}


def score_json(tokenizer, token):
    result = {**probability_json(tokenizer, token, selected=True),
              "top_logprobs": [probability_json(tokenizer, p) for p in token.top]}
    if token.sampling is not None:
        result['strata_sampling'] = {**token.sampling, 'top': [
            {**p, 'bytes': list(tokenizer.token_bytes(p['id'])),
             'token': tokenizer.token_bytes(p['id']).decode('utf-8', errors='replace')}
            for p in token.sampling['top']]}
    return result


@dataclass
class _Span:
    start: int
    raw: bytes
    token: ScoredToken
    covered: int = 0

    @property
    def end(self):
        return self.start + len(self.raw)


class ContentScores:
    """Keep unresolved spans; annotate exact parser byte ranges without retokenizing.

    UTF-8 characters can span tokens and parser deltas can split tokens. A score
    follows when the whole token is emitted. A token shared between hidden syntax
    and visible content has no honest content-only score and fails explicitly.
    """
    def __init__(self, tokenizer):
        self.tokenizer, self.spans, self.position = tokenizer, deque(), 0

    def add(self, token):
        raw = self.tokenizer.token_bytes(token.id)
        if not raw:
            raise ValueError("cannot align an empty generated token")
        self.spans.append(_Span(self.position, raw, token))
        self.position += len(raw)

    def discard_before(self, offset):
        while self.spans and self.spans[0].end <= offset:
            span = self.spans.popleft()
            if span.covered:
                raise ValueError("logprobs token crosses visible content and hidden parser syntax")

    def annotate(self, events, resolved):
        for ev in events:
            if ev.kind != "content" or not ev.text:
                continue
            if ev.source_start is None:
                raise ValueError("missing content source position for logprobs")
            start, text = ev.source_start, ev.text.encode("utf-8")
            self.discard_before(start)
            cursor, scores = 0, []
            while cursor < len(text):
                if not self.spans:
                    raise ValueError("content lacks a native token score")
                span = self.spans[0]
                if span.start + span.covered != start + cursor:
                    raise ValueError("logprobs token crosses hidden parser syntax and visible content")
                size = min(len(span.raw) - span.covered, len(text) - cursor)
                if span.raw[span.covered:span.covered + size] != text[cursor:cursor + size]:
                    raise ValueError("content bytes differ from the scored native tokens")
                span.covered += size
                cursor += size
                if span.covered == len(span.raw):
                    scores.append(score_json(self.tokenizer, span.token))
                    self.spans.popleft()
            ev.logprobs = scores
        self.discard_before(resolved)
        return events

    def finish(self):
        if any(s.covered for s in self.spans):
            raise ValueError("logprobs token ended partly inside hidden parser syntax")
        self.spans.clear()
