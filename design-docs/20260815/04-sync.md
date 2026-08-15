# 設計書: Supabase同期（Phase 4）

- 作成日: 2026-08-15
- 対象機能: F-06 SQLite ↔ Supabase 同期
- 前提: Phase 1〜3 完了（テスト72件パス、実機動作確認済み）

---

## 1. このPhaseのゴール

**ローカルSQLiteの内容をSupabaseに送り、Web側から統計を読める状態にする。**

いちばん大事な原則は変わらない。

> **UIはネットワークを一切待たない。** 同期はバックグラウンドで走り、
> 失敗しても次回に持ち越すだけ。オフラインでもアプリは完全に動く。

Phase 1 で仕込んでおいた `words.synced_at` / `learning_records.synced_at` /
`answer_log.synced` が、ここで初めて使われる。

### やること

| ID | 内容 |
|---|---|
| 4-1 | Supabase側のテーブル作成（Postgres DDL）+ RLS有効化 |
| 4-2 | `sync_state` テーブルをSQLiteに追加（最終pull時刻の保存） |
| 4-3 | `Store` に同期用メソッドを追加 |
| 4-4 | `RemoteClient`（Supabase呼び出しの抽象）と `SupabaseClient` |
| 4-5 | `SyncEngine`（push / pull / LWW）— ネットワークに依存しない形で実装 |
| 4-6 | バックグラウンド同期ワーカー + メニュー表示 |
| 4-7 | `SyncEngine` のテスト（偽RemoteClient注入） |

### やらないこと（明示）

- **Webダッシュボード** → Phase 5
- **Googleログイン / RLSポリシー本実装** → Phase 6
  （Phase 4 では RLS を「有効化するがポリシーを書かない」= anon から一切読めない状態にする。
  Macアプリは `service_role` キーで RLS をバイパスするため動く）
- ~~**`answer_log` の pull** → 書き手がMacアプリだけなので不要。push のみ~~
  → **撤回（2026-08-15 追記。詳細は12節）。`answer_log` も pull する。**
- 複数Mac間の同期テスト → 端末が1台のため実施しない（設計上は成立する）

---

## 2. Supabase側のスキーマ（4-1）

SQLiteとの差分だけ注意する。

| SQLite | Postgres | 理由 |
|---|---|---|
| `TEXT`（UUID） | `uuid` | 型を効かせる |
| `TEXT`（ISO8601） | `timestamptz` | 時刻として扱えるようにする |
| `INTEGER`（0/1） | `boolean` | |
| `REAL` | `real` | |
| `synced_at` / `synced` | **無し** | ローカル専用列。クラウドには送らない |

```sql
-- words
create table if not exists words (
  id                uuid primary key,
  user_id           uuid,
  english           text not null,
  japanese          text not null,
  part_of_speech    text,
  example_sentence  text,
  created_at        timestamptz not null,
  updated_at        timestamptz not null,
  deleted           boolean not null default false
);

-- learning_records
create table if not exists learning_records (
  word_id        uuid primary key references words(id) on delete cascade,
  user_id        uuid,
  last_reviewed  timestamptz,
  next_review    timestamptz,
  ease_factor    real    not null default 2.5,
  interval_days  real    not null default 0,
  repetitions    integer not null default 0,
  total_correct  integer not null default 0,
  total_seen     integer not null default 0,
  updated_at     timestamptz not null
);

-- answer_log（追記のみ・不変）
create table if not exists answer_log (
  id           uuid primary key,
  user_id      uuid,
  word_id      uuid not null references words(id) on delete cascade,
  is_correct   boolean not null,
  answered_at  timestamptz not null,
  source       text not null default 'mac'
);

create index if not exists idx_words_updated on words(updated_at);
create index if not exists idx_lr_updated    on learning_records(updated_at);
create index if not exists idx_answer_time   on answer_log(answered_at);

-- RLSを有効化する。ポリシーを書かないので anon からは一切読めない（既定で拒否）。
-- Macアプリは service_role キーを使うためRLSをバイパスして動く。
-- Phase 6 でGoogleログインを入れる際に user_id ベースのポリシーを追加する。
alter table words            enable row level security;
alter table learning_records enable row level security;
alter table answer_log       enable row level security;
```

