/**
 * 統計の集計
 *
 * このファイルは Supabase も React も import しない。
 * データを受け取って計算するだけの層にして、そこだけテストする。
 * （Mac アプリ側で srs / quiz / llm / sync に対して守ってきた方針と同じ）
 *
 * ## JST の扱い
 *
 * `answered_at` は UTC で保存されている。日本時間の「1日」で区切るには
 * +9時間してから日付を取り出す必要がある。
 *
 * Mac アプリ側は `date(answered_at, '+9 hours')`（src/db/store.py）で
 * 同じことをしている。ここがずれると両者で連続日数が食い違うので、
 * 必ず揃えること。
 */

import type {
  AnswerRow,
  DailyPoint,
  DueCounts,
  Overall,
  RecordRow,
  WeakWord,
  WordRow,
} from "./types";

const JST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

/** UTC の ISO8601 文字列を JST の日付（"YYYY-MM-DD"）に変換する */
export function toJstDate(iso: string): string {
  const shifted = new Date(new Date(iso).getTime() + JST_OFFSET_MS);
  return shifted.toISOString().slice(0, 10);
}

/** 今日（JST）の日付 */
export function jstToday(now: Date = new Date()): string {
  return new Date(now.getTime() + JST_OFFSET_MS).toISOString().slice(0, 10);
}

function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS)
    .toISOString()
    .slice(0, 10);
}

function diffDays(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS,
  );
}

/** 通算の回答数・正解数・正答率 */
export function overallStats(rows: AnswerRow[]): Overall {
  const total = rows.length;
  const correct = rows.filter((r) => r.is_correct).length;
  return {
    total,
    correct,
    incorrect: total - correct,
    accuracy: total ? (correct / total) * 100 : 0,
  };
}

/**
 * 日別（JST）の正答率。直近 `days` 日を、回答が無い日も含めて古い順で返す。
 *
 * 回答が無い日を飛ばすとグラフの横軸が詰まって「毎日やっている」ように
 * 見えてしまうため、0件の日も並べる。
 */
export function dailyAccuracy(
  rows: AnswerRow[],
  days = 30,
  now: Date = new Date(),
): DailyPoint[] {
  const buckets = new Map<string, { total: number; correct: number }>();
  for (const row of rows) {
    const date = toJstDate(row.answered_at);
    const bucket = buckets.get(date) ?? { total: 0, correct: 0 };
    bucket.total += 1;
    if (row.is_correct) bucket.correct += 1;
    buckets.set(date, bucket);
  }

  const today = jstToday(now);
  const points: DailyPoint[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const date = addDays(today, -i);
    const bucket = buckets.get(date) ?? { total: 0, correct: 0 };
    points.push({
      date,
      total: bucket.total,
      correct: bucket.correct,
      accuracy: bucket.total ? (bucket.correct / bucket.total) * 100 : 0,
    });
  }
  return points;
}

/**
 * 連続学習日数（JST基準）
 *
 * Mac アプリの `Store.get_streak()` と同じ仕様にすること:
 *   - 今日まだ未回答でも、昨日まで続いていれば継続扱い
 *     （今日これからやる余地を残すため）
 *   - 直近の学習日が今日でも昨日でもなければ 0
 */
export function currentStreak(rows: AnswerRow[], now: Date = new Date()): number {
  const studied = [...new Set(rows.map((r) => toJstDate(r.answered_at)))].sort().reverse();
  if (studied.length === 0) return 0;

  if (diffDays(studied[0], jstToday(now)) > 1) return 0;

  let streak = 1;
  for (let i = 0; i < studied.length - 1; i++) {
    if (diffDays(studied[i + 1], studied[i]) === 1) streak += 1;
    else break;
  }
  return streak;
}

/** ヒートマップ用に、日付ごとの回答数を返す */
export function answersByDate(rows: AnswerRow[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const date = toJstDate(row.answered_at);
    counts.set(date, (counts.get(date) ?? 0) + 1);
  }
  return counts;
}

/** 苦手な単語（誤答が多い順）。全問正解の単語は含めない */
export function weakWords(
  rows: AnswerRow[],
  words: WordRow[],
  limit = 10,
): WeakWord[] {
  const byId = new Map(words.map((w) => [w.id, w]));
  const tally = new Map<string, { total: number; incorrect: number }>();

  for (const row of rows) {
    if (!byId.has(row.word_id)) continue; // 削除済みの単語は集計しない
    const entry = tally.get(row.word_id) ?? { total: 0, incorrect: 0 };
    entry.total += 1;
    if (!row.is_correct) entry.incorrect += 1;
    tally.set(row.word_id, entry);
  }

  return [...tally.entries()]
    .filter(([, v]) => v.incorrect > 0)
    .map(([wordId, v]) => {
      const word = byId.get(wordId)!;
      return {
        wordId,
        english: word.english,
        japanese: word.japanese,
        total: v.total,
        incorrect: v.incorrect,
        errorRate: (v.incorrect / v.total) * 100,
      };
    })
    .sort((a, b) => b.incorrect - a.incorrect || b.total - a.total)
    .slice(0, limit);
}

/** 復習予定数（期限切れ / 今週 / 未学習） */
export function dueCounts(records: RecordRow[], now: Date = new Date()): DueCounts {
  const nowMs = now.getTime();
  const weekMs = nowMs + 7 * DAY_MS;

  let overdue = 0;
  let withinWeek = 0;
  let unlearned = 0;

  for (const record of records) {
    if (record.next_review === null) {
      unlearned += 1;
      continue;
    }
    const next = Date.parse(record.next_review);
    if (next <= nowMs) overdue += 1;
    if (next <= weekMs) withinWeek += 1;
  }

  return { overdue, withinWeek, unlearned };
}
