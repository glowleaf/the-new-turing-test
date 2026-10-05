#!/usr/bin/env python
"""Turn guide-labelled decisions into Laya training cases.

Differs from to_laya_dataset.py in one crucial way: the gold label comes from
`guide_label` — the strategy knowledge base's rules (tools/rule_teacher.py) — not from
`stock_label`, the engine's greedy AI. The greedy AI is the ceiling on play strength, so
imitating it can never exceed it; the guide disagrees with it on ~half of attack decisions,
and that disagreement is the training signal worth having.

    python tools/to_laya_from_guide.py [guide_labelled.jsonl] [out.jsonl]
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dataset", "guide_labelled_big.jsonl")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "dataset", "laya_guide_cases.jsonl")
CAP = int(sys.argv[3]) if len(sys.argv) > 3 else 1500

INSTR = {
    "attack": ("Should the creature named in `state` attack the defending player this turn, or "
               "be held back? Attack when the attack is lethal, unblocked, or a favourable "
               "trade, or when you are the beatdown and the race is the game. Hold back when a "
               "blocker kills your attacker and survives, or when you are behind and need it to "
               "block. Note: 'you should usually attack if you can' - passivity in combat is "
               "the most common error, but do not throw creatures away for zero damage."),
    "block": ("Should this creature block, and which attacker should it block? Block when it is "
              "an even trade or better, or when the incoming damage is lethal - a chump block is "
              "correct precisely then. Do NOT chump block early: the blocker still has work to "
              "do, and life is a resource worth spending to keep it."),
}


def main():
    by_kind = collections.defaultdict(list)
    skipped = 0
    for line in open(SRC, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        kind = "block" if r.get("kind", "").startswith("block") else "attack"
        label = r.get("guide_label") or ""
        options = list(dict.fromkeys(r.get("options") or []))
        if not options or label not in options or len(options) < 2:
            skipped += 1
            continue
        crit = {o: o for o in options}
        by_kind[kind].append({
            "state": r.get("state", ""),
            "questions": {"action": {"type": "choice", "instructions": INSTR[kind], "criteria": crit}},
            "gold": {"action": {"probabilities": {o: (1.0 if o == label else 0.0) for o in options}}},
            "_reason": r.get("guide_reason"),
            "_kind": kind,
        })

    # balance the two heads so neither swamps the other
    rng = random.Random(0)
    cases = []
    for kind, rows in by_kind.items():
        rows = list(rows)
        if len(rows) > CAP:
            rng.shuffle(rows)
            rows = rows[:CAP]
        elif rows and len(rows) < CAP:
            base = list(rows)
            while len(rows) < CAP:
                rows.append(base[len(rows) % len(base)])
        cases.extend(rows)
    rng.shuffle(cases)

    os.makedirs(os.path.dirname(DST) or ".", exist_ok=True)
    with open(DST, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("guide cases written: %d -> %s  (skipped %d)" % (len(cases), DST, skipped))
    for kind, rows in sorted(by_kind.items()):
        print("  %-7s %d labelled rows (capped/duplicated to %d)" % (kind, len(rows), CAP))
    print()
    print("NOTE: gold = the GUIDE's choice, not the bot's. To measure how much of this is new")
    print("signal, compare against the stock labels in the same rows.")


if __name__ == "__main__":
    main()
