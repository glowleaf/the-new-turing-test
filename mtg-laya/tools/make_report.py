#!/usr/bin/env python
"""Build the results summary: parses every arm's stdout log and decision log, computes win
rates with Wilson 95% intervals and the decision mix vs the expert, then writes
results/summary.json, results/ANALYSIS.md and a self-contained results/analysis.html chart.

    python tools/make_report.py
"""
import collections
import glob
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XM = os.path.join(ROOT, "dist", "xmage")
RES = os.path.join(ROOT, "results")

# run id -> (label, kind, decision-log path or None)
ARMS = [
    ("run5",  "baseline: stock greedy AI",            "baseline", None),
    ("run8",  "baseline: stock greedy AI",            "baseline", None),
    ("run8b", "baseline: stock greedy AI",            "baseline", None),
    ("run4",  "base Laya (no fine-tune)",             "laya",     "results/laya_decisions_run4_base.jsonl"),
    ("run7",  "base Laya + confidence gate (rule, not a model)", "rule", "results/laya_decisions_run7_threshold_arm.jsonl"),
    ("run9",  "fine-tune v1 (all heads)",             "laya",     "results/laya_decisions_run9_finetuned.jsonl"),
    ("run10", "fine-tune v2 (aligned prompts)",       "laya",     None),
    ("run11", "v2 hybrid (attack head only)",         "laya",     "results/laya_decisions_run11_hybrid_attack.jsonl"),
    ("run12", "fine-tune v3 (balanced heads)",        "laya",     "results/laya_decisions_run12_v3_balanced.jsonl"),
    ("run13", "attack-only model (single head)",      "laya",     "results/laya_decisions_run13_attack_only.jsonl"),
]

EXPERT_LOG = os.path.join(ROOT, "dataset", "decisions.jsonl")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def read_wr(run):
    p = os.path.join(XM, f"{run}_stdout.log")
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8", errors="ignore").read()
    m = re.findall(r"Player A win rate: ([\d.]+)% \(([\d]+)/([\d]+)\)", txt)
    if not m:
        return None
    pct, k, n = m[-1]
    return int(k), int(n)


