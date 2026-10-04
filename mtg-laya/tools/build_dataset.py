#!/usr/bin/env python
"""Turn the harness's raw decision log into a training dataset + stats.

Input : dataset_raw.jsonl  (written by LayaPlayer with -Dlaya.logOnly=true)
Output: dataset/decisions.jsonl  — one labelled decision per line
        and a printed summary, including what the stock AI's policy actually looks like
        (the label distribution we would be teaching Laya to imitate).

Usage:  python tools/build_dataset.py [raw.jsonl] [outdir]
"""
import collections
import json
import os
import sys

RAW = sys.argv[1] if len(sys.argv) > 1 else "dist/xmage/dataset_raw.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "dataset"


def main():
    rows = []
    outcomes = {}
    with open(RAW, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("event") == "decision":
                rows.append(d)
            elif d.get("event") == "game_end":
                outcomes[d["game"]] = bool(d.get("won"))

    for r in rows:
        r["won"] = outcomes.get(r["game"])

    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, "decisions.jsonl")
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({
                "game": r["game"], "player": r["player"], "kind": r["kind"],
                "state": r.get("state", ""), "question": r.get("question", ""),
                "options": r.get("options", []), "label": r.get("answer", ""),
                "won": r.get("won"),
            }, ensure_ascii=False) + "\n")

    kinds = collections.Counter(r["kind"] for r in rows)
    print("decisions written : %d -> %s" % (len(rows), out_path))
    print("by kind           : %s" % dict(kinds))
    known = [r for r in rows if r.get("won") is not None]
    print("with game outcome : %d (%.0f%%)" % (len(known), 100.0 * len(known) / max(1, len(rows))))
    won = sum(1 for r in known if r["won"])
    print("from winning side : %d" % won)
    print("games covered     : %d" % len({r["game"] for r in rows}))

    print()
    print("label distribution (what the stock AI actually does — the imitation target):")
    for kind in sorted(kinds):
        labels = collections.Counter(r["answer"] for r in rows if r["kind"] == kind)
        top = ", ".join("%s=%d" % (k[:28], v) for k, v in labels.most_common(4))
        print("  %-16s n=%-5d %s" % (kind, kinds[kind], top))

    # the interesting comparison: what the stock AI does vs what Laya answered on the
    # same hooks in the earlier runs (Laya said ATTACK 296/296, BLOCK 79/79)
    atk = [r for r in rows if r["kind"] == "attack-stock"]
    if atk:
        a = sum(1 for r in atk if str(r["answer"]).startswith("ATTACK"))
        print()
        print("stock AI attack rate : %d/%d (%.0f%%)  <-- Laya answered ATTACK 100%%"
              % (a, len(atk), 100.0 * a / len(atk)))
        by_out = collections.Counter()
        for r in atk:
            by_out[(str(r["answer"]).startswith("ATTACK"), r.get("won"))] += 1
        for k in sorted(by_out, key=lambda x: (x[0], str(x[1]))):
            print("   attack=%-5s won=%-5s -> %d" % (k[0], k[1], by_out[k]))


if __name__ == "__main__":
    main()
