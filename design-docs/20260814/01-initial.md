# 初期設計書 — VocabLib v2

- 作成日: 2026-08-14
- 対象: プロジェクト全体の初期設計（v1のGoogle Sheets構成を廃し、ローカルファースト＋Supabase＋Webへ刷新）
- 前提: `SPEC.md`（要件定義）の確定事項に従う

---

## 0. 設計の背景と方針

### v1の問題（実測・コードレビュー由来）
| 問題 | 原因 | v2での解決 |
|------|------|-----------|
| 1回答あたりAPI呼び出し4回（全列スキャン2回含む） | Sheetsで `(word, meaning)` 文字列照合し行番号を探していた | SQLite + UUID主キー |
| 並行書き込みでデータ破損の恐れ | `googleapiclient` を複数スレッドから同時使用 | 書き込みを単一ワーカーで直列化 |
| 初回不正解の単語で例文が保存されない | 行が未作成のまま `save_example_sentence` が走る順序バグ | 例文は `words` に持ち、単語行は登録時に必ず存在 |
| 統計が再起動で消える | `self.stats` がメモリのみ（`stats.json` は未使用） | `answer_log` に永続化し集計で復元 |
| 生成品質が低い | llama2 | Gemini主 + gemma従 |

### 中核となる設計原則
1. **ローカルファースト** — SQLiteが source of truth。UIはネットワークを一切待たない。
2. **イベントソーシング（簡易版）** — 回答は `answer_log` に追記のみ。`learning_records` は導出値であり再計算可能。
3. **同期は裏方** — 失敗は握りつぶしてキューに残す。オンライン復帰時にまとめて送る。
4. **秘密情報をクライアントに置かない** — LLMキーは Edge Function 側。Webは anon key + RLS。

---

## 1. フォルダ構成

```
VocabLib/
├── SPEC.md                  # 要件定義（確定事項）
├── CLAUDE.md
├── README.md                # ※未作成 → Phase 1で作る
├── design-docs/             # 設計書（本ファイル）
├── development-logs/        # 開発ログ
├── docs/                    # 外部資料
├── legacy/                  # v1コード（参照専用・触らない）
├── src/                     # Mac常駐アプリ（Python）
│   ├── __init__.py
│   ├── main.py              # エントリポイント
│   ├── config.py            # 環境変数
│   ├── app.py               # rumps/PyObjC メニューバーUI
│   ├── db/
│   │   ├── schema.sql       # SQLite DDL
│   │   └── store.py         # データアクセス層（v1 sheets_client の後継）
│   ├── sync/
│   │   └── syncer.py        # Supabase同期ワーカー
│   ├── llm/
│   │   ├── client.py        # Gemini → gemma → ローカル生成 の3段
│   │   └── prompts.py       # プロンプト定義
│   └── srs/
│       └── spaced_repetition.py  # SM-2（v1からほぼ流用可）
├── supabase/
│   └── migrations/          # Postgres DDL
├── web/                     # Next.js（Phase 3）
└── tests/
```

**判断理由**: CLAUDE.md がルート直下 `src/` を必須としているため、Mac常駐アプリを `src/` に置く。Webは `web/` に分離。

---

## 2. データベース設計

### 2.1 テーブル（SQLite / Postgres 共通の論理設計）
`SPEC.md` 5章に準拠。3テーブル：`words` / `learning_records` / `answer_log`

### 2.2 SQLite スキーマ（`src/db/schema.sql`）

```sql
PRAGMA journal_mode = WAL;      -- 読み書き並行性を確保
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
  id                TEXT PRIMARY KEY,          -- UUID（クライアント生成）
  english           TEXT NOT NULL,
  japanese          TEXT NOT NULL,
  part_of_speech    TEXT,
  example_sentence  TEXT,
  created_at        TEXT NOT NULL,             -- ISO8601 UTC
  updated_at        TEXT NOT NULL,
  deleted           INTEGER NOT NULL DEFAULT 0,
  synced_at         TEXT                       -- ★ローカル専用: 最後にpushした時刻
);

CREATE TABLE IF NOT EXISTS learning_records (
  word_id        TEXT PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
  last_reviewed  TEXT,
  next_review    TEXT,
  ease_factor    REAL NOT NULL DEFAULT 2.5,
  interval_days  REAL NOT NULL DEFAULT 0,
  repetitions    INTEGER NOT NULL DEFAULT 0,
  total_correct  INTEGER NOT NULL DEFAULT 0,
  total_seen     INTEGER NOT NULL DEFAULT 0,
  updated_at     TEXT NOT NULL,
  synced_at      TEXT                          -- ★ローカル専用
);

CREATE TABLE IF NOT EXISTS answer_log (
  id           TEXT PRIMARY KEY,               -- UUID
  word_id      TEXT NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  is_correct   INTEGER NOT NULL,
  answered_at  TEXT NOT NULL,
  source       TEXT NOT NULL DEFAULT 'mac',
  synced       INTEGER NOT NULL DEFAULT 0      -- ★0=未送信 / 1=送信済
);

CREATE INDEX IF NOT EXISTS idx_lr_next_review  ON learning_records(next_review);
CREATE INDEX IF NOT EXISTS idx_answer_time     ON answer_log(answered_at);
CREATE INDEX IF NOT EXISTS idx_answer_unsynced ON answer_log(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_words_dirty     ON words(updated_at, synced_at);
```

