#!/usr/bin/env python3
"""Standalone CPU toy: demonstrates LOGICAL context branching, NOT GPU KV reuse.

Uses the immutable store plus the exact-rational reference toy to show expected
branching histories, time travel, evaluation and atomic winner adoption.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "reference"))
from context_time_travel import Store
from test_context_time_travel_toy import Snapshot as ToyState, attention


def main():
    with tempfile.TemporaryDirectory(prefix="ctt-demo-") as tmp:
        store = Store(tmp)
        p = (1, 3)
        contract = "toy-mean-v1;integer-inputs;exact-fractions"
        controller = {"stream_key_hex": b"demo-key".hex(), "next_draw": 0,
                      "generation_status": "idle"}
        old_states = {}
        # Toy values can be negative, whereas real token IDs are nonnegative.
        # Zigzag encode toy values at the fixture boundary only, not in the store.
        def enc(x): return 2*x if x >= 0 else -2*x-1
        def dec(x): return x//2 if x%2 == 0 else -(x+1)//2
        root = store.create_root(contract, tuple(map(enc, p)), controller)
        store.fork("main", root)
        for name, suffix in (("A", (5,)), ("B", (9,)), ("C", (-1,))):
            store.fork(name, root)
            tip = store.append(root, tuple(map(enc, suffix)), controller)
            store.move(name, 0, tip, "append"+name)
            old_states[name] = tip
            inputs = tuple(map(dec, store.lineage(tip)[1]))
            observed = attention(ToyState(inputs, b"demo-key"))
            expected = Fraction(sum(p + suffix), len(p + suffix))
            assert observed == expected
            print(f"{name}: {inputs} -> exact toy attention {observed}")
        # Rewind A and explore D while preserving original A.
        store.move("A", 1, root, "rewindA")
        new_a = store.append(root, tuple(map(enc, (7,))), controller)
        store.move("A", 2, new_a, "replaceA")
        assert tuple(map(dec, store.lineage(old_states["A"])[1])) == p+(5,)
        assert tuple(map(dec, store.lineage(new_a)[1])) == p+(7,)
        print("Rewind A -> D: old A still retained; D has exact history", p+(7,))
        # Toy evaluator deliberately does not mutate the store.
        candidates = {**old_states, "D": new_a}
        before = {name: store.head(name) for name in ("A", "B", "C", "main")}
        scores = {}
        for name, snapshot_id in candidates.items():
            x = tuple(map(dec, store.lineage(snapshot_id)[1]))
            scores[name] = -abs(attention(ToyState(x, b"demo-key")) - Fraction(2))
        assert {name: store.head(name) for name in before} == before
        winner = max(sorted(scores), key=lambda k: scores[k])
        store.move("main", 0, candidates[winner], "adoptWinner")
        print("Independent toy evaluation scores:", {k:str(v) for k,v in sorted(scores.items())})
        print(f"Winner = {winner}; main branch revision = {store.head('main').revision}")
        reopened = Store(tmp)
        history = tuple(map(dec, reopened.lineage(reopened.head("main").tip)[1]))
        print("Cold reopen preserved winning exact token history:", history)
        assert store.head("main") == reopened.head("main")
        print("TOY DEMO PASS (not a real-model, durability or COW certification)")


if __name__ == "__main__":
    main()
