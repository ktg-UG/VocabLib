-- Supabase（PostgreSQL）側のスキーマ
--
-- 実行方法: Supabaseダッシュボード → SQL Editor に貼り付けて Run。
-- マイグレーションツールは使わない（テーブル3つ・変更頻度が低いため）。
-- 変更したらこのファイルも必ず更新すること。
--
-- ローカルSQLite（src/db/schema.sql）との差分:
--   TEXT(UUID)     → uuid
--   TEXT(ISO8601)  → timestamptz
--   INTEGER(0/1)   → boolean
--   synced_at / synced 列は無い（ローカル専用の同期管理列のため送らない）

-- ── 単語帳 ──────────────────────────────────────────────────────────────
create table if not exists words (
  id                uuid primary key,
  user_id           uuid,
  english           text not null,
  japanese          text not null,
  part_of_speech    text,
  tag               text not null default '',
  example_sentence  text,
  created_at        timestamptz not null,
  updated_at        timestamptz not null,
  deleted           boolean not null default false
);

-- 既存のプロジェクトに後から列を足す場合はこちら（create table は既存テーブルに効かない）
alter table words add column if not exists tag text not null default '';

-- ── SM-2の現在状態（1単語1行・上書き） ──────────────────────────────────
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

-- ── 回答イベント履歴（追記のみ・不変） ──────────────────────────────────
create table if not exists answer_log (
  id           uuid primary key,
  user_id      uuid,
  word_id      uuid not null references words(id) on delete cascade,
  is_correct   boolean not null,
  answered_at  timestamptz not null,
  source       text not null default 'mac'
);

-- 差分pull（updated_at > 前回時刻）とWeb側の集計のためのインデックス
create index if not exists idx_words_updated on words(updated_at);
create index if not exists idx_lr_updated    on learning_records(updated_at);
create index if not exists idx_answer_time   on answer_log(answered_at);

-- ── RLS（Row Level Security） ───────────────────────────────────────────
-- 有効化するがポリシーは書かない = anon キーからは一切読み書きできない。
-- 「うっかり公開」を構造的に防ぐための安全な既定状態。
--
-- Macアプリは service_role キーを使うためRLSをバイパスして動作する。
-- （service_role キーは絶対にブラウザ・Webフロント・Gitに置かないこと）
--
-- Phase 6 でGoogleログインを入れる際に、user_id = auth.uid() のポリシーを追加する。
-- そのとき既存行の user_id（現在NULL）を自分のUUIDで一度だけ埋める。
alter table words            enable row level security;
alter table learning_records enable row level security;
alter table answer_log       enable row level security;

-- ── ポリシー（Phase 6 で追加） ──────────────────────────────────────────
-- 実行前に、既存行の user_id を自分のUUIDで埋めておくこと。
-- 順序を逆にすると user_id が NULL のままポリシーが効き、自分のデータすら
-- 見えなくなる。
--
--   update words            set user_id = (select id from auth.users order by created_at limit 1) where user_id is null;
--   update learning_records set user_id = (select id from auth.users order by created_at limit 1) where user_id is null;
--   update answer_log       set user_id = (select id from auth.users order by created_at limit 1) where user_id is null;
--
-- select のみ。Webは読み取り専用（SPEC 1.3で編集は対象外）なので、
-- 書き込みポリシーは作らない。書けないものは壊せない。
-- Macアプリは service_role なのでポリシーの影響を受けず、従来どおり書き込める。

create policy "自分の単語のみ参照" on words
  for select using (auth.uid() = user_id);

create policy "自分の学習記録のみ参照" on learning_records
  for select using (auth.uid() = user_id);

create policy "自分の回答履歴のみ参照" on answer_log
  for select using (auth.uid() = user_id);

-- ── 書き込みポリシーと自動生成トリガー（Phase 9 で追加） ────────────────
-- Phase 6 では「select だけにする。書けないものは壊せない」としたが、
-- SPEC 1.4 でWebが単語の一覧・編集・削除・登録を担うと決めたため、この判断を変更する。
--
-- ここから下は、既にプロジェクトを作ってある場合に**追加で実行する**部分。
-- 何度実行しても同じ状態になるよう、drop してから作り直している。

-- user_id を書き忘れると with check で弾かれるので、既定値を入れておく。
-- Macアプリは明示的に user_id を送るので影響を受けない。
alter table words alter column user_id set default auth.uid();

-- 自分の行だけ追加できる
drop policy if exists "自分の単語のみ追加" on words;
create policy "自分の単語のみ追加" on words
  for insert with check (auth.uid() = user_id);

-- 自分の行だけ更新できる（編集と論理削除の両方がこれで通る）
drop policy if exists "自分の単語のみ更新" on words;
create policy "自分の単語のみ更新" on words
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- delete ポリシーは作らない。
-- 「単語を削除できない」という意味ではなく、削除は deleted = true の更新で行うため
-- SQLの DELETE を許す必要が無いということ。
-- むしろ物理削除を許すと、Macに削除が伝わらず次のpushで単語が復活する経路を
-- 自分で開けることになる（同期は「updated_at が新しい行」を拾う仕組みのため、
-- 行ごと消えると何も届かない）。使わない権限は与えない。

-- ── words に行が入ったら learning_records も必ず作る ────────────────────
-- Webから単語を登録すると、words の行だけができて learning_records が無い
-- 状態になりうる。**これは v1 で実際に起きたバグ**（例文の保存に失敗する原因）。
--
-- PostgRESTは1リクエスト1文なので、アプリ側で2テーブルへのinsertを並べても
-- トランザクションにならない。DB側に寄せて、どの経路から入っても
-- 学習記録が存在するという不変条件を保証する。
create or replace function create_learning_record()
returns trigger language plpgsql security definer as $$
begin
  insert into learning_records (word_id, user_id, ease_factor, updated_at)
  values (new.id, new.user_id, 2.5, new.created_at)
  on conflict (word_id) do nothing;   -- Macのpushと衝突しても無害
  return new;
end;
$$;

drop trigger if exists words_create_learning_record on words;
create trigger words_create_learning_record
  after insert on words
  for each row execute function create_learning_record();
