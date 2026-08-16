import { describe, expect, it } from "vitest";

import type { WordRow } from "./types";
import { countTags, filterWords } from "./words";

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