### `user_id` の扱い

Phase 4 の時点では認証が無いので **NULL のまま送る**。
Phase 6 でGoogleログインを入れたとき、`auth.uid()` で得た自分のUUIDを
既存行に一度だけ流し込む（UPDATE 1回）。

> ここで無理に仮のUUIDを振ると、Supabase Authが発行する本物のUUIDと
> 食い違って結局付け替えることになる。それなら最初はNULLの方が素直。

**この DDL は Supabase ダッシュボードの SQL Editor に貼って実行する。**
マイグレーションツールは導入しない（テーブル3つで、変更頻度も低いため）。

---

## 3. ローカル側の追加（4-2）

`src/db/schema.sql` に1テーブル追加する。

```sql
CREATE TABLE IF NOT EXISTS sync_state (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
```

- `last_pulled_at` … 前回pullした時刻（この時刻より新しい行だけ取りに行く）

`schema.sql` は起動のたびに `executescript` で流しているので、
`CREATE TABLE IF NOT EXISTS` を足すだけで既存DBにも自動で追加される。

> 注意: 既存テーブルへの**列追加**はこの方法では効かない（`ALTER TABLE` が必要）。
> 今回は新規テーブルなので問題ない。

---

## 4. 同期アルゴリズム（4-5）

### 4-1. 全体の流れ

```
sync()
 ├─ push_words()             送信 → synced_at を更新
 ├─ push_learning_records()  送信 → synced_at を更新
 ├─ push_answer_log()        送信 → synced = 1
 ├─ pull_words()             取得 → LWWで採否を判定
 ├─ pull_learning_records()  取得 → LWWで採否を判定
 └─ last_pulled_at を更新
```

**pushを先にやる。** 先にpullすると、まだ送っていないローカルの変更が
古いリモート値で上書きされる可能性がある。

### 4-2. push の対象（「まだ送っていない行」の判定）

| テーブル | 条件 | 送信後 |
|---|---|---|
| `words` | `synced_at IS NULL OR updated_at > synced_at` | `synced_at = now` |
| `learning_records` | 同上 | `synced_at = now` |
| `answer_log` | `synced = 0` | `synced = 1` |

`answer_log` は追記のみ・不変なので、**この `synced = 0` がそのまま送信キューになる**。
別途アウトボックステーブルを持つ必要がない（Phase 1 の設計意図）。

送信は `upsert`（`on conflict (id) do update`）にする。
同じ行を2回送っても壊れないので、**送信直後にクラッシュしても再送で回復する**。

### 4-3. pull と衝突解決（LWW）

```
リモートの行ごとに:
    local = 手元の同じidの行
    if local が無い          → INSERT
    elif remote.updated_at > local.updated_at → UPDATE（リモート採用）
    else                     → 何もしない（ローカルの方が新しい）
```

- `updated_at` はISO8601のUTC文字列。**文字列比較でそのまま時系列比較になる**
  （Phase 1 で `_iso()` をUTC固定にしてあるのはこのため）
- リモートを採用したときは `updated_at` をリモート値のまま入れ、
  `synced_at = now` にする。こうしないと「pullした直後に同じ行をpushし返す」
  無限ピンポンになる
- `deleted = true` の行も普通にpullする（**墓標を伝えるのが論理削除の目的**）

### 4-4. 失敗したらどうするか

| 失敗 | 挙動 |
|---|---|
| ネットワーク断・Supabase障害 | 例外を握りつぶし、WARNINGログ。`synced_at` / `synced` は更新しないので次回そのまま再送される |
| 一部のテーブルだけ成功 | 成功した分だけマークされる。残りは次回 |
| pullが失敗 | `last_pulled_at` を更新しないので次回同じ範囲を取り直す |

**ユーザーにモーダルを出さない。** 同期はユーザーが頼んだ操作ではないので、
失敗を知らせる場所はメニューの表示（「最終同期: 12:34」）とログで足りる。

---

## 5. モジュール構成

