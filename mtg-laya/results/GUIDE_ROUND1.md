# Guide-trained model — round 1 result

**Verdict: the number improved, the behaviour did not. The test did not work.**

## What was tested

Train on the strategy knowledge base's rules instead of imitating the engine's greedy AI.
Rationale: the greedy AI is the ceiling on play strength, so imitating it cannot exceed it, and
the guide's rules disagree with the bot on a substantial share of attack decisions.

Pipeline: `tools/rule_teacher.py` (guide rules → labels) → `tools/to_laya_from_guide.py`
(labels → Laya cases) → fine-tune → deploy → 50-game arm.

## Numbers

| | |
|---|---|
| training | 3,318 guide-labelled attack decisions → 1,500 balanced cases |
| losses | 0.5408 → 0.6971 → 0.0921 → **0.0118** |
| fitted temperature | **1.0** (calibrated, vs 5–6 for the imitation models) |
| **arm win rate** | **28.0% (14/50)** — best of any arm |
| attack rate | 86% overall |
| attack vs 0 blockers | **85%** |
| attack vs 1+ blockers | **87%** |
| mean confidence | **1.000** |

## Why it does not count as a win

1. **No discrimination.** 85% vs 87% by blocker count is no signal at all — the same failure as
   every previous arm, which ran 100/100 or 63/51.
2. **Confidence pinned at 1.000.** The model is not weighing anything; it is reciting a learned
   constant. The low training loss (0.0118) on 1,500 binary cases is memorisation, not judgement.
3. **Sample size.** n=50, and the baseline itself spans 18–27% across two 200-game runs. 28% is
   inside that band. Nothing is established.

The plausible mechanism for the gain is simply that the guide says "you should usually attack if
you can" and the bot only attacks 71% of the time — so a model that always attacks is closer to
correct for an aggro deck. That is a *rate* correction, not a decision skill, and it is the one
thing here that might be real (needs a 500+ game arm to check).

## What round 2 needs

1. **Train the block head too.** This round it had 0 block rows: the dataset path for blocking
   was still logging bare options, so the rule teacher could not parse them. Fixed in
   `LayaPlayer` — both combat decisions now share the consequence-carrying option text between
   the live path and the dataset path.
2. **Fix the saturation.** Confidence 1.000 means the head is saturated; the guide's labels are
   one-hot and the task is binary, so the model can fit them exactly. Train against the guide's
   *reasons* as soft targets, or hold out far more data, so the model has to generalise.
3. **Bigger arms.** 500+ games to resolve anything under ~8 points, or paired seeds.

## Standing

Across five models now (4 imitation fine-tunes, 1 guide-trained, plus a 4-generation policy
network) and ~2,700 games, every one ends as a near-constant on the decision heads, with win
rates 14–30% against a baseline spanning 18–27%. The consistent finding is that the models'
probability *ordering* tracks the position while their argmax does not. The guide-trained route
is the only one with a mechanism behind it, and it is now built and reproducible — it just has
not produced a model that decides yet.