def mix(path):
    """decision counts per kind and the share that took the 'action' option"""
    out = collections.defaultdict(lambda: {"n": 0, "action": 0, "conf": 0.0})
    if not path or not os.path.exists(os.path.join(ROOT, path)):
        return None
    for line in open(os.path.join(ROOT, path), encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        k = d.get("kind", "")
        a = str(d.get("answer") if d.get("answer") is not None else d.get("label", ""))
        if k.startswith("attack"):
            key, pos = "attack", a.startswith("ATTACK")
        elif k.startswith("block"):
            key, pos = "block", a.startswith("BLOCK")
        elif k.startswith("chooseUse"):
            key, pos = "use", a.startswith("TAKE")
        else:
            continue
        s = out[key]
        s["n"] += 1
        s["action"] += 1 if pos else 0
        s["conf"] += float(d.get("confidence") or 0.0)
    for s in out.values():
        s["rate"] = 100.0 * s["action"] / s["n"] if s["n"] else 0.0
        s["conf"] = s["conf"] / s["n"] if s["n"] else 0.0
    return dict(out)


def main():
    arms = []
    for run, label, kind, log in ARMS:
        wr = read_wr(run)
        if not wr:
            continue
        k, n = wr
        lo, hi = wilson(k, n)
        m = mix(log)
        arms.append({"run": run, "label": label, "kind": kind, "wins": k, "games": n,
                     "rate": 100.0 * k / n, "ci": [lo * 100, hi * 100], "mix": m})

    expert = mix(EXPERT_LOG)
    base = [a for a in arms if a["kind"] == "baseline"]
    laya = [a for a in arms if a["kind"] == "laya"]
    bn = sum(a["games"] for a in base)
    bk = sum(a["wins"] for a in base)
    base_lo, base_hi = wilson(bk, bn)

    summary = {
        "baseline_pooled": {"wins": bk, "games": bn, "rate": 100.0 * bk / bn,
                            "ci": [base_lo * 100, base_hi * 100],
                            "observed_range": [min(a["rate"] for a in base), max(a["rate"] for a in base)]},
        "arms": arms,
        "expert_mix": expert,
        "control_test": {
            "base_laya":  {"won_board": ["ATTACK", 0.143], "lost_board": ["ATTACK", 0.012]},
            "finetune_v1": {"won_board": ["ATTACK", 0.894], "lost_board": ["HOLD it back", 0.904]},
            "finetune_v2": {"won_board": ["ATTACK", 0.747], "lost_board": ["HOLD it back", 0.716]},
        },
        "rounds": [
            {"round": 1, "data": "4,834 cases (imitation)", "temp": 6.048, "note": "constant-answer failure fixed"},
            {"round": 2, "data": "5,066 cases (prompt-aligned)", "temp": 5.162, "note": "chooseUse collapsed 2% -> 0%"},
            {"round": 3, "data": "4,800 cases (heads balanced 1,200 each)", "temp": 3.372, "note": "mix unchanged: 42/66/2"},
            {"round": 4, "data": "1,200 cases (attack head ONLY)", "temp": 6.114, "note": "attack 45% and 24.0% - identical to the multi-head hybrid"},
        ],
    }

    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # ---------------------------------------------------------------- markdown
    md = ["# Results summary", "",
          "Every arm, Standard-MonoR (player A) vs Standard-MonoG, same XMage engine, random seeds.", "",
          "## Win rate by arm", "",
          "| arm | run | games | win rate | 95% CI |", "|---|---|---|---|---|"]
    for a in arms:
        md.append("| %s | %s | %d | %.1f%% (%d/%d) | %.1f-%.1f%% |" %
                  (a["label"], a["run"], a["games"], a["rate"], a["wins"], a["games"],
                   a["ci"][0], a["ci"][1]))
    md += ["| **pooled baseline** | run5+8+8b | %d | **%.1f%%** (%d/%d) | %.1f-%.1f%% |" %
           (bn, 100.0 * bk / bn, bk, bn, base_lo * 100, base_hi * 100), "",
          "The same baseline configuration produced **%.1f%% and %.1f%% on two separate 200-game"
          " runs** — that spread is the run-to-run variance you have to beat before any claim"
          " about a Laya arm means anything." % (min(a["rate"] for a in base), max(a["rate"] for a in base)), "",
          "## Decision mix vs the expert", "",
          "| decision | expert (stock AI) | v1 | v2 | v3 | hybrid (attack only) |", "|---|---|---|---|---|---|"]
    labels = {"attack": "attack", "block": "block", "use": "take optional action"}
    for key in ("attack", "block", "use"):
        row = ["| %s |" % labels[key]]
        row.append(" %.0f%% |" % (expert[key]["rate"] if expert and key in expert else float("nan")))
        for a in [x for x in laya if x["kind"] == "laya"]:
            if a["mix"] and key in a["mix"]:
                row.append(" %.0f%% |" % a["mix"][key]["rate"])
            else:
                row.append(" — |")
        md.append("".join(row))
    md += ["", "## Rounds", "", "| round | data | fitted choice temperature | finding |", "|---|---|---|---|"]
    for r in summary["rounds"]:
        md.append("| %d | %s | %.3f | %s |" % (r["round"], r["data"], r["temp"], r["note"]))
    md += ["", "## The control test (does the answer depend on the board?)", "",
           "| checkpoint | won board | lost board |", "|---|---|---|"]
    for name, v in summary["control_test"].items():
        md.append("| %s | %s (%.3f) | %s (%.3f) |" % (name, v["won_board"][0], v["won_board"][1],
                                                      v["lost_board"][0], v["lost_board"][1]))
    md += ["", "## What the numbers say", "",
           "1. **No Laya variant beats the baseline, and none is demonstrably worse.** Every Laya"
           " arm lands between 19.0% and 24.0%; the baseline's own two runs span 18.0% to 27.0%."
           " The differences are inside the engine's run-to-run variance.",
           "2. **The fine-tuning worked at the model level**: the base checkpoint answered a"
           " constant (ATTACK at 0.01-0.14 confidence on both a won and a lost board); every"
           " fine-tuned checkpoint flips the answer with the board at 0.72-0.90 confidence.",
           "3. **It did not transfer to play.** In game the decision mix stays skewed from the"
           " expert's at every round: attack 40-45% (expert 71%), block 66-81% (expert 44%),"
           " take 0-2% (expert 57%).",
           "4. **Four separate explanations were tested and falsified**: prompt wording (round 2),"
           " option order (round 2), item imbalance (round 3), and head interference (round 4 — a"
           " single-purpose attack-only model still attacks 45% and wins 24.0%, identical to the"
           " multi-head hybrid). The skew is not a data or training artefact; it is the interface:"
           " a flat board summary in, typed heads out, no search.",
           "5. **Beating a professional player is not reachable on this path.** The engine's own RL"
           " track (MageZero) took a deck from 16% to 66% against a minimax pool (~61% estimated vs"
           " humans) by training a policy on state features. A 421M text classifier choosing"
           " between option strings is the wrong architecture for a strong player.", ""]
    with open(os.path.join(RES, "ANALYSIS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    # ---------------------------------------------------------------- html
    def bar_chart():
        w, hgt = 660, 250
        pad_l, pad_b, pad_t = 150, 34, 12
        plot = w - pad_l - 40
        rows = arms + [{"label": "pooled baseline", "run": "run5+8+8b", "rate": 100.0 * bk / bn,
                        "ci": [base_lo * 100, base_hi * 100], "wins": bk, "games": bn, "pooled": True}]
        bh = (hgt - pad_t - pad_b) / len(rows)
        out = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">' % (w, hgt, w)]
        for i, a in enumerate(rows):
            y = pad_t + i * bh + 2
            col = "var(--accent)" if a.get("pooled") else ("#7a7a7a" if "baseline" in a["label"] else "#4a90d9")
            x2 = pad_l + plot * min(1.0, a["rate"] / 35.0)
            x1 = pad_l + plot * max(0.0, a["ci"][0] / 35.0)
            out.append('<text x="%d" y="%.1f" font-size="10" fill="var(--muted-foreground)" text-anchor="end">%s</text>'
                       % (pad_l - 6, y + bh / 2, a["label"][:26]))
            out.append('<rect x="%d" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="%.2f" rx="2"/>'
                       % (pad_l, y + 2, x2 - pad_l, bh - 8, col, 0.95 if a.get("pooled") else 0.8))
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--foreground)" stroke-width="1.2"/>'
                       % (x1, y + bh / 2 - 5, x1, y + bh / 2 + 5))
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--foreground)" stroke-width="1.2"/>'
                       % (pad_l + plot * a["ci"][1] / 35.0, y + bh / 2 - 5,
                          pad_l + plot * a["ci"][1] / 35.0, y + bh / 2 + 5))
            out.append('<text x="%.1f" y="%.1f" font-size="10" fill="var(--foreground)">%.1f%%</text>'
                       % (x2 + 4, y + bh / 2 + 3, a["rate"]))
        # baseline band
        bl = pad_l + plot * min(a["rate"] for a in base) / 35.0
        bh2 = pad_l + plot * max(a["rate"] for a in base) / 35.0
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="var(--accent)" opacity="0.12"/>'
                   % (bl, pad_t, bh2 - bl, hgt - pad_t - pad_b))
        out.append('<text x="%.1f" y="%d" font-size="9" fill="var(--muted-foreground)">baseline runs: 18-27%%</text>'
                   % (bl, hgt - 6))
        out.append('</svg>')
        return "".join(out)

    def mix_chart():
        keys = [("attack", "attack"), ("block", "block"), ("use", "take optional")]
        series = [("expert", None)] + [(a["run"], a["mix"]) for a in laya if a["kind"] == "laya"]
        w, hgt = 660, 230
        pad_l, pad_b, pad_t = 60, 46, 16
        plot = w - pad_l - 20
        gw = plot / len(keys)
        out = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">' % (w, hgt, w)]
        for gi, (key, klab) in enumerate(keys):
            x0 = pad_l + gi * gw
            bars = [("expert", expert.get(key, {}).get("rate", 0), "var(--muted-foreground)")]
            for name, m in [(a["run"], a["mix"]) for a in laya]:
                if m and key in m:
                    bars.append((name, m[key]["rate"], "#4a90d9"))
            bw = gw / (len(bars) + 1)
            for bi, (name, val, col) in enumerate(bars):
                hh = (hgt - pad_t - pad_b) * val / 100.0
                x = x0 + bw * (bi + 0.5)
                out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.85" rx="2"/>'
                           % (x, hgt - pad_b - hh, bw * 0.8, hh, col))
                out.append('<text x="%.1f" y="%.1f" font-size="9" fill="var(--foreground)" text-anchor="middle">%.0f</text>'
                           % (x + bw * 0.4, hgt - pad_b - hh - 3, val))
            out.append('<text x="%.1f" y="%d" font-size="11" fill="var(--foreground)" text-anchor="middle">%s</text>'
                       % (x0 + gw / 2, hgt - pad_b + 16, klab))
        out.append('<text x="%d" y="%d" font-size="10" fill="var(--muted-foreground)">grey = the expert the model was cloned from</text>'
                   % (pad_l, 10))
        out.append('</svg>')
        return "".join(out)

    html = """<!doctype html><meta charset="utf-8">
<style>
 body{font-family:inherit;color:var(--foreground);background:transparent;margin:0}
 h2{font-size:15px;margin:18px 0 6px}
 .sub{color:var(--muted-foreground);font-size:12px;margin-bottom:10px}
 .card{border:1px solid var(--border);border-radius:8px;padding:12px;background:var(--card);margin:10px 0}
 table{border-collapse:collapse;font-size:12px}
 th,td{border-bottom:1px solid var(--border);padding:3px 8px;text-align:left}
 th{color:var(--muted-foreground);font-weight:600}
 .big{font-size:26px;font-weight:700}
 ul{margin:6px 0 0 18px;padding:0;font-size:12.5px;line-height:1.5}
</style>
<h2>Laya on Magic: The Gathering — measured results</h2>
<div class="sub">XMage + MageZero harness, Standard-MonoR (player A) vs Standard-MonoG, random seeds. Laya served from the DGX over HTTP.</div>

<div class="card">
  <div class="big">__POOLED__</div>
  <div class="sub">pooled baseline win rate (3 runs, __BGAMES__ games) — the same configuration gave __BRANGE__ on two separate 200-game runs, which is the noise floor every Laya arm must beat.</div>
  __BARS__
</div>

<div class="card">
  <h2 style="margin-top:0">Decision mix: model vs the expert it was cloned from</h2>
  <div class="sub">In-game shares. The expert is mixed and position-driven; every Laya checkpoint answers in a skew that survived prompt alignment and head balancing.</div>
  __MIX__
</div>

<div class="card">
  <h2 style="margin-top:0">The control test — the answer does flip, on clean boards</h2>
  <table><tr><th>checkpoint</th><th>won board</th><th>lost board</th></tr>
  __CTRL__
  </table>
  <div class="sub" style="margin-top:8px">The base checkpoint answers a constant (ATTACK both times). Every fine-tuned checkpoint flips with the board — so the model learned something real, it just does not reproduce the expert's policy in game.</div>
</div>

<div class="card">
  <h2 style="margin-top:0">Rounds</h2>
  <table><tr><th>round</th><th>data</th><th>choice temp</th><th>finding</th></tr>
  __ROUNDS__
  </table>
</div>
"""

    ctrl_rows = "".join(
        "<tr><td>%s</td><td>%s (%.3f)</td><td>%s (%.3f)</td></tr>" % (name, v["won_board"][0], v["won_board"][1],
                                                                     v["lost_board"][0], v["lost_board"][1])
        for name, v in summary["control_test"].items())
    round_rows = "".join("<tr><td>%d</td><td>%s</td><td>%.3f</td><td>%s</td></tr>"
                         % (r["round"], r["data"], r["temp"], r["note"]) for r in summary["rounds"])
    html = (html
            .replace("__POOLED__", "%.1f%% baseline" % (100.0 * bk / bn))
            .replace("__BGAMES__", str(bn))
            .replace("__BRANGE__", "%.1f%% and %.1f%%" % (min(a["rate"] for a in base), max(a["rate"] for a in base)))
            .replace("__BARS__", bar_chart())
            .replace("__MIX__", mix_chart())
            .replace("__CTRL__", ctrl_rows)
            .replace("__ROUNDS__", round_rows))
    with open(os.path.join(RES, "analysis.html"), "w", encoding="utf-8") as fh:
        fh.write(html)

    # ---------------------------------------------------------------- console
    print("arms parsed: %d" % len(arms))
    print()
    print("%-36s %-8s %6s %8s  95%% CI" % ("arm", "run", "games", "winrate"))
    for a in arms:
        print("%-36s %-8s %6d %7.1f%%  %.1f-%.1f" % (a["label"], a["run"], a["games"], a["rate"],
                                                     a["ci"][0], a["ci"][1]))
    print("%-36s %-8s %6d %7.1f%%  %.1f-%.1f" % ("POOLED BASELINE", "5+8+8b", bn, 100.0 * bk / bn,
                                                 base_lo * 100, base_hi * 100))
    print()
    print("expert mix:", {k: round(v["rate"]) for k, v in (expert or {}).items()})
    for a in laya:
        if a["mix"]:
            print("  %-34s %s" % (a["label"], {k: round(v["rate"]) for k, v in a["mix"].items()}))
    print()
    print("wrote results/summary.json, results/ANALYSIS.md, results/analysis.html")


if __name__ == "__main__":
    main()
