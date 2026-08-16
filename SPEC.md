# VocabLib 仕様書（要件定義）

## 更新履歴

| 日付       | 更新内容                         | 担当 |
| ---------- | -------------------------------- | ---- |
| 2026-08-16 | Phase 8（タグ機能）完了を反映。F-13「タグ」を追加し 12.11 を新設（1語1タグ・`#` 記法・`words.tag` 列・`_migrate()` によるマイグレーション方針）。5.1/5.2 に `tag` 列、12.6 に `tag` の同期を追記。**Macの「単語一覧...」を削除**（SPEC 1.4 の役割分担に従い、一覧はWebに一本化）。12.1 に `src/tags.py` を追記 | UG   |
| 2026-08-16 | Phase 7 完了を反映。F-12「単語の一括インポート」を追加し、12.10を追加（カンマ区切りで和訳・品詞を直接指定できる書式、4択の誤答を同じ品詞から選ぶ仕様、v1の25語の移行方針）。品詞の正式な一覧を `db.store.PARTS_OF_SPEECH` に集約。9の当てずっぽう対策に品詞フィルタ導入を反映。12.5にGeminiの無料枠実測値（20req/日・5req/分）と有料化（前払い2000円）を追記 | UG   |
| 2026-08-15 | 設計原則「1.4 Macアプリ と Webアプリ の役割分担」を追加（Macは登録・出題・統計数値のみ、複雑なUIはWeb）。これに伴い1.3の「Webからの単語編集は対象外」を撤回し、Webを書き込み可能とする方針に変更 | UG   |
| 2026-08-15 | Phase 6（認証・デプロイ）完了を反映。F-08を「実装済（公開中）」、F-10を「実装済」に変更。本番URL `https://vocablib.vercel.app` を公開。Web側を `service_role` から `anon`＋Googleログインに切替え、RLSポリシー（select のみ）を追加。Mac側に `SUPABASE_USER_ID` を追加。12.8「認証とデプロイ」を追加 | UG   |
| 2026-08-15 | Phase 5（Webダッシュボード）完了を反映。F-08を「実装済（ローカルのみ・未デプロイ）」に変更。`web/`（Next.js 16 / TypeScript / Tailwind v4 / Recharts / Vitest）を追加。12.7「Webダッシュボード」を追加。UI作り込みはPhase 7に分離 | UG   |
| 2026-08-15 | Phase 4（Supabase同期）完了を反映。F-06を「実装済」に変更。Supabase側DDLを `src/db/supabase_schema.sql` として追加しRLSを有効化。環境変数に `SUPABASE_URL` `SUPABASE_SERVICE_ROLE_KEY` `SYNC_INTERVAL_MINUTES` を追加。12.7「同期仕様」を追加 | UG   |
| 2026-08-15 | Phase 3（LLM連携）完了を反映。F-03/F-09を「実装済」、F-04を「LLM補強は保留（登録30語到達後に再判断）」に変更。Geminiモデルを `gemini-3.7-flash` に、ローカルLLMを `gemma3:4b` に確定。環境変数に `GEMINI_MODEL` `LLM_TIMEOUT_SECONDS` `AUTOFILL_TIMEOUT_SECONDS` `LOG_LEVEL` を追加。12.5「LLMフォールバック仕様」を追加。単語追加をフォーム1枚に刷新 | UG   |
| 2026-08-15 | Phase 1・2 の実装完了を反映（F-01/F-02/F-04/F-05/F-07を「実装済」、F-09を「一部実装」に変更）。環境変数に `CHOICE_COUNT` `VOCABLIB_DB_PATH` を追加。8.1にMac起動方法（`uv run python -m src.main`）とDB保存先を追記。12節「実装済みの構成」を追加 | UG   |
| 2026-08-14 | 設計判断5件とWeb表示指標4種を確定し「11. 確定した設計判断」を追加（出題間隔5分 / Googleログイン / 例文は不正解時生成 / gemma 2B / 意味は主要1件） | UG   |
| 2026-08-14 | 1.1 目的から学習・ポートフォリオ目的の記述を削除しプロダクト要件に限定 | UG   |
| 2026-08-14 | 初版作成（v2刷新方針の要件定義） | UG   |

---

## 1. 概要

### 1.1 目的（なぜ作るか）

PC作業中に英単語を強制的・自動的に出題し、意思に依存しない反復学習で語彙を定着させる。

### 1.2 解決する課題

- 既存のスマホ単語アプリは「アプリを開く手間」「SNSの誘惑」で継続しない。
- 一日で最も長く触れているPC作業中の時間を使い、ユーザーの意思に依存しない反復を実現する。
- （v1の課題）Google Sheets運用が遅く・重い／統計が再起動で消える／Ollama(llama2)の生成品質が低い。

### 1.3 スコープ

- やること:
  - Mac常駐アプリ（自動出題・SM-2スケジューリング・不正解時AI例文）＝v1機能を継承
  - ローカルファースト化（SQLiteを正）＋ Supabase への非ブロッキング同期
  - Webダッシュボード（統計可視化）＝ **Tier1・優先**
  - 単語追加フォーム（英単語入力 → 和訳・品詞をLLMでauto-fill）
  - LLM刷新（Gemini主 ＋ ローカルgemma従 ＋ ローカル生成の最終フォールバック）
- やらないこと（現時点で明示的に対象外）:
  - スマホ/Webでのテスト受験（Tier2）は後回し
  - ~~Webからの単語編集~~ → **1.4 の役割分担により対象に変更（2026-08-15）**
  - AWSの利用（Vercel＋Supabaseで完結）
  - 発音記号（pronunciation）フィールド
  - Google Sheets連携（v2で廃止）