**★印の3列がローカル専用**（Supabaseには存在しない）。同期状態の管理に使う。
- `synced_at < updated_at` なら「ローカルで変更されたがまだpushしていない」＝dirty
- `answer_log.synced = 0` が送信待ちキューそのもの（**別途キューテーブルを作らない**＝シンプル）

### 2.3 Postgres スキーマ（`supabase/migrations/`）
`SPEC.md` 5.2 の通り。SQLiteとの差分のみ記載：
- `id` は `uuid` 型（SQLiteは TEXT）
- `user_id uuid references auth.users(id)` を全テーブルに付与（認証導入まで NULL 可）
- 時刻は `timestamptz`
- `synced_at` / `synced` 列は**持たない**
- 全テーブル RLS 有効化。ポリシーは Phase 4（認証）で追加

### 2.4 データベースファイルの置き場所
`~/Library/Application Support/VocabLib/vocablib.db`
（v1が `.env` / `token.json` を置いていたのと同じ書き込み可能ディレクトリ。PyInstallerバンドル時も安全）

---

## 3. データアクセス層 `src/db/store.py`

### 3.1 責務
SQLiteへの全アクセスを集約。**UIスレッドから直接呼ばれる（高速なので同期処理でよい）**。

### 3.2 主要API
```python
class Store:
    def __init__(self, db_path: Path)

    # 単語
    def add_word(english, japanese, part_of_speech=None) -> str   # 戻り: word_id
    def list_words(include_deleted=False) -> list[Word]
    def soft_delete_word(word_id) -> None
    def set_example_sentence(word_id, sentence) -> None

    # 出題
    def get_next_word() -> Word | None            # SM-2の優先順位で選択
    def get_distractor_meanings(exclude_word_id, n=3) -> list[str]

    # 回答記録（1トランザクションで2テーブル更新）
    def record_answer(word_id, is_correct) -> None
        # ① answer_log に INSERT（synced=0）
        # ② learning_records を SM-2 で UPDATE
        # ③ 同一トランザクションでコミット

    # 統計
    def get_stats_overall() -> dict                # 総正解/総数/正答率
    def get_stats_daily(days=30) -> list[dict]     # 日別正答率
    def get_streak() -> int                        # 連続学習日数
    def get_weak_words(limit=10) -> list[dict]     # 誤答率上位
    def get_due_counts() -> dict                   # 今日/今週の復習予定数
```

### 3.3 スレッド安全性の方針
- SQLite接続は `check_same_thread=False` + **1本の接続を `threading.Lock` で保護**
- WALモードにより読み取りは並行可能
- v1のような「複数スレッドから同一HTTPクライアント」問題は構造的に発生しない

### 3.4 v1からの移行対応
`legacy/src/app.py` は `sheets_client.get_next_word()` / `record_answer()` / `get_example_sentence()` を呼んでいる。
**`Store` はこれらと同等の責務を持つが、キーを `(word, meaning)` から `word_id` に変えるため、呼び出し側も合わせて書き換える**（v2はゼロから書くので単純移植ではなく再実装）。

---

## 4. 同期設計 `src/sync/syncer.py`

### 4.1 起動タイミング
- アプリ起動時に1回
- 以降 **5分間隔**（出題タイマーとは独立したバックグラウンドスレッド）
- 回答直後にも軽くトリガ（任意・遅延実行）

### 4.2 Push（ローカル → Supabase）
```
1. words:            updated_at > synced_at の行を upsert → 成功したら synced_at = now
2. learning_records: 同上
3. answer_log:       synced = 0 の行を一括 insert → 成功したら synced = 1
```
- `answer_log` は追記のみ・IDがUUIDなので**再送しても重複しない**（upsertで冪等）
- 通信失敗時: 何もせずreturn（フラグを更新しないので次回自動リトライ）

### 4.3 Pull（Supabase → ローカル）
```
1. words を取得（updated_at がローカルより新しい行のみ）
2. LWW: remote.updated_at > local.updated_at なら上書き
3. deleted=true の行はローカルも論理削除
```
- `answer_log` は基本Pullしない（Tier2でWeb回答を導入したら追加）
- `learning_records` も当面Mac側が唯一の更新者なのでPull不要（Tier2で必要になる）

### 4.4 衝突解決
| テーブル | 方式 | 理由 |
|---------|------|------|
| words | LWW（updated_at） | 単一ユーザーで同時編集は稀 |
| learning_records | Mac側が唯一の書き手（当面） | 衝突しない |
| answer_log | 衝突しない | 追記専用・不変・UUID |

### 4.5 認証
Macアプリは `SUPABASE_SERVICE_ROLE_KEY` を使用（RLSバイパス）。`.env` に置き `.gitignore` で除外。

---

## 5. LLM層 `src/llm/client.py`

