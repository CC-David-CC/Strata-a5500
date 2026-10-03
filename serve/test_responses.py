"""Responses contract tests over real HTTP + the existing semantic Service/MockEngine.

All scripted engine output is synthetic. Client capture/SDK receipts name their
provenance separately; these tests do not establish Codex or native GPU support.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import socket
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

from serve import server
from serve.frontend import ChatTemplate, Event
from serve.responses import (RequestError, create_response, execute_response, resolve_input,
                             strict_json, transition, validate_request)

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3.8-flash-next"


def service(script="Hello, 猫.", engine_class=server.MockEngine, **kwargs):
    tok = server.ByteTokenizer()
    engine = engine_class(tok, script, **kwargs)
    svc = server.Service(engine, tok, ChatTemplate(ROOT / "serve/chat_template.jinja"))
    svc.experimental_responses = True
    return svc


def request(**kwargs):
    return {"model": MODEL, "input": "Hello", "store": False, **kwargs}


@contextlib.contextmanager
def listening(svc):
    with mock.patch.object(svc, "start_telemetry"):
        httpd = server.serve(svc, port=0)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def http(base, body=None, path="/v1/responses", headers=None, method=None):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = urllib.request.Request(base + path, data=data,
        headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        result = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as exc:
        result = exc
    with result:
        return result.status, dict(result.headers), result.read()


class Normalization(unittest.TestCase):
    def setUp(self):
        self.svc = service()

    def test_explicit_stateless_contract(self):
        for body in (request(store=True), {"model": MODEL, "input": "hi"}, request(store=0)):
            with self.subTest(body=body), self.assertRaises(RequestError) as err:
                create_response(self.svc, body)
            self.assertEqual(err.exception.param, "store")
        self.assertEqual(self.svc.engine.last_prompt, [])

    def test_priority_order_and_content_bearing_ids(self):
        req = request(instructions="top", input=[
            {"role": "developer", "content": "developer"}, {"role": "system", "content": "system"},
            {"role": "user", "content": [{"type": "input_text", "text": "first"}]},
            {"id": "msg_not_stored", "type": "message", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": "answer", "annotations": [], "logprobs": []}]},
            {"role": "user", "content": "second"}])
        original = copy.deepcopy(req)
        normalized = resolve_input(validate_request(req, self.svc))
        self.assertEqual([m["role"] for m in normalized], ["system", "developer", "system", "user", "assistant", "user"])
        self.assertEqual([m["content"] for m in normalized], ["top", "developer", "system", "first", "answer", "second"])
        self.assertEqual(req, original)

    def test_unsupported_capabilities_rejected_before_load(self):
        cases = [dict(previous_response_id="resp_missing"), dict(background=True),
                 dict(text={"format": {"type": "json_schema", "schema": {}}}),
                 dict(text={"format": {"type": "json_object"}}), dict(text={"verbosity": "high"}),
                 dict(reasoning={"summary": "auto"}), dict(include=["reasoning.encrypted_content"]),
                 dict(input=[{"type": "item_reference", "id": "msg_missing"}]),
                 dict(input=[{"role": "user", "content": [{"type": "input_image", "image_url": "file://private"}]}]),
                 dict(grammar="root ::= \"x\""), dict(response_format={"type": "json_object"}),
                 dict(conversation="conv_any"), dict(prompt_cache_key="session"), dict(tool_choice="required"),
                 dict(tools=[{"type": "web_search"}]), dict(client_metadata={"private": "ignored?"})]
        with mock.patch.object(self.svc, "load") as load:
            for extra in cases:
                with self.subTest(extra=extra), self.assertRaises(RequestError):
                    create_response(self.svc, request(**extra))
            load.assert_not_called()

    def test_bad_types_and_limits(self):
        for extra in (dict(model="missing"), dict(stream=1), dict(max_output_tokens=True),
                      dict(max_output_tokens=0), dict(input={}), dict(input=[]), dict(temperature=float("nan")),
                      dict(top_p=0), dict(top_p=2), dict(metadata={"a": 4}), dict(instructions=9)):
            with self.subTest(extra=extra), self.assertRaises(RequestError):
                create_response(self.svc, request(**extra))

    def test_json_transport_is_strict_without_schema_support(self):
        for raw in ('{"store":false,"store":true}', '{"x":NaN}', '{"x":1e999}', '{"x":"\\ud800"}', '{'):
            with self.subTest(raw=raw), self.assertRaises(RequestError):
                strict_json(raw)

    def test_known_harmless_metadata_and_effective_sampling(self):
        self.svc.sampling_defaults = {"temperature": 0.7, "top_p": 0.8, "top_k": 9}
        p = create_response(self.svc, request(metadata={"purpose": "fixture"}, reasoning={"effort": "none"}))
        self.assertEqual(p.sampling, {"temperature": 0.7, "top_p": 0.8})
        self.assertEqual(p.assembler.snapshot()["metadata"], {"purpose": "fixture"})


class Lifecycle(unittest.TestCase):
    def test_normal_execution_and_terminal_immutability(self):
        svc = service("hello")
        p = create_response(svc, request())
        events = list(execute_response(svc, p, threading.Event()))
        final = p.assembler.snapshot()
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["output"][0]["content"][0]["text"], "hello")
        self.assertEqual(final["usage"]["output_tokens"], 6)
        self.assertEqual(events[-1]["response"], final)
        for action in (lambda: p.assembler.append_output(Event("content", "late")),
                       lambda: p.assembler.finalize_response("fail")):
            with self.assertRaises(ValueError):
                action()
            self.assertEqual(p.assembler.snapshot(), final)
        final["output"].clear()
        self.assertEqual(len(p.assembler.snapshot()["output"]), 1)

    def test_budget_means_incomplete(self):
        svc = service("hello")
        p = create_response(svc, request(max_output_tokens=2))
        list(execute_response(svc, p, threading.Event()))
        result = p.assembler.snapshot()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["incomplete_details"], {"reason": "max_output_tokens"})
        self.assertEqual(result["output"][0]["content"][0]["text"], "he")

    def test_bad_transition_does_not_invent_lifecycle_states(self):
        self.assertEqual(transition("queued", "start"), "in_progress")
        self.assertEqual(transition("in_progress", "output"), "in_progress")
        for state, event in (("queued", "output"), ("completed", "fail"), ("in_progress", "delete"),
                             ("in_progress", "request_cancel")):
            with self.assertRaises(ValueError):
                transition(state, event)


class HttpBoundary(unittest.TestCase):
    def test_flag_off_and_old_endpoints(self):
        svc = service("</think>old")
        svc.experimental_responses = False
        with listening(svc) as base:
            self.assertEqual(http(base, request())[0], 404)
            self.assertEqual(http(base, {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                                  path="/v1/chat/completions")[0], 200)
        self.assertFalse(hasattr(svc, "response_store"))

    def test_auth_cors_and_host_origin_guards(self):
        svc = service()
        svc.api_key = "fixture-only"
        svc.cors_origins = ["https://client.example"]
        with listening(svc) as base:
            self.assertEqual(http(base, request())[0], 401)
            code, headers, body = http(base, request(), headers={"Authorization": "Bearer fixture-only",
                                                               "Origin": "https://client.example"})
            self.assertEqual(code, 200)
            self.assertEqual(headers["Access-Control-Allow-Origin"], "https://client.example")
            self.assertEqual(json.loads(body)["status"], "completed")
            self.assertEqual(http(base, method="OPTIONS", headers={"Origin": "https://client.example"})[0], 204)
            svc.api_key = ""
            self.assertEqual(http(base, request(), headers={"Host": "evil.example"})[0], 403)
            self.assertEqual(http(base, request(), headers={"Origin": "https://evil.example"})[0], 403)

    def test_no_storage_or_previous_instruction_inheritance(self):
        svc = service()
        with listening(svc) as base:
            _, _, body = http(base, request(instructions="FIRST_ONLY"))
            first = json.loads(body)
            self.assertEqual(http(base, path="/v1/responses/" + first["id"])[0], 404)
            self.assertEqual(http(base, request(input=[{"role": "user", "content": "old"}, *first["output"],
                                                      {"role": "user", "content": "new"}]))[0], 200)
            self.assertNotIn("FIRST_ONLY", svc.tok.decode(svc.engine.last_prompt))
            self.assertEqual(http(base, request(previous_response_id=first["id"]))[0], 400)

    def test_invalid_json_and_context_before_success(self):
        svc = service(max_context=1024)
        with listening(svc) as base:
            for raw in (b'{"store":false,"store":true}', b'[]', b'{"input":NaN}'):
                self.assertEqual(http(base, raw)[0], 400)
            self.assertEqual(http(base, request(max_output_tokens=100000))[0], 400)
            self.assertEqual(svc.engine.last_prompt, [])

    def test_monitor_observes_final_snapshot(self):
        svc = service()
        svc.api_monitor = True
        with listening(svc) as base:
            code, _, body = http(base, request())
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(svc.api_requests[-1]["response"]), json.loads(body))


class Startup(unittest.TestCase):
    def test_cli_config_and_default_activation(self):
        for cfg, flag, expected in (({}, False, False), ({"experimental_responses": True}, False, True),
                                    ({}, True, True), ({"experimental_responses": False}, True, True)):
            with self.subTest(cfg=cfg, flag=flag), tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "config.json"
                config.write_text(json.dumps(cfg), encoding="utf-8")
                argv = ["server", "--port", "0", "--config", str(config), "--tokenizer", directory]
                if flag:
                    argv.append("--experimental-responses")
                with mock.patch("sys.argv", argv), mock.patch.object(server, "serve") as start, \
                     mock.patch.object(server, "time", mock.Mock(wraps=time, sleep=mock.Mock(side_effect=KeyboardInterrupt))), \
                     mock.patch.object(server.signal, "signal"), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(server.main(), 0)
                self.assertIs(start.call_args.args[0].experimental_responses, expected)


def sse_events(raw):
    events, comments = [], []
    for block in raw.decode("utf-8").split("\n\n"):
        if not block:
            continue
        if block.startswith(":"):
            comments.append(block)
            continue
        lines = block.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        event = json.loads("\n".join(line[6:] for line in lines if line.startswith("data: ")))
        if name != event["type"]:
            raise AssertionError("SSE name differs from JSON event type")
        events.append(event)
    return events, comments


def normalized(obj):
    if isinstance(obj, list):
        return [normalized(x) for x in obj]
    if isinstance(obj, dict):
        return {k: ("<volatile>" if k in ("id", "call_id", "created_at", "completed_at") and v is not None
                    else normalized(v)) for k, v in obj.items()}
    return obj


class Streaming(unittest.TestCase):
    def test_unicode_reassembly_matches_final_json(self):
        text = 'A 猫 🐈 e\u0301\n"quoted" \\ end'
        svc = service(text)
        with listening(svc) as base:
            code, _, body = http(base, request())
            self.assertEqual(code, 200)
            final = json.loads(body)
            code, headers, raw = http(base, request(stream=True))
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/event-stream")
        self.assertNotIn(b"[DONE]", raw)
        events, _ = sse_events(raw)
        self.assertEqual([e["sequence_number"] for e in events], list(range(len(events))))
        self.assertEqual([e["type"] for e in events[:4]], ["response.created", "response.in_progress",
            "response.output_item.added", "response.content_part.added"])
        self.assertEqual(events[0]["response"]["output"], [])
        item_id = events[2]["item"]["id"]
        text_so_far = ""
        for event in events[3:]:
            if "item_id" in event:
                self.assertEqual(event["item_id"], item_id)
                self.assertEqual(event["output_index"], 0)
                self.assertEqual(event["content_index"], 0)
            if event["type"] == "response.output_text.delta":
                text_so_far += event["delta"]
            elif event["type"] == "response.output_text.done":
                self.assertEqual(event["text"], text_so_far)
            elif event["type"] == "response.content_part.done":
                self.assertEqual(event["part"]["text"], text_so_far)
            elif event["type"] == "response.output_item.done":
                self.assertEqual(event["item"]["content"][0]["text"], text_so_far)
        self.assertEqual(text_so_far, text)
        self.assertEqual(events[-1]["type"], "response.completed")
        self.assertEqual(normalized(events[-1]["response"]), normalized(final))

    def test_empty_response_and_output_limit(self):
        for text, cap, expected in (("", 10, "completed"), ("abcdef", 2, "incomplete")):
            with self.subTest(expected=expected), listening(service(text)) as base:
                code, _, raw = http(base, request(stream=True, max_output_tokens=cap))
                self.assertEqual(code, 200)
                events, _ = sse_events(raw)
                self.assertEqual(events[-1]["type"], "response." + expected)
                self.assertEqual(sum(e["type"] in ("response.completed", "response.incomplete", "response.failed")
                                     for e in events), 1)
                if text:
                    self.assertEqual(events[-1]["response"]["output"][0]["content"][0]["text"], "ab")

    def test_preflight_error_precedes_stream_headers(self):
        svc = service()
        with listening(svc) as base:
            for body in (request(stream=True, store=True), request(stream=True, max_output_tokens=999999)):
                code, headers, _ = http(base, body)
                self.assertEqual(code, 400)
                self.assertEqual(headers["Content-Type"], "application/json")
            with mock.patch.object(svc, "load", side_effect=server.EngineStarting("not ready")):
                code, headers, _ = http(base, request(stream=True))
                self.assertEqual(code, 503)
                self.assertEqual(headers["Content-Type"], "application/json")

    def test_error_after_headers_is_failed_and_next_request_works(self):
        for fail_after in (0, 3):
            class FaultEngine(server.MockEngine):
                fail = True
                closed = False

                def generate(self, *args, **kwargs):
                    try:
                        if self.fail:
                            self.fail = False
                            yield None
                            for n, token in enumerate(super().generate(*args, **kwargs)):
                                if n == fail_after:
                                    raise server.EngineDied("scripted generation failure")
                                yield token
                        else:
                            yield from super().generate(*args, **kwargs)
                    finally:
                        self.closed = True

            svc = service("abcdef", engine_class=FaultEngine)
            with self.subTest(fail_after=fail_after), listening(svc) as base:
                code, _, raw = http(base, request(stream=True))
                self.assertEqual(code, 200)
                events, comments = sse_events(raw)
                self.assertIn(": keep-alive", comments)
                self.assertEqual(events[-1]["type"], "response.failed")
                self.assertNotIn("response.completed", [e["type"] for e in events])
                self.assertTrue(svc.engine.closed)
                self.assertFalse(svc.status["busy"])
                code, _, body = http(base, request())
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body)["output"][0]["content"][0]["text"], "abcdef")

    def test_missing_done_is_failure_not_completion(self):
        svc = service()
        p = create_response(svc, request())
        def broken(*args, **kwargs):
            yield "start", None
            yield "event", Event("content", "partial")
        with mock.patch.object(svc, "run", broken):
            events = list(execute_response(svc, p, threading.Event()))
        self.assertEqual(events[-1]["type"], "response.failed")
        self.assertIn("without a generation outcome", events[-1]["response"]["error"]["message"])

    def test_nonstream_failure_is_not_http_success(self):
        svc = service()
        def broken(*args, **kwargs):
            yield "start", None
            raise ValueError("scripted failure")
        with listening(svc) as base, mock.patch.object(svc, "run", broken):
            code, _, body = http(base, request())
            self.assertEqual(code, 500)
            self.assertEqual(json.loads(body)["status"], "failed")

    def test_iterator_close_confirms_stop_after_drain(self):
        svc = service()
        p = create_response(svc, request())
        cancel = threading.Event()
        observed = []
        def running(*args, **kwargs):
            try:
                yield "start", None
                yield "event", Event("content", "x")
                yield "ping", None
            finally:
                observed.append((cancel.is_set(), p.assembler.snapshot()["status"]))
        with mock.patch.object(svc, "run", running):
            events = execute_response(svc, p, cancel)
            while next(events)["type"] != "response.output_text.delta":
                pass
            cancel.set()
            self.assertEqual(p.assembler.snapshot()["status"], "in_progress")
            events.close()
        self.assertEqual(observed, [(True, "in_progress")])
        self.assertEqual(p.assembler.snapshot()["status"], "cancelled")

    def test_disconnect_queued_prefill_decode_and_next_request(self):
        for phase in ("queued", "prefill", "decode"):
            class BlockingEngine(server.MockEngine):
                calls = 0
                stopped = threading.Event()

                def generate(self, ids, max_new, sampling, cancel):
                    self.calls += 1
                    if phase != "queued" and self.calls == 1:
                        try:
                            if phase == "decode":
                                yield from self.tok.encode("partial")
                            while not cancel.wait(0.02):
                                yield None
                        finally:
                            self.stopped.set()
                        return
                    yield from super().generate(ids, max_new, sampling, cancel)

            svc = service("next request", engine_class=BlockingEngine)
            with self.subTest(phase=phase), listening(svc) as base:
                if phase == "queued":
                    svc.fifo.acquire()
                port = int(base.rsplit(":", 1)[1])
                sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                body = json.dumps(request(stream=True)).encode()
                sock.sendall(b"POST /v1/responses HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n" +
                             f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
                target = b"response.created" if phase == "queued" else (
                    b"response.output_text.delta" if phase == "decode" else b": keep-alive")
                received = b""
                while target not in received:
                    received += sock.recv(65536)
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                if phase == "queued":
                    time.sleep(0.65)  # existing disconnect watcher runs every 0.5 seconds
                    svc.fifo.release()
                else:
                    self.assertTrue(svc.engine.stopped.wait(4), "engine was not stopped/drained")
                deadline = time.monotonic() + 4
                while (svc.status["busy"] or svc.status["queued"]) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse(svc.status["busy"])
                self.assertEqual(svc.status["queued"], 0)
                if phase == "queued":
                    self.assertEqual(svc.engine.calls, 0)
                code, _, body = http(base, request())
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body)["output"][0]["content"][0]["text"], "next request")


if __name__ == "__main__":
    unittest.main()