### 1.4 Macアプリ と Webアプリ の役割分担（設計原則）

**Macアプリは「簡単な操作」だけを担い、複雑なUIが要るものはすべてWebに置く。**

| | Macアプリ（メニューバー常駐） | Webアプリ |
| --- | --- | --- |
| 位置づけ | 作業中に割り込む道具。操作は最小限 | じっくり見る・触る場所 |
| 担当 | 単語の登録 / 出題・回答 / 統計の**数値**確認 | グラフ・可視化 / データの一覧・検索 / 編集・削除 |

理由:

- メニューバーアプリは画面が狭く、`rumps` と `NSPanel` で作り込むコストが高い。
  同じものをWebで作る方が速く、スマホからも使える
- 作業を中断させる側（Mac）に複雑な操作を置くと、集中を奪う時間が長くなる
- 一覧・検索・編集はデータ量が増えるほどUIが必要になり、メニューバーでは破綻する

この原則により、以下が決まる。

- Macアプリに一覧・検索・編集・削除のUIを作らない
  （Phase 8 で「単語一覧...」を削除し、原則どおりに揃えた。
  **Webに一覧ができるまで、登録済みの単語を画面で確認する手段は無い**）
- **Webは読み取り専用ではない。** 編集・削除を担うため書き込み権限を持つ
  （1.3 の「Webからの単語編集は対象外」は本原則により撤回。RLSに更新ポリシーが必要）
- 迷ったときの判断基準は「**それは作業中に3秒で終わる操作か？**」
  Yesならmac、Noならweb

---

## 2. 関係者

| 役割             | 氏名 / 会社      | 連絡先 |
| ---------------- | ---------------- | ------ |
| ユーザー（唯一） | UG（開発者本人） | -      |
| 開発担当         | UG               | -      |

※ 単一ユーザー前提。ただしWebは公開URLになるため認証で本人のみに限定する。

---

## 3. 環境・技術スタック

| 区分                      | 内容                                                          |
| ------------------------- | ------------------------------------------------------------- |
| Mac常駐アプリ             | Python 3.12 / rumps / PyObjC（NSPanel 等）                    |
| ローカルDB                | SQLite（source of truth・オフライン動作）                     |
| クラウドDB / バックエンド | Supabase（PostgreSQL / Auth / Edge Functions / 自動REST API） |
| Webフロント               | Next.js 16（App Router）/ TypeScript / Tailwind CSS v4 / Recharts / Vitest |
| Webホスティング           | Vercel                                                        |
| LLM（主）                 | Google Gemini（`gemini-3.7-flash`、従量課金）                 |
| LLM（従）                 | ローカルLLM（Ollama / gemma3:4b）                             |
| LLM（最終保険）           | ローカル生成（`"word" means "meaning"`）                    |
| パッケージ管理            | uv（Python） / npm or pnpm（Web）                             |
| 配布                      | PyInstaller（.app、`LSUIElement=true`）                     |
| リージョン                | Supabase: Tokyo（ap-northeast-1）                             |

---

## 4. 機能仕様

### 4.1 機能一覧

| ID   | 機能名                        | 概要                                              | ステータス       |
| ---- | ----------------------------- | ------------------------------------------------- | ---------------- |
| F-01 | 自動出題（Mac）               | 設定間隔で4択クイズをメニューバーから自動表示     | **実装済**（Phase 2） |
| F-02 | SM-2スケジューリング          | 正誤で次回出題日時を自動調整                      | **実装済**（Phase 1） |
| F-03 | AI例文生成（不正解時）        | 不正解時に記憶に残る例文を生成・キャッシュ        | **実装済**（Phase 3） |
| F-04 | 4択クイズ生成                 | 誤答選択肢の生成（登録済み和訳から抽出）          | **実装済**（Phase 2）。LLM補強は**保留**（登録30語到達後に再判断。12.9参照） |
| F-05 | ローカルSQLite永続化          | 単語・学習状態・回答履歴をローカル保存            | **実装済**（Phase 1） |
| F-06 | Supabase同期                  | SQLite ↔ Supabase の同期（オフライン耐性）       | **実装済**（Phase 4）。12.6参照 |
| F-07 | 統計の永続化・集計            | answer_log から正答率・継続日数などを集計         | **実装済**（Phase 1）。Mac側の表示はPhase 2で実装 |
| F-08 | Webダッシュボード             | スマホ/PCで統計を可視化（Tier1）                  | **実装済・公開中**（Phase 5・6）。https://vocablib.vercel.app 。12.7参照 |
| F-09 | 単語追加フォーム（auto-fill） | 英単語入力→和訳・品詞をLLM自動入力・編集して保存 | **実装済**（Phase 3）。Mac側のみ。Web側はPhase 5 |
| F-10 | 認証（Googleログイン）        | Webの本人限定アクセス／RLS                        | **実装済**（Phase 6）。12.8参照 |
| F-11 | Webでテスト受験               | スマホから出題・回答（Tier2）                     | 対象外（将来）   |
| F-12 | 単語の一括インポート          | テキストファイルから複数語をまとめて登録          | **実装済**（Phase 7）。12.10参照 |
| F-13 | タグ                          | 単語を1つのタグで分類し、出題を絞り込む          | **実装済**（Phase 8）。12.11参照 |

### 4.2 各機能の詳細（主要のみ）

#### F-01 自動出題（Mac）