### 5.1 3段フォールバック
```
generate_quiz_distractors(word, meaning) / generate_example(word, meaning)
   ↓ ①Gemini API（主）           失敗・タイムアウト・オフライン
   ↓ ②ローカル gemma 2B（従）     失敗
   ↓ ③ローカル生成（保険）        必ず成功
```
- ③の中身: distractorは他単語の意味から補充 / 例文は `"word" means "meaning"`
- **③が必ず成功するので、この関数は例外を投げない**（呼び出し側が単純になる）

### 5.2 呼び出し方
- **必ずバックグラウンドスレッド**で実行し、`PyObjCTools.AppHelper.callAfter` でUI更新（v1の方式を踏襲。これは良かった点）
- タイムアウト: Gemini 10秒 / gemma 20秒

### 5.3 v1から引き継ぐ良い実装
`legacy/src/ollama_client.py` の以下は再利用価値が高い（テストも書く）：
- `_extract_example_line()` — LLM出力から「英語 — 和訳」を抽出・正規化
- `_sentence_uses_word()` — 生成文が対象単語を含むか検証（活用形許容）
- 生成失敗時の最大3回リトライ

### 5.4 APIキーの扱い
- Macアプリ: `.env` の `GEMINI_API_KEY` を直接使用（ローカル実行なので可）
- Web: **Edge Function経由**でキーを秘匿（ブラウザに出さない）

---

## 6. Macアプリ UI `src/app.py`

v1の構造を踏襲（`rumps.App` + `NSPanel`）。**v1で良かった点はそのまま残す**：
- `LSUIElement=true` でDock非表示
- 右下フローティングパネル（非ブロッキング）
- 正解時1秒で自動クローズ

### v1から変更する点
| 項目 | v1 | v2 |
|------|----|----|
| 統計表示 | メモリのみ（再起動で消失） | `Store.get_stats_overall()` から復元 |
| 不正解パネルの閉じ方 | フォーカスが外れたら即閉じる（例文を読めない） | **「閉じる」ボタンのみ**で閉じる |
| 保存タイミング | パネルを閉じた後にSheetsへ | 回答した瞬間にSQLiteへ（即時・確実） |
| メニュー | 今すぐクイズ / 自動クイズ / 再読み込み / 統計 | ＋「単語を追加」「今すぐ同期」 |

---

## 7. Webアプリ `web/`（Phase 3）

- Next.js（App Router）+ TypeScript
- Supabase JS クライアント（anon key）+ Googleログイン
- 画面: **ダッシュボード1枚**（`SPEC.md` 11.1 の4指標）＋ 単語追加フォーム
- チャート: 正答率推移（折れ線）/ streak（ヒートマップ）/ 苦手単語（横棒）/ 復習予定（数値タイル）
- デプロイ: Vercel

---

## 8. 実装順序（フェーズ計画）

| Phase | 内容 | 完了条件（DoD） |
|-------|------|----------------|
| **1** | プロジェクト初期化（uv init / README / .gitignore）＋ SQLite層（schema.sql / store.py） | 単語を追加し、`get_next_word` と `record_answer` が動くことをテストで確認 |
| **2** | SM-2移植 ＋ Macアプリ UI（オフライン完結で動く） | 実際にクイズが自動出題され、正誤がSQLiteに残り、再起動しても統計が消えないことを確認 |
| **3** | LLM層（Gemini→gemma→ローカル） | 4択と例文が生成され、Geminiを止めてもフォールバックで動くことを確認 |
| **4** | Supabaseスキーマ ＋ 同期ワーカー | 機内モードで回答→オンライン復帰→Supabaseに反映されることを確認 |
| **5** | Webダッシュボード（Vercel） | スマホのブラウザで統計4指標が表示されることを確認 |
| **6** | 認証（Googleログイン）＋ RLSポリシー | 未ログインではデータが見えないことを確認 |

**Phase 2 終了時点で「オフラインで完全に動く単語アプリ」が完成する**。Supabase/Webはその上に載せる増築とする。

---

## 9. この設計で解決される v1 の課題（対応表）

| v1の課題 | 解決するPhase | 手段 |
|---------|--------------|------|
| Sheets API 4回/回答・全列スキャン | Phase 1 | SQLite + UUID主キー + インデックス |
| スレッド安全性 | Phase 1 | 単一接続 + Lock + WAL |
| 例文が初回不正解時に保存されない | Phase 1 | 例文を `words` に持ち、単語行は常に存在 |
| 統計が再起動で消える | Phase 2 | `answer_log` に永続化 |
| 例文を読む前にパネルが閉じる | Phase 2 | 「閉じる」ボタンのみで閉じる |
| llama2の生成品質 | Phase 3 | Gemini主 + gemma従 |
| オフラインで使えない（Sheets必須） | Phase 4 | ローカルファースト設計 |

---

## 10. 未決定・実装時に判断する事項
- SM-2の `quality` 値（v1は正解=4固定でEFが伸びない問題があった）→ Phase 2で見直す
- gemma 2B の実際の生成品質 → Phase 3で実測し、不足なら7Bへ
- 同期間隔5分の妥当性 → Phase 4で調整
