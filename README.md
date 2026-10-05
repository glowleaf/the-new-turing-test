# the-new-turing-test

Experiments in making a machine play games that require judgement.

## [mtg-laya](mtg-laya/) — Laya plays Magic: The Gathering

Laya (`convaiinnovations/laya`, a 421M fp16 ModernBERT encoder classifier — it never
generates text) wired into real, fully-ruled MTG games through XMage + the MageZero
self-play harness. Engine, JVM and logs run on a Windows PC; Laya is served over HTTP
from a DGX Spark and is the only thing running there.

First measured run: 3 games headless, Laya piloting Standard-MonoR vs the stock greedy AI,
2/3 wins (n=3 — not meaningful yet), 5 intercepted decisions, all accepted,
**89 ms average** decision latency.

Now expanded: combat (attackers + blockers), triggers, targets and choices are all handed
to Laya, and four arms ran — 50 games each for the Laya-piloted and baseline arms:

| arm | rule | games | win rate |
|---|---|---|---|
| Laya piloting | take Laya's pick | 50 | 30.0% |
| **baseline: stock greedy AI alone** | — | 50 | **24.0%** |
| Laya, neutral wording | take Laya's pick | 20 | 40.0% |
| Laya, confidence ≥ 0.5 | only act when confident | 20 | 10.0% |

Every difference is inside the noise at those sample sizes — and a control test showed why
the win rate was never the interesting number: **Laya's answer is constant.** Faced with the
same attack question on a won board and on a lost board it says ATTACK both times (296/296
attacks and 79/79 blocks in game). Only its *confidence* moves with the board (0.55 vs
0.37) and never high enough to gate on — forcing a 0.5 threshold makes it never attack, and
that arm wins 10%.

So the wiring, harness and measurement are sound, and the honest result is that Laya — a
421M classifier calibrated for routing, guardrails and email triage — does not carry enough
board-state judgement to play. Next step is fine-tuning it on the harness's own labeled
decision data, not more prompting.

See [mtg-laya/README.md](mtg-laya/README.md) for the design, the intercepted decision
points, the control test and how to reproduce it.

## Operations note — the gate is a symlink

`mtg-laya/OPERATIONS.md` records something that bit us: the DGX Laya service serves whatever
`~/models/laya-current` points at, and `tools/deploy_laya_dgx.sh` repoints that symlink when
shipping a fine-tune. So every MTG experiment silently replaced the **routing/guardrail model the
real pipelines call** — the gate spent hours answering site-routing and guardrail queries with a
model fine-tuned on Magic decisions. Always repoint it back after an experiment; the procedure and
the exact base-checkpoint path are in that file.
