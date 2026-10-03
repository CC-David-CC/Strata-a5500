"""Raw GBNF request contract. Compilation and token legality belong to native code.

This is a Strata extension, not an OpenAI JSON format or custom-tool frontend.
"""
from dataclasses import dataclass
import math


CAPABILITY = "gbnf-v2"
ANSWER_PREFIX = "<|im_start|>assistant\n<think>\n\n</think>\n\n"


@dataclass(frozen=True)
class GrammarConstraint:
    source: str

    def __post_init__(self):
        if not isinstance(self.source, str):
            raise ValueError("grammar must be a UTF-8 GBNF source string with a root rule")
        try:
            raw = self.source.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("grammar must be valid UTF-8") from exc
        if not 1 <= len(raw) <= 8192 or b"\0" in raw:
            raise ValueError("grammar must contain 1..8192 UTF-8 bytes, without NUL")

    def frame(self, command):
        # One byte write under the service FIFO; grammar cannot inject commands.
        if "\n" in command or "\r" in command or "\0" in command or not (
                command == "CHECKG" or command.startswith("GEN ")):
            raise ValueError("invalid native grammar command")
        raw = self.source.encode("utf-8")
        return f"GENG1 {len(raw)}\n".encode("ascii") + raw + b"\n" + command.encode("ascii") + b"\n"


def validate_grammar_request(req, api):
    """Normalize one optional constraint; reject conflicts before model loading."""
    if "grammar" not in req:
        return None
    constraint = GrammarConstraint(req["grammar"])
    if req.get("tools") or req.get("functions") or req.get("strata_mcp"):
        raise ValueError("grammar cannot be combined with tools or MCP")
    if req.get("tool_choice", "auto") not in ("auto", "none") or req.get("function_call") is not None:
        raise ValueError("grammar cannot request a tool call")
    if req.get("stop") not in (None, []):
        raise ValueError("grammar cannot be combined with custom stop strings")
    if req.get("response_format") not in (None, {"type": "text"}):
        raise ValueError("grammar cannot be combined with response_format JSON requirements")
    if req.get("text", {"format": {"type": "text"}}) != {"format": {"type": "text"}}:
        raise ValueError("grammar requires plain text.format")
    reasoning = req.get("reasoning", {})
    if not isinstance(reasoning, dict) or reasoning.get("summary") is not None:
        raise ValueError("grammar cannot generate reasoning or a reasoning summary")
    if req.get("include") or req.get("reasoning_budget_tokens") is not None:
        raise ValueError("grammar cannot request reasoning output or a thinking budget")
    kw = req.get("chat_template_kwargs", {})
    if not isinstance(kw, dict):
        raise ValueError("chat_template_kwargs must be an object")
    efforts = [v for v in (reasoning.get("effort"), req.get("reasoning_effort"), kw.get("reasoning_effort"))
               if v is not None]
    if any(v != "none" for v in efforts) or ("enable_thinking" in kw and kw["enable_thinking"] is not False):
        raise ValueError("grammar requires reasoning to be explicitly disabled")
    if api == "responses":
        if reasoning.get("effort") != "none":
            raise ValueError("grammar requires explicit reasoning.effort:none")
    elif not efforts and kw.get("enable_thinking") is not False:
        raise ValueError("grammar requires reasoning_effort:none or chat_template_kwargs.enable_thinking:false")
    if api == "chat":
        # The legacy adapter is permissive. The new constrained profile must not
        # silently ignore behavior-changing fields (e.g. logit_bias or audio).
        allowed = set("model messages stream stream_options max_tokens max_completion_tokens temperature top_p top_k "
                      "min_p seed presence_penalty frequency_penalty repetition_penalty penalty_last_n grammar "
                      "tools tool_choice parallel_tool_calls response_format reasoning reasoning_effort chat_template_kwargs "
                      "stop n logprobs top_logprobs logit_bias user metadata strata_mcp experimental_speed_projection".split())
        unknown = set(req) - allowed
        if unknown:
            raise ValueError("unsupported grammar request fields: " + ", ".join(sorted(unknown)))
        if type(req.get("n", 1)) is not int or req.get("n", 1) != 1 \
                or (req.get("logprobs") is not None and req["logprobs"] is not False) or req.get("top_logprobs") is not None \
                or req.get("logit_bias") not in (None, {}):
            raise ValueError("grammar supports n:1, no logprobs and no logit_bias")
        for key in ("max_tokens", "max_completion_tokens"):
            if key in req and req[key] is not None and type(req[key]) is not int:
                raise ValueError(f"{key} must be an integer")
        if req.get("max_tokens") is not None and req.get("max_completion_tokens") is not None:
            raise ValueError("grammar requests must use only one output-token limit field")
        if "stream" in req and type(req["stream"]) is not bool:
            raise ValueError("stream must be a boolean")
        opts = req.get("stream_options")
        if opts is not None:
            raise ValueError("grammar does not support stream_options; the existing Chat stream includes usage "
                             "in its final choice chunk")
        if set(kw) - {"enable_thinking", "reasoning_effort"}:
            raise ValueError("unsupported chat_template_kwargs for grammar")
        if set(reasoning) - {"effort", "summary"}:
            raise ValueError("unsupported reasoning fields for grammar")
    validate_sampling(req)
    return constraint


def validate_sampling(values):
    # These are the existing native sampler's ranges, not a new sampler. A
    # top_k of zero has the existing documented mapping to its 64-candidate cap.
    ranges = {"temperature": (0, 2), "top_p": (0, 1), "min_p": (0, 1),
              "presence_penalty": (-2, 2), "frequency_penalty": (-2, 2), "repetition_penalty": (0, 100)}
    for key, (lo, hi) in ranges.items():
        value = values.get(key)
        if value is None:
            continue
        if type(value) not in (float, int) or not math.isfinite(value) or not lo <= value <= hi \
                or (key in ("top_p", "repetition_penalty") and value == 0):
            raise ValueError(f"unsupported grammar sampling value: {key}")
    for key, lo, hi in (("top_k", 0, 64), ("seed", 0, 2**64 - 1), ("penalty_last_n", 1, 8192)):
        value = values.get(key)
        if value is not None and (type(value) is not int or not lo <= value <= hi):
            raise ValueError(f"unsupported grammar sampling value: {key}")
    if values.get("strata_tune"):
        raise ValueError("grammar requests cannot override native speculation/tuning settings")


def vocabulary_identity(tok, stops):
    """Match the native byte-table diagnostic to catch tokenizer configuration drift.

    This is not authentication. Tokenizer objects and native model files remain
    trusted server configuration; no Python tokenizer or matcher is substituted.
    """
    types = getattr(tok, "token_types", None)
    if not hasattr(tok, "token_bytes") or not types or len(types) > 300000:
        raise ValueError("grammar needs a tokenizer with explicit emitted bytes and token types")
    value = 14695981039346656037

    def feed(raw):
        nonlocal value
        for b in raw:
            value = ((value ^ b) * 1099511628211) & 0xffffffffffffffff

    def number(n):
        feed(n.to_bytes(8, "little"))

    number(len(types))
    for i, kind in enumerate(types):
        raw = tok.token_bytes(i) if kind == 1 and i not in stops else b""
        number(len(raw))
        feed(raw)
    number(len(stops))
    for i in sorted(stops):
        number(i)
    return f"bytes-v1-fnv1a64:{value:016x}"
