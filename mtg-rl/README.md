# mtg-rl — training a *policy* for MTG (the MageZero route)

The Laya work in `../mtg-laya/` answered its question: a 421M text classifier distilled from
the engine's greedy AI cannot pilot the game (four hypotheses tested and falsified — see
`../mtg-laya/results/FINETUNE.md`). This directory is the other route, the one the engine's
own authors took: **learn a policy from game outcomes and play it through MCTS**.

Uses [WillWroble/MageZero](https://github.com/WillWroble/MageZero) (MIT) and its XMage fork,
running headless on the Windows PC. Laya stays on the DGX; nothing here touches it.

## Wiring the harness on a Windows box with no system-wide JDK

`mz-xmage.bat` calls bare `java`, and the runner launches it with `cmd /c` — so neither a
shell `export PATH` nor a registry PATH edit is reliably visible to it. Fix it in the batch
file instead (`bin/mz-xmage.bat`): resolve the JVM explicitly via `JAVA_EXE`.

Things that do **not** work, learned the hard way:
- `export PATH=…` in the shell that runs `mz` — the child `cmd /c` does not inherit it.
- `setx PATH` to append a dir — it **silently truncates at 1024 chars** and will chop the
  tail off the real user PATH. Restore with PowerShell's `SetEnvironmentVariable`, which has
  no such limit.

Also: kill stray JVMs before a re-run (`bin/killjava.cmd`) — a leftover JVM holds the HDF5
files open and `rm` fails with `Device or resource busy`, which then short-circuits any
`&&` chain behind it.

## Configs

| file | purpose |
|---|---|
| `configs/game_smoke.yml` + `configs/run_smoke.yml` | cheap wiring test — search_budget 50, timeout 250 ms, max_turns 12, 4 games. Proves data → train → checkpoint → win rate in ~3 minutes. |
| `configs/game_run.yml` + `configs/run_mz.yml` | the real curriculum — search_budget 600, timeout 1.2 s, max_turns 50, 6 threads/JVM, 4 generations × 100 games × 2 opponents, `see_opponent_hand: false`. |

**The shipped `configs/game.yml` is a trap for a first run**: its 1,000-node budget with a
4-second decision timeout and 50-turn games means the bootstrap generation takes tens of
minutes *per game* with no trained net. Budget the search budget against measured throughput.

## Throughput (measured on this PC)

- ~53 MCTS evaluations/second, single matchup thread
- with the real config: **1.5–2 games/minute across two concurrent JVMs**
- so 800 games ≈ an overnight run

## Run it

```bash
.venv-mz/Scripts/mz train --run configs/run_mz.yml --game configs/game_run.yml
```

Artifacts per generation: `models/UWTempo/ver<N>/model.pt.gz`, `data/UWTempo/ver<N>/`, and
`runs/<timestamp>/{run.json,train.log}`.
