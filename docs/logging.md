# ログとローテーション（運用メモ）

このファイルは VocabLib が利用するローカル Ollama サーバのログ保存場所とローテーション設定をまとめた運用メモです。

## 保存場所
- LaunchAgent plist: `~/Library/LaunchAgents/com.yujikatagi.ollama.plist`
- Ollama 標準出力ファイル: `~/Library/Logs/ollama/ollama.out.log`
- Ollama 標準エラーファイル: `~/Library/Logs/ollama/ollama.err.log`
- ローテート先ディレクトリ: `~/Library/Logs/ollama/`（圧縮済みログは `*.log.gz`）
- ローテーションスクリプト: `~/bin/ollama-log-rotate.sh`
- ローテーション LaunchAgent: `~/Library/LaunchAgents/com.yujikatagi.ollama-logrotate.plist`

## ローテーション方針
- 実行頻度: 日次（デフォルトは毎朝 03:00）
- 保持期間: 圧縮ログを 7 日保持（7 日より古いファイルは自動削除）
- 実行内容: `/tmp` にある元ログをコピーして gz 圧縮し、元ファイルをtruncateして稼働中プロセスが同じファイルディスクリプタへ書き続けられるようにする

## 運用で使うコマンド
- 現在のサービス状態を確認:

```bash
launchctl list | grep com.yujikatagi.ollama
launchctl list | grep com.yujikatagi.ollama-logrotate
```

- ログをリアルタイムで見る:

```bash
tail -f ~/Library/Logs/ollama/ollama.err.log
```

- ローテーションを手動で実行（テスト用）:

```bash
~/bin/ollama-log-rotate.sh
ls -la ~/Library/Logs/ollama
```

- LaunchAgent を再読み込み（plist を編集したとき）:

```bash
launchctl unload ~/Library/LaunchAgents/com.yujikatagi.ollama.plist 2>/dev/null || true
launchctl load -w ~/Library/LaunchAgents/com.yujikatagi.ollama.plist
```

## 注意点
- 現在はログを `~/Library/Logs/ollama` に集約しています。OS の再起動や一時掃除で消える `/tmp` より永続的に保存されます。
- ログが非常に大きくなる運用（1 日あたり数百MB 以上）の場合は、圧縮レベルを下げたり（`gzip -1`）、ローテーション頻度を上げることを検討してください。

## Issue 提出用ログ収集（必要時）
- 問題を upstream に報告する場合は以下を添えてください:
  - `/Users/$(whoami)/Library/Logs/ollama/ollama.err.log`（該当日時の圧縮ログ）
  - `/tmp/ollama-serve.err.log`（もし存在すれば）
  - `ollama --version` の出力
  - `brew info ollama` の出力
  - `system_profiler SPHardwareDataType SPSoftwareDataType` の出力

---
更新: 2026-02-14
