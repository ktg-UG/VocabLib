/**
 * Supabase の行の型
 *
 * Mac アプリ側の `src/db/supabase_schema.sql` と対応している。
 * DDL を変更したらこのファイルも直すこと。
 */

export type WordRow = {
  id: string;
  english: string;
  japanese: string;
  part_of_speech: string | null;
  example_sentence: string | null;
  created_at: string;
  updated_at: string;
  deleted: boolean;
};

export type AnswerRow = {
  id: string;
  word_id: string;
  is_correct: boolean;
  answered_at: string; // ISO8601 (UTC)
};

export type RecordRow = {
  word_id: string;
  next_review: string | null; // null = 未学習
  total_correct: number;
  total_seen: number;
};

export type DailyPoint = {
  date: string; // "2026-08-15"（JST）
  total: number;
  correct: number;
  accuracy: number; // 0-100
};

export type WeakWord = {
  wordId: string;
  english: string;
  japanese: string;
  total: number;
  incorrect: number;
  errorRate: number; // 0-100
};

export type DueCounts = {
  overdue: number;
  withinWeek: number;
  unlearned: number;
};

export type Overall = {
  total: number;
  correct: number;
  incorrect: number;
  accuracy: number; // 0-100
};