- 入力: タイマーtick（デフォルト5分間隔、`QUIZ_INTERVAL_MINUTES`）
- 処理: SM-2で次単語を決定 → LLMで4択生成 → 右下にNSPanel表示（非ブロッキング）
- 出力: 4択クイズパネル
- 例外時: 単語0件ならアラート。LLM失敗時はローカル生成にフォールバック

#### F-06 Supabase同期

- 入力: ローカルの未同期変更 / リモートの更新
- 処理: Push（3テーブル）→ Pull（3テーブル）の順。衝突は `updated_at` のLWW
- 出力: 両DBの整合
- 例外時: 通信失敗は握りつぶし、未送信フラグを残して次回再送（UIは待たせない）
- 詳細は12.6

#### F-09 単語追加フォーム（auto-fill）

- 入力: 英単語（ユーザー入力）
- 処理: Edge Function経由でLLM呼び出し → `{japanese, part_of_speech}` をJSONで取得
- 出力: フォームに反映（**編集可能な下書き**）→ 確認して保存
- 例外時: LLM失敗時は空欄で手入力可能

---

## 5. データ仕様

### 5.1 データ構造（3テーブル）

```
words            単語帳（参照データ）
learning_records SM-2の現在状態（1単語1行・上書き）
answer_log       回答イベント履歴（追記のみ・不変）→ 統計の元データ
```

- ID戦略: UUID（クライアント生成 → オフラインでも採番不要）
- 同期列: `updated_at`（LWW衝突解決）／`deleted`（論理削除の墓標）
- 設計思想: `learning_records` は `answer_log` から再計算可能（イベントソーシング簡易版）

### 5.2 主要項目

#### words

| 項目                    | 型          | 必須 | 説明                                  |
| ----------------------- | ----------- | ---- | ------------------------------------- |
| id                      | uuid        | ○   | PK・クライアント生成                  |
| user_id                 | uuid        |      | 所有者（RLS用、認証導入まではNULL可） |
| english                 | text        | ○   | 英単語                                |
| japanese                | text        | ○   | 和訳                                  |
| part_of_speech          | text        |      | 品詞（auto-fill）                     |
| tag                     | text        | ○   | タグ（1語1タグ・`''` はタグなし）    |
| example_sentence        | text        |      | AI例文キャッシュ                      |
| created_at / updated_at | timestamptz | ○   | 作成・更新時刻                        |
| deleted                 | boolean     | ○   | 論理削除                              |

#### learning_records

| 項目                        | 型          | 必須 | 説明           |
| --------------------------- | ----------- | ---- | -------------- |
| word_id                     | uuid        | ○   | PK・FK→words  |
| user_id                     | uuid        |      | 所有者         |
| last_reviewed / next_review | timestamptz |      | 最終・次回出題 |
| ease_factor                 | real        | ○   | EF（初期2.5）  |
| interval_days               | real        | ○   | 復習間隔       |
| repetitions                 | int         | ○   | 連続正解回数   |
| total_correct / total_seen  | int         | ○   | 正解数・出題数 |
| updated_at                  | timestamptz | ○   | 同期用         |

#### answer_log

| 項目        | 型          | 必須 | 説明              |
| ----------- | ----------- | ---- | ----------------- |
| id          | uuid        | ○   | PK                |
| user_id     | uuid        |      | 所有者            |
| word_id     | uuid        | ○   | FK→words         |
| is_correct  | boolean     | ○   | 正誤              |
| answered_at | timestamptz | ○   | 回答時刻          |
| source      | text        |      | `mac` / `web` |

---

## 6. 外部連携

| 連携先                        | 用途                             | 認証方式                                      |
| ----------------------------- | -------------------------------- | --------------------------------------------- |
| Supabase                      | DB・認証・API・Edge Functions    | anon key（Web＋RLS）/ service_role key（Mac） |
| Google Gemini API             | 4択生成・例文生成・単語auto-fill | APIキー（Edge Function側に秘匿）              |
| ローカルLLM（Ollama gemma等） | オフライン時のフォールバック生成 | ローカルHTTP（localhost:11434）               |

---

## 7. 環境変数・設定値（予定）

| 変数名                    | 用途                           | 置き場所                    |
| ------------------------- | ------------------------------ | --------------------------- |
| SUPABASE_URL              | プロジェクトURL                | Mac / Web                   |
| SUPABASE_SERVICE_ROLE_KEY | Mac常駐アプリ用（RLSバイパス） | Mac`.env` のみ（Git除外） |
| SUPABASE_ANON_KEY         | Web用（RLS前提）               | Web環境変数                 |
| GEMINI_API_KEY            | LLM呼び出し                    | Edge Function（秘匿）       |
| QUIZ_INTERVAL_MINUTES     | 出題間隔（既定5）              | Mac`.env`                 |
| AUTO_START_QUIZ           | 起動時自動開始（既定true）     | Mac`.env`                 |
| CHOICE_COUNT              | 選択肢の数（既定4）            | Mac`.env`                 |
| VOCABLIB_DB_PATH          | ローカルDBの位置を上書き（開発用） | Mac`.env` / 環境変数    |
| GEMINI_MODEL              | 使用モデル（既定 `gemini-3.7-flash`） | Mac`.env`            |
| OLLAMA_HOST / OLLAMA_MODEL | ローカルLLM（既定 `gemma3:4b`） | Mac`.env`                |
| LLM_TIMEOUT_SECONDS       | 例文生成の待ち上限（既定20）   | Mac`.env`                 |
| AUTOFILL_TIMEOUT_SECONDS  | オートフィルの待ち上限（既定10。Geminiの下限が10秒のためこれ未満不可） | Mac`.env` |
| LOG_LEVEL                 | ログ詳細度（既定INFO。DEBUGでフォールバック理由まで出る） | Mac`.env` |
| SYNC_INTERVAL_MINUTES     | 自動同期の間隔（既定10）       | Mac`.env`                 |
| SUPABASE_USER_ID          | 送信行に付ける所有者UUID（RLS判定用） | Mac`.env`           |

