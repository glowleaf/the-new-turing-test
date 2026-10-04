# Fine-tuning Laya to play MTG — round 1 (imitation of the engine's greedy AI)

First pass at making Laya *able* to decide, rather than answering a constant.

> **Round 2 is appended at the end of this file** — prompt alignment, a second training run,
> the per-question-type collapse it exposed, and the hybrid pilot that followed.

## What was done

1. **Data** — `tools/build_dataset.py` (dataset mode of `LayaPlayer`, `-Dlaya.logOnly=true`)
   ran 200 games of stock-AI-vs-stock-AI and logged every decision: the state text, the
   option list, and the option the stock AI actually took → 4,963 decisions.
2. **Convert** — `tools/to_laya_dataset.py` turned them into Laya's training schema
   (`state` + typed `questions` with instructions/criteria + `gold` distributions) →
   **4,834 cases** (129 skipped where the label was not among the options).
3. **Train** — Laya's own single-device RLCD trainer (`tools/finetune_single_device.py`,
   vendored from `NandhaKishorM/laya`), on the RTX 5060 Ti 16 GB:
   4,434 train items + **400 held out for temperature calibration**, 4 epochs,
   555 steps/epoch, fp16 + gradient checkpointing, ~20 minutes, 10.8 GB VRAM.
   Epoch losses 0.4380 → 0.4340 → 0.5721 → 0.5355 (the RLCD objective is not monotone —
   it mixes a policy-gradient term with the soft cross-entropy term).
   Fitted temperatures (choice, score, noul) = **6.048** / 1.2 / 1.2.
4. **Serve** — `tools/deploy_laya_dgx.sh` ships the checkpoint to the DGX, repoints the
   `~/models/laya-current` symlink (`~/models/laya-mtg-v1`) and restarts `laya-gate`.
   The base checkpoint is left on disk untouched.
5. **Re-measure** — the same arms as before, unchanged.

> Env note learned the hard way: the 5060 Ti is `sm_120` (Blackwell) — plain PyPI `torch`
> installs **CPU-only** and silently reports `cuda False`. Pin `torch==2.8.0+cu128`.
> Also install `laya` with `--no-deps` so it does not clobber the CUDA torch.

## Result 1 — the model now reads the board

Same question, two board states, answered through the live DGX `/choose` endpoint with the
prompt the checkpoint was trained on:

| board | base Laya | fine-tuned Laya |
|---|---|---|
| won board (opponent at 1 life, empty board) | ATTACK, conf **0.143** | ATTACK, conf **0.894** |
| lost board (me at 1 life, three 5/6 blockers) | ATTACK, conf **0.012** | **HOLD it back**, conf **0.904** |

The base checkpoint answered ATTACK on both — a constant. The fine-tuned checkpoint
**flips with the board at ~0.9 confidence**. That was the whole blocker, and one training
run on 4,834 decisions removed it.

## Result 2 — and it did not win more games

200 games, Standard-MonoR (player A) vs Standard-MonoG, same engine, random seeds:

| arm | games | player-A win rate |
|---|---|---|
| **fine-tuned Laya piloting** | 200 | **20.0%** (40/200) |
| stock greedy AI (baseline, drawn from the dataset run) | 200 | **27.0%** (54/200) |
| base Laya piloting | 50 | 30.0% |
| stock greedy AI (baseline) | 50 | 24.0% |

−7 pp against the same-size baseline: z ≈ −1.65, p ≈ 0.10 — **marginally worse, not
better.** A model that reads the board better than the base checkpoint still pilots worse
than the AI it was cloned from.

## Result 3 — the reason is visible in the decision mix

| decision | fine-tuned Laya | stock AI (the thing it imitated) |
|---|---|---|
| attack | **42%** (679/1613) | 71% |
| block | **66%** (496/746) | 44% |
| take an optional action | **2%** (2/129) | 57% |

Mean confidence: attack 0.831, block 0.194, optional action 0.871 — it is *confident* while
being systematically skewed.

That is textbook behaviour-cloning failure, and both causes are identifiable:

1. **Distribution shift.** The training states came from stock-vs-stock games; at
   evaluation the states come from games a *different* player is producing. The
   off-distribution states get minority-ish answers that the majority label never
   demonstrated.
2. **A prompt-format mismatch on one head.** `chooseUse` training cases carried the proposed
   action as `Question: <message>` while the live player sends `Proposed action: <message>`
   — and that head collapsed to 2% TAKE vs the 57% it was trained on. Cheap to fix, and
   worth fixing before trusting any of it.

## What round 2 should be

1. **Align the prompts** — one source of truth for each decision's instructions/criteria
   shared by the dataset builder and the Java player (the `chooseUse` collapse is the tell).
2. **DAgger, not plain imitation** — this is exactly what the Laya authors did for their
   browser agent ("on-policy corrections"): let the fine-tuned model play, log its states,
   relabel those states with the stock AI's choices, retrain. It fixes the shift directly.
   The harness already has the hook: `LayaPlayer` can ask Laya *and* let the stock AI decide
   in the same position, logging both.
3. **Outcome labels** — needs a game-end hook (`cleanUpOnMatchEnd` is not called by this
   harness path); with them, filtered imitation (train on winners) and the MageZero-style
   TD-labelled targets become available.
