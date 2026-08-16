/**
 * 集計ロジックのテスト（ネットワークにもDBにも触らない）
 *
 * 最大の関心事は JST の扱い。Mac アプリ側（Python）と結果が一致しないと、
 * 同じデータなのに画面によって連続日数が違う、という事故になる。
 */
import { describe, expect, it } from "vitest";

import {
  answersByDate,
  currentStreak,
  dailyAccuracy,
  dueCounts,
  jstToday,
  overallStats,
  toJstDate,
  weakWords,
} from "./stats";
import type { AnswerRow, RecordRow, WordRow } from "./types";

const answer = (
  answered_at: string,
  is_correct: boolean,
  word_id = "w1",
): AnswerRow => ({
  id: `${word_id}-${answered_at}-${is_correct}`,
  word_id,
  is_correct,
  answered_at,
});

const word = (id: string, english: string, japanese: string): WordRow => ({
  id,
  english,
  japanese,
  part_of_speech: null,
  tag: "",
  example_sentence: null,
  created_at: "2026-08-01T00:00:00+00:00",
  updated_at: "2026-08-01T00:00:00+00:00",
  deleted: false,
});

// ── JSTの日付変換 ─────────────────────────────────────────────────────────

describe("toJstDate", () => {
  it("UTCの日中はそのままの日付になる", () => {
    expect(toJstDate("2026-08-15T03:00:00+00:00")).toBe("2026-08-15");
  });

  it("UTC 15時以降はJSTでは翌日になる", () => {
    expect(toJstDate("2026-08-15T15:30:00+00:00")).toBe("2026-08-16");
  });

  it("JST深夜の回答がその日に数えられる", () => {
    // UTC 8/15 20:00 = JST 8/16 05:00。UTC基準だと前日に数えてしまう
    expect(toJstDate("2026-08-15T20:00:00+00:00")).toBe("2026-08-16");
  });

  it("Z表記でも同じ結果になる", () => {
    expect(toJstDate("2026-08-15T15:30:00Z")).toBe("2026-08-16");
  });
});

describe("jstToday", () => {
  it("UTC深夜でもJSTの日付を返す", () => {
    expect(jstToday(new Date("2026-08-15T16:00:00Z"))).toBe("2026-08-16");
  });
});

// ── 通算 ──────────────────────────────────────────────────────────────────

describe("overallStats", () => {
  it("回答数と正答率を計算できる", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", true),
      answer("2026-08-15T02:00:00+00:00", false),
      answer("2026-08-15T03:00:00+00:00", true),
    ];
    expect(overallStats(rows)).toEqual({
      total: 3,
      correct: 2,
      incorrect: 1,
      accuracy: (2 / 3) * 100,
    });
  });

  it("回答が無ければ0を返す", () => {
    expect(overallStats([])).toEqual({
      total: 0,
      correct: 0,
      incorrect: 0,
      accuracy: 0,
    });
  });
});

// ── 日別 ──────────────────────────────────────────────────────────────────

describe("dailyAccuracy", () => {
  const now = new Date("2026-08-15T06:00:00Z"); // JST 8/15 15:00

  it("同じ日の回答がまとまる", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", true),
      answer("2026-08-15T02:00:00+00:00", false),
    ];
    const points = dailyAccuracy(rows, 3, now);
    const today = points.at(-1)!;

    expect(today.date).toBe("2026-08-15");
    expect(today.total).toBe(2);
    expect(today.accuracy).toBe(50);
  });

  it("回答が無い日も0件として並ぶ", () => {
    const points = dailyAccuracy([], 7, now);

    expect(points).toHaveLength(7);
    expect(points.every((p) => p.total === 0)).toBe(true);
  });

  it("古い順に並ぶ", () => {
    const points = dailyAccuracy([], 3, now);
    expect(points.map((p) => p.date)).toEqual([
      "2026-08-13",
      "2026-08-14",
      "2026-08-15",
    ]);
  });
});

// ── 連続学習日数 ──────────────────────────────────────────────────────────

