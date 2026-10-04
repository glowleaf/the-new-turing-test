#!/usr/bin/env python
"""Control test: is Laya's MTG answer actually driven by the board state, or by the
surface form of the prompt (option order / wording)?

Sends the same decision to the DGX Laya gate (:5555) while varying ONLY the board state
and the option order, and prints what comes back. If the answer never changes, the
engine's win rate is measuring a fixed policy, not judgement.
"""
import json
import urllib.request

LAYA = "http://192.168.1.166:5555/decide"

GOOD_BOARD = ("turn 4, PRECOMBAT_MAIN. my life 20, opponent life 6. "
              "my battlefield: Goblin Guide 2/2, Monastery Swiftspear 1/2, "
              "opponent battlefield: (empty). my hand: Lightning Bolt, Mountain.")
BAD_BOARD = ("turn 4, PRECOMBAT_MAIN. my life 2, opponent life 20. "
             "my battlefield: Goblin Guide 2/2, Monastery Swiftspear 1/2. "
             "opponent battlefield: Tarmogoyf 5/6, Siege Rhino 4/5, Sylvan Caryatid 0/3. "
             "my hand: Mountain.")

Q = "Is attacking with this creature better than keeping it back?"
OPTS = ["ATTACK with it", "HOLD it back"]
REV = list(reversed(OPTS))

CASES = [
    ("good board, normal order", GOOD_BOARD, OPTS),
    ("good board, REVERSED order", GOOD_BOARD, REV),
    ("BAD board (2 life vs 3 blockers), normal order", BAD_BOARD, OPTS),
    ("BAD board, REVERSED order", BAD_BOARD, REV),
]

BLOCK_Q = "Should I block with this creature, and which attacker?"
BLOCK_OPTS = ["NO do not block", "BLOCK Tarmogoyf 5/6", "BLOCK Siege Rhino 4/5"]


def ask(text, question, choices):
    body = json.dumps({"task": "decide", "text": text, "question": question,
                       "choices": choices}).encode()
    req = urllib.request.Request(LAYA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


if __name__ == "__main__":
    print("=== attack question: does the BOARD change the answer? ===")
    for name, board, opts in CASES:
        d = ask(board, Q, opts)
        print("  %-46s -> %-14s conf %.3f  (%s ms)" %
              (name, d.get("choice"), d.get("confidence", 0), d.get("ms")))

    print()
    print("=== block question: does the attacker list change the answer? ===")
    for name, board in (("my 3/3 vs their 5/6 + 4/5",
                         "turn 5. my life 4, opponent life 18. my battlefield: Centaur Courser 3/3. "
                         "opponent battlefield: Tarmogoyf 5/6, Siege Rhino 4/5."),
                        ("no attackers at all",
                         "turn 5. my life 20, opponent life 18. my battlefield: Centaur Courser 3/3. "
                         "opponent battlefield: (empty).")):
        d = ask(board, BLOCK_Q, BLOCK_OPTS)
        print("  %-46s -> %-22s conf %.3f" % (name, d.get("choice"), d.get("confidence", 0)))
