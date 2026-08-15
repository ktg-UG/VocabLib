# VocabLib

PC作業中に英単語を自動で出題する、macOSメニューバー常駐の反復学習アプリ。
「勉強しようと思い立つ」必要をなくし、意思に依存しない反復で語彙を定着させる。

## 主な機能

- 一定間隔（デフォルト5分）で英単語の4択クイズを自動出題
- 忘却曲線（SM-2アルゴリズム）に基づく復習タイミングの自動調整
- ローカルSQLiteにデータを保存（オフラインでも全機能が動作）
- 学習統計の記録（正答率・連続学習日数・苦手単語・復習予定数）
- Supabase経由でクラウド同期し、Webダッシュボードから統計を閲覧（Phase 5以降）

詳細な仕様は [SPEC.md](SPEC.md)、設計方針は [design-docs/](design-docs/) を参照。

## セットアップ

### 前提

| 項目 | バージョン |
|------|-----------|
| Python | 3.12（`.python-version` で固定） |
| パッケージ管理 | [uv](https://docs.astral.sh/uv/) |
| OS | macOS（メニューバー常駐アプリのため） |

### インストール

```bash
# uvが未導入なら
brew install uv

# 依存関係のインストール（.venv が自動作成される）
uv sync
```

### 環境変数

`.env.example` をコピーして `.env` を作成する。

```bash
cp .env.example .env
```

Phase 1（ローカルDB層）は環境変数なしで動作する。各変数がいつ必要になるかは `.env.example` のコメントを参照。

## 実行方法

### テスト

```bash
uv run pytest -v
```

### アプリ本体

Phase 2（メニューバーUI）で実装予定。

## データの保存先

| 種類 | パス |
|------|------|
| ローカルDB | `~/Library/Application Support/VocabLib/vocablib.db` |

SQLite形式。`sqlite3` コマンドで直接中身を確認できる。

```bash
sqlite3 ~/Library/Application\ Support/VocabLib/vocablib.db ".tables"
```

## ディレクトリ構成

```
VocabLib/
├── SPEC.md              仕様書（確定事項）
├── CLAUDE.md            開発ガイドライン
├── design-docs/         設計書（YYYYMMDD-{機能名}.md）
├── development-logs/    開発ログ（YYYYMMDD-devlogs.md）
├── docs/                外部資料
├── src/
│   ├── db/              SQLiteデータアクセス層
│   └── srs/             忘却曲線アルゴリズム（SM-2）
├── tests/               pytestのテストコード
└── legacy/              v1のコード（Google Sheets版・参照用）
```
