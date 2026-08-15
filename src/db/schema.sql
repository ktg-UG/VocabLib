-- VocabLib v2 ローカルDB（SQLite）スキーマ
--
-- 設計方針（design-docs/20260814-initial.md 参照）:
--   - このDBが source of truth。アプリはネットワークを待たずにここを読み書きする
--   - 時刻は ISO8601 の UTC 文字列で保存する（例: 2026-08-14T07:30:00+00:00）
--     → 文字列のまま比較・ソートしても時系列順になるため、SQLiteでは扱いやすい
--   - synced_at / synced 列はローカル専用。Supabase側には存在しない

PRAGMA journal_mode = WAL;   -- 書き込み中でも読み取りをブロックしない
PRAGMA foreign_keys = ON;    -- 外部キー制約を有効化（SQLiteは既定でオフ）


-- ── 単語帳 ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS words (
    id                TEXT    PRIMARY KEY,          -- UUID（クライアント生成）
    english           TEXT    NOT NULL,
    japanese          TEXT    NOT NULL,
    part_of_speech    TEXT,                         -- 品詞（auto-fillで埋める）
    example_sentence  TEXT,                         -- AI例文のキャッシュ
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    deleted           INTEGER NOT NULL DEFAULT 0,   -- 論理削除（0/1）
    synced_at         TEXT                          -- 最後にSupabaseへpushした時刻
);

-- 同じ (英単語, 和訳) の重複登録を防ぐ。削除済みは対象外にしたいので部分インデックス
CREATE UNIQUE INDEX IF NOT EXISTS idx_words_unique
    ON words(english, japanese) WHERE deleted = 0;


-- ── SM-2の現在状態（words と1対1、単語登録時に必ず同時作成する）─────────
CREATE TABLE IF NOT EXISTS learning_records (
    word_id        TEXT    PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
    last_reviewed  TEXT,                            -- NULL = 未学習
    next_review    TEXT,                            -- NULL = 未学習（最優先で出題したい）
    ease_factor    REAL    NOT NULL DEFAULT 2.5,
    interval_days  REAL    NOT NULL DEFAULT 0,
    repetitions    INTEGER NOT NULL DEFAULT 0,      -- 連続正解回数
    total_correct  INTEGER NOT NULL DEFAULT 0,
    total_seen     INTEGER NOT NULL DEFAULT 0,
    updated_at     TEXT    NOT NULL,
    synced_at      TEXT
);


-- ── 回答履歴（追記のみ・不変。統計はすべてここから集計する）─────────────
CREATE TABLE IF NOT EXISTS answer_log (
    id           TEXT    PRIMARY KEY,               -- UUID
    word_id      TEXT    NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    is_correct   INTEGER NOT NULL,                  -- 0/1
    answered_at  TEXT    NOT NULL,
    source       TEXT    NOT NULL DEFAULT 'mac',    -- 'mac' / 'web'
    synced       INTEGER NOT NULL DEFAULT 0         -- 0=未送信（これ自体が送信キュー）
);


-- ── インデックス ────────────────────────────────────────────────────────
-- 出題する単語を選ぶたびに next_review で絞り込む
-- 同期の進捗を覚えておくための汎用キーバリュー（ローカル専用・クラウドには送らない）
--   last_pulled_at … 前回pullした時刻。これより新しい行だけを取りに行く
CREATE TABLE IF NOT EXISTS sync_state (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_lr_next_review ON learning_records(next_review);

-- 統計（日別集計・streak）で answered_at を範囲検索する
CREATE INDEX IF NOT EXISTS idx_answer_time ON answer_log(answered_at);

-- 単語別の正誤集計（苦手単語ランキング）
CREATE INDEX IF NOT EXISTS idx_answer_word ON answer_log(word_id);

-- 未送信のログだけを引く。部分インデックスなので synced=1 の行は含まれず軽い
CREATE INDEX IF NOT EXISTS idx_answer_unsynced ON answer_log(synced) WHERE synced = 0;
