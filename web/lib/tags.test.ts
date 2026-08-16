/**
 * `lib/tags.ts` のテスト
 *
 * **`tests/test_tags.py`（Python版）と同じケースを並べてある。**
 * どちらか片方だけ規則が変わると、ここと向こうで結果がずれる。
 * 追加・変更するときは両方に同じケースを足すこと。
 */
import { describe, expect, it } from "vitest";

import { normalizeTag, parseWordInput } from "./tags";

describe("normalizeTag", () => {
  it("前後の空白を除去する", () => {
    expect(normalizeTag("  TOEIC  ")).toBe("TOEIC");
  });

  it("先頭のシャープを取る", () => {
    expect(normalizeTag("#TOEIC")).toBe("TOEIC");
  });

  it("シャープと空白が混ざっていても取れる", () => {
    expect(normalizeTag(" # TOEIC ")).toBe("TOEIC");
  });

  it("内側の空白は保つ", () => {
    expect(normalizeTag("TOEIC Part5")).toBe("TOEIC Part5");
  });

  it("大文字小文字は変換しない", () => {
    expect(normalizeTag("toeic")).toBe("toeic");
  });

  it("カンマを除去する", () => {
    expect(normalizeTag("TOEIC,ビジネス")).toBe("TOEICビジネス");
  });

  it("空文字とnullはタグなし", () => {
    expect(normalizeTag("")).toBe("");
    expect(normalizeTag(null)).toBe("");
    expect(normalizeTag(undefined)).toBe("");
    expect(normalizeTag("   ")).toBe("");
    expect(normalizeTag("#")).toBe("");
  });
});

describe("parseWordInput", () => {
  it("シャープ以降がタグになる", () => {
    expect(parseWordInput("incorporation #TOEIC")).toEqual([
      "incorporation",
      "TOEIC",
    ]);
  });

  it("シャープが無ければタグなし", () => {
    expect(parseWordInput("incorporation")).toEqual(["incorporation", ""]);
  });

  it("空白を含むフレーズでも切れる", () => {
    expect(parseWordInput("extend an invitation to #TOEIC")).toEqual([
      "extend an invitation to",
      "TOEIC",
    ]);
  });

  it("シャープの後の空白は無視する", () => {
    expect(parseWordInput("yield # TOEIC")).toEqual(["yield", "TOEIC"]);
  });

  it("シャープだけならタグなし", () => {
    expect(parseWordInput("yield #")).toEqual(["yield", ""]);
  });

  it("最初のシャープで1回だけ切る", () => {
    expect(parseWordInput("yield #a#b")).toEqual(["yield", "a#b"]);
  });

  it("空入力", () => {
    expect(parseWordInput("")).toEqual(["", ""]);
  });
});
