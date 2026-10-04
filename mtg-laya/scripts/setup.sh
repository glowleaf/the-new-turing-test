#!/usr/bin/env bash
# Fetch everything needed to run the Laya-on-MTG testbed. No admin rights required:
# the JDK is a plain zip and the XMage distro is a precompiled release asset.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

JDK_DIR="$ROOT/tools/jdk"
XMAGE_DIR="$ROOT/dist/xmage"
JDK_URL="https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk"
XMAGE_URL="https://github.com/WillWroble/MageZero/releases/download/v0.2.0-alpha/magezero-xmage-v0.2.0-alpha.zip"

mkdir -p tools dist

if [ ! -x "$JDK_DIR/bin/java" ]; then
  echo "== downloading Temurin 21 ..."
  curl -sL -o tools/temurin21.zip "$JDK_URL"
  mkdir -p tools/jdk_tmp
  unzip -q -o tools/temurin21.zip -d tools/jdk_tmp
  mv tools/jdk_tmp/jdk-* "$JDK_DIR" 2>/dev/null || true
  rm -rf tools/jdk_tmp tools/temurin21.zip
fi
"$JDK_DIR/bin/java" -version

if [ ! -d "$XMAGE_DIR/lib" ]; then
  echo "== downloading the MageZero XMage distribution (~450 MB) ..."
  curl -sL -o tools/magezero-xmage.zip "$XMAGE_URL"
  unzip -q -o tools/magezero-xmage.zip -d dist
  rm -f tools/magezero-xmage.zip
fi

# the harness writes HDF5 game data here and dies if the dirs are missing
mkdir -p "$XMAGE_DIR/data/playerA" "$XMAGE_DIR/data/playerB"

echo "== compiling ..."
mkdir -p classes
"$JDK_DIR/bin/javac" -nowarn -cp "$XMAGE_DIR/lib/*" -d classes \
  src/mage/player/ai/LayaPlayer.java src/org/mage/magezero/LayaMain.java

echo
echo "ready. run a game with:"
echo "  cd $XMAGE_DIR"
echo "  $JDK_DIR/bin/java -cp \"lib/*;$ROOT/classes\" \\"
echo "    -Dlaya.url=http://192.168.1.166:5555 -Dlaya.log=laya_decisions.jsonl \\"
echo "    -Xms2g -Xmx16g --add-opens=java.base/java.lang=ALL-UNNAMED \\"
echo "    org.mage.magezero.LayaMain $ROOT/configs/run3.yml"
