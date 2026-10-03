"""Stateless Responses protocol adapter over Strata's semantic service iterator.

One request-local assembler owns output and lifecycle. It never executes tools,
stores responses, calls another HTTP API, or selects a native inference mode.
"""
from __future__ import annotations

import copy
import json
import math
import time
import uuid
from dataclasses import dataclass

MAX_REQUEST_BYTES = 4 * 1024 * 1024
TERMINAL = frozenset(("completed", "incomplete", "failed", "cancelled"))


class RequestError(ValueError):
    def __init__(self, message, param=None, code="invalid_parameter", status=400):
        super().__init__(message)
        self.param, self.code, self.status = param, code, status

    def wire(self):
        return {"error": {"type": "invalid_request_error", "code": self.code,
                          "param": self.param, "message": str(self)}}


def strict_json(raw):
    """Validate the JSON transport, not a structured-output/schema guarantee."""
    def pairs(entries):
        obj = {}
        for key, value in entries:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj

    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    try:
        obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return obj
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RequestError("invalid JSON: " + str(exc), "body") from exc


def fields(obj, allowed, param):
    if not isinstance(obj, dict):
        raise RequestError("expected an object", param)
    extra = set(obj) - set(allowed.split())
    if extra:
        key = sorted(extra)[0]
        raise RequestError("unsupported parameter", f"{param}.{key}" if param else key, "unsupported_parameter")


def string(value, param, empty=True):
    if not isinstance(value, str) or (not empty and not value):
        raise RequestError("expected a string" + ("" if empty else " that is not empty"), param)
    return value


def unsupported(message, param):
    raise RequestError(message, param, "unsupported_parameter")


def validate_request(request, svc):
    """Single capability gate, before loading a model or writing success headers."""
    fields(request, "model input instructions stream store background metadata max_output_tokens temperature top_p "
           "text tools tool_choice parallel_tool_calls truncation include reasoning previous_response_id", "")
    req = copy.deepcopy(request)
    if req.get("model") not in svc.model_names():
        raise RequestError("model not found", "model", "model_not_found", 404)
    if req.get("store") is not False:
        unsupported("this stateless profile requires explicit store:false", "store")
    for key, default in (("stream", False), ("background", False), ("parallel_tool_calls", True)):
        req.setdefault(key, default)
        if type(req[key]) is not bool:
            raise RequestError("expected a boolean", key)
    if req["background"]:
        unsupported("background execution is not supported", "background")
    if req.get("previous_response_id") is not None:
        unsupported("replay full input items; no retained response context is available", "previous_response_id")
    if req.get("truncation", "disabled") != "disabled":
        unsupported("only truncation:disabled is supported", "truncation")
    if req.get("include", []) != []:
        unsupported("include representations, including encrypted reasoning, are not supported", "include")
    if "reasoning" in req and req["reasoning"] != {"effort": "none"}:
        unsupported("this profile supports only reasoning.effort:none", "reasoning")
    if req.get("instructions") is not None:
        string(req["instructions"], "instructions")
    cap = req.get("max_output_tokens")
    if cap is not None and (type(cap) is not int or cap < 1):
        raise RequestError("expected a positive integer", "max_output_tokens")
    defaults = {**svc.sampling_defaults, **svc.shared}
    for key, fallback, maximum in (("temperature", 0.0, 2.0), ("top_p", 1.0, 1.0)):
        value = req.get(key, defaults.get(key, fallback))
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise RequestError(f"expected a finite number from 0 to {maximum}", key)
        if key == "top_p" and value == 0:
            unsupported("the native sampler requires top_p > 0", key)
        req[key] = value
    metadata = req.setdefault("metadata", {})
    if not isinstance(metadata, dict) or len(metadata) > 16 or any(
            not isinstance(k, str) or len(k) > 64 or not isinstance(v, str) or len(v) > 512
            for k, v in metadata.items()):
        raise RequestError("metadata allows 16 string pairs (64-character keys, 512-character values)", "metadata")
    text = req.setdefault("text", {"format": {"type": "text"}})
    fields(text, "format", "text")
    fmt = text.setdefault("format", {"type": "text"})
    if fmt != {"type": "text"}:
        unsupported("only plain text.format is supported; JSON formats are excluded", "text.format")
    tools = req.setdefault("tools", [])
    if not isinstance(tools, list):
        raise RequestError("expected an array", "tools")
    if tools:
        unsupported("function tools are not enabled in this phase", "tools")
    if req.setdefault("tool_choice", "auto") not in ("auto", "none"):
        unsupported("only auto and none tool choices are supported", "tool_choice")
    return req


