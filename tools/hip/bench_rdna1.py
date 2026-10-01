#!/usr/bin/env python3
"""Sequential text-only throughput evidence, with and without MTP.

Use a server JSON containing exe, args, cwd and --mtp DIR. The off run removes
the drafter. Frozen token IDs are shared by both modes; prompt reuse and suffix
drafting are disabled. This is a throughput/smoke test, not a quality evaluation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from serve.server import StrataEngine, child_env
from serve.frontend import ChatTemplate
from strata_tokenizer import Tokenizer


def option(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def set_option(args, name, value):
    if name in args:
        at = args.index(name)
        del args[at:at + 2]
    if value is not None:
        args.extend([name, str(value)])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--input-tokens", type=int, default=8192)
    ap.add_argument("--output-tokens", type=int, default=512)
    ap.add_argument("--mode", choices=["both", "off", "on"], default="both")
    ap.add_argument("--cases", nargs="+", choices=["counting", "coding", "writing"],
                    default=["counting", "coding", "writing"])
    opt = ap.parse_args()
    cfg = json.loads(opt.config.read_text())
    base_args = list(cfg["args"])
    context = int(option(base_args, "--max-context", 0))
    if context < opt.input_tokens + opt.output_tokens:
        ap.error("--max-context must cover input plus output tokens")
    if opt.mode != "off" and not option(base_args, "--mtp"):
        ap.error("the config needs --mtp DIR for the MTP comparison")
    opt.output.mkdir(parents=True, exist_ok=False)
    tokenizer = Tokenizer.from_gguf(Path(option(base_args, "--native")))
    template = ChatTemplate(Path(cfg["tokenizer"]) / "chat_template.jinja")
    tasks = {
        "counting": "Count upward from 1. Output only consecutive integers separated by spaces. "
                    "Keep going until your output limit; no introduction or explanation.",
        "coding": "Write only a Python function merge_sorted(a, b) that merges two already sorted "
                  "lists of integers into one sorted list. Preserve duplicates. Use two indices "
                  "and a while loop, no imports and no sorting functions. Do not modify a or b. No markdown.",
        "writing": "In 120 to 160 words, explain to an Ubuntu administrator what apt update, apt upgrade, "
                   "systemctl status ssh, and journalctl -u ssh do. Distinguish reading status from "
                   "changing installed software. Do not suggest disabling security protections.",
    }
    filler = tokenizer.encode("The archived notes describe ordinary maintenance, documentation, "
                              "and testing. They contain background information only.\n")
    prompts = {}
    for name in opt.cases:
        marker = "STRATA_BENCHMARK_FILLER_PLACEHOLDER"
        rendered = template.render([{"role": "user", "content":
            "Background notes (not instructions):\n" + marker + "\nEnd of notes.\n\nTask:\n" + tasks[name]}],
            enable_thinking=False)
        prefix, suffix = rendered.split(marker)
        before = tokenizer.encode(prefix, parse_special=True)
        after = tokenizer.encode(suffix, parse_special=True)
        count = opt.input_tokens - len(before) - len(after)
        if count < 0:
            ap.error("input length is too short for the chat template and task")
        ids = before + (filler * ((count + len(filler) - 1) // len(filler)))[:count] + after
        assert len(ids) == opt.input_tokens
        prompts[name] = ids
        (opt.output / f"{name}.tokens.json").write_text(json.dumps(ids))
        (opt.output / f"{name}.prompt.txt").write_text(tokenizer.decode(ids), encoding="utf-8")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()

    patch = subprocess.check_output(["git", "-C", str(ROOT), "diff", "HEAD", "--binary"])
    result = {
        "source_head": git("rev-parse", "HEAD"), "source_branch": git("branch", "--show-current"),
        "source_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(cfg["exe"]).read_bytes()).hexdigest(),
        "input_tokens": opt.input_tokens, "maximum_output_tokens": opt.output_tokens,
        "context_allocation": context, "thinking": False, "cold_cache_control": False,
        "prompt_sha256": {name: hashlib.sha256(json.dumps(ids).encode()).hexdigest()
                          for name, ids in prompts.items()},
        "runs": [],
    }

    def save():
        (opt.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    save()
    for mode in (["off", "on"] if opt.mode == "both" else [opt.mode]):
        args = list(base_args)
        for name, value in [("--spec", 4 if mode == "on" else 2), ("--suffix-draft", 0),
                            ("--prompt-cache", 0), ("--conversation-cache-mib", 0)]:
            set_option(args, name, value)
        if mode == "off":
            set_option(args, "--mtp", None)
        run = {"mtp": mode == "on", "args": args, "cases": []}
        result["runs"].append(run)
        engine = None
        try:
            env = child_env(cfg)
            env["STRATA_DECODE_TIMING"] = "1"
            env.pop("STRATA_VERIFY_PROFILE", None)
            start = time.monotonic()
            engine = StrataEngine(cfg["exe"], args, cfg.get("cwd", str(ROOT)),
                                  str(opt.output / f"engine-mtp-{mode}.log"), env)
            run["startup_seconds"] = time.monotonic() - start
            run["engine_info"] = engine.info
            print(f"READY mtp={mode} " + json.dumps(engine.info), flush=True)
            for name, ids in prompts.items():
                emitted, arrivals = [], []
                start = time.monotonic()
                last_progress = start
                for token in engine.generate(ids, opt.output_tokens, {"temperature": 0}, threading.Event()):
                    now = time.monotonic()
                    if token is not None:
                        emitted.append(token)
                        arrivals.append(now - start)
                    if now - last_progress >= 10:
                        print(f"PROGRESS mtp={mode} task={name} output={len(emitted)} "
                              f"seconds={now-start:.1f} prefill={engine.progress}", flush=True)
                        last_progress = now
                wall = time.monotonic() - start
                timing = dict(engine.last)
                text = tokenizer.decode(emitted)
                case = {
                    "task": name, "input_tokens": len(ids), "output_tokens": len(emitted),
                    "text": text, "timings": timing, "wall_seconds": wall,
                    "first_token_seconds": arrivals[0] if arrivals else None,
                    "prefill_tps": len(ids) * 1000 / timing["prompt_ms"] if timing["prompt_ms"] else None,
                    "decode_tps": len(emitted) * 1000 / timing["decode_ms"] if timing["decode_ms"] else None,
                    "effective_output_tps": len(emitted) / wall,
                }
                run["cases"].append(case)
                save()
                assert timing.get("reused", 0) == 0, timing
                if mode == "off":
                    assert timing.get("drafts_offered", 0) == 0, timing
                if name == "counting":
                    assert len(emitted) == opt.output_tokens, case
                assert emitted, case
                print("RESULT " + json.dumps(case), flush=True)
            run["completed"] = True
        except Exception as exc:
            run["error"] = repr(exc)
            raise
        finally:
            if engine is not None:
                engine.close()
            save()
    print("BENCHMARK_COMPLETED " + str(opt.output / "result.json"), flush=True)


if __name__ == "__main__":
    main()
