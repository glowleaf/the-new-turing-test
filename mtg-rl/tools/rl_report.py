#!/usr/bin/env python
"""Report a MageZero run: progress, per-generation policy accuracy, dataset shape.

Parses the run dir for everything the harness actually records:
  jvm_*.log          per-matchup game completions and inter-game timing
  test.log           per-generation accuracy per policy head (THE metric)
  dataset_stats.log  training-set composition per generation
  models/*/ver*/     checkpoints written

Writes results/rl_status.json. Safe to run while a run is in flight.

    python tools/rl_report.py [repo_dir]
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "repo")
OUT = os.path.join(HERE, "results")

GAME_RE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ Game #(\d+) completed successfully")
ACC_RE = re.compile(r"Test (\w+)_accuracy=([\d.]+)")
LOSS_RE = re.compile(r"Validation loss:\s+(.*)")
AGG_RE = re.compile(r"\[stats\] aggregated samples=(\d+) \(pA=(\d+), pB=(\d+), t=(\d+), b=(\d+)\)")


def read(p):
    return open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p) else ""


def parse():
    runs = sorted(d for d in glob.glob(os.path.join(REPO, "runs", "*")) if os.path.isdir(d))
    if not runs:
        return {"error": "no runs found", "repo": REPO}
    run = max(runs, key=os.path.getmtime)
    rname = os.path.basename(run)

    matchups, total = {}, 0
    for log in sorted(glob.glob(os.path.join(run, "jvm_*.log"))):
        name = os.path.basename(log)[len("jvm_"):-len(".log")]
        times = GAME_RE.findall(read(log))
        nums = [int(n) for _, n in times]
        gaps = [(datetime.strptime(times[i][0], "%Y-%m-%d %H:%M:%S")
                 - datetime.strptime(times[i - 1][0], "%Y-%m-%d %H:%M:%S")).total_seconds()
                for i in range(1, len(times))]
        matchups[name] = {
            "game_lines": len(times),
            "highest_game_number": max(nums) if nums else None,
            "last_game_at": times[-1][0] if times else None,
            "median_seconds_between_games": sorted(gaps)[len(gaps) // 2] if gaps else None,
        }
        total += max(nums) if nums else 0

    tests = {}
    for block in read(os.path.join(run, "test.log")).split("=== GEN ")[1:]:
        gen = int(block.split(" ")[0])
        loss = LOSS_RE.search(block)
        tests[gen] = {
            "accuracy": {k: float(v) for k, v in ACC_RE.findall(block)},
            "validation_loss_line": loss.group(1).strip() if loss else None,
        }

    stats = {}
    for block in read(os.path.join(run, "dataset_stats.log")).split("=== GEN ")[1:]:
        gen = int(block.split(" ")[0])
        m = AGG_RE.search(block)
        if m:
            stats[gen] = {"samples": int(m.group(1)), "pA": int(m.group(2)), "pB": int(m.group(3)),
                          "target": int(m.group(4)), "binary": int(m.group(5))}

    ckpts = [os.path.relpath(c, REPO).replace("\\", "/")
             for c in sorted(glob.glob(os.path.join(REPO, "models", "*", "ver*", "*.pt.gz")))]

    rj = {}
    p = os.path.join(run, "run.json")
    if os.path.exists(p):
        rj = json.loads(read(p))

    return {
        "run_dir": rname,
        "current_gen": rj.get("current_gen"),
        "stage": rj.get("stage"),
        "completed_at": rj.get("completed_at"),
        "generations_recorded": sorted(rj.get("gens", {}).keys()) if rj.get("gens") else [],
        "total_games_completed": total,
        "matchups": matchups,
        "policy_accuracy_by_gen": tests,
        "dataset_composition_by_gen": stats,
        "checkpoints": ckpts,
    }


def main():
    s = parse()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "rl_status.json"), "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=2)

    if "error" in s:
        print(s["error"], s["repo"])
        return

    print("run            : %s" % s["run_dir"])
    print("current gen    : %s   stage %s" % (s["current_gen"], s["stage"]))
    print("generations    : %s" % (s["generations_recorded"] or "?"))
    print("games done     : %d" % s["total_games_completed"])
    for name, m in s["matchups"].items():
        print("  %-18s %3d lines  last Game #%s  median %.0fs  at %s" %
              (name, m["game_lines"], m["highest_game_number"],
               m["median_seconds_between_games"] or 0, m["last_game_at"]))
    print()
    print("POLICY ACCURACY (what this harness measures - argmax agreement with MCTS):")
    if not s["policy_accuracy_by_gen"]:
        print("  (none yet - test runs after a generation closes)")
    for gen, t in sorted(s["policy_accuracy_by_gen"].items()):
        a = t["accuracy"]
        print("  gen %-3s priority_A=%-6s choose_use=%-6s choose_target=%-6s" %
              (gen, a.get("priority_A"), a.get("choose_use"), a.get("choose_target")))
    print()
    print("DATASET COMPOSITION:")
    for gen, d in sorted(s["dataset_composition_by_gen"].items()):
        print("  gen %-3s samples=%-7d pA=%-6d pB=%-4d target=%-5d binary=%-5d" %
              (gen, d["samples"], d["pA"], d["pB"], d["target"], d["binary"]))
    print()
    print("checkpoints    : %s" % (s["checkpoints"] or "none"))
    print("NOTE: no win rate exists in this pipeline - accuracy is imitation of MCTS, not")
    print("      strength; a win-rate arm must be run separately.")
    print()
    print("wrote results/rl_status.json")


if __name__ == "__main__":
    main()
