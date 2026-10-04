#!/usr/bin/env python
"""Load a local Laya checkpoint and ask it the same board-state questions the DGX gate
was asked — used to check whether fine-tuning changed the answer at all, without
touching the live service.

    ./.venv-train/Scripts/python tools/laya_local_probe.py laya_finetuned_mtg
"""
import json
import sys

import laya

CKPT = sys.argv[1] if len(sys.argv) > 1 else "laya_finetuned_mtg"

GOOD = ("turn 6, PRECOMBAT_MAIN. my life 20, opponent life 1. my battlefield: Goblin Guide 5/5, "
        "Monastery Swiftspear 4/4. opponent battlefield: (empty). my hand: Lightning Bolt.")
BAD = ("turn 6, PRECOMBAT_MAIN. my life 1, opponent life 20. my battlefield: Goblin Guide 1/1. "
       "opponent battlefield: Colossal Dreadmaw 6/6, Tarmogoyf 5/6, Siege Rhino 4/5. "
       "my hand: Mountain.")

Q = {
    "action": {
        "type": "choice",
        "instructions": ("Should the creature named in `state` attack the defending player this "
                         "turn, or be held back? Attacking is only correct when it advances "
                         "winning: the opponent is low on life, my creature cannot be blocked "
                         "profitably, or I am the aggressor racing them."),
        "criteria": {
            "ATTACK with it": "attacking wins value here: unblocked damage, a favourable trade, or lethal pressure",
            "HOLD it back": "holding back is right: it would die to a blocker, or it must stay untapped to block",
        },
    }
}


def main():
    agent = laya.load(CKPT, device="cuda")
    print("loaded", CKPT)
    for name, state in (("WIN board (they are at 1, empty board)", GOOD),
                        ("LOSE board (I am at 1 vs three 5/6 blockers)", BAD)):
        r = agent.predict(state, Q)
        a = r["answers"]["action"]
        print("  %-44s -> %-16s conf %.3f" % (name, a.get("choice"), float(a.get("confidence", 0))))


if __name__ == "__main__":
    main()
