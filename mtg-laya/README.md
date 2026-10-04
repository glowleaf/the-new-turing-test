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

### Head-to-head, 50 games per arm — same decks, same engine, random seeds

| arm | player A (Standard-MonoR) | player A win rate |
|---|---|---|
| **run4 — Laya piloting** | stock greedy AI won 15/50 | **30.0%** |
| **run5 — baseline** | stock greedy AI won 12/50 | **24.0%** |

`+6 pp` for Laya, but with n=50 the standard error is ~6 pp — **this is inside the noise and
is not yet evidence that Laya plays better.** It is evidence that the pipeline works and
that 50 games is not enough. 50 games cost ~2 minutes.

### What Laya actually decided (run4, 448 decisions across 50 games)

| kind | n | all accepted | mean confidence |
|---|---|---|---|
| attack | 296 | yes | **0.349** |
| block | 79 | yes | **0.046** |
| chooseUse | 61 | yes | **0.046** |
| trigger | 12 | yes | 0.593 |

Latency **avg 77 ms** (min 58, max 468) → **34.5 s of total Laya compute for 50 whole games**.

The confidence column is the interesting one: on MTG board-state text Laya is *barely*
confident (0.05–0.35), because its calibration was trained on routing / guardrail / email
triage decisions, not on creatures. Combat and triggers are now hooked, and the
engine-vs-engine comparison runs clean, but a real verdict needs a few hundred games per
arm before any of these numbers mean anything.

Raw logs: `results/laya_decisions.jsonl` (run4), `results/WinRates.txt`.

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
