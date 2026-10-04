# Results summary

Every arm, Standard-MonoR (player A) vs Standard-MonoG, same XMage engine, random seeds.

## Win rate by arm

| arm | run | games | win rate | 95% CI |
|---|---|---|---|---|
| baseline: stock greedy AI | run5 | 50 | 24.0% (12/50) | 14.3-37.4% |
| baseline: stock greedy AI | run8 | 200 | 27.0% (54/200) | 21.3-33.5% |
| baseline: stock greedy AI | run8b | 200 | 18.0% (36/200) | 13.3-23.9% |
| base Laya (no fine-tune) | run4 | 50 | 30.0% (15/50) | 19.1-43.8% |
| base Laya + confidence gate (rule, not a model) | run7 | 20 | 10.0% (2/20) | 2.8-30.1% |
| fine-tune v1 (all heads) | run9 | 200 | 20.0% (40/200) | 15.0-26.1% |
| fine-tune v2 (aligned prompts) | run10 | 200 | 19.0% (38/200) | 14.2-25.0% |
| v2 hybrid (attack head only) | run11 | 200 | 24.0% (48/200) | 18.6-30.4% |
| fine-tune v3 (balanced heads) | run12 | 200 | 20.5% (41/200) | 15.5-26.6% |
| **pooled baseline** | run5+8+8b | 450 | **22.7%** (102/450) | 19.0-26.8% |

The same baseline configuration produced **18.0% and 27.0% on two separate 200-game runs** — that spread is the run-to-run variance you have to beat before any claim about a Laya arm means anything.

## Decision mix vs the expert

| decision | expert (stock AI) | v1 | v2 | v3 | hybrid (attack only) |
|---|---|---|---|---|---|
| attack | 71% | 100% | 42% | — | 45% | 42% |
| block | 45% | 100% | 66% | — | — | 66% |
| take optional action | 66% | 71% | 2% | — | — | 2% |

## Rounds

| round | data | fitted choice temperature | finding |
|---|---|---|---|
| 1 | 4,834 cases (imitation) | 6.048 | constant-answer failure fixed |
| 2 | 5,066 cases (prompt-aligned) | 5.162 | chooseUse collapsed 2% -> 0% |
| 3 | 4,800 cases (heads balanced 1,200 each) | 3.372 | mix unchanged: 42/66/2 |

## The control test (does the answer depend on the board?)

| checkpoint | won board | lost board |
|---|---|---|
| base_laya | ATTACK (0.143) | ATTACK (0.012) |
| finetune_v1 | ATTACK (0.894) | HOLD it back (0.904) |
| finetune_v2 | ATTACK (0.747) | HOLD it back (0.716) |

## What the numbers say

1. **No Laya variant beats the baseline, and none is demonstrably worse.** Every Laya arm lands between 19.0% and 24.0%; the baseline's own two runs span 18.0% to 27.0%. The differences are inside the engine's run-to-run variance.
2. **The fine-tuning worked at the model level**: the base checkpoint answered a constant (ATTACK at 0.01-0.14 confidence on both a won and a lost board); every fine-tuned checkpoint flips the answer with the board at 0.72-0.90 confidence.
3. **It did not transfer to play.** In game the decision mix stays skewed from the expert's at every round: attack 40-45% (expert 71%), block 66-81% (expert 44%), take 0-2% (expert 57%).
4. **Three separate explanations were tested and falsified**: prompt wording (round 2), option order (round 2), item imbalance (round 3). The skew persists unchanged, so it is structural — one shared representation carrying several typed heads.
5. **Beating a professional player is not reachable on this path.** The engine's own RL track (MageZero) took a deck from 16% to 66% against a minimax pool (~61% estimated vs humans) by training a policy on state features. A 421M text classifier choosing between option strings is the wrong architecture for a strong player.