`SUPABASE_URL` と `SUPABASE_SERVICE_ROLE_KEY` のどちらかが未設定なら同期は丸ごと無効になり、
アプリはローカル完結で動作する（メニューに「同期: 未設定」と表示）。

### 7.1 Web側（`web/.env.local` / Vercel Environment Variables）

| 変数名 | 用途 |
| ------ | ---- |
| NEXT_PUBLIC_SUPABASE_URL | プロジェクトURL |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | `anon` キー |

テンプレートは `web/.env.example`。ローカルと Vercel の両方に同じ値を設定する。

**`service_role` キーはWeb側では一切使わない**（Phase 6 で撤去）。
Vercel の環境変数にも登録しない。

`NEXT_PUBLIC_` が付いているのは設計どおり。`anon` キーは「匿名ユーザーという名札」で、
実際に何が見えるかはRLSポリシーが決めるためブラウザに出て良い。
ログインボタンがブラウザ側で Supabase Auth を呼ぶため、この2つは公開が必須。

テンプレートは `.env.example`。`cp .env.example .env` して使う。`.env` はGit除外。

---

## 8. 運用

### 8.1 起動・実行方法

- Mac常駐アプリ（現行）: `uv run python -m src.main`
  - `.app` 化（PyInstaller）は未着手。ログイン項目への登録もこれに含めて後日決定する。
- テスト: `uv run pytest`（Python） / `cd web && npm test`（TypeScript）
- Web: **https://vocablib.vercel.app**
  - `main` ブランチへの push で Vercel が自動デプロイする
  - Vercel の Root Directory は `web`
  - **push前に `cd web && npm run build` を通すこと。** `npm run dev` では
    型チェックが緩く、本番ビルドで初めて落ちることがある

### 8.1.1 データ保存先

| 種類 | パス |
| ---- | ---- |
| ローカルDB | `~/Library/Application Support/VocabLib/vocablib.db` |

`VOCABLIB_DB_PATH` を設定するとこの位置を上書きできる（開発時に本番DBを汚さないため）。

### 8.2 定期実行

- 自動出題タイマー（`QUIZ_INTERVAL_MINUTES` ごと）

---

## 9. 制約・既知の問題

- 単一ユーザー前提（マルチデバイス同期は対応するが多人数運用は想定外）。
- 4択・意味選択のため勘で正解し得る → SM-2が「覚えた」と誤判定する余地。
  Phase 7 で**誤答を同じ品詞から選ぶ**ようにして消去法を潰した（12.10）。
  出題方向の切替（和訳→英単語）や入力式の要否は引き続きTBD。
- 生成品質はLLMモデルに依存。
- ローカルファースト同期の衝突解決はLWW（追記ログ以外）。同一行を複数端末でほぼ同時編集した場合は後勝ち。

---

## 10. 用語集

| 用語               | 説明                                                               |
| ------------------ | ------------------------------------------------------------------ |
| SM-2               | SuperMemo 2。忘却曲線に基づく復習間隔アルゴリズム                  |
| EF（ease_factor）  | 単語ごとの覚えやすさ係数（下限1.3）                                |
| ローカルファースト | ローカルDBを正とし、クラウドは後から同期する設計                   |
| イベントソーシング | 状態でなくイベント（回答履歴）を貯め、状態はそこから導出する考え方 |
| RLS                | Row Level Security。DB側で行単位のアクセス制御を強制する仕組み     |
| LWW                | Last-Write-Wins。更新時刻の新しい方を採用する衝突解決              |

---

## 11. 確定した設計判断（2026-08-14）

| 項目 | 決定 | 補足 |
|------|------|------|
| 出題間隔デフォルト | **5分** | `QUIZ_INTERVAL_MINUTES` で変更可 |
| 認証方式 | **Googleログイン**（Supabase Auth） | Webのみ。Macは service_role で認証不要 |
| 例文の生成タイミング | **不正解時に生成しキャッシュ** | 登録時auto-fillは和訳・品詞のみ。例文は間違えた単語だけに付与 |
| ローカルLLMフォールバック | **gemma3:4b**（2026-08-15変更。当初は gemma2:2b） | Gemma 2は英語中心、Gemma 3から多言語対応。和訳付き例文を生成する用途のため3系に変更 |
| auto-fillの意味数 | **主要1件のみ** | 1行 = 1つの (英語, 和訳) ペア。複数意味は将来対応 |

### 11.1 Webダッシュボード 表示指標（Tier1・確定4種）
| # | 指標 | 内容 | データ元 |
|---|------|------|---------|
| 1 | 正答率の推移 | 日別の正答率を時系列で表示 | `answer_log` |
| 2 | 継続日数（streak） | 連続学習日数。カレンダーヒートマップ | `answer_log` |
| 3 | 苦手単語 Top | 誤答率の高い単語ランキング | `answer_log` × `words` |
| 4 | 復習予定数 | 今日 / 今週に出題予定の単語数 | `learning_records.next_review` |

---

## 12. 実装済みの構成（2026-08-15 時点 / Phase 1・2 完了）

### 12.1 モジュール

