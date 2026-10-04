#!/usr/bin/env python
"""Parse a MageZero RL run's logs into a progress/win-rate report.

Reads runs/<ts>/jvm_*.log (per-matchup game completions) and any win-rate lines the harness
prints, then writes results/rl_status.json and prints a table. Safe to run repeatedly while
a run is in flight.

    python tools/rl_report.py [repo_dir]
"""
import collections
import glob
import json
import os
import re
import sys
from datetime import datetime

REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "repo")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

GAME_RE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ Game #(\d+) completed successfully")
WR_RE = re.compile(r"(?:Current WR|win rate|WR)[: =]+([01]?\.\d+|\d+\.?\d*%?)", re.I)


def parse():
    runs = sorted(glob.glob(os.path.join(REPO, "runs", "*")))
    if not runs:
        return {"error": "no runs found", "repo": REPO}
    run = runs[-1]                       # newest run dir
    rname = os.path.basename(run)

    matchups = {}
    total = 0
    for log in sorted(glob.glob(os.path.join(run, "jvm_*.log"))):
        name = os.path.basename(log)[len("jvm_"):-len(".log")]
        times = GAME_RE.findall(open(log, encoding="utf-8", errors="ignore").read())
        games = len(times)
        total += games
        gaps = []
        for i in range(1, len(times)):
            t0 = datetime.strptime(times[i - 1][0], "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(times[i][0], "%Y-%m-%d %H:%M:%S")
            gaps.append((t1 - t0).total_seconds())
        matchups[name] = {
            "games": games,
            "last_game_at": times[-1][0] if times else None,
            "median_seconds_between_games": sorted(gaps)[len(gaps) // 2] if gaps else None,
        }

    # run-level: generations announced, win rates if the harness logged any
    rlog = None
    for cand in ("mz_run.log", "mz_smoke.log"):
        p = os.path.join(REPO, cand)
        if os.path.exists(p):
            rlog = p
            break
    text = open(rlog, encoding="utf-8", errors="ignore").read() if rlog else ""
    gens = re.findall(r"={10} GEN (\d+) ={10}", text)
    wrs = [m for m in WR_RE.findall(text)]

    # checkpoints written so far
    ckpts = sorted(glob.glob(os.path.join(REPO, "models", "*", "ver*", "*.pt.gz")))
    ckpts = [os.path.relpath(c, REPO).replace("\\", "/") for c in ckpts]

    started = rname
    return {
        "run_dir": rname,
        "generations_started": [int(g) for g in gens],
        "total_games_completed": total,
        "matchups": matchups,
        "win_rates_logged": wrs,
        "checkpoints": ckpts,
        "data_size": sum(os.path.getsize(f) for f in
                         glob.glob(os.path.join(REPO, "data", "**", "*.hdf5"), recursive=True)),
    }


def main():
    s = parse()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "rl_status.json"), "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=2)

    if "error" in s:
        print(s["error"], s["repo"])
        return
    print("run           : %s" % s["run_dir"])
    print("generations   : %s" % (s["generations_started"] or "?"))
    print("games done    : %d" % s["total_games_completed"])
    for name, m in s["matchups"].items():
        print("  %-18s %3d games   median %.0fs between games   last %s" %
              (name, m["games"], m["median_seconds_between_games"] or 0, m["last_game_at"]))
    print("checkpoints   : %s" % (s["checkpoints"] or "none yet"))
    print("data written  : %.1f MB" % (s["data_size"] / 1048576.0))
    if s["win_rates_logged"]:
        print("win rates     : %s" % s["win_rates_logged"][-6:])
    print()
    print("wrote results/rl_status.json")


if __name__ == "__main__":
    main()