def resolve_input(req):
    """Map supplied content to the existing service representation; IDs are never lookups."""
    items = req.get("input", [])
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    if not isinstance(items, list) or not items:
        raise RequestError("input must be text or a nonempty array of items", "input")
    messages = []
    if req.get("instructions") is not None:
        messages.append({"role": "system", "content": req["instructions"]})
    for i, item in enumerate(items):
        param = f"input[{i}]"
        fields(item, "type id role content status", param)
        if item.get("type", "message") != "message":
            unsupported("only content-bearing message input is supported in this phase", param + ".type")
        if "id" in item:
            string(item["id"], param + ".id", False)
        if "status" in item and item["status"] != "completed":
            unsupported("only completed items can be replayed", param + ".status")
        role = item.get("role")
        if role not in ("system", "developer", "user", "assistant"):
            raise RequestError("unsupported message role", param + ".role")
        content = item.get("content")
        if isinstance(content, list):
            if not content:
                raise RequestError("expected nonempty content", param + ".content")
            parts = []
            for j, part in enumerate(content):
                loc = f"{param}.content[{j}]"
                fields(part, "type text annotations logprobs", loc)
                accepted = ("input_text", "output_text") if role == "assistant" else ("input_text",)
                if part.get("type") not in accepted:
                    unsupported("only text content is supported", loc + ".type")
                if part.get("annotations", []) != [] or part.get("logprobs", []) != []:
                    unsupported("annotated content is not supported", loc)
                parts.append(string(part.get("text"), loc + ".text"))
            content = "".join(parts)
        messages.append({"role": role, "content": string(content, param + ".content")})
    return messages


def transition(current, event):
    """Pure lifecycle decision, with no HTTP, filesystem or model operations."""
    if current == "queued" and event == "start":
        return "in_progress"
    if current == "in_progress":
        if event == "output":
            return current
        if event in ("complete", "exhaust"):
            return "completed" if event == "complete" else "incomplete"
    if current in ("queued", "in_progress"):
        if event in ("fail", "stopped"):
            return "failed" if event == "fail" else "cancelled"
    raise ValueError(f"invalid response transition: {current} / {event}")


def new_id(prefix):
    return prefix + "_" + uuid.uuid4().hex


class ResponseAssembler:
    """Canonical request-local owner. Incremental buffers are serialized only at boundaries."""
    def __init__(self, request, input_tokens, max_new):
        self.response = {
            "id": new_id("resp"), "object": "response", "created_at": int(time.time()),
            "status": "queued", "completed_at": None, "error": None, "incomplete_details": None,
            "instructions": request.get("instructions"), "model": request["model"], "output": [],
            "usage": None, "store": False, "background": False, "previous_response_id": None,
            "max_output_tokens": max_new, "temperature": request["temperature"], "top_p": request["top_p"],
            "text": copy.deepcopy(request["text"]), "tools": copy.deepcopy(request["tools"]),
            "tool_choice": request["tool_choice"], "parallel_tool_calls": request["parallel_tool_calls"],
            "reasoning": {"effort": "none", "summary": None}, "truncation": "disabled",
            "metadata": copy.deepcopy(request["metadata"]),
        }
        self.input_tokens = input_tokens
        self.sequence = 0
        self.fragments = []
        self.item = None

    def snapshot(self):
        result = copy.deepcopy(self.response)
        if self.item is not None and self.response["status"] not in TERMINAL:
            result["output"][-1]["content"][0]["text"] = "".join(self.fragments)
        return result

    def event(self, kind, **data):
        event = {"type": kind, "sequence_number": self.sequence, **data}
        self.sequence += 1
        return event

    def advance_response(self, event):
        self.response["status"] = transition(self.response["status"], event)

    def append_output(self, event):
        self.advance_response("output")
        if event.kind != "content":
            raise ValueError(f"unexpected semantic output in answer-only profile: {event.kind}")
        if not event.text:
            return []
        out = []
        if self.item is None:
            self.item = {"id": new_id("msg"), "type": "message", "status": "in_progress", "role": "assistant",
                         "content": []}
            self.response["output"].append(self.item)
            out.append(self.event("response.output_item.added", output_index=0, item=copy.deepcopy(self.item)))
            part = {"type": "output_text", "text": "", "annotations": [], "logprobs": []}
            self.item["content"].append(part)
            out.append(self.event("response.content_part.added", item_id=self.item["id"], output_index=0,
                                  content_index=0, part=copy.deepcopy(part)))
        self.fragments.append(event.text)
        out.append(self.event("response.output_text.delta", item_id=self.item["id"], output_index=0,
                              content_index=0, delta=event.text, logprobs=[]))
        return out

    def finalize_response(self, outcome, done=None, error=None):
        # Decide before touching any content: terminal responses are immutable.
        terminal = transition(self.response["status"], outcome)
        out = []
        if self.item is not None:
            part = self.item["content"][0]
            part["text"] = "".join(self.fragments)
            self.fragments.clear()
            self.item["status"] = "completed" if terminal == "completed" else "incomplete"
            out.append(self.event("response.output_text.done", item_id=self.item["id"], output_index=0,
                                  content_index=0, text=part["text"], logprobs=[]))
            out.append(self.event("response.content_part.done", item_id=self.item["id"], output_index=0,
                                  content_index=0, part=copy.deepcopy(part)))
            out.append(self.event("response.output_item.done", output_index=0, item=copy.deepcopy(self.item)))
        self.response["status"] = terminal
        self.response["error"] = error
        self.response["incomplete_details"] = {"reason": "max_output_tokens"} if terminal == "incomplete" else None
        if terminal == "completed":
            self.response["completed_at"] = int(time.time())
        if done is not None:
            count = done["completion_tokens"]
            self.response["usage"] = {"input_tokens": self.input_tokens, "output_tokens": count,
                "total_tokens": self.input_tokens + count,
                "input_tokens_details": {"cached_tokens": min(done.get("reused") or 0, self.input_tokens)},
                "output_tokens_details": {"reasoning_tokens": 0}}
        # Transport cancellation follows a disconnected connection. There is no
        # documented response.cancelled SSE event and no cancel endpoint here.
        if terminal != "cancelled":
            out.append(self.event("response." + terminal, response=self.snapshot()))
        return out


