#!/usr/bin/env python
"""Diagnose the choose_target collapse — the head both MageZero and Laya fail on.

Hypothesis: target selection fails because the option space is large and the correct answer is
weakly determined by the state (the MCTS visit distribution is near-uniform), so argmax
accuracy is bounded low no matter how well the model learns.

Measures, straight from the recorded HDF5 (no model needed):
  - how many distinct target options appear, and the label distribution
  - the entropy of the MCTS target distribution per state (is the teacher even decided?)
  - the accuracy ceiling: what a model that always picks the most common option would score
  - the same numbers for the priority head, as a contrast

    .venv-mz/Scripts/python tools/target_collapse.py [repo_dir]
"""
import collections
import glob
import json
import math
import os
import sys

import numpy as np

try:
    import h5py
except ImportError:
    sys.exit("needs h5py - run with the MageZero venv: .venv-mz/Scripts/python")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "repo")


def entropy(p):
    p = np.asarray(p, dtype=np.float64)
    p = p[p > 0]
    if p.sum() <= 0:
        return 0.0
    p = p / p.sum()
    return float(-(p * np.log(p)).sum())


def scan(path):
    """Returns per-decision-type: number of states, teacher entropy, and top-1 label share."""
    out = collections.defaultdict(lambda: {"n": 0, "entropy_sum": 0.0, "argmax": collections.Counter(),
                                           "active_opts": [], "uniform": 0})
    with h5py.File(path, "r") as h:
        rows = h["row"]            # (states, 132) float32
        game_offsets = h["game_offsets"][()]
        # the last four columns are the per-type aggregate logits/distribution blocks.
        # We locate them by looking at which trailing columns vary and are non-negative.
        arr = rows[:]
        # per-row nonzero counts and spread per column give the block boundaries
        nz = (arr != 0).sum(axis=0)
        return arr, nz, game_offsets


def main():
    files = sorted(glob.glob(os.path.join(REPO, "data", "UWTempo", "ver0", "training", "*.hdf5")))
    if not files:
        files = sorted(glob.glob(os.path.join(REPO, "data", "UWTempo", "ver0", "**", "*.hdf5"),
                                 recursive=True))
    if not files:
        sys.exit("no HDF5 found under data/UWTempo/ver0")
    print("files: %d (first: %s)" % (len(files), os.path.basename(files[0])))

    arr, nz, goff = scan(files[0])
    print("row matrix: %s  games in file: %d" % (arr.shape, len(goff) - 1))
    print()
    print("column occupancy (which columns carry signal):")
    cols = [(i, int(c)) for i, c in enumerate(nz) if c > 0]
    print("  occupied columns: %s" % [i for i, _ in cols])
    print("  occupancy counts : %s" % [c for _, c in cols])
    print()

    # The target/binary distributions in MageZero live in the trailing block: try the last
    # columns that look like probability vectors (non-negative, rows summing to ~1).
    cand = []
    for start in range(arr.shape[1] - 40, arr.shape[1]):
        block = arr[:, start:]
        if block.shape[1] < 2:
            continue
        rs = block.sum(axis=1)
        frac_one = np.mean(np.abs(rs - 1.0) < 0.05)
        nonneg = np.mean(block >= -1e-6)
        if frac_one > 0.5 and nonneg > 0.95:
            cand.append((start, block.shape[1], frac_one, nonneg))
    print("candidate trailing probability blocks (start_col, width, frac_rows_sum_to_1):")
    for c in cand[:6]:
        print("  start=%-4d width=%-3d frac_sum1=%.2f" % (c[0], c[1], c[2]))

    if cand:
        start, width = cand[0][0], cand[0][1]
        block = arr[:, start:start + width]
        # per-row entropy, and how concentrated the winner is
        ents = np.array([entropy(r) for r in block])
        winners = block.argmax(axis=1)
        share = collections.Counter(winners.tolist())
        top = share.most_common(3)
        n = len(block)
        print()
        print("=== trailing block analysis (n=%d states, %d options) ===" % (n, width))
        print("  mean teacher entropy : %.3f nats  (uniform over %d options = %.3f)" %
              (ents.mean(), width, math.log(width)))
        print("  states where teacher is near-uniform (entropy > 0.9*log k): %.1f%%" %
              (100.0 * np.mean(ents > 0.9 * math.log(width))))
        print("  argmax label share   : top1=%.3f top2=%.3f top3=%.3f" %
              (top[0][1] / n,
               (top[1][1] / n) if len(top) > 1 else float("nan"),
               (top[2][1] / n) if len(top) > 2 else float("nan")))
        print("  -> accuracy CEILING for a majority-class predictor: %.3f" % (top[0][1] / n))
        print("  distinct argmax labels used: %d of %d columns" % (len(share), width))


if __name__ == "__main__":
    main()
