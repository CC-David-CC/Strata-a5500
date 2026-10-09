"""GCC selection for Linux CUDA setup (#1645). No GPU, compiler or downloads needed.

    python -m unittest tools.test_setup_gcc
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup


class GCCSelection(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.enterContext = stack.enter_context          # also works on setup's minimum Python 3.10
        self.enterContext(mock.patch.dict(os.environ, {"STRATA_GCC": ""}))
        self.enterContext(mock.patch.object(setup, "WIN", False))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def test_default_does_not_look_up_or_override_compilers(self):
        with mock.patch.object(setup.shutil, "which") as which:
            self.assertEqual(setup.gcc_compilers(), {})
            which.assert_not_called()

    def test_versioned_and_full_path_toolchains(self):
        for gcc, cxx in (("gcc-14", "g++-14"), ("/opt/GCC 14/bin/gcc", "/opt/GCC 14/bin/g++"),
                         ("/opt/gcc/bin/gcc-13", "/opt/gcc/bin/g++-13"),
                         ("x86_64-linux-gnu-gcc-14", "x86_64-linux-gnu-g++-14")):
            with self.subTest(gcc=gcc), mock.patch.dict(os.environ, {"STRATA_GCC": gcc}), \
                    mock.patch.object(setup.shutil, "which", side_effect=lambda name: name):
                self.assertEqual(setup.gcc_compilers(), {"C": os.path.abspath(gcc),
                                 "CXX": os.path.abspath(cxx), "CUDA_HOST": os.path.abspath(cxx)})

    def test_missing_c_or_cxx_fails_without_installing(self):
        for missing in ("gcc-14", "g++-14"):
            with self.subTest(missing=missing), mock.patch.dict(os.environ, {"STRATA_GCC": "gcc-14"}), \
                    mock.patch.object(setup.shutil, "which", side_effect=lambda n: None if n == missing else n), \
                    mock.patch.object(setup, "run") as run, self.assertRaises(SystemExit):
                setup.gcc_compilers()
            run.assert_not_called()

    def test_invalid_compiler_name_is_rejected(self):
        with mock.patch.dict(os.environ, {"STRATA_GCC": "clang"}), self.assertRaises(SystemExit):
            setup.gcc_compilers()

    def test_windows_default_ignores_gcc_environment(self):
        with mock.patch.object(setup, "WIN", True), mock.patch.dict(os.environ, {"STRATA_GCC": "gcc-14"}):
            self.assertEqual(setup.gcc_compilers(), {})

    def test_versioned_compiler_satisfies_build_tools_without_unversioned_gpp(self):
        def which(name):
            return os.path.abspath(name) if name in ("gcc-14", "g++-14") else None
        with mock.patch.dict(os.environ, {"STRATA_GCC": "gcc-14"}), \
                mock.patch.object(setup.shutil, "which", side_effect=which), \
                mock.patch.object(setup, "find_nvcc", return_value=("/cuda/bin/nvcc", (12, 9))), \
                mock.patch.object(setup, "run") as run, mock.patch.object(setup, "ask") as ask:
            self.assertEqual(setup.install_build_tools({"arch": "86", "toolkit": 12}, True),
                             ("/cuda/bin/nvcc", None))
            run.assert_not_called()
            ask.assert_not_called()

    def test_cli_overrides_environment_before_setup_work(self):
        class StopBeforeSetup(Exception):
            pass
        with mock.patch.dict(os.environ, {"STRATA_GCC": "gcc-13"}), \
                mock.patch.object(sys, "argv", ["setup.py", "--gcc", "gcc-14", "--check"]), \
                mock.patch.object(setup, "gcc_compilers") as compilers, \
                mock.patch.object(setup, "data_folder", side_effect=StopBeforeSetup):
            with self.assertRaises(StopBeforeSetup):
                setup.main()
            self.assertEqual(os.environ["STRATA_GCC"], "gcc-14")
            compilers.assert_called_once_with()

    def test_cli_rejects_other_backends_and_windows(self):
        for win, args in ((True, []), (False, ["--backend", "hip"]), (False, ["--backend", "sycl"])):
            with mock.patch.object(setup, "WIN", win), \
                    mock.patch.object(sys, "argv", ["setup.py", "--gcc", "gcc-14", *args]), \
                    self.assertRaises(SystemExit) as caught:
                setup.main()
            self.assertEqual(caught.exception.code, 2)

    def test_cmake_explicit_host_beats_cuda_host_environment(self):
        with mock.patch.dict(os.environ, {"CUDAHOSTCXX": "g++-15"}), \
                mock.patch.object(setup, "find_tool", side_effect=lambda name: name), \
                mock.patch.object(setup, "run", return_value=mock.Mock(returncode=0)) as run:
            setup.cmake_build("src", "build", "strata", ["-DCMAKE_CUDA_HOST_COMPILER=/opt/GCC 14/g++"], None, "")
            self.assertEqual(run.call_args_list[0].kwargs["env"]["CUDAHOSTCXX"], "/opt/GCC 14/g++")
            self.assertEqual(os.environ["CUDAHOSTCXX"], "g++-15")

    def test_cmake_default_command_and_environment_are_unchanged(self):
        with mock.patch.object(setup, "find_tool", side_effect=lambda name: name), \
                mock.patch.object(setup, "run", return_value=mock.Mock(returncode=0)) as run:
            setup.cmake_build("src", "build", "strata", ["-DSTRATA_ENABLE_CUDA=ON"], None, "")
            self.assertEqual(run.call_args_list[0], mock.call([
                "cmake", "-G", "Ninja", "-DCMAKE_MAKE_PROGRAM=ninja", "-S", "src", "-B", "build",
                "-DCMAKE_BUILD_TYPE=Release", "-DSTRATA_ENABLE_CUDA=ON"]))


class BuildReuse(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.enterContext = stack.enter_context
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.object(setup, "ROOT", self.root))
        self.enterContext(mock.patch.object(setup, "WIN", False))
        self.enterContext(mock.patch.dict(os.environ, {"STRATA_GCC": ""}))
        self.enterContext(mock.patch.object(setup, "source_hash", return_value="same-source"))
        self.enterContext(mock.patch.object(setup, "source_version", return_value="0.1.41"))
        self.enterContext(mock.patch.object(setup, "cpu_info", return_value=("CPU", True)))
        self.enterContext(mock.patch.object(setup, "cpu_floor", return_value=""))
        self.enterContext(mock.patch.object(setup, "install_build_tools", return_value=("/cuda/bin/nvcc", None)))
        self.enterContext(mock.patch.object(setup.shutil, "which", side_effect=lambda name: name))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.build = self.enterContext(mock.patch.object(setup, "cmake_build", side_effect=self.fake_build))

    def fake_build(self, src, bdir, target, defs, vcvars, bat_name):
        binary = bdir / setup.EXE if target == "strata" else bdir / "bin" / setup.VEXE
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("built")

    def compile(self, gcc="", toolkit=12, vision="gpu"):
        os.environ["STRATA_GCC"] = gcc
        return setup.build_engine({"arch": "86"}, vision, True, self.root / "llama", toolkit=toolkit)

    def test_default_build_dirs_defs_and_stamp_stay_unchanged(self):
        for toolkit, dirs in ((12, ("build-cuda12", "build-vision-cuda12")), (13, ("build", "build-vision"))):
            self.build.reset_mock()
            eng = self.compile(toolkit=toolkit)
            self.assertEqual([c.args[1].name for c in self.build.call_args_list], list(dirs))
            for call in self.build.call_args_list:
                self.assertFalse(any(d.startswith(("-DCMAKE_C_COMPILER=", "-DCMAKE_CXX_COMPILER=",
                                                   "-DCMAKE_CUDA_HOST_COMPILER=")) for d in call.args[3]))
            self.assertNotIn("gcc_compilers", json.loads((eng / "BUILD.json").read_text()))

    def test_override_reaches_engine_and_vision_for_both_toolkits(self):
        for toolkit in (12, 13):
            self.build.reset_mock()
            eng = self.compile("gcc-14", toolkit)
            compilers = setup.gcc_compilers()
            self.assertEqual(self.build.call_count, 2)
            for call in self.build.call_args_list:
                self.assertIn("-gcc-", call.args[1].name)
                for key, value in compilers.items():
                    self.assertIn(f"-DCMAKE_{key}_COMPILER={value}", call.args[3])
            self.assertEqual(json.loads((eng / "BUILD.json").read_text())["gcc_compilers"], compilers)
            self.build.reset_mock()
            self.compile("gcc-14", toolkit)
            self.build.assert_not_called()

    def test_changing_and_removing_selection_rebuilds_both_without_touching_old_cache(self):
        self.compile()
        default_cache = self.root / "build-cuda12" / "CMakeCache.txt"
        default_cache.write_text("old default compiler cache")
        previous_dirs = [c.args[1] for c in self.build.call_args_list]
        for gcc in ("gcc-14", "gcc-13", ""):
            self.build.reset_mock()
            self.compile(gcc)
            self.assertEqual(self.build.call_count, 2)
            dirs = [c.args[1] for c in self.build.call_args_list]
            self.assertNotEqual(dirs, previous_dirs)
            self.assertEqual(default_cache.read_text(), "old default compiler cache")
            previous_dirs = dirs
        self.assertEqual(previous_dirs[0].name, "build-cuda12")

    def test_cpu_vision_uses_selected_c_and_cxx(self):
        self.compile("gcc-14", vision="cpu")
        defs = self.build.call_args_list[1].args[3]
        self.assertIn("-DSTRATA_VISION_CUDA=OFF", defs)
        self.assertIn("-DCMAKE_CXX_COMPILER=" + os.path.abspath("g++-14"), defs)


if __name__ == "__main__":
    unittest.main()
