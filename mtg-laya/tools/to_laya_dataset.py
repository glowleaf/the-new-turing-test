#!/usr/bin/env python
"""Convert the harness's labelled decisions into Laya's fine-tuning schema.
Laya's single-device trainer (research/scripts/finetune_single_device.py in
NandhaKishorM/laya) reads one JSONL case per line:

    {"state": "...",
     "questions": {"<qid>": {"type": "choice", "instructions": "...",
                             "criteria": {"<option>": "<what that option means>"}}},
     "gold":      {"<qid>": {"probabilities": {"<option>": 1.0}}}}

This script turns dataset/decisions.jsonl (produced by build_dataset.py from the
XMage harness) into exactly that, one case per logged decision.

Usage: python tools/to_laya_dataset.py [decisions.jsonl] [out.jsonl]
"""
import collections
import json
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "dataset/decisions.jsonl"
DST = sys.argv[2] if len(sys.argv) > 2 else "dataset/laya_cases.jsonl"

# what Laya is asked at each decision point, phrased the way a decision head should be:
# the candidates live in the option list, never buried in the state text
SPEC = {
    "attack-stock": {
        "qid": "action",
        "instructions": ("Should the creature named in `state` attack the defending player this "
                         "turn, or be held back? Attacking is only correct when it advances "
                         "winning: the opponent is low on life, my creature cannot be blocked "
                         "profitably, or I am the aggressor racing them."),
        "criteria": {
            "ATTACK with it": "attacking wins value here: unblocked damage, a favourable trade, or lethal pressure",
            "HOLD it back": "holding back is right: it would die to a blocker, or it must stay untapped to block",
        },
    },
    "block-stock": {
        "qid": "block",
        "instructions": ("Should this creature block an attacker, and which one should it block? "
                         "Blocking is worth it only when the block trades up, kills an important "
                         "attacker, or prevents lethal damage."),
        "criteria": {
            "NO do not block": "declining the block is right: blocking would lose the creature for nothing",
        },
    },
    "chooseUse-stock": {
        "qid": "use",
        "instructions": ("Should the player take the action described in `state`, or decline it? "
                         "Take it when it advances winning; decline when it costs more than it gains."),
        "criteria": {
            "TAKE the action": "the action is worth taking",
            "DECLINE the action": "the action costs more than it gains right now",
        },
    },
    "trigger-stock": {
        "qid": "trigger",
        "instructions": ("Several triggered abilities are waiting. Which one should be put on the "
                         "stack first? Order matters: put the ability you care about resolving last."),
        "criteria": {},
    },
    "target-stock": {
        "qid": "target",
        "instructions": "Which target should the effect point at, given the board in `state`?",
        "criteria": {},
    },
}


# round 3: the shared heads collapse when item counts are wildly imbalanced
# (attack 3381 / block 1154 / use 412 / trigger 119). Cap the big ones and duplicate the
# small ones so every decision type contributes the same number of training items.
CAP = int(sys.argv[3]) if len(sys.argv) > 3 else 1200


def balance(cases_by_kind, cap, seed=0):
    import random
    rng = random.Random(seed)
    out = []
    for kind, rows in cases_by_kind.items():
        rows = list(rows)
        if len(rows) > cap:
            rng.shuffle(rows)
            rows = rows[:cap]
        elif len(rows) < cap and rows:
            base = list(rows)
            while len(rows) < cap:
                rows.append(base[len(rows) % len(base)])
        out.extend(rows)
    rng.shuffle(out)
    return out


def main():
    cases = []
    by_kind = collections.defaultdict(list)
    skipped = 0
    per_kind = collections.Counter()
    per_label = collections.Counter()

    with open(SRC, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            kind = r.get("kind")
            spec = SPEC.get(kind)
            if not spec:
                skipped += 1
                continue
            options = list(dict.fromkeys(r.get("options") or []))   # de-dup, keep order
            label = str(r.get("label") or "")
            if len(options) < 2 or label not in options:
                skipped += 1
                continue

            criteria = dict(spec["criteria"])
            for o in options:
                criteria.setdefault(o, o)          # never leave an option undescribed
            criteria = {o: criteria[o] for o in options}

            cases.append({
                # the harness logs the exact state string the live player sends, so it is
                # used verbatim here — no re-wording between training and inference
                "state": r.get("state", ""),
                "questions": {spec["qid"]: {"type": "choice",
                                            "instructions": spec["instructions"],
                                            "criteria": criteria}},
                "gold": {spec["qid"]: {"probabilities": {o: (1.0 if o == label else 0.0)
                                                         for o in options}}},
            })
            by_kind[kind].append(cases[-1])
            per_kind[kind] += 1
            per_label[(kind, label if len(label) < 34 else label[:34])] += 1

    before = len(cases)
    cases = balance(by_kind, CAP)
    print("balanced to cap=%d: %d -> %d items (%s)" % (
        CAP, before, len(cases),
        ", ".join("%s=%d" % (k, min(len(v), CAP)) for k, v in sorted(by_kind.items()))))

    os.makedirs(os.path.dirname(DST) or ".", exist_ok=True)
    with open(DST, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("cases written : %d -> %s   (skipped %d)" % (len(cases), DST, skipped))
    print("by kind       : %s" % dict(per_kind))
    print()
    print("label balance per kind (what the fine-tune will learn to imitate):")
    for kind in sorted(per_kind):
        rows = [(k, v) for k, v in per_label.items() if k[0] == kind]
        tot = sum(v for _, v in rows)
        for (_, lab), v in sorted(rows, key=lambda x: -x[1])[:3]:
            print("  %-16s %-36s %5d (%.0f%%)" % (kind, lab, v, 100.0 * v / tot))


if __name__ == "__main__":
    main()