| パス | 役割 |
| ---- | ---- |
| `src/db/schema.sql` | SQLiteのDDL（4テーブル＋インデックス） |
| `src/db/supabase_schema.sql` | Supabase側のDDL。SQL Editorに貼って実行する |
| `src/db/store.py` | `Store` クラス。DBへの全アクセスを集約 |
| `src/srs/spaced_repetition.py` | SM-2。純粋関数のみでDB/UIに非依存 |
| `src/quiz.py` | `build_quiz()`。出題単語と選択肢を決める。UIに非依存 |
| `src/config.py` | `.env` 読み込みと既定値 |
| `src/tags.py` | タグの正規化と `#` 記法のパース（純粋関数） |
| `src/llm/parsing.py` | LLM出力の抽出・検証（純粋関数） |
| `src/llm/base.py` | Provider共通インターフェース |
| `src/llm/gemini.py` / `ollama.py` | 各LLMの呼び出し |
| `src/llm/client.py` | `LLMClient`。3段フォールバックの司令塔 |
| `src/sync/remote.py` | `RemoteClient` Protocol と `SupabaseClient` |
| `src/sync/engine.py` | `SyncEngine`。push / pull / LWW |
| `src/ui/menubar.py` | `VocabLibApp`（rumps）。タイマー・メニュー・出題タグの切替 |
| `src/ui/panel.py` | `QuizPanel`（NSPanel）。4択表示と正誤演出 |
| `src/ui/add_word_panel.py` | `AddWordPanel`。単語追加の確認フォーム |
| `src/ui/dialogs.py` | 単語登録フロー・統計 |
| `src/tools/import_words.py` | 単語の一括インポートCLI（`python -m`） |
| `src/main.py` | エントリポイント |
| `web/lib/stats.ts` | 統計の集計（純粋関数）。SupabaseもReactもimportしない |
| `web/lib/supabase/client.ts` | ブラウザ用クライアント（ログインボタン） |
| `web/lib/supabase/server.ts` | サーバー用クライアント（Cookieからセッションを読む） |
| `web/lib/supabase/data.ts` | データ取得。RLSが絞るので user_id 条件を書かない |
| `web/lib/types.ts` | DBの行の型 |
| `web/proxy.ts` | 認証ガードとセッション更新（Next 16で middleware から改名） |
| `web/app/page.tsx` | ダッシュボード本体（Server Component） |
| `web/app/login/page.tsx` | ログイン画面 |
| `web/app/auth/callback/route.ts` | 認可コード→セッションCookieへの交換 |
| `web/components/*.tsx` | 表示部品 |

依存の向き: `db` / `srs` → `quiz` → `ui`、`config` → `llm` → `ui`。
`ui` より下の層は `rumps` / `AppKit` を import しないため、pytestで検証できる。

### 12.2 SM-2パラメータ（実装値）

| 項目 | 値 |
| ---- | -- |
| 初期EF | 2.5 |
| EF下限 / 上限 | 1.3 / 3.0 |
| 正解時のquality | 5（v1は4。増分が0になりEFが回復しない不具合があった） |
| 不正解時のquality | 2 |
| 復習間隔 | 1回目=1日 / 2回目=6日 / 3回目以降=前回×EF |
| 不正解時の再出題 | 5分後 |

### 12.3 出題単語の選択順位

1. 復習期限を過ぎた単語（`next_review` が古い順）
2. 未学習の単語（`next_review IS NULL`、ランダム）
3. 期限前で最も出題が近い単語

### 12.4 テスト

`uv run pytest` で93件。

| ファイル | 件数 | 対象 |
| -------- | ---- | ---- |
| `test_spaced_repetition.py` | 8 | SM-2 |
| `test_store.py` | 20 | SQLiteデータ層 |
| `test_quiz.py` | 9 | 出題データ組み立て |
| `test_llm_parsing.py` | 21 | LLM出力の抽出・検証 |
| `test_llm_client.py` | 14 | 3段フォールバック（偽Provider注入。ネットワーク不要） |
| `test_sync.py` | 21 | push / pull / LWW（偽RemoteClient注入。ネットワーク不要） |

`src/ui/` と各Providerの実通信部分は自動テストせず手動確認で担保する
（イベントループ起動・ネットワークが必要で費用対効果が低いため）。

Web側は `cd web && npm test`（Vitest）で24件。対象は `web/lib/stats.ts` のみ。
Reactコンポーネントの描画テストはしない。

### 12.5 LLMフォールバック仕様

| 段 | Provider | 使う条件 |
| -- | -------- | -------- |
| 1 | Gemini (`gemini-3.7-flash`) | `GEMINI_API_KEY` が設定されている |
| 2 | Ollama (`gemma3:4b`) | localhost:11434 が応答する |
| 3 | ローカル生成 | 常に成功（`"word" means "meaning"`） |

- **呼べたが出力が使い物にならない場合も次の段に落ちる。** 例文が対象単語を含まない、
  JSONが壊れている、和訳が英語のまま等は不採用とし、次のProviderを試す。
- 例文生成は**不正解時のみ**。生成結果は `words.example_sentence` にキャッシュし、
  2回目以降は即時表示（LLMを呼ばない）。
- オートフィルは1段目が待ち上限まで粘った時点で打ち切り、2段目に持ち越さない。
- Gemini APIはデッドライン10秒未満を 400 で拒否するため、`GeminiProvider` 側で
  10秒未満の指定は10秒に切り上げる。
- どの段が答えたかは `INFO` ログに出る（`例文を生成: provider=gemini word=...`）。

#### Gemini の課金（2026-08-16 確定）

| 項目 | 値 |
| ---- | -- |
| 無料枠（実測） | `gemini-3.7-flash` で **1日20リクエスト / 1分5リクエスト** |
| 現在の契約 | 前払い（プリペイド）で **2000円チャージ済み** |

