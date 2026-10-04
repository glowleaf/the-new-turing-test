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
to Laya, and both arms ran **50 games each** — Laya piloted MonoR to a **30.0%** win rate
against the stock greedy AI on MonoG, versus **24.0%** for the same stock AI in the
baseline arm. That +6 pp is inside the noise at n=50 and is *not* yet evidence Laya plays
better; 448 Laya decisions were logged, all accepted, **77 ms average** latency,
34.5 s of total Laya compute for 50 games. The honest headline is in the confidence column:
on MTG board-state text Laya is barely confident (0.05-0.35).

See [mtg-laya/README.md](mtg-laya/README.md) for the design, the intercepted decision
points, what is still not hooked (the cast/play loop), and how to reproduce it.
