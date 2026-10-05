"""Verify archived requests and recompute comparisons using only the standard library."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
WORK = (
    "generated", "prompt_read", "drafts_accepted", "drafts_offered", "reused",
    "hits", "lookups", "offloaded", "ram_blobs", "file_blobs", "file_mb",
)


def signature(run):
    request = run["requests"][0]
    return {
        "timings": {key: request["timings"].get(key) for key in WORK},
        "async": run.get("async_counters"),
        "duplex": run.get("duplex_counters"),
        "resident": run.get("resident_exchanges"),
    }


def first_difference(a, b):
    for index, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return index
    return min(len(a), len(b)) if len(a) != len(b) else None


def verify_suite(relative):
    path = ROOT / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("completed") and not data.get("error"), relative
    assert len(data["runs"]) == len(data["plan"]["cases"]), relative
    rows = {}
    for run in data["runs"]:
        label, case = run["label"], run["case"]
        assert run.get("finished_unix"), label
        assert len(run["requests"]) == 1, label
        request = run["requests"][0]
        timing = request["timings"]
        assert len(request["token_ids"]) == request["output_tokens"] == case["output"], label
        assert timing["generated"] == case["output"], label
        assert timing["prompt_read"] == case["input"], label
        assert timing["finish"] == "length" and timing["reused"] == 0, label
        assert run["engine_info"]["kv"] == "fp16", label
        rate = request["output_tokens"] * 1000 / timing["decode_ms"]
        assert abs(rate - request["decode_tok_s"]) < 1e-8, label
        assert all(bad == 0 for _, bad in run.get("pdl_edges", [])), label
        if case.get("expect_pdl"):
            assert any(count > 0 for count, _ in run["pdl_edges"]), label
        if "expect_branches" in case:
            assert run["branches_enabled"] == case["expect_branches"], label
        if case["mtp_t"] == 1:
            assert timing.get("drafts_offered", 0) == 0, label
        rows[label] = run

    comparisons = []
    for pair in data["plan"]["pairs"]:
        left, right = (rows[label] for label in pair["labels"])
        a, b = left["requests"][0], right["requests"][0]
        tokens_equal = a["token_ids"] == b["token_ids"]
        work_equal = signature(left) == signature(right)
        if pair.get("require_token_equality", True):
            assert tokens_equal, pair["labels"]
        if pair.get("require_work_equality", True):
            assert work_equal, pair["labels"]
        comparisons.append({
            "labels": pair["labels"],
            "tokens_identical": tokens_equal,
            "recorded_work_including_transfers_identical": work_equal,
            "first_difference": first_difference(a["token_ids"], b["token_ids"]),
            "decode_gain_pct": 100 * (b["decode_tok_s"] / a["decode_tok_s"] - 1),
            "request_time_reduction_pct": 100 * (1 - b["wall_seconds"] / a["wall_seconds"]),
        })
    return {"suite": relative, "runs": len(rows), "comparisons": comparisons}


def main():
    manifest = ROOT / "sha256.json"
    if manifest.exists():
        for name, expected in json.loads(manifest.read_text(encoding="utf-8")).items():
            with (ROOT / name).open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            assert actual == expected, name + ": hash mismatch"
    suites = [
        "initial-pr904/q2-gate/result.json",
        "initial-pr904/q8-screen/result.json",
        "focused/q2-gate/result.json",
        "focused/q8-screen/result.json",
    ]
    print(json.dumps([verify_suite(name) for name in suites], indent=2))


if __name__ == "__main__":
    main()