無料枠では**25語の一括インポート1回で使い切り**、全件が429で2段目（Ollama）に落ちた。
Ollamaは品詞を誤る（`incorporation` を動詞と判定する等）ため、日常運用には足りない。

APIの呼び出し回数は**語彙数に比例し、利用時間には比例しない**
（オートフィルは1語1回、例文は単語ごとにキャッシュされ再生成しない）ため、
チャージ分で当面まかなえる見込み。

### 12.6 同期仕様（Phase 4）

#### 順序

```
push: words → learning_records → answer_log
pull: words → learning_records → answer_log
```

- **pushが先。** 逆にすると、まだ送っていないローカルの変更が古いリモート値で上書きされる。
- pull内の順序は外部キーの都合（`learning_records.word_id` と `answer_log.word_id` が
  `words(id)` を参照しているため、単語が先に入っている必要がある）。

#### 送信対象の判定

| テーブル | 未送信の条件 | 送信後 |
| -------- | ------------ | ------ |
| `words` | `synced_at IS NULL OR updated_at > synced_at` | `synced_at = now` |
| `learning_records` | 同上 | `synced_at = now` |
| `answer_log` | `synced = 0` | `synced = 1` |

`synced_at` / `synced` はローカル専用列でSupabaseには存在しない。
`answer_log.synced = 0` がそのまま送信キューとして機能するため、
別途アウトボックステーブルを持たない。

送信は `upsert`（id衝突時は更新）。同じ行を2回送っても壊れないので、
送信直後にクラッシュしても再送で回復する。

#### 衝突解決

- `words` / `learning_records` … `updated_at` によるLWW。
  比較と更新をSQL 1文（`WHERE excluded.updated_at > ...`）で行うため原子的。
- `answer_log` … 追記のみ・不変なのでLWW不要。`INSERT OR IGNORE`。
- 取り込んだ行は `updated_at` をリモート値のまま入れ `synced_at = now` にする。
- `words.tag`（Phase 8）は列が1つ増えただけなので、この仕様に変更は無い。
  列を足す前にSupabaseへ入った行は `tag` が欠けているため `''` として取り込む。
  これを怠ると「pull → 変更扱い → push」の無限ピンポンになる。
- 時刻はISO8601のUTC文字列として**文字列比較**する。Postgres由来の `Z` 表記等は
  取り込み時に正規化する。

#### pullの役割

Supabaseに書く相手はMacアプリだけなので、通常運用ではpullで何も返らない。
pullが効くのは **ローカルDBを失ったときの復元**。
`answer_log` を含めて取り込むことで、単語・学習状態・統計のすべてが復旧する
（＝Supabaseが実質バックアップになる）。

#### 失敗時

| 失敗 | 挙動 |
| ---- | ---- |
| 通信断・Supabase障害 | 例外を握りつぶしWARNINGログ。未送信フラグを残すので次回再送 |
| 一部テーブルだけ成功 | 成功分だけマークされ、残りは次回 |
| pull失敗 | `last_pulled_at` を進めないので次回同じ範囲を取り直す |

同期の失敗でモーダルは出さない（ユーザーが頼んだ操作ではないため）。
状態はメニューの「同期: HH:MM 完了 / 失敗」とログで示す。

#### 実行タイミング

アプリ起動直後に1回、以後 `SYNC_INTERVAL_MINUTES`（既定10分）ごと。
メニューの「今すぐ同期」で手動実行も可能。実行中に次が来たらskipする。

#### `user_id` の扱い

Phase 4 時点では認証が無いため **NULL のまま送る**。
Phase 6 でGoogleログインを入れる際に `auth.uid()` のUUIDで既存行を一度だけ埋める。

#### RLS

3テーブルすべてRLSを有効化し、**ポリシーは書いていない**（= anonからは一切読み書き不可）。
MacアプリはRLSをバイパスする `service_role` キーで接続する。
Phase 6 で `user_id = auth.uid()` のポリシーを追加する。

### 12.7 Webダッシュボード（Phase 5）

#### 起動

```bash
cd web
npm install      # 初回のみ
npm run dev      # http://localhost:3000
npm test         # 集計ロジックのテスト
```

#### データの流れ

```
ブラウザ ──> Next.js Server Component ──> Supabase
              （service_role）
```

- Supabaseへの接続は **Server Component からのみ**。ブラウザは完成したHTMLを受け取る
- Phase 5 時点でブラウザに渡す環境変数は**ゼロ**
- 生データを取得し、集計は `web/lib/stats.ts`（純粋関数）で行う

#### 集計をTypeScript側で行う理由と限界

Postgresのビュー/RPCを作らず、全件取得してTSで集計している。

- `answer_log` は個人利用で1日数十件。年単位でも数万行に届かず全件取得で軽い
- SQLビューを足すとスキーマ変更になり、Phase 4 の同期の前提に触る
- 集計が純粋関数なのでそのままテストできる

**判断ライン: `answer_log` が1万行を超えたら集計をSQL側（ビューまたはRPC）に移す。**

#### JSTの扱い（重要）

`answered_at` はUTC保存。日本時間の「1日」で区切るため +9時間してから日付を取る。
Mac側の `date(answered_at, '+9 hours')`（`src/db/store.py`）と**同じ基準にすること**。
ずれると同じデータなのに画面によって連続日数が変わる。

連続日数の仕様もMac側の `Store.get_streak()` に合わせている。

- JST基準の連続日数
- 今日まだ未回答でも、昨日まで続いていれば継続扱い
- 直近の学習日が今日でも昨日でもなければ0

