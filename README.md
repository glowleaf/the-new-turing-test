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

See [mtg-laya/README.md](mtg-laya/README.md) for the design, the intercepted decision
points, the coverage gap (combat + the action loop are not hooked yet) and how to
reproduce it.