4. **More data** — 4,834 cases is a first pass; 2,000 games ≈ 50k cases, which is the scale
   the Laya docs quote for real work.

## Honest standing

Laya is now a model that reads an MTG board and picks between described options with real
discrimination. It still loses to the engine's own greedy AI, and a professional human
player is not on this path at all — that is the MageZero-style RL ladder (their published
47.9% vs a minimax pool, ~61% estimated vs humans). What this round proves is that the
blocker was the checkpoint, not the harness: the same pipeline can now be iterated.

Reproduce:

```bash
python tools/build_dataset.py dist/xmage/dataset_raw.jsonl dataset
python tools/to_laya_dataset.py dataset/decisions.jsonl dataset/laya_cases.jsonl
./.venv-train/Scripts/python tools/finetune_single_device.py --data dataset/laya_cases.jsonl \
    --model-dir laya-ckpt --output-dir laya_finetuned_mtg --device cuda --epochs 4
bash tools/deploy_laya_dgx.sh laya_finetuned_mtg mtg-v1
cd dist/xmage && ../../tools/jdk/bin/java -cp "lib/*;../../classes" \
    -Dlaya.url=http://192.168.1.166:5555 org.mage.magezero.LayaMain ../../configs/run9.yml
```

---

# Round 2 — prompt alignment + hybrid pilot (and what it exposed)

## What changed

1. `LayaPlayer`'s dataset mode now logs **exactly the state string the live player sends**
   (` Creature in question: X 2/2`, ` Blocker under consideration: …`, ` Proposed action: …`),
   and `tools/to_laya_dataset.py` uses it verbatim — no re-wording between training and
   inference. (Round 1's `chooseUse` head had a real `Question:` vs `Proposed action:`
   mismatch.)
2. Regenerated the data: 200 games → 5,208 decisions → **5,066 cases** (round 1: 4,834).
3. Retrained → `laya_finetuned_mtg_v2`: losses 0.3156 / 0.4087 / 0.3366 (round 1:
   0.4380 → 0.5355), fitted choice temperature **5.162** (round 1: 6.048). Served on the
   DGX as `~/models/laya-mtg-v2`.
4. Added `-Dlaya.kinds=…` so Laya can be restricted to specific decision types, and ran a
   **hybrid** arm with Laya driving only the attack head.

## Results — all arms at 200 games (Standard-MonoR vs Standard-MonoG)

| arm | win rate | ATTACK | BLOCK | TAKE |
|---|---|---|---|---|
| stock greedy AI (baseline, both sides) | **27.0%** (54/200) | 71% | 44% | 57% |
| Laya v1, all heads | 20.0% (40/200) | 42% | 66% | 2% |
| Laya v2, all heads (aligned prompts) | 19.0% (38/200) | 40% | 81% | 0% |
| **Laya v2, attack head only (hybrid)** | **24.0%** (48/200) | 45% | — (stock) | — (stock) |

Every Laya-driven variant is at or below the AI it was cloned from. Turning off the collapsed
heads recovered ~5 pp (19 → 24) but did not reach parity.

## The collapse is per question type, not a prompt artefact

The `chooseUse` head answers **DECLINE the action at 0.939 confidence** regardless of the
board — and regardless of the option order in the schema:

| board | criteria order | answer | conf |
|---|---|---|---|
| should take (opponent at 4, I have the board) | TAKE first | DECLINE | 0.939 |
| should decline (I at 2, empty board) | TAKE first | DECLINE | 0.939 |
| should take | DECLINE first | DECLINE | 0.939 |
| should decline | DECLINE first | DECLINE | 0.936 |

So prompt alignment fixed nothing measurable, and position bias is ruled out. What the heads
have in common is extreme item imbalance: attack 3,381 / block 1,154 / **use 412** /
trigger 119 in one model with one shared representation and four typed heads.

Meanwhile the *attack* head still discriminates on clean control boards
(ATTACK 0.747 on a won board, HOLD 0.716 on a lost one) yet only attacks 40–45% in game
against the expert's 71% — the synthetic control boards are not representative of in-game
states, and that gap is exactly what a control test cannot see.

## What round 3 should be (in order of expected value per hour)

1. **Balance or separate the heads** — cap/oversample per decision type so the small heads are
   not swamped, and/or train one adapter per decision type with no interference.
2. **DAgger with on-policy relabelling** — the model plays, its states get relabelled by the
   stock AI, retrain. This is the technique the Laya authors used for their browser-agent
   head, and it is the direct fix for the distribution gap the hybrid arm just demonstrated.
3. **Outcome labels** (needs a game-end hook) for filtered imitation on winners.
4. **For a player that actually beats strong humans, this is the wrong architecture.** The
   engine's own RL track (MageZero) took a deck from 16% to 66% vs a minimax pool and is
   estimated at ~61% vs humans, by training a policy on state features — not by distilling a
   greedy AI into a 421M text classifier.

## Where the project stands

The harness, the dataset generator, the training pipeline, the deploy path and the four
measurement arms all work end to end and are reproducible from this repo. Laya now reads a
board well enough to flip a decision on a control case, but across 200-game arms it does not
beat the stock greedy AI, and the evidence says the limit is the model+data recipe, not the
plumbing. Every number above is in `results/`.
