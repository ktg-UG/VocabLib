#!/usr/bin/env bash
set -euo pipefail

# Installs a user LaunchAgent to run `ollama serve` with nice(10).
# Replaces /path/to/ollama with the discovered `which ollama`.

LABEL=com.yujikatagi.ollama.serve
PLIST=~/Library/LaunchAgents/${LABEL}.plist

OLLAMA_PATH=$(command -v ollama || true)
if [ -z "$OLLAMA_PATH" ]; then
  echo "ollama が見つかりません。先に 'ollama' をインストールしてください。"
  exit 1
fi

cat > /tmp/${LABEL}.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/nice</string>
    <string>-n</string>
    <string>10</string>
    <string>${OLLAMA_PATH}</string>
    <string>serve</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/ollama-serve.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/ollama-serve.err.log</string>
</dict>
</plist>
EOF

mkdir -p "$(dirname "$PLIST")"
mv /tmp/${LABEL}.plist "$PLIST"
echo "Wrote $PLIST"

echo "Loading LaunchAgent..."
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "LaunchAgent loaded. Logs: /tmp/ollama-serve.out.log /tmp/ollama-serve.err.log"

echo "To stop: launchctl unload $PLIST"