```
src/sync/
├── __init__.py
├── remote.py    RemoteClient（Protocol）と SupabaseClient
└── engine.py    SyncEngine（push / pull / LWW）
```

### `RemoteClient` インターフェース

```python
class RemoteClient(Protocol):
    def upsert(self, table: str, rows: list[dict]) -> None: ...
    def fetch_since(self, table: str, column: str, since: str | None) -> list[dict]: ...
```

**`SyncEngine` はこの2メソッドしか知らない。** これがテスト可能性の要で、
偽 `RemoteClient` を注入すればネットワーク無しで同期ロジック全体を検証できる。
Phase 3 で `LLMClient(providers=...)` にしたのと同じ手口。

### `SyncEngine`

```python
class SyncEngine:
    def __init__(self, store: Store, remote: RemoteClient): ...
    def sync(self) -> SyncResult: ...
```

```python
@dataclass(frozen=True)
class SyncResult:
    pushed: int
    pulled: int
    error: str | None      # 失敗しても例外にせず、ここに入れて返す
```

---

## 6. `Store` に足すメソッド（4-3）

同期のためのDBアクセスも `Store` に集約する（Phase 1 の方針を維持）。

| メソッド | 用途 |
|---|---|
| `get_unsynced_words()` / `get_unsynced_records()` / `get_unsynced_answers()` | push対象を取り出す（クラウドに無い列は落とす） |
| `mark_words_synced(ids)` / `mark_records_synced(ids)` / `mark_answers_synced(ids)` | 送信済みにする |
| `apply_remote_word(row)` / `apply_remote_record(row)` | LWW判定込みで取り込む。採用したら True |
| `get_sync_value(key)` / `set_sync_value(key, value)` | `sync_state` の読み書き |

`apply_remote_*` の中でLWW比較まで行う。
SQLの `WHERE updated_at < ?` を使えば**比較と更新を1文で原子的に**実行でき、
「読んでから書くまでの間に別スレッドが書き換える」競合を避けられる。

---

## 7. バックグラウンド同期（4-6）

### 起動

- アプリ起動時に1回
- 以後 `SYNC_INTERVAL_MINUTES`（既定10分）ごと
- メニューの「今すぐ同期」で手動実行

### スレッド

Phase 2 で決めた規約に従う。

> **DBアクセス・ネットワークはワーカースレッド。UI操作は必ず `callAfter` でメインスレッドに戻す。**

`rumps.Timer` で刻み、発火のたびに `threading.Thread` で `sync()` を回す。
`Store` は接続1本を `Lock` で守っているのでスレッドから呼んで安全（Phase 1で対応済み）。

**同期中に次の同期が来たら skip する**（`threading.Lock(blocking=False)` で二重起動を防ぐ）。

### メニュー表示

```
今すぐ出題
─────────
自動出題: 4分32秒後
─────────
単語を追加...
単語一覧...
─────────
統計...
128/156正解（82.1%） 連続5日 復習待ち12
─────────
同期: 12:34 完了          ← 追加（未設定なら「同期: 未設定」）
今すぐ同期                 ← 追加
─────────
終了
```

`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` が未設定なら
同期は**丸ごと無効**にし、メニューには「同期: 未設定」と出す。
（Phase 3 で `GEMINI_API_KEY` 未設定時にGemini段を飛ばしたのと同じ考え方）

---

## 8. 追加する依存ライブラリ

CLAUDE.md の規約により、**導入前に開発者の承認を得る**。

| ライブラリ | 用途 |
|---|---|
| `supabase` | Supabase公式Pythonクライアント（PostgREST呼び出し・upsert・フィルタ） |

> `requests` でPostgREST APIを直接叩くことも可能（依存が増えない）。
> ただし upsert のヘッダ指定やフィルタ構文を自前で組むことになるため、
> **公式クライアントを推奨**。

---

## 9. テスト方針（4-7）

**ネットワークに触らないテストだけを書く。** `tests/test_sync.py`。

