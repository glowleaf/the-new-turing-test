# Conclusions — can Laya play Magic: The Gathering?

**Short answer: not as it is.** Laya is a 421M fp16 ModernBERT *encoder classifier*
calibrated for routing, guardrails and email triage. Wired into a real rules engine
(XMage via the MageZero harness) it controls the game flow perfectly and decides nothing.

This file is the honest record: what was built, every arm that was run, the control tests
that explain the numbers, and what would actually have to change.

---

## 1. What was built

| piece | what it does |
|---|---|
| `dist/xmage/` | XMage (MIT) + the MageZero self-play harness — precompiled release, runs headless AI-vs-AI, writes a win rate |
| `src/mage/player/ai/LayaPlayer.java` | XMage's stock greedy AI (`ComputerPlayer8`) with 6 decision hooks routed to Laya over HTTP |
| `src/org/mage/magezero/LayaMain.java` | harness main that understands `type: laya` |
| `tools/laya_control_test.py` | varies only the board state / option order to test whether Laya's answer depends on the position |
| `tools/build_dataset.py` | turns the harness's raw decision log into a labelled `(state, options, choice)` dataset |
| Laya service | DGX Spark, `:5555`, `typed-decisions` 421M checkpoint on GPU, `LAYA_LOW_CONF=0.0` |

Hooked decision points: `choose(Choice)`, `chooseUse`, `choose(Target)`,
`chooseTriggeredAbility`, `selectAttackers`, `selectBlockers`. Everything else falls
through to the stock AI, so games stay legal.

Not hooked: the cast/play loop (`ComputerPlayer6.act`) — `Player.getPlayable` +
`activateAbility`/`playLand` is the API to take it over.

---

## 2. Every arm that was run

Same decks (Standard-MonoR vs Standard-MonoG), same engine, random seeds.

| run | rule | games | player-A win rate | what it shows |
|---|---|---|---|---|
| run4 | take Laya's pick on the hooked decisions | 50 | **30.0%** | inside the noise |
| run5 | *baseline: stock greedy AI alone* | 50 | **24.0%** | the reference |
| run6 | pick, neutral option wording | 20 | 40.0% | wording changed nothing |
| run7 | only act when confidence ≥ 0.5 | 20 | **10.0%** | never attacks → loses |
| run8 | dataset mode (no Laya), 200 games | 200 | 27.0% | baseline is stable (24–27%) |

At n=20/50 the standard error is ±6–11 pp: **none of these differences is significant.**

## 3. The control tests — why the win rate was never the point

Same question, only the board and the option order varied:

| board | options | answer | conf |
|---|---|---|---|
| good (opponent at 6, empty board) | ATTACK / HOLD | ATTACK | 0.554 |
| good, reversed | HOLD / ATTACK | ATTACK | 0.623 |
| **bad (I am at 2 vs three blockers)** | ATTACK / HOLD | **ATTACK** | 0.365 |
| bad, reversed | HOLD / ATTACK | **ATTACK** | 0.435 |
| one-win board (`they are at 1 life`) via `/choose` + criteria | ATTACK / HOLD | ATTACK | 0.174 |
| unwinnable board (three 5/6 blockers) via `/choose` + criteria | ATTACK / HOLD | HOLD | 0.020 |

Also tried: criteria-rich schemas on Laya's native `POST /choose` with four instruction
styles (backticked `state`, `request`, no placeholder, plain words) — three of four returned
ATTACK on both boards. A graded three-option form ("attack all" / "attack if unblocked" /
"hold") also returned the aggressive option on both, at confidence 0.07–0.09.

**The choice does not depend on the board. The confidence does** (0.55 good → 0.37 bad) —
but in game it never clears a usable level, so gating on it just makes the player passive
(run7: 0 attacks in 168 chances, 10% win rate).

## 4. What the stock AI actually does (the honest yardstick)

From 200 games / 4,963 logged decisions (`dataset/decisions.jsonl`):

| decision | stock greedy AI | Laya |
|---|---|---|
| attack | **71%** attack / 29% hold (2335 / 951) | **100% attack** |
| block | 44% block / 56% no block | **100% block** |
| optional action | 57% take / 43% decline | **100% take** |

The engine's own AI plays a *mixed* policy driven by the position. Laya answers a
constant. That single table is the whole result: whatever the win rates say, Laya is not
reading the board, so it cannot be driving the decisions.

## 5. What would actually have to change

To make **Laya** play, the model has to be trained on this decision type — the plumbing is
already done and measured:

1. **Dataset** — `tools/build_dataset.py` already produces 4,963 labelled
   `(state, options, choice)` rows from 200 games (3.4 MB). Add outcome labels (needs a
   game-end hook; `cleanUpOnMatchEnd` is not called by this harness path) to enable
   *filtered imitation* — train only on decisions from games the decision-maker won.
2. **Fine-tune** `laya-typed-decisions` (or the English checkpoint) on those rows — LoRA on
   the PC's RTX 5060 Ti 16GB; the Laya repo ships a fine-tuning notebook for exactly this
   checkpoint, and the checkpoint is 421M so it fits comfortably.
3. **Serve the fine-tuned checkpoint** on the DGX `:5555` (swap `~/models/laya-current`,
   restart `laya-gate`) and re-run the same arms — the harness and all four arms re-run
   unchanged, so improvement is directly measurable.

Beating a *professional human* is not reachable on this path. The ladder is:
stock greedy AI (24–27% in this matchup) → engine MCTS → MageZero's trained RL policy,
which the authors measured at a 47.9% average against a five-deck minimax pool (win rate
16% → 66% on their tempo deck), with an estimated ~61% human win rate. A 421M text
classifier asked to pick between option strings will not close that gap; a policy model
trained on the position will.

## 6. Reproduce anything here

```bash
bash scripts/setup.sh                       # JDK + XMage distro + compile
python tools/laya_control_test.py           # the control test (needs the Laya service)
# an arm:
cd dist/xmage && ../../tools/jdk/bin/java -cp "lib/*;../../classes" \
  -Dlaya.url=http://192.168.1.166:5555 org.mage.magezero.LayaMain ../../configs/run4.yml
# dataset mode (no Laya; logs what the stock AI does):
  ... -Dlaya.logOnly=true -Dlaya.log=dataset_raw.jsonl ... ../../configs/run8.yml
python tools/build_dataset.py dist/xmage/dataset_raw.jsonl dataset
```
