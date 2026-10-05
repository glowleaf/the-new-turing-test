# mtg-rl status — run 1 COMPLETE

4 generations, ~800 games, ~9 hours (with one PC-restart resume). Full results and analysis:
**[RESULTS.md](RESULTS.md)**.

Headline, with the majority-class baseline this harness does not print:

| head | do-nothing ceiling | gen 1 | gen 3 |
|---|---|---|---|
| `priority` (which action) | **0.791** | 0.822 | 0.797 |
| `choose_use` (binary) | **0.535** | 0.594 | **0.692** |
| `choose_target` | **0.201** | 0.191 | 0.280 |

Training losses fell every generation and the vocabulary grew (3,865 -> 4,936 rows), so the loop
works. But the head that picks the action never leaves the majority class, and **no win rate was
ever measured** — this harness reports imitation accuracy only.

Reproduce: `python tools/rl_report.py`, `.venv-mz/Scripts/python tools/head_metrics.py`.
