#!/usr/bin/env bash
# Ship a fine-tuned Laya checkpoint to the DGX and serve it on :5555 (the swap is the
# documented symlink pattern: ~/models/laya-current -> the checkpoint dir, restart the unit).
#
#   bash tools/deploy_laya_dgx.sh laya_finetuned_mtg mtg-v1
#
# The previous checkpoint is left on disk untouched; only the symlink is repointed.
set -euo pipefail

CKPT="${1:-laya_finetuned_mtg}"
NAME="${2:-mtg-v1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -d "$CKPT" ] || { echo "no such checkpoint dir: $CKPT"; exit 1; }

# Laya loads a checkpoint dir; make sure the pieces the loader expects are present
for f in model.safetensors rl_agent_config.json; do
  [ -e "$CKPT/$f" ] || { echo "checkpoint is missing $f"; exit 1; }
done
# the base config.json / encoder config are needed too — borrow them if the trainer
# did not write them
[ -e "$CKPT/config.json" ] || cp laya-ckpt/config.json "$CKPT/config.json"
[ -e "$CKPT/encoder/config.json" ] || cp laya-ckpt/encoder/config.json "$CKPT/encoder/config.json"

echo "== shipping $CKPT to the DGX as ~/models/laya-$NAME"
ssh spark "mkdir -p ~/models/laya-$NAME"
scp -q -r "$CKPT/." "spark:~/models/laya-$NAME/"

echo "== repointing ~/models/laya-current and restarting the gate"
ssh spark "ln -sfn ~/models/laya-$NAME ~/models/laya-current && systemctl --user restart laya-gate.service && sleep 30 && curl -s http://127.0.0.1:8917/health; echo; readlink -f ~/models/laya-current"

echo
echo "== verifying from this machine"
curl -s -m 20 http://192.168.1.166:5555/health; echo
echo "run the arms:  configs/run4.yml (Laya) vs configs/run5.yml (baseline)"