#### 表示指標

11.1 で確定した4種（正答率の推移 / 継続日数ヒートマップ / 苦手単語 Top / 復習予定数）
＋ サマリーカード4枚（通算・正答率・連続学習・登録単語数）。

#### デプロイ

**Phase 5 時点では未デプロイ。** RLSポリシーが無い状態で公開すると、
URLを知っている人が誰でも学習データを見られるため。
Phase 6 でGoogleログインとRLSポリシーを入れてからVercelにデプロイする。

#### UIの作り込み

Phase 7 に分離した。理由は、未デプロイの段階で磨いてもフィードバックが得られず、
かつUI変更はデータ構造に影響しないため後回しにしてもコストが変わらないため。

### 12.8 認証とデプロイ（Phase 6）

#### 認証の構成

```
ブラウザ ──Cookie付き──> Server Component ──> Supabase
                          （anonキー + セッション）
                                    ↓
                          RLS が auth.uid() = user_id で絞る
```

- Supabase Auth の Google プロバイダ
- `@supabase/ssr` でセッションを **Cookie** に保存する
  （既定の `localStorage` は Server Component から読めないため）
- `web/proxy.ts`（Next 16 で `middleware` から改名）で未ログインを `/login` へ飛ばす
- 認証判定は `getSession()` ではなく **`getUser()`** を使う。前者はCookieの中身を
  そのまま信じるが、後者はSupabaseに問い合わせてトークンを検証する

#### リダイレクトURLの登録箇所は2つある

2段階のリダイレクトが起きるため、ホワイトリストも2箇所必要。

| 登録先 | 値 | 守る区間 |
| ------ | -- | -------- |
| Google Cloud Console | `https://ozcoyvdgaumvwwkrutau.supabase.co/auth/v1/callback` | Google → Supabase |
| Supabase URL Configuration | `https://vocablib.vercel.app/auth/callback`<br>`http://localhost:3000/auth/callback` | Supabase → 自分のアプリ |

**Supabase側にはVercelの固定ドメインを登録すること。** デプロイごとに変わる
`vocablib-xxxxx.vercel.app` 形式のURLを登録すると、次のデプロイでログインが壊れる。

#### RLSポリシー

3テーブルとも `for select using (auth.uid() = user_id)` のみ。
Webは読み取り専用（SPEC 1.3で編集は対象外）なので書き込みポリシーは作らない。

ポリシー適用の前に、既存行の `user_id` を自分のUUIDで埋める必要がある
（順序を逆にすると自分のデータすら見えなくなる）。DDLとUPDATE文は
`src/db/supabase_schema.sql` に記録している。

| 状況 | 結果 |
| ---- | ---- |
| 未ログインでURLを開く | `/login` へリダイレクト。データは1行も返らない |
| 他人がGoogleでログイン | ログインはできるが `auth.uid()` が違うので空のダッシュボード |
| `anon` キーが漏れる | RLSが守るので実害なし |

#### Mac側

`service_role` のまま（手元でしか動かないためログインUIは実装しない）。
ただし `SUPABASE_USER_ID` を送信行に付け、pull時のフィルタにも使う。
`service_role` はRLSをバイパスするため、自分で絞らないと他人の行まで取ってくる。

`user_id` の付与とフィルタは `SupabaseClient` の中だけで完結させており、
`SyncEngine` は `user_id` を知らない（Phase 4 のテスト21件は無修正）。

#### ローカルSQLiteに `user_id` 列は無い

ローカルDBは構造上ひとり分。pullした行に `user_id` があっても
`apply_remote_*` は必要な列だけを明示的に読むため無視される。
「クラウドは複数ユーザーを区別するが、ローカルは自分専用」という非対称性。

### 12.9 4択誤答のLLM生成を見送った理由（2026-08-15）

出題は5分ごとに発生するため、毎回LLMを呼ぶとレイテンシと無料枠を消費し、
失敗時のフォールバック経路も出題パスに増える。現状の「登録済み単語の和訳から抽出」で
十分機能している。

実施する場合は毎回生成ではなく**単語ごとに1回生成してDBにキャッシュ**する形にする
（`words` に列追加＝スキーマ変更のため、Supabase同期のテーブル定義に影響する）。
**判断ライン: 登録単語が30語に到達した時点で4択の手応えを再評価する。**

### 12.10 一括インポートと出題精度（Phase 7）

#### 一括インポート（F-12）

```bash
uv run python -m src.tools.import_words tmp.txt            # 登録する
uv run python -m src.tools.import_words tmp.txt --dry-run  # 登録せず結果だけ見る
```

入力は1行1件のテキストファイル。2つの書き方を混在できる。

| 書き方 | 例 | 挙動 |
| ------ | -- | ---- |
| 英単語だけ | `yield` | LLMが和訳と品詞を補完する |
| カンマ区切り | `incorporation, 法人設立, 名詞` | 書いたとおりに登録（**LLMを呼ばない**。品詞は省略可） |

- 空行と `#` 始まりの行は無視。ファイル内の重複は除く（大文字小文字を区別しない）
- 既に登録済みの英単語は**LLMを呼ばずに**skip（再実行しても二重登録されない）
- 和訳を取得できなかった単語は**登録しない**。空欄の単語は出題も選択肢にも使えないため、
  一覧で報告して手で登録してもらう
- `--delay`（既定1.0秒）は**LLMを呼ぶ行の間だけ**待つ。レート制限のための待機なので、
  カンマ区切りの行では待たない

