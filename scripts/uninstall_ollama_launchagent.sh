#!/usr/bin/env bash
set -euo pipefail

LABEL=com.yujikatagi.ollama.serve
PLIST=~/Library/LaunchAgents/${LABEL}.plist

if [ -f "$PLIST" ]; then
  echo "Unloading $PLIST..."
  launchctl unload "$PLIST" || true
  rm -f "$PLIST"
  echo "Removed $PLIST"
else
  echo "No plist found at $PLIST"
fi

echo "Logs (if any): /tmp/ollama-serve.out.log /tmp/ollama-serve.err.log"
