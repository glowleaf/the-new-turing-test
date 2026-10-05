# Operations — the Laya service and the swap that bit us

## The gate checkpoint is a symlink, and experiments must be undone

`laya-gate.service` on the DGX serves whatever `~/models/laya-current` points at:

```
~/models/laya-current -> <checkpoint dir>
```

`tools/deploy_laya_dgx.sh` ships a fine-tune to `~/models/laya-<name>/` and repoints that
symlink. **That means every MTG experiment silently replaced the routing/guardrail model your
pipelines actually call.** During this work the gate spent hours serving `laya-mtg-attack` — a
model fine-tuned on Magic: The Gathering decisions — while gate calls (site routing, guardrails,
moderation) kept being made against it.

Always repoint it back when an experiment ends:

```bash
ssh spark 'ln -sfn <the base checkpoint> ~/models/laya-current \
           && systemctl --user restart laya-gate.service && sleep 25 \
           && curl -s http://127.0.0.1:8917/health'
```

The base checkpoint is the `typed-decisions` snapshot in the HF cache:

```
/home/machinegeorge/.cache/huggingface/hub/models--convaiinnovations--laya-typed-decisions/snapshots/e929ae5cf69bc34259cd2f95c9e91145b818b1f0
```

Experiment checkpoints (`laya-mtg-v1`, `-v2`, `-v3`, `-attack`) stay on disk; repointing the
symlink is all that changes, so nothing is ever lost.

Verify it is a gate again, not a game model — a real routing call:

```bash
curl -s -X POST http://192.168.1.166:8917/decide -H 'Content-Type: application/json' \
  -d '{"task":"route","text":"Bitcoin ETF inflows hit a record this week"}'
# -> {"choice":"LOVEISBITCOIN", ...}
```

## Two service configurations, deliberately different

| host | model | device | port | `LAYA_LOW_CONF` |
|---|---|---|---|---|
| **Ubuntu box** (`ssh ubuntu`, PRIMARY gate) | english 421M | cpu | 8917 | 0.20 (default) |
| **DGX** (`ssh spark`, experiments) | `~/models/laya-current` | cuda | 8917 + 5555 (socat) | **0.0** |

`LAYA_LOW_CONF=0.0` on the DGX exists so a caller gets the model's actual choice with its
confidence instead of the literal string `UNCLEAR`. With the default 0.20, every MTG answer below
0.20 was rewritten to `UNCLEAR` and could never be used — that is why the first Laya run produced
zero usable decisions.

**Do not set 0.0 on the Ubuntu gate**: its callers rely on `UNCLEAR` meaning "no verdict, queue
for George".

**Port 6666 is Libby's Qwen3-TTS voice socat — never take it.** The MTG experiments used 5555.

## Live state (last verified)

| | |
|---|---|
| DGX gate | serving the base `typed-decisions` checkpoint, `active`, routing verified |
| PC | no harness processes running |
| RL run 1 | complete — 4 generations, ~800 games, ~9 h (`../mtg-rl/RESULTS.md`) |
| experiment checkpoints on disk | `laya-mtg-v1`, `laya-mtg-v2`, `laya-mtg-v3`, `laya-mtg-attack` |