| テスト | 内容 |
|---|---|
| 未送信の単語だけがpushされる | 既に送信済みの行は含まれない |
| push後に送信済みになる | 2回目のsyncで再送されない |
| 回答ログはsynced=0のものだけ送られる | 送信キューとして機能している |
| リモートに新しい行があればローカルに入る | pull → INSERT |
| リモートの方が新しければ上書きする | LWW（リモート採用） |
| **ローカルの方が新しければ上書きしない** | LWW（ローカル勝ち）。ここが衝突解決の肝 |
| pullした行を次のsyncでpushし返さない | ピンポン防止 |
| `deleted=true` の行がpullで反映される | 墓標が伝わる |
| ネットワーク例外でも `sync()` は例外を投げない | `SyncResult.error` に入る |
| 送信失敗した行は送信済みにならない | 次回再送される |
| 同期が二重に走らない | 実行中はskip |

`SupabaseClient` の実通信部分は自動テストせず、手動確認で担保する。

---

## 10. 完了の定義（DoD）

`uv run pytest` が通ることに加え、以下を手動で確認する。

### 同期が無効な状態（最重要）

1. `SUPABASE_URL` 未設定で起動 → メニューに「同期: 未設定」と出る
2. **この状態でPhase 1〜3の全機能が変わらず動く**（同期導入で既存機能が壊れていないこと）

### 同期あり

3. Supabase SQL Editor で DDL を実行し、3テーブルが作られる
4. `.env` にURLと `service_role` キーを設定して起動 → 数秒後にメニューが「同期: HH:MM 完了」になる
5. Supabaseダッシュボードの Table Editor で、`words` に登録済みの単語が入っている
6. 新しく単語を追加 → 「今すぐ同期」→ Supabase側にも増えている
7. クイズに回答 → 同期 → `answer_log` に行が増え、`learning_records` が更新されている
8. **もう一度同期しても同じ行が二重に増えない**（upsertとsyncedフラグが効いている）

### 異常系

9. Wi-Fiを切って起動 → 同期は失敗するが**アプリは普通に使える**。メニューは「同期: 失敗」
10. Wi-Fiを戻して「今すぐ同期」→ オフライン中に貯まった回答がまとめて送られる
11. Supabase側で単語の和訳を直接書き換える → 同期 → Macアプリ側に反映される（pull）

### セキュリティ

12. `anon` キーでは何も読めないことを確認（RLS有効・ポリシー無しのため）

確認結果は `development-logs/YYYYMMDD-devlogs.md` に記録する。

---

## 12. 追記（2026-08-15）: `answer_log` を pull 対象に追加

当初は「Supabaseに書く相手がMacアプリだけなので `answer_log` の pull は不要」と判断したが、
**実機確認で穴が出たため撤回する。**

### 何が起きたか

ローカルDBを削除して起動したところ、同期で `words` と `learning_records` は復元されたが、
統計が空のままだった。

```
18:30:00 INFO src.sync.engine: 同期完了: 送信0件 受信10件
→ 単語と学習状態は戻ったが「統計: まだ回答がありません」
```

`answer_log` は正答率・連続日数・日別推移すべての元データなので、
これを取り込まないと**Supabase側にデータがあるのにMac側だけ統計が空**になる。

### 判断の誤り

「pullは他の書き手がいる場合にだけ必要」と考えたのが誤りだった。
pullには**ローカルDBを失ったときの復元**という役割がある。
このアプリの価値は学習データの蓄積そのものなので、ここが戻らないのは致命的。

### 実装

- pull順は `words` → `learning_records` → `answer_log`（外部キーがあるので単語が先）
- `answer_log` は追記のみ・不変なので**LWW判定が不要**。`INSERT OR IGNORE` で
  「知らないidなら入れる」だけ
- 取り込んだ行は `synced = 1` で入れるので送り返さない
- 差分の起点は `answered_at`

これにより **Supabaseが実質バックアップになり、Macが壊れても学習履歴は残る**。

---

## 11. 完了後にやること

- SPEC.md の F-06 を「実装済」に更新
- SPEC.md 7節に `SYNC_INTERVAL_MINUTES` を追加
- SPEC.md 12.1 のモジュール表に `src/sync/` を追記
- SPEC.md にSupabase側のDDLと `user_id` のPhase 6での扱いを追記
