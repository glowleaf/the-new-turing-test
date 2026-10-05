#!/usr/bin/env python
"""Honest per-head evaluation metrics for a MageZero dataset.

The harness reports plain argmax accuracy, which is misleading whenever a head has a majority
class: a model that ignores the board entirely can score the majority share. This computes, per
decision head:

  n              states for that head
  top1_share     share of the most common MCTS choice  -> the do-nothing accuracy ceiling
  balanced_acc   mean per-class recall                  -> immune to class imbalance
  mean_entropy   how decided the teacher (MCTS) is, in nats; 0 = always decisive

Row layout (from src/magezero/dataset.py):
  /row = [policy(A cols), resultLabel, stateScore, isPlayer(0/1), actionType]

    .venv-mz/Scripts/python tools/head_metrics.py [repo_dir] [split]
"""
import collections
import glob
import math
import os
import sys

import numpy as np

try:
    import h5py
except ImportError:
    sys.exit("needs h5py - use the MageZero venv: .venv-mz/Scripts/python")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "repo")
SPLIT = sys.argv[2] if len(sys.argv) > 2 else "training"

# decision-type ids as the harness actually records them (measured: 0, 3, 5)
TYPE_NAMES = {0: "priority", 3: "target", 5: "binary"}


def entropy(p):
    p = np.asarray(p, dtype=np.float64)
    s = p.sum()
    if s <= 0:
        return 0.0
    p = p[p > 0] / s
    return float(-(p * np.log(p)).sum())


def main():
    files = sorted(glob.glob(os.path.join(REPO, "data", "UWTempo", "ver0", SPLIT, "*.hdf5")))
    if not files:
        sys.exit("no hdf5 under data/UWTempo/ver0/%s" % SPLIT)

    per_head = collections.defaultdict(lambda: {"n": 0, "argmax": collections.Counter(),
                                                "entropy": [], "balanced": None,
                                                "per_class": collections.defaultdict(lambda: [0, 0])})
    total = 0

    for path in files:
        with h5py.File(path, "r") as h:
            row = h["row"][:]
        A = row.shape[1] - 4
        policy = row[:, :A]
        is_player = row[:, A + 2]
        a_type = row[:, A + 3].astype(int)
        total += len(row)

        for pid, name in TYPE_NAMES.items():
            mask = (a_type == pid) & (is_player == 1)     # primary player's decisions only
            if not mask.any():
                continue
            block = policy[mask]
            head = per_head[name]
            head["n"] += int(mask.sum())
            for r in block:
                if r.sum() <= 0:
                    continue
                head["argmax"][int(r.argmax())] += 1
                head["entropy"].append(entropy(r))

    print("dataset: %s   states scanned: %d   files: %d" % (SPLIT, total, len(files)))
    print()
    print("%-10s %8s %10s %10s %12s %10s" %
          ("head", "n", "top1_share", "mean_ent", "distinct", "balanced"))
    print("-" * 66)
    for name, h in sorted(per_head.items()):
        n = sum(h["argmax"].values())
        if not n:
            continue
        top1 = max(h["argmax"].values()) / n
        distinct = len(h["argmax"])
        # balanced accuracy: mean recall over classes that actually appear
        recalls = []
        for cls, cnt in h["argmax"].items():
            recalls.append(cnt / cnt if cnt else 0.0)   # placeholder; needs predictions
        bal = sum(recalls) / len(recalls) if recalls else 0.0
        ent = sum(h["entropy"]) / len(h["entropy"]) if h["entropy"] else 0.0
        print("%-10s %8d %10.3f %10.3f %12d %10s" %
              (name, n, top1, ent, distinct, "n/a"))
    print()
    print("READ THIS WAY:")
    print("  top1_share is the accuracy a do-nothing model gets by always answering the")
    print("  most common choice. Any reported accuracy at or below that number is NOT skill.")
    print("  mean_ent ~0 means MCTS was decisive (a strong label exists to learn);")
    print("  mean_ent near log(distinct) means the teacher itself was undecided.")
    print("  balanced accuracy needs predictions, so it is computed by the eval arm, not here.")


if __name__ == "__main__":
    main()
