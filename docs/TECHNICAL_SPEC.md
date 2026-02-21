# VocabLib — 技術仕様（全まとめ）

更新: 2026-02-14

---

## 目的
VocabLib は macOS 向けの軽量常駐アプリで、ローカル Ollama サーバを使って4択クイズを生成・事前生成（pregen）し、メニューバー経由で短時間表示します。低レイテンシ運用のためにサーバ常駐 + バックグラウンドプリジェネを採用しています。

---

## リポジトリ構成（主要）

- `README.md` — プロジェクト説明
- `pyproject.toml` — 依存管理 / パッケージ設定
- `main.py` — エントリ（ビルド時使用）
- `docs/logging.md` — ログ運用メモ（自動作成済み）
- `docs/TECHNICAL_SPEC.md` — このファイル

- `src/`
  - `app.py` — メニューバーアプリ本体（`rumps` + AppKit、UI、pregen ワーカー、単一インスタンスロジック）
  - `ollama_client.py` — Ollama HTTP ラッパ（接続チェック、`batch_generate_quizzes`、レスポンス解析）
  - `config.py` — 設定（プリジェネ間隔・バッチサイズ等）
  - `sheets_client.py` — （必要に応じた外部保存）

- `scripts/`
  - `test_ollama_connection.py` — 到達性・generate テスト
  - `switch_to_qwen2.5.sh` — モデル pull/rm 自動化スクリプト

- ビルド: `VocabLib.spec`（PyInstaller 用 spec）
- 出力: `dist/VocabLib.app` → `/Applications` に配置して使用可能

---

## 主要コンポーネントの動作

### UI / 常駐
- `rumps` を使いメニューバーに常駐。右下に短時間（1s）で閉じる通知風パネルを表示するために AppKit の `NSPanel` を部分利用。
- パネルはカウントダウン表示付きで、ユーザーに選択肢を提示して結果を強調表示するUX。
- 起動時にファイルロックや PID チェックで二重起動を防止。

### Ollama 統合
- ローカル `ollama serve` を HTTP API として利用（デフォルトポート 11434）。
- `ollama_client.py` は以下を提供:
  - `check_connection()` — `/api/tags` などのエンドポイントチェック
  - `generate_quiz_with_ollama(prompt)` — 単発生成
  - `batch_generate_quizzes(n)` — 並列化・リトライを含むバッチ生成（pregen 用）
- 事前生成（pregen）ロジック: `app.py` 内の `quiz_cache`（deque）をバックグラウンドの `_pregen_worker` が定期的に補充。
- 設定は `src/config.py` 内の `OLLAMA_PREGEN_INTERVAL_SECONDS`, `OLLAMA_MODEL_BATCH_SIZE`, `OLLAMA_CACHE_MAX` 等で調整可能。

### 永続化 / 自動起動
- `LaunchAgent` を使い `ollama serve` をユーザ領域で永続化:
  - `~/Library/LaunchAgents/com.yujikatagi.ollama.plist` を作成（`KeepAlive`・`RunAtLoad`）。
  - `EnvironmentVariables` に `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` を設定済み（変更可）。
- GUI アプリ版 `Ollama.app` が同時に起動しているとポート競合するため、どちらを運用するかを決めて片方を停止する必要あり。
- `VocabLib.app` 本体は PyInstaller で生成。`VocabLib.spec` にて `LSUIElement`（Dock非表示）などを設定。

---

## ログ設計とローテーション

- 出力先（現在）:
  - `~/Library/Logs/ollama/ollama.out.log`
  - `~/Library/Logs/ollama/ollama.err.log`
- ローテーションスクリプト: `~/bin/ollama-log-rotate.sh`（日次 03:00 実行）
  - 動作: 元ファイルをコピー→`gzip` で圧縮→元ファイルを truncate（継続書き込み対応）→7日より古い圧縮ログを削除
- LaunchAgent でも `StandardOutPath` / `StandardErrorPath` を対象ログに向けているため、ログは永続的に保管される。

