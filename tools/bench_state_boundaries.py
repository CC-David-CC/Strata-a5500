#!/usr/bin/env python3
"""Inspect serving state at short output caps; no throughput claims."""
import argparse
import hashlib
import json
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from serve.server import StrataEngine, child_env
from bench_mtp_modes import set_option


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--prompt", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--caps", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 17])
    ap.add_argument("--eos-id", type=int,
                    help="Use a known early reference token as EOS to test stopping inside a verified prefix")
    opt = ap.parse_args()
    opt.output.mkdir(parents=True, exist_ok=False)
    cfg = json.loads(opt.config.read_text())
    original = json.loads(opt.prompt.read_text())
    if len(original) < 8192:
        ap.error("Expected a frozen prompt of at least 8192 tokens")
    # Keep the chat header and whole final task, shortening only archived filler.
    ids = original[:128] + original[-8064:]
    (opt.output / "prompt.tokens.json").write_text(json.dumps(ids))
    result = {
        "engine_sha256": hashlib.sha256(Path(cfg["exe"]).read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
        "input_tokens": len(ids), "runs": [],
        "eos_id": opt.eos_id,
        "note": "State hash instrumentation invalidates throughput; stale/dead/MTP state is reported separately.",
    }
    def save():
        (opt.output / "result.json").write_text(json.dumps(result, indent=2))
    save()
    for mode in ("off", "on"):
        args = list(cfg["args"])
        for name, value in [("--spec", 4), ("--mtp-max-t", 4), ("--suffix-draft", 0),
                            ("--spec-min-p", 0), ("--max-context", 16384),
                            ("--prompt-cache", 1), ("--prompt-cache-every", 0),
                            ("--prompt-cache-root", 0), ("--turn-token", -1),
                            ("--conversation-cache-mib", 0)]:
            set_option(args, name, value)
        if mode == "off":
            set_option(args, "--mtp", None)
        if opt.eos_id is not None:
            set_option(args, "--eos-ids", opt.eos_id)
        env = child_env(cfg)
        env["STRATA_STATE_HASH"] = "1"
        log = opt.output / f"engine-{mode}.log"
        run = {"mtp": mode == "on", "args": args, "cases": []}
        result["runs"].append(run)
        engine = None
        try:
            engine = StrataEngine(cfg["exe"], args, cfg.get("cwd", str(ROOT)), str(log), env)
            run["info"] = engine.info
            for cap in opt.caps:
                offset = log.stat().st_size
                tokens = [t for t in engine.generate(ids, cap, {"temperature": 0}, threading.Event()) if t is not None]
                with log.open("rb") as f:
                    f.seek(offset)
                    new_log = f.read().decode(errors="replace")
                hashes = [dict(re.findall(r"(\w+)=([^\s]+)", line)) for line in new_log.splitlines()
                          if "strata serve: STATE_HASH " in line]
                if len(hashes) != 1:
                    raise RuntimeError(f"Expected one state fingerprint, got {len(hashes)}")
                state = hashes[0]
                expected = len(ids) + len(tokens) - 1
                case = {"cap": cap, "token_ids": tokens, "timings": dict(engine.last),
                        "state": state, "expected_consumed": expected,
                        "consumed_matches_emitted": int(state["L"]) == expected}
                run["cases"].append(case)
                save()
                if engine.last.get("reused", 0):
                    raise RuntimeError("State control unexpectedly reused a prefix")
                if opt.eos_id is not None:
                    if not tokens or tokens[-1] != opt.eos_id or len(tokens) >= cap:
                        raise RuntimeError("Custom EOS control did not stop before its cap")
                elif len(tokens) != cap:
                    raise RuntimeError("Short boundary prompt stopped before its cap")
                print(json.dumps({k: v for k, v in case.items() if k not in ("token_ids", "timings")}), flush=True)
            run["completed"] = True
        finally:
            if engine is not None:
                engine.close()
            save()
    compared = []
    for a, b in zip(result["runs"][0]["cases"], result["runs"][1]["cases"]):
        fields = ("L", "gdn", "ple", "tail", "pooled", "kv", "ple_prev")
        compared.append({"cap": a["cap"], "tokens_match": a["token_ids"] == b["token_ids"],
                         "different_state_fields": [k for k in fields if a["state"][k] != b["state"][k]],
                         "serial_consumed_ok": a["consumed_matches_emitted"],
                         "mtp_consumed_ok": b["consumed_matches_emitted"]})
    result["comparison"] = compared
    result["completed"] = True
    save()
    print("COMPARISON " + json.dumps(compared), flush=True)


if __name__ == "__main__":
    main()