品詞は `db.store.PARTS_OF_SPEECH` の9種のみ受け付け、外れた値はパース時に行番号付きで
エラーにする。表記ゆれ（動詞 / 他動詞 / 【動】…）が入ると、下の誤答選択が効かなくなるため。
Macの追加フォームのプルダウンも同じ定数から作る。

#### 4択の誤答を同じ品詞から選ぶ

`Store.get_distractor_meanings()` に `part_of_speech` を渡せるようにし、`build_quiz()` が
出題単語の品詞を渡す。

1. まず同じ品詞の和訳から選ぶ
2. 足りなければ品詞を問わず補充する（出題できないより、少し易しい方がマシ）
3. 品詞が未設定（NULL）の単語は従来どおり品詞を問わない

品詞が混ざると「動詞を問う問題に名詞の選択肢が並ぶ」形になり、意味を知らなくても
消去法で正解できてしまっていた（9の既知の問題への対策）。

#### v1からの単語移行（2026-08-16）

v1の25語は**単語の綴りだけ**を引き継ぎ、学習状態（EF・復習間隔）は移行しない。
v1のSM-2にはEFが回復しないバグがあり、歪んだ値を持ち込むことになるため。

和訳・品詞は**LLMではなく人手で確定**させた。無料枠切れで全件がOllamaに落ち、
`incorporation` を動詞、`resilience` を形容詞と判定するなど品詞の誤りが目立ったため。

動作確認用に登録していたテストデータ（apple / lemon など）は、この移行に合わせて
ローカルDB・Supabaseの両方から削除した。

### 12.11 タグ機能（Phase 8）

#### 決定事項

| 論点 | 決定 |
| ---- | ---- |
| 個数 | **1単語につき1タグ** |
| 持ち方 | `words.tag`（`text not null default ''`）。別テーブルにしない |
| 用途 | 出題の絞り込み / 一覧の分類。**タグ別統計はやらない** |
| 入力 | 英単語の入力欄に `incorporation #TOEIC` と書く。`#` 以降がタグ |

別テーブルにしなかったのは同期のコストが理由。列を1つ増やすだけなら
`SyncEngine` もRLSポリシーも変更が要らない。4つ目のテーブルにすると
「push / pull / 墓標 / LWW / RLS」を新たに設計することになる。

#### 正規化（`src/tags.py`）

`normalize_tag()` を通してから保存する。前後の空白を除去し、先頭の `#` を取り、
カンマを除去する（インポータの区切り文字と衝突するため）。内側の空白と
大文字小文字は保つ。**`toeic` と `TOEIC` は同一視しない**（メニューから選べるので、
手で打ち直す機会が少ない）。

`parse_word_input()` は**最初の `#` で1回だけ**分割する。
英単語側に空白を含むフレーズ（`extend an invitation to`）があるため、空白では切れない。

#### スキーマ変更の手順（重要）

`schema.sql` は `CREATE TABLE IF NOT EXISTS` なので、**既存DBには効かない**。
列を書き足しただけでは手元のDBに生えず、新規インストールでしか動かない変更になる。

**列の追加は必ず `Store._migrate()` に書く。** 起動のたびに走るのでべき等にすること。

```python
columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(words)")}
if "tag" not in columns:
    self._conn.execute("ALTER TABLE words ADD COLUMN tag TEXT NOT NULL DEFAULT ''")
```

Supabase側は `supabase_schema.sql` の `alter table ... add column if not exists` を
SQL Editorで実行する。

#### 出題の絞り込み

- `Store.get_next_word(tag)` … 1語1タグなので `WHERE tag = ?` の完全一致
- メニューバーの「出題するタグ ▸」で切り替え、`sync_state` の `quiz_tag_filter` に保存
  （再起動後も維持）
- 該当が0件でも**勝手に絞り込みを解除しない**（設定が効いていないように見えるため）。
  ただし選択中のタグの単語が1語も無くなったらメニューから消えるので「すべて」に戻す
- **4択の誤答はタグで絞らない。** 絞ると在庫が枯れて同じ4語が並び、
  綴りではなく位置で覚えてしまう。誤答に必要なのは品詞が揃っていること（12.10）

#### 一括インポート

4列目がタグ（`incorporation, 法人設立, 名詞, TOEIC`）。1列目の `#` 記法も使えるが、
**4列目があればそちらを優先**する。

| オプション | 意味 |
| ---------- | ---- |
| `--tag TOEIC` | 行に指定が無いときに使う共通タグ |
| `--retag` | 登録済みの単語にもタグを付ける。**既にタグがある単語は変更しない** |

`--retag` が上書きしないのは、1語1タグでは上書き＝前のタグの消滅であり、
Webや `#` 記法で付けたタグをインポータが黙って消すことになるため。

#### 同期

`tag` は `words` の列なので、`SyncEngine` のロジックは変更なし。
LWWもRLSも既存のまま効く。列を足す前にSupabaseへ入った行は `''` として取り込む。

---

## 未確定事項（TBD）

- [ ] Mac常駐アプリの `.app` 配布手順（PyInstaller）とログイン項目への登録 — 8.1
  - 現行は `uv run python -m src.main` で運用（2026-08-15 時点）
- [x] ~~Vercelデプロイ手順の確定~~ — 2026-08-15 完了（8.1・12.8）
- [ ] 4択の当てずっぽう対策（入力式・出題方向の切替）の要否 — 9
- [ ] UI・ビジュアルの作り込み — Phase 8 で対応
- [x] ~~Gemini APIの有料化~~ — 2026-08-16 完了（前払い2000円チャージ。12.5）
- [ ] Google Cloud の予算アラート設定（チャージ切れに気付けるようにする） — 12.5
