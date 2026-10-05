# mtg-rl — training a policy for MTG (MageZero route): results

The Laya investigation (`../mtg-laya/`) concluded that a 421M text classifier distilled from the
engine's greedy AI cannot pilot the game (four falsified hypotheses, ten arms, ~2,600 games).
This directory is the other route: **learn a policy from the engine's own search and play it
through MCTS**, using [WillWroble/MageZero](https://github.com/WillWroble/MageZero) (MIT) and its
XMage fork, headless on a Windows PC. Laya stays on the DGX; nothing here touches it.

## The run

`configs/run_mz.yml` + `configs/game_run.yml`, 4 generations x 100 games x 2 opponents,
primary deck **UWTempo** (the deck MageZero's own README says is "extremely punishing for
greedy AI": minimax scores 16% with it), search_budget 600, `see_opponent_hand: false`,
6 threads per JVM, two JVMs concurrently. A PC restart mid-run was resumed with `mz train
--resume`, which picked up at the right generation and skipped the games already done.

Completed: 4 generations, ~800 games, ~9 hours wall clock.

## What the harness measures — and what it does NOT

It reports **policy accuracy**: the argmax of the net's head matching the argmax of MCTS's
visit distribution. **It does not measure win rate anywhere.** That distinction matters,
because accuracy against a strong teacher is not strength, and accuracy against a head with a
majority class is not even imitation.

`tools/head_metrics.py` computes the missing baseline — the accuracy of a model that ignores the
board and always answers the most common choice (top1_share), plus the teacher's mean entropy:

| head | n (train) | do-nothing ceiling | gen 3 accuracy | mean entropy | distinct choices |
|---|---|---|---|---|---|
| `priority` (which action) | 29,390 | **0.791** | 0.797 | 0.311 | 20 |
| `choose_use` (binary act) | 2,244 | **0.535** | 0.692 | 0.567 | 2 |
| `choose_target` (which target) | 3,422 | **0.201** | 0.280 | 0.859 | 41 |

## The accuracy curve across generations

| gen | priority_A | choose_use | choose_target | val loss | decision states |
|---|---|---|---|---|---|
| 0 | (bootstrap — not evaluated) | — | — | — | 17,816 |
| 1 | 0.822 | 0.594 | 0.191 | 0.644 | 17,240 |
| 2 | 0.838 | 0.616 | 0.250 | 0.600 | 18,684 |
| 3 | 0.797 | **0.692** | **0.280** | **0.506** | 17,714 |

Training losses fell steadily every generation (`priority_A` 0.171 → 0.086, `value` 0.128 →
0.033, `choose_target` 0.378 → 0.236), and the feature vocabulary grew as new states appeared
(3,865 → 4,936 embedding rows), so the loop is genuinely closing.

## Reading it honestly

1. **`priority` never leaves the majority class.** 0.791 is free; the model reaches 0.797–0.838.
   At generation 3 it *dropped* to 0.797 — level with the ceiling. On the head that chooses the
   action, the net is indistinguishable from always answering the same thing.
2. **`choose_use` genuinely improved, from about chance to clearly above it.** 0.5 is a coin
   flip; it went 0.594 → 0.616 → 0.692, well clear of the 0.535 ceiling. This is the one head
   with real signal, and it is also the smallest option space (two options).
3. **`choose_target` improved but is still marginal against its ceiling** — 0.191 → 0.250 →
   0.280 against a 0.201 floor. The teacher is decisive here (0.859 nats, far below the 3.71 of
   a uniform 41-way choice), so a pattern exists; finding it across 41 skewed options is simply
   hard, and this is the same head Laya collapsed on.
4. **No win rate was ever produced.** So the honest status is: *the loop trains, accuracy on the
   two-option head improves measurably, and nothing here demonstrates that the agent plays Magic
   better than the search it learned from.*

## Defects found in the shipped harness

1. **`priority_B` trains on zero samples — by design.** `filter_opponent_states` in
   `src/magezero/dataset.py` drops every opponent-priority state (`is_player == 0 and
   actionType == 0`), so the opponent head reports `priority_B_loss=0.000` and the test log prints
   "No priority B samples" in every generation. The head exists in the architecture and is never
   fed. Consequence: the net models only its own moves, never the opponent's — which is the
   capability that makes search strong.
2. **Accuracy is reported without its majority-class baseline.** `test.py` prints
   `Test priority_A_accuracy=0.822` with no reference point, so a number at the ceiling reads as
   skill. This is the defect that most misleads a reader of the logs, and it applies to the Laya
   work too.
3. **The shipped `configs/game.yml` is a trap for a first run**: a 1,000-node search budget with
   a 4-second decision timeout and 50-turn games makes the bootstrap generation take tens of
   minutes *per game* with no trained net. Budget search against measured throughput
   (~53 MCTS evaluations/second here).

## Practical notes

- `bin/mz-xmage.bat` resolves the JVM via `JAVA_EXE`. The runner launches it with `cmd /c`, so a
  shell `export PATH` is invisible to it, and `setx` **truncates the user PATH at 1024 chars**.
- Kill stray JVMs before a re-run (`bin/killjava.cmd`); a leftover JVM holds HDF5 files open and
  `rm` fails with `Device or resource busy`, silently breaking any `&&` chain behind it.
- Measured throughput: ~2.5 games/minute across two concurrent JVMs with search_budget 600, so
  100 games per opponent per generation is about an hour.
- Reproduce the metrics: `python tools/rl_report.py` (progress + accuracy),
  `.venv-mz/Scripts/python tools/head_metrics.py` (ceilings per head).

## Where this leaves the question

Two independent architectures, trained on the same engine's decisions by two different methods,
both end up at or below the majority-class ceiling on the head that picks the action. The
mechanism is not prompts, not data balance, not head interference, and not the training loop —
all four were tested and falsified on the Laya side and the same pattern reappears here. Learning
to imitate a search that answers the same thing 79% of the time teaches the prior, not the
position.

The remaining lever that could actually change the outcome is **generating labels from game
outcomes (win/loss) rather than imitating the search**, which is a change to how data is produced,
not a training tweak. Until that exists, every number above measures imitation, and none of them
measures strength.
