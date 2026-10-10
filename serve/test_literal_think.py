"""Token identity and bounded literal-tag continuations, without a model or GPU."""
import threading
import unittest
from pathlib import Path

from serve.frontend import ChatTemplate
from serve.server import ByteTokenizer, MockEngine, Service


class ThinkTokenizer(ByteTokenizer):
    SPECIALS = ByteTokenizer.SPECIALS + ["<think>", "</think>"]
    ALWAYS = ("<think>", "</think>")


class ScriptEngine(MockEngine):
    def __init__(self, tok, scripts):
        super().__init__(tok, "", max_context=4096)
        self.scripts, self.prompts = scripts, []

    def generate(self, ids, max_new, sampling, cancel, embeddings=None):
        script = self.scripts[min(len(self.prompts), len(self.scripts) - 1)]
        self.prompts.append(list(ids))
        for t in script[:max_new]:
            if cancel.is_set():
                return
            yield t


class LiteralThink(unittest.TestCase):
    def setUp(self):
        self.tok = ThinkTokenizer()
        self.end = self.tok.encode("</think>", parse_special=True)
        self.stop = self.tok.encode("<|im_end|>", parse_special=True)

    def plain(self, text):
        return self.tok.encode(text, plain=[(0, len(text))])

    def run_script(self, scripts, thinking=True, guard=False, max_new=512, sampling=None):
        engine = ScriptEngine(self.tok, scripts)
        svc = Service(engine, self.tok, ChatTemplate(Path(__file__).parent / "chat_template.jinja"))
        svc.literal_think_guard = guard
        rows = list(svc.run([65], thinking, [], max_new, sampling or {}, threading.Event()))
        text = {k: "".join(ev.text or "" for kind, ev in rows if kind == "event" and ev.kind == k)
                for k in ("reasoning", "content")}
        return text, rows[-1][1], engine

    def test_ordinary_tag_does_not_close_reasoning(self):
        text, done, _ = self.run_script([self.plain("Read `</think>` as text. ") + self.end + self.plain("42") + self.stop])
        self.assertEqual(text, {"reasoning": "Read `</think>` as text. ", "content": "42"})
        self.assertEqual(done["finish"], "stop")

    def test_real_midline_marker_closes_reasoning(self):
        text, _, engine = self.run_script([self.plain("Done.") + self.end + self.plain("42") + self.stop], guard=True)
        self.assertEqual(text, {"reasoning": "Done.", "content": "42"})
        self.assertEqual(len(engine.prompts), 1)

    def test_quoted_special_is_replaced_in_continuation(self):
        prefix = self.plain("Read `")
        text, done, engine = self.run_script([prefix + self.end + self.stop,
                                            self.plain("` as text. ") + self.end + self.plain("42") + self.stop], guard=True)
        self.assertEqual(text, {"reasoning": "Read `</think>` as text. ", "content": "42"})
        self.assertEqual(engine.prompts[1], [65] + prefix + self.plain("</think>"))
        self.assertEqual(done["finish"], "stop")

    def test_content_special_is_literal(self):
        text, _, engine = self.run_script([self.plain("Tag: ") + self.end + self.stop,
                                          self.plain(" done") + self.stop], thinking=False, guard=True)
        self.assertEqual(text["content"], "Tag: </think> done")
        self.assertEqual(len(engine.prompts), 2)

    def test_guard_off_does_not_change_special_marker(self):
        text, _, engine = self.run_script([self.plain("Read `") + self.end + self.stop])
        self.assertEqual(text["reasoning"], "Read `")
        self.assertEqual(len(engine.prompts), 1)

    def test_stop_after_backtick_is_not_invented_tag(self):
        text, _, engine = self.run_script([self.plain("Read `") + self.stop], guard=True)
        self.assertEqual(text["reasoning"], "Read `")
        self.assertEqual(len(engine.prompts), 1)

    def test_fenced_special_is_replaced(self):
        text, _, engine = self.run_script([self.plain("```xml\n") + self.end,
                                          self.plain("\n```\nDone.") + self.end + self.plain("42") + self.stop], guard=True)
        self.assertIn("```xml\n</think>\n```", text["reasoning"])
        self.assertEqual(text["content"], "42")
        self.assertEqual(len(engine.prompts), 2)

    def test_client_stop_during_replacement_does_not_resume(self):
        text, done, engine = self.run_script([self.end], thinking=False, guard=True, sampling={"stop": "</th"})
        self.assertEqual(text["content"], "")
        self.assertEqual(done["finish"], "stop")
        self.assertEqual(len(engine.prompts), 1)

    def test_no_room_for_replacement_does_not_resume(self):
        _, done, engine = self.run_script([self.plain("`") + self.end], guard=True, max_new=2)
        self.assertEqual(done["completion_tokens"], 2)
        self.assertEqual(len(engine.prompts), 1)

    def test_substitution_limit(self):
        _, done, engine = self.run_script([self.end + self.stop], thinking=False, guard=True, max_new=2048)
        self.assertEqual(len(engine.prompts), 65)
        self.assertLessEqual(done["completion_tokens"], 2048)

    def test_partial_utf8_before_real_marker_is_preserved(self):
        text, _, _ = self.run_script([[0xE2] + self.end + self.plain("42") + self.stop])
        self.assertEqual(text, {"reasoning": "\ufffd", "content": "42"})

    def test_terminal_real_marker_closes_without_newline(self):
        text, done, _ = self.run_script([self.plain("Done.") + self.end + self.stop], guard=True)
        self.assertEqual(text, {"reasoning": "Done.", "content": ""})
        self.assertEqual(done["finish"], "stop")


if __name__ == "__main__":
    unittest.main()