@dataclass
class PreparedResponse:
    assembler: ResponseAssembler
    ids: list
    max_new: int
    sampling: dict


def create_response(svc, request):
    req = validate_request(request, svc)
    messages = resolve_input(req)
    svc.load()
    ids, thinking, max_new = svc.prepare(messages, None, {"enable_thinking": False}, req.get("max_output_tokens"))
    if thinking:
        raise ValueError("answer-only preparation unexpectedly enabled reasoning")
    return PreparedResponse(ResponseAssembler(req, len(ids), max_new), ids, max_new,
                            {"temperature": req["temperature"], "top_p": req["top_p"]})


def execute_response(svc, prepared, cancel):
    """One execution for JSON and SSE. Closing it cancels/drains before returning ownership."""
    owner = prepared.assembler
    iterator = None
    try:
        yield owner.event("response.created", response=owner.snapshot())
        iterator = svc.run(prepared.ids, False, None, prepared.max_new, prepared.sampling, cancel, lifecycle=True)
        done = None
        for kind, value in iterator:
            if kind == "start":
                owner.advance_response("start")
                yield owner.event("response.in_progress", response=owner.snapshot())
            elif kind == "event":
                if not cancel.is_set():
                    yield from owner.append_output(value)
            elif kind == "ping":
                yield None
            elif kind == "done":
                done = value
            else:
                raise ValueError(f"unknown service event: {kind}")
        if done is None:
            raise ValueError("service ended without a generation outcome")
        finish = done["finish"]
        if cancel.is_set() or finish == "cancel":
            outcome = "stopped"
        elif finish == "stop":
            outcome = "complete"
        elif finish == "length":
            outcome = "exhaust"
        else:
            raise ValueError(f"unexpected generation outcome: {finish}")
        yield from owner.finalize_response(outcome, done)
    except GeneratorExit:
        cancel.set()
        raise
    except Exception as exc:
        cancel.set()
        if iterator is not None:
            try:
                iterator.close()
            except Exception as cleanup_error:
                exc = cleanup_error
            iterator = None
        if owner.response["status"] in TERMINAL:
            raise
        yield from owner.finalize_response("fail", error={"code": "server_error", "message": str(exc)})
    finally:
        try:
            if iterator is not None:
                iterator.close()
        except Exception as exc:
            if owner.response["status"] not in TERMINAL:
                owner.finalize_response("fail", error={"code": "server_error", "message": str(exc)})
            raise
        else:
            if owner.response["status"] not in TERMINAL:
                # Cleanup has confirmed work stopped; requesting cancellation
                # alone never changes the canonical response to cancelled.
                owner.finalize_response("stopped")
