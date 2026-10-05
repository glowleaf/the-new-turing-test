#!/usr/bin/env python
"""Rule-based teacher built from the strategy knowledge base.

The models trained so far imitate the engine's greedy AI, which is the ceiling on how well
they can ever play. This labels decisions from the *guide's* rules instead, so the training
signal is correct play rather than "what a mediocre bot did".

Rules encoded (source: kb/level_one, Reid Duke's Level One; attribution in kb/SOURCES.md):

  attacking-and-blocking:  "you should usually attack if you can and usually block if you can"
                           creatures that neither attack nor block waste a turn of value
  damage-racing:           "little point to chump blocking early" - the blocker has future value
                           once behind, "stem the bleeding" instead of racing
                           a race is won by thinking ahead; life points change value over time
  role-assignment:         "who's the beatdown" - the player with inevitability should not be it
                           role is fluid; press an early advantage when you have one

Usage:
    python tools/rule_teacher.py [decisions.jsonl] [out.jsonl]

Reads the harness's decision log (state text + option text, which carries the consequences)
and emits one labelled row per decision with `guide_label` and `guide_reason`.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dataset", "decisions.jsonl")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "dataset", "guide_labelled.jsonl")

RE_LIFE = re.compile(r"my life (\d+), opponent life (\d+)")
RE_TURN = re.compile(r"turn (\d+)")
RE_ATK = re.compile(r"deals (\d+) damage, opponent (\d+) -> (-?\d+) life, (\d+) untapped creature")
RE_ATK_BLOCKERS = re.compile(r"\(([^)]*)\)")
RE_HOLD = re.compile(r"stays untapped to block next turn, opponent stays at (\d+) life")
RE_NOBLOCK = re.compile(r"I take (\d+) damage this combat, my life (\d+) -> (-?\d+) life")
RE_BLOCK = re.compile(r"BLOCK (.+?) (\d+)/(\d+) with (.+?) (\d+)/(\d+): ([^,]+), I take 0 damage")
RE_MYSTATS = re.compile(r"(\d+)/(\d+)")


def label_attack(row, my_life, opp_life, turn):
    """Return (choice, reason) for an attack decision, per the guide.

    The guide's rule is "you should usually attack if you can" — but "usually" carries the
    exceptions, and they are the whole point: a bad block while behind, or early with a
    creature that has future value, is where attacking loses the game. A rule that always
    attacks is a constant, and a constant teaches nothing.
    """
    opts = row.get("options") or []
    atk = next((o for o in opts if o.startswith("ATTACK:")), None)
    hold = next((o for o in opts if o.startswith("HOLD:")), None)
    if not atk or not hold:
        return None, None
    m = RE_ATK.search(atk)
    if not m:
        return None, None
    dmg, opp_before, opp_after, nblock = (int(m.group(1)), int(m.group(2)),
                                          int(m.group(3)), int(m.group(4)))
    # lethal: always attack, no exceptions
    if opp_after <= 0:
        return atk, "lethal on board - attack"
    # unblocked: free damage, and the guide says attack if you can
    if nblock == 0:
        return atk, "unblocked - free damage"
    # blocked. work out whether the block kills my attacker and whether it kills theirs
    my_p, my_t = None, None
    mm = RE_MYSTATS.search(row.get("state", ""))
    if mm:
        my_p, my_t = int(mm.group(1)), int(mm.group(2))
    blockers = RE_ATK_BLOCKERS.search(atk)
    i_die_for_nothing = False      # their blocker kills mine and survives
    i_kill_for_free = False        # my attacker kills theirs and survives
    neither_dies = True
    if blockers and my_p is not None:
        for b in blockers.group(1).split(","):
            bm = RE_MYSTATS.search(b)
            if not bm:
                continue
            bp, bt = int(bm.group(1)), int(bm.group(2))
            kills_me = bp >= my_t
            i_kill = my_p >= bt
            if kills_me and not i_kill:
                i_die_for_nothing = True
                neither_dies = False
            elif i_kill and not kills_me:
                i_kill_for_free = True
                neither_dies = False
            elif kills_me and i_kill:
                neither_dies = False
    if i_kill_for_free:
        return atk, "favourable trade available - attack"
    # the beatdown question: ahead on life = press, behind = stem the bleeding
    behind = my_life < opp_life
    if i_die_for_nothing:
        if behind:
            return hold, "behind on life and the blocker kills my attacker for nothing - hold"
        if turn <= 6:
            return hold, "early: do not trade the creature away for zero damage"
        return atk, "late: pressure is worth the risk, downside is bounded"
    if neither_dies:
        # a chump blocker absorbs the damage either way; the guide still says attack when
        # you can, unless you are the control player with a clock to respect
        if behind and turn >= 8:
            return hold, "behind late: keep the blocker home rather than feeding it to a chump"
        return atk, "attack when you can - the block costs them a creature"
    return atk, "attack when you can"


def label_block(row, my_life, opp_life, turn):
    """Return (choice, reason) for a block decision, per the guide."""
    opts = row.get("options") or []
    nob = next((o for o in opts if o.startswith("NO BLOCK")), None)
    blocks = [o for o in opts if o.startswith("BLOCK ")]
    if not nob or not blocks:
        return None, None
    m = RE_NOBLOCK.search(nob)
    incoming, life_before, life_after = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 1)
    # lethal incoming: block if any block can reduce it (chump is correct here)
    if life_after <= 0:
        return blocks[0], "incoming damage is lethal - chump blocking is correct now"
    # find a block that kills theirs and keeps mine
    for b in blocks:
        bm = RE_BLOCK.search(b)
        if not bm:
            continue
        their_t, my_t = int(bm.group(3)), int(bm.group(6))
        if int(bm.group(5)) >= their_t:          # my power >= their toughness -> theirs dies
            return b, "block kills their creature"
    # otherwise: is this a chump block? my creature dies for nothing
    for b in blocks:
        bm = RE_BLOCK.search(b)
        if not bm:
            continue
        if int(bm.group(2)) >= int(bm.group(6)):  # their power >= my toughness -> mine dies
            if turn <= 7:
                return nob, "chump blocking early wastes a creature - the guide says wait"
            return b, "late game: chump to survive"
    return nob, "no profitable block available"


def main():
    rows_out = []
    counts = {"attack": 0, "block": 0, "skipped": 0}
    agree = {"attack": 0, "block": 0}
    for line in open(SRC, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        kind = r.get("kind", "")
        state = r.get("state", "")
        lm = RE_LIFE.search(state)
        tm = RE_TURN.search(state)
        my_life, opp_life = (int(lm.group(1)), int(lm.group(2))) if lm else (20, 20)
        turn = int(tm.group(1)) if tm else 1

        if kind.startswith("attack"):
            choice, reason = label_attack(r, my_life, opp_life, turn)
            k = "attack"
        elif kind.startswith("block"):
            choice, reason = label_block(r, my_life, opp_life, turn)
            k = "block"
        else:
            counts["skipped"] += 1
            continue

        if choice is None:
            counts["skipped"] += 1
            continue
        counts[k] += 1
        stock = str(r.get("label") or r.get("answer") or "")
        # agreement between the guide and the stock AI's actual choice
        if (k == "attack" and stock.startswith("ATTACK")) or (k == "block" and stock.startswith("BLOCK ")):
            agree[k] += 1
        rows_out.append({"kind": kind, "state": state, "question": r.get("question"),
                         "options": r.get("options"), "guide_label": choice,
                         "guide_reason": reason, "stock_label": stock,
                         "turn": turn, "my_life": my_life, "opp_life": opp_life})

    os.makedirs(os.path.dirname(DST) or ".", exist_ok=True)
    with open(DST, "w", encoding="utf-8") as fh:
        for r in rows_out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("labelled decisions: %d -> %s" % (len(rows_out), DST))
    print("  attack %d   block %d   skipped %d" % (counts["attack"], counts["block"], counts["skipped"]))
    for k in ("attack", "block"):
        n = counts[k]
        if n:
            print("  guide vs stock AI agreement on %-6s: %.1f%% (%d/%d)" %
                  (k, 100.0 * agree[k] / n, agree[k], n))
    print()
    print("A LOW agreement number is the point: it means the guide disagrees with the bot on")
    print("that share of decisions, so training on guide labels teaches something the bot")
    print("never demonstrated.")


if __name__ == "__main__":
    main()
