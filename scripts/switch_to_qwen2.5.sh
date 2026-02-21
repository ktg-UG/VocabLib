#!/usr/bin/env bash
set -euo pipefail

# Switch Ollama server to use qwen2.5:1.5b by pulling it and removing qwen3:1.7b
# This may download multiple GBs. Run only if you consent.

OLLAMA_BIN=$(command -v ollama || true)
if [ -z "$OLLAMA_BIN" ]; then
  echo "ollama が見つかりません。先に ollama をインストールしてください。"
  exit 1
fi

echo "Pulling qwen2.5:1.5b (this may take a long time and use a lot of disk)..."
$OLLAMA_BIN pull qwen2.5:1.5b

echo "Attempting to remove qwen3:1.7b (if present)..."
# Try common remove commands; ignore failures
$OLLAMA_BIN rm qwen3:1.7b 2>/dev/null || $OLLAMA_BIN remove qwen3:1.7b 2>/dev/null || true

echo "Done."
