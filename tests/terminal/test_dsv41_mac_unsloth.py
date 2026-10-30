"""Unsloth's UD-IQ1_S / UD-IQ1_M DeepSeek sets on a Mac (0.2.9): their IQ1_S experts have no Metal kernel yet, so the sets are not offered there
(model list, `--model`, `--model-path`, the app's "I already have the model" check, setup), and the line says what does work.
On every other computer nothing changes."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from strata_cli.launch import settings as S
from strata_cli.launch.catalog import Catalog
from strata_cli.launch.runner import LaunchError, Runner
from strata_control import dsv41_fit, dsv41_sets, models
from tests.terminal.launch_support import HW_12, Home, catalog

LINE = "Unsloth's 1-bit DeepSeek sets don't run on a Mac yet; the 2.00 and 2.25 sets do."
MAC = {**HW_12, "mac": True, "ram_gb": 128.0, "disk_free_gb": 900.0, "gpus": [], "engine_vendor": "apple"}
PC = {**HW_12, "ram_gb": 64.0, "disk_free_gb": 900.0, "engine_vendor": "nvidia"}
UD = ("UD-IQ1_S", "UD-IQ1_M")


def ud_files(model):
    return {**dsv41_sets.tables()["sets"][model]["shards"], **dsv41_sets.tables()["sets"][model]["engram_alt"]}


class Line(unittest.TestCase):
    def test_the_line_and_the_names(self):
        self.assertEqual(dsv41_fit.MAC_NOT_YET, UD)
        self.assertEqual(dsv41_fit.MAC_NOT_YET_LINE, LINE)
        self.assertFalse(set(UD) & set(dsv41_fit.MAC_SET_PACK))


class Lists(unittest.TestCase):
    def setUp(self):
        self.home = Home().__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        self.hw = dict(MAC)
        p = mock.patch.object(Catalog, "hardware", lambda s, fresh=False: dict(self.hw))
        p.start()
        self.addCleanup(p.stop)

    def models(self):
        return [r.model for r in catalog(self.hw).rows() if r.family == "deepseek41"]

    def test_a_mac_is_not_offered_the_unsloth_sets(self):
        got = self.models()
        for m in UD:
            self.assertNotIn(m, got)
        self.assertFalse(set(got) - set(dsv41_fit.MAC_SET_PACK), got)

    def test_a_pc_is_offered_them(self):
        self.hw = dict(PC)
        got = self.models()
        for m in UD:
            self.assertIn(m, got)

    def test_model_flag_on_a_mac_says_what_works(self):
        with self.assertRaises(ValueError) as cm:
            catalog(self.hw).resolve("ud-iq1_m", None)
        self.assertIn(LINE, str(cm.exception))
        self.assertIn("ist-das-2.25bpw", str(cm.exception))
        self.assertEqual(catalog(self.hw).resolve("ist-das-2.25bpw"), ("deepseek41", "IST-DAS-2.25bpw"))

    def test_model_flag_on_a_pc_is_unchanged(self):
        self.hw = dict(PC)
        self.assertEqual(catalog(self.hw).resolve("ud-iq1_s"), ("deepseek41", "UD-IQ1_S"))


class OwnFiles(unittest.TestCase):
    def setUp(self):
        self.home = Home().__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        self.hw = dict(MAC)
        p = mock.patch.object(Catalog, "hardware", lambda s, fresh=False: dict(self.hw))
        p.start()
        self.addCleanup(p.stop)

    def folder(self, model):
        folder = Path(os.environ["STRATA_INSTALL_DIR"]) / model
        folder.mkdir(parents=True, exist_ok=True)
        for name in dsv41_sets.tables()["sets"][model]["shards"]:
            (folder / name).write_bytes(b"GGUF")
        return folder

    def test_model_path_of_a_ud_folder_on_a_mac_stops_with_the_line(self):
        for model in UD:
            folder = self.folder(model)
            with mock.patch.object(sys, "platform", "darwin"):
                with self.assertRaises(LaunchError) as cm:
                    Runner(S.LaunchSettings(model_path=str(folder)), catalog=catalog(self.hw)).check_own_files()
            self.assertIn(LINE, cm.exception.text)
            self.assertIn("2.25", cm.exception.hint if hasattr(cm.exception, "hint") else cm.exception.text)

    def test_the_same_folder_on_another_computer_is_the_model(self):
        folder = self.folder("UD-IQ1_S")
        with mock.patch.object(sys, "platform", "linux"):
            r = Runner(S.LaunchSettings(model_path=str(folder)), catalog=catalog(self.hw))
            r.check_own_files()
        self.assertEqual((r.s.family, r.s.model), ("deepseek41", "UD-IQ1_S"))


class AppCheck(unittest.TestCase):
    def preview(self, model, platform):
        with mock.patch.object(models, "_dsv41_files", return_value=ud_files(model)), mock.patch.object(sys, "platform", platform), \
                __import__("tempfile").TemporaryDirectory() as tmp:
            return models.plan_import(tmp)

    def test_on_a_mac_the_preview_says_so_and_selects_nothing(self):
        for model in UD:
            plan = self.preview(model, "darwin")
            self.assertIn(LINE, plan["messages"])
            self.assertIn("not_on_this_mac", plan["issues"])
            self.assertEqual(plan["file_set_status"], "invalid_or_incomplete")
            self.assertIsNone(plan["candidate_selection"])
            self.assertIn(LINE.rstrip("."), plan["plain_issues"])

    def test_on_a_pc_the_preview_is_the_set(self):
        for model in UD:
            plan = self.preview(model, "linux")
            self.assertEqual(plan["file_set_status"], "plausible", plan["issues"])
            self.assertEqual(plan["candidate_selection"]["model"], model)
            self.assertNotIn(LINE, plan["messages"])

    def test_an_ist_das_set_on_a_mac_is_still_the_set(self):
        t = dsv41_sets.tables()["sets"]["IST-DAS-2.25bpw"]["shards"]
        eng = next(iter(dsv41_sets.tables()["engram"]))
        with mock.patch.object(models, "_dsv41_files", return_value={**t, eng: dsv41_sets.tables()["engram"][eng]}), \
                mock.patch.object(sys, "platform", "darwin"), __import__("tempfile").TemporaryDirectory() as tmp:
            plan = models.plan_import(tmp)
        self.assertEqual(plan["file_set_status"], "plausible", plan["issues"])
        self.assertEqual(plan["candidate_selection"]["model"], "IST-DAS-2.25bpw")


class Setup(unittest.TestCase):
    """setup.py is the last stop: the line, before an engine, a download or a pack is touched."""

    def run_setup(self, model, platform):
        import contextlib
        import importlib.util
        import io
        import types
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("setup_mac_ud", root / "setup.py")
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        a = types.SimpleNamespace(model=model, models_dir="/nonexistent/models", yes=True, gguf_dir=None)
        out = io.StringIO()
        with mock.patch.object(sys, "platform", platform), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                setup.install_dsv41(a, "deepseek41", {}, False, False, 13, True, 8080, 128.0, False)
            except BaseException as exc:                      # noqa: BLE001 - fail() exits; anything after the check would raise something else
                return type(exc).__name__, out.getvalue()
        return None, out.getvalue()

    def test_a_mac_is_stopped_before_anything_else(self):
        for model in UD:
            exc, text = self.run_setup(model, "darwin")
            self.assertEqual(exc, "SystemExit", (model, text[-400:]))
            self.assertIn(LINE, text)
            self.assertIn("IST-DAS-2.25bpw", text)
            self.assertIn("nothing has been downloaded", text)


if __name__ == "__main__":
    unittest.main()