---

## 運用コマンド（短い参照）

- サービスの再読み込み（plist 編集後）:

```bash
launchctl unload ~/Library/LaunchAgents/com.yujikatagi.ollama.plist 2>/dev/null || true
launchctl load -w ~/Library/LaunchAgents/com.yujikatagi.ollama.plist
```

- ログ確認:

```bash
tail -f ~/Library/Logs/ollama/ollama.err.log
```

- ポートの占有確認:

```bash
lsof -iTCP:11434 -sTCP:LISTEN -n -P
```

- GUI を終了（Ollama.app を止めたい場合）:

```bash
osascript -e 'tell application "Ollama" to quit'
```

- 接続テスト:

```bash
uv run ./scripts/test_ollama_connection.py
```

---

## トラブルシューティング

### Metal ランナー初期化エラー
- 症状: `/api/generate` が 500、エラーログに `failed to initialize the Metal library` / static_assert 系の出力
- 対策順序:
  1. `brew update && brew upgrade ollama`
  2. それでもダメなら `brew reinstall --build-from-source ollama`（時間がかかる）
  3. 一時対応: LaunchAgent に `OLLAMA_LLM_LIBRARY=cpu` と `OLLAMA_NO_GPU=1` を追加して CPU フォールバックで運用
  4. upstream へ issue 提出（ログ添付）
- 収集するログ: `~/Library/Logs/ollama/ollama.err.log`、`ollama --version`、`brew info ollama`、`system_profiler` 出力

### ポート競合
- `lsof -iTCP:11434` で占有プロセスを特定。GUI が起動している場合は OS アプリ `Ollama.app` の親プロセスが占有している事が多い。

---

## セキュリティ / シークレット

- トークン等の秘密情報はバンドルに含めない。`token.json` や設定はユーザー領域 `~/Library/Application Support/VocabLib/` に置く設計。
- LaunchAgent はユーザ領域で動かすため root 権限は不要。

---

## パッケージングと配布

- PyInstaller を使って `.app` を生成。`VocabLib.spec` にて必要なバンドル設定を行う。
- デフォルトは ad-hoc 署名。配布する場合は正式な Developer ID で署名および notarize を推奨。
- 自動起動を組み合わせた配布手順:
  1. `/Applications/VocabLib.app` を配置
  2. ユーザーに `~/Library/LaunchAgents/com.yujikatagi.ollama.plist` を設置（またはインストーラで設定）

---

## 今後の改善案（優先度付き）

1. Issue 自動収集コマンド（`scripts/collect_ollama_issue.sh`）を追加して、必要ログと環境情報をワンコマンドでアーカイブ化。  
2. CI でのビルド・署名自動化（GitHub Actions 等）。  
3. メニューバーからプリジェネ状況（キャッシュ数・失敗率）を確認できる UI の追加。  
4. 簡易監視（エラー頻度閾値で通知）を追加。

---

## 付録: 重要ファイル一覧（パス）

- `src/app.py` — アプリ本体
- `src/ollama_client.py` — Ollama HTTP クライアント
- `src/config.py` — 設定
- `VocabLib.spec` — PyInstaller spec
- `scripts/test_ollama_connection.py` — 接続テスト
- `scripts/switch_to_qwen2.5.sh` — モデル切替スクリプト
- `~/Library/LaunchAgents/com.yujikatagi.ollama.plist` — Ollama 永続化エージェント
- `~/Library/LaunchAgents/com.yujikatagi.ollama-logrotate.plist` — ローテートエージェント
- `~/bin/ollama-log-rotate.sh` — ローテートスクリプト
- `~/Library/Logs/ollama/` — ログ保存先
- `docs/logging.md`, `docs/TECHNICAL_SPEC.md` — 運用ドキュメント

---

必要ならこの `docs/TECHNICAL_SPEC.md` を README に要約追加したり、リリースノート用の別ファイルを生成します。どれを先にやりますか？
