# Laya plays Magic: The Gathering

Testing **Laya** (`convaiinnovations/laya`, a 421M fp16 ModernBERT-large *encoder
classifier* — it never generates text) as the decision-maker inside real, fully-ruled
Magic: The Gathering games.

- **Engine / harness (this repo):** XMage + the MageZero self-play harness, running on a
  Windows PC. Nothing is built from source — the MageZero release ships a precompiled
  XMage JAR with all dependencies.
- **Laya:** served separately on a DGX Spark (`http://192.168.1.166:5555`, the
  `typed-decisions` 421M checkpoint on GPU). The Java player calls it over HTTP.
- **Only Laya runs on the DGX** — engine, JVM, decks and logs all live on the PC.

## Why XMage + MageZero

[XMage](https://github.com/magefree/mage) (MIT) is a complete open-source MTG rules
engine. [MageZero](https://github.com/WillWroble/MageZero) (MIT) is a headless self-play
harness built around a fork of it: players get their policy from a remote HTTP model
(`RemoteModelEvaluator` → `POST /evaluate`), and the whole thing runs AI-vs-AI without a
client, writing a win rate for every run.

Rejected alternatives: **Forge** (GPL, AI baked into Java — a custom player means patching
the engine), **Magarena** (built as an AI testbed, but unmaintained since 2023),
**open-mtg** (pure Python and easy to hook, but partial rules, dead since 2019),
**grove** (C#, no hook).

## How Laya plugs in

`LayaPlayer extends ComputerPlayer8` — XMage's stock greedy AI — and hands it the
decisions that can be expressed as an **enumerated, human-readable list**. Everything
else falls through to the stock AI, so games stay legal and a Laya-piloted player can be
compared head-to-head against the same opponent.

Intercepted today:

| hook | Laya's question |
|---|---|
| `choose(Outcome, Choice, Game)` | which of the enumerated options |
| `chooseUse(Outcome, String, Ability, Game)` | YES / NO on a proposed action |
| `choose(Outcome, Target, Ability, Game)` | which target |
| `chooseTriggeredAbility(List<TriggeredAbility>, Game)` | which trigger goes on the stack first |
| `selectAttackers(Game, UUID)` | should each of my creatures attack? |
| `selectBlockers(Ability, Game, UUID)` | should this blocker block, and which attacker? |

Each call is appended to `laya_decisions.jsonl` (kind, options, answer, confidence,
latency, used-or-fell-back), so agreement, latency and coverage are measurable.

### Still not hooked

The main action loop (`ComputerPlayer6.act`) — which spell to cast or land to play — still
runs the stock AI's minimax simulation. `Player.getPlayable(Game, boolean)` plus
`activateAbility` / `playLand` are the API to intercept it; until then Laya controls
combat, triggers, targets and choices, but not what gets cast.

## Measured results

**Full write-up, every arm and every control test: [results/CONCLUSIONS.md](results/CONCLUSIONS.md).**

Summary of the conclusion: Laya controls the game flow perfectly and decides nothing — on
every hooked decision its answer is a constant that does not depend on the board, while the
engine's own AI plays a mixed, position-driven policy (attacks 71% of the time; Laya says
ATTACK 100%). The plumbing, the harness and the measurement are sound and reusable; the
421M routing/guardrail classifier is the limiting factor. The path to a Laya that plays is
fine-tuning it on the labelled decision data this harness already generates
(`dataset/decisions.jsonl`, 4,963 rows from 200 games).

### Head-to-head arms — same decks, same engine, random seeds

| arm | rule on the combat prompts | games | win rate |
|---|---|---|---|
| run4 | take Laya's pick (argmax) | 50 | **30.0%** |
| run5 | *baseline: the stock greedy AI alone* | 50 | **24.0%** |
| run6 | argmax, neutral option wording | 20 | 40.0% |
| run7 | only act when confidence ≥ 0.5 | 20 | **10.0%** |

n=20/50 means every difference here is inside the noise (±6 pp at n=50). The informative
part of these runs is the *behaviour*, not the win rate:

### What Laya actually decided

run4, 448 decisions over 50 games — **every one accepted**:

| kind | n | mean confidence | times it chose the "action" option |
|---|---|---|---|
| attack | 296 | 0.349 | **296 / 296** |
| block | 79 | 0.046 | **79 / 79** |
| chooseUse | 61 | 0.046 | 61 / 61 take |
| trigger | 12 | 0.593 | — |

Latency **avg 77 ms** (58–468) → **34.5 s of total Laya compute for 50 full games**.

### Control test — `tools/laya_control_test.py`

Same question, only the board state and the option order varied:

| board | options | Laya's answer | confidence |
|---|---|---|---|
| good (opponent at 6, empty board) | `ATTACK` / `HOLD` | ATTACK | 0.554 |
| good, options reversed | `HOLD` / `ATTACK` | ATTACK | 0.623 |
| bad (I am at 2 life vs 3 blockers) | `ATTACK` / `HOLD` | **ATTACK** | 0.365 |
| bad, options reversed | `HOLD` / `ATTACK` | **ATTACK** | 0.435 |
| graded 3-option, both boards | attack / attack-if-unblocked / hold | ATTACK with everything | 0.07–0.09 |

**Conclusion:** the *choice* does not depend on the board — Laya's argmax on these prompts
is a constant ("attack"). Only the *confidence* moves, and it moves in the right direction
(0.55 on a good board, 0.37 on a losing one) but never reaches a usable level in game, so
neither the argmax nor a 0.5 confidence gate gives a real policy: the gate simply makes it
never attack, and a deck that never attacks wins 10%.

That is the honest result of the experiment: Laya's calibration was trained for routing,
guardrails and email triage, **not** for board-state judgement, and the free-text +
option-list interface of the gate does not carry enough of the state for a 421M classifier
to act on. The wiring, the harness and the measurement are all sound — the model is the
limiting factor.

### Where that leaves it

1. **Fine-tune** the `typed-decisions` checkpoint on MTG decisions. The harness already
   writes labeled decision data for exactly this (that is what MageZero trains on), and the
   Laya repo ships a fine-tuning notebook for running it on free Kaggle GPUs. This is the
   real path to Laya-as-policy.
2. Intercept the cast/play loop (`Player.getPlayable` + `activateAbility`/`playLand`) so
   Laya controls the whole turn, not just combat.
3. Or stop here: treat Laya as what it is — a routing/guardrail gate — and use the XMage
   harness to test an actual policy model instead.

**Operational note:** the Laya service used for MTG runs with `LAYA_LOW_CONF=0.0`. With
the default 0.20 the gate rewrites any low-confidence answer to the literal choice
`UNCLEAR`, which is useless to a game engine — the first run produced 0 usable decisions
for exactly that reason.

## Reproduce it

```bash
# 1. fetch the JDK + the precompiled XMage distro (no admin rights needed)
bash scripts/setup.sh

# 2. or compile by hand, from this directory, against the distro jars
tools/jdk/bin/javac -nowarn -cp "dist/xmage/lib/*" -d classes \
    src/mage/player/ai/LayaPlayer.java src/org/mage/magezero/LayaMain.java

# 3. run (from the xmage distro dir, so decks/ and db/ resolve)
cd dist/xmage
../../tools/jdk/bin/java -cp "lib/*;../../classes" \
  -Dlaya.url=http://192.168.1.166:5555 -Dlaya.log=laya_decisions.jsonl \
  -Xms2g -Xmx16g --add-opens=java.base/java.lang=ALL-UNNAMED \
  org.mage.magezero.LayaMain ../../configs/run3.yml
```

Config knobs that matter: `player_a.type` (`laya` | `minimax` | `mcts`),
`deckPath`, `training.games/threads/max_turns`, `logging.save_final_wr` (writes
`WinRates.txt`), `logging.log_feature_hash` (leave `false`; `true` writes a 41 MB
feature table).

## Repo layout

```
mtg-laya/
  src/mage/player/ai/LayaPlayer.java     the Laya-driven AI
  src/org/mage/magezero/LayaMain.java    harness main that understands `type: laya`
  configs/run1.yml minimax vs minimax (engine smoke test, no model server needed)
  configs/run2.yml Laya vs minimax, 1 game
  configs/run3.yml Laya vs minimax, 3 games
  scripts/setup.sh                       downloads JDK + XMage distro, makes data/ dirs
  results/                               decision log + win rates
```
