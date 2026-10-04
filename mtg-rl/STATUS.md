# mtg-rl status

Live progress of the MageZero policy-training run. Regenerate with:

```bash
python tools/rl_report.py /path/to/mtg-laya/repo
```

It parses `runs/<ts>/jvm_*.log` for per-matchup game completions and inter-game timing,
counts checkpoints written, and reports HDF5 bytes on disk. Safe to run while training.

## Run 1 — `2026-10-04_18-23-00`

Curriculum: `configs/run_mz.yml` + `configs/game_run.yml`
4 generations x 100 games x 2 opponents, primary deck **UWTempo** (MageZero's published case:
the greedy AI scores 16% with it, so improvement is clearest), search_budget 600,
`see_opponent_hand: false`.

| | |
|---|---|
| generation | 0 (offline bootstrap) |
| games completed | 22 at the first report |
| per-game interval | median **34 s** (MonoB) / **43 s** (MonoG) |
| throughput | ~2.5 games/minute across two concurrent JVMs |
| projected total | 800 games -> roughly 5-7 hours |
| checkpoint | none yet (written when generation 0 closes) |

Nothing here is a result yet — generation 0 is a search-only bootstrap with no network, so it
produces training data, not a policy. The first meaningful number is the evaluated win rate of
generation 1 against generation 0, and it gets compared against the **22.7% greedy-AI
baseline** measured on the same harness in `../mtg-laya/results/ANALYSIS.md`.