describe("currentStreak", () => {
  const now = new Date("2026-08-15T06:00:00Z"); // JST 8/15

  it("回答が無ければ0", () => {
    expect(currentStreak([], now)).toBe(0);
  });

  it("今日だけなら1", () => {
    expect(currentStreak([answer("2026-08-15T01:00:00+00:00", true)], now)).toBe(1);
  });

  it("連続した日数を数える", () => {
    const rows = [
      answer("2026-08-13T01:00:00+00:00", true),
      answer("2026-08-14T01:00:00+00:00", true),
      answer("2026-08-15T01:00:00+00:00", true),
    ];
    expect(currentStreak(rows, now)).toBe(3);
  });

  it("今日未回答でも昨日まで続いていれば継続扱い", () => {
    // Macアプリの Store.get_streak() と同じ仕様。ここがずれると画面ごとに数字が変わる
    const rows = [
      answer("2026-08-13T01:00:00+00:00", true),
      answer("2026-08-14T01:00:00+00:00", true),
    ];
    expect(currentStreak(rows, now)).toBe(2);
  });

  it("2日以上空いたら0", () => {
    const rows = [answer("2026-08-10T01:00:00+00:00", true)];
    expect(currentStreak(rows, now)).toBe(0);
  });

  it("途切れた分は数えない", () => {
    const rows = [
      answer("2026-08-10T01:00:00+00:00", true), // 途切れている
      answer("2026-08-14T01:00:00+00:00", true),
      answer("2026-08-15T01:00:00+00:00", true),
    ];
    expect(currentStreak(rows, now)).toBe(2);
  });

  it("同じ日に何度回答しても1日と数える", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", true),
      answer("2026-08-15T02:00:00+00:00", true),
      answer("2026-08-15T03:00:00+00:00", true),
    ];
    expect(currentStreak(rows, now)).toBe(1);
  });
});

// ── ヒートマップ ──────────────────────────────────────────────────────────

describe("answersByDate", () => {
  it("日付ごとの回答数を返す", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", true),
      answer("2026-08-15T02:00:00+00:00", false),
      answer("2026-08-14T01:00:00+00:00", true),
    ];
    const counts = answersByDate(rows);

    expect(counts.get("2026-08-15")).toBe(2);
    expect(counts.get("2026-08-14")).toBe(1);
  });
});

// ── 苦手単語 ──────────────────────────────────────────────────────────────

describe("weakWords", () => {
  const words = [
    word("w1", "postpone", "延期する"),
    word("w2", "abandon", "見捨てる"),
  ];

  it("誤答が多い順に並ぶ", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", false, "w1"),
      answer("2026-08-15T02:00:00+00:00", false, "w1"),
      answer("2026-08-15T03:00:00+00:00", false, "w2"),
      answer("2026-08-15T04:00:00+00:00", true, "w2"),
    ];
    const result = weakWords(rows, words);

    expect(result[0].english).toBe("postpone");
    expect(result[0].incorrect).toBe(2);
    expect(result[0].errorRate).toBe(100);
    expect(result[1].english).toBe("abandon");
    expect(result[1].errorRate).toBe(50);
  });

  it("全問正解の単語は含まれない", () => {
    const rows = [answer("2026-08-15T01:00:00+00:00", true, "w1")];
    expect(weakWords(rows, words)).toEqual([]);
  });

  it("削除された単語は集計しない", () => {
    const rows = [answer("2026-08-15T01:00:00+00:00", false, "deleted-word")];
    expect(weakWords(rows, words)).toEqual([]);
  });

  it("件数を制限できる", () => {
    const rows = [
      answer("2026-08-15T01:00:00+00:00", false, "w1"),
      answer("2026-08-15T02:00:00+00:00", false, "w2"),
    ];
    expect(weakWords(rows, words, 1)).toHaveLength(1);
  });
});

// ── 復習予定数 ────────────────────────────────────────────────────────────

describe("dueCounts", () => {
  const now = new Date("2026-08-15T00:00:00Z");
  const record = (next_review: string | null): RecordRow => ({
    word_id: `w-${next_review}`,
    next_review,
    total_correct: 0,
    total_seen: 0,
  });

  it("期限切れ・今週・未学習を区分できる", () => {
    const records = [
      record("2026-08-14T00:00:00+00:00"), // 期限切れ
      record("2026-08-17T00:00:00+00:00"), // 今週
      record("2026-09-30T00:00:00+00:00"), // 先
      record(null), // 未学習
    ];

    // 期限切れは「今週」にも含まれる（Macアプリの get_due_counts と同じ）
    expect(dueCounts(records, now)).toEqual({
      overdue: 1,
      withinWeek: 2,
      unlearned: 1,
    });
  });

  it("記録が無ければ全て0", () => {
    expect(dueCounts([], now)).toEqual({
      overdue: 0,
      withinWeek: 0,
      unlearned: 0,
    });
  });
});
