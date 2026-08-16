import { describe, expect, it } from "vitest";

import type { WordRow } from "./types";
import { countTags, filterWords, summarizeWords, tagHue } from "./words";

const word = (
  english: string,
  japanese: string,
  tag = "",
): WordRow => ({
  id: english,
  english,
  japanese,
  part_of_speech: null,
  tag,
  example_sentence: null,
  created_at: "2026-08-01T00:00:00+00:00",
  updated_at: "2026-08-01T00:00:00+00:00",
  deleted: false,
});

const words = [
  word("incorporation", "法人設立、組み入れ", "TOEIC"),
  word("yield", "産出する、もたらす", "TOEIC"),
  word("apple", "りんご", "日常"),
];

const all = { query: "", tag: null };

describe("filterWords", () => {
  it("空クエリなら全件返す", () => {
    expect(filterWords(words, all)).toHaveLength(3);
  });

  it("英単語で一致する", () => {
    expect(filterWords(words, { ...all, query: "yield" })).toEqual([words[1]]);
  });

  it("和訳でも一致する", () => {
    // 英語で思い出せないときに和訳から引けること
    expect(filterWords(words, { ...all, query: "法人" })).toEqual([words[0]]);
  });

  it("部分一致で引ける", () => {
    expect(filterWords(words, { ...all, query: "corp" })).toEqual([words[0]]);
  });

  it("大文字小文字を無視する", () => {
    expect(filterWords(words, { ...all, query: "YIELD" })).toEqual([words[1]]);
  });

  it("前後の空白を無視する", () => {
    expect(filterWords(words, { ...all, query: "  yield  " })).toEqual([words[1]]);
  });

  it("タグで絞り込める", () => {
    expect(filterWords(words, { query: "", tag: "TOEIC" })).toHaveLength(2);
  });

  it("タグと検索語は両方効く", () => {
    expect(filterWords(words, { query: "りんご", tag: "TOEIC" })).toEqual([]);
  });

  it("該当が無ければ空", () => {
    expect(filterWords(words, { ...all, query: "存在しない" })).toEqual([]);
  });
});

describe("countTags", () => {
  it("語数の多い順に返す", () => {
    expect(countTags(words)).toEqual([
      { tag: "TOEIC", count: 2 },
      { tag: "日常", count: 1 },
    ]);
  });

  it("タグなしは含めない", () => {
    expect(countTags([word("postpone", "延期する")])).toEqual([]);
  });

  it("単語が無ければ空", () => {
    expect(countTags([])).toEqual([]);
  });
});

describe("summarizeWords", () => {
  const now = new Date("2026-08-16T00:00:00Z");
  const record = (
    word_id: string,
    total_seen: number,
    total_correct: number,
    next_review: string | null,
  ) => ({ word_id, total_seen, total_correct, next_review });

  it("学習記録から正答率を出す", () => {
    const result = summarizeWords(
      [word("yield", "産出する")],
      [record("yield", 10, 7, null)],
      now,
    );

    expect(result[0].accuracy).toBeCloseTo(70);
    expect(result[0].seen).toBe(10);
    expect(result[0].correct).toBe(7);
  });

  it("出題されていなければ正答率はnull", () => {
    const result = summarizeWords([word("yield", "産出する")], [], now);

    expect(result[0].accuracy).toBeNull();
    expect(result[0].seen).toBe(0);
  });

  it("次回復習までの日数を出す", () => {
    const result = summarizeWords(
      [word("yield", "産出する")],
      [record("yield", 3, 3, "2026-08-19T00:00:00Z")],
      now,
    );

    expect(result[0].dueInDays).toBe(3);
  });

  it("期限切れはマイナスになる", () => {
    const result = summarizeWords(
      [word("yield", "産出する")],
      [record("yield", 3, 3, "2026-08-14T00:00:00Z")],
      now,
    );

    expect(result[0].dueInDays).toBe(-2);
  });

  it("数時間後は0日ではなく1日後として扱う", () => {
    // 「今日中に来る」ものを「0日後」と出すと期限切れと紛らわしい
    const result = summarizeWords(
      [word("yield", "産出する")],
      [record("yield", 3, 3, "2026-08-16T18:00:00Z")],
      now,
    );

    expect(result[0].dueInDays).toBe(1);
  });

  it("未学習は日数もnull", () => {
    const result = summarizeWords(
      [word("yield", "産出する")],
      [record("yield", 0, 0, null)],
      now,
    );

    expect(result[0].dueInDays).toBeNull();
  });
});

describe("tagHue", () => {
  it("同じタグは常に同じ色相になる", () => {
    expect(tagHue("TOEIC")).toBe(tagHue("TOEIC"));
  });

  it("違うタグは違う色相になる", () => {
    expect(tagHue("TOEIC")).not.toBe(tagHue("ビジネス"));
  });

  it("0〜359に収まる", () => {
    for (const tag of ["TOEIC", "ビジネス", "IT", "日常", "医療", ""]) {
      expect(tagHue(tag)).toBeGreaterThanOrEqual(0);
      expect(tagHue(tag)).toBeLessThan(360);
    }
  });
});
