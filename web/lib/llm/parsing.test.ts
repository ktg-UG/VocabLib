/**
 * `lib/llm/parsing.ts` のテスト
 *
 * **`tests/test_llm_parsing.py`（Python版）と同じケースを並べてある。**
 * 同じ検証を2言語で持つことになるので、片方だけ規則が変わると
 * ここと向こうで結果がずれる。どちらかを直すときは必ず両方に手を入れること。
 */
import { describe, expect, it } from "vitest";

import {
  extractExampleLine,
  extractJson,
  looksJapanese,
  sentenceUsesWord,
} from "./parsing";

describe("extractExampleLine", () => {
  it("例文行を抽出できる", () => {
    const out = "He postponed the meeting. — 彼は会議を延期した。";
    expect(extractExampleLine(out)).toBe(
      "He postponed the meeting. — 彼は会議を延期した。",
    );
  });

  it("先頭の例マーカーを取り除く", () => {
    const out = "例: He postponed the meeting. — 彼は会議を延期した。";
    expect(extractExampleLine(out)?.startsWith("He postponed")).toBe(true);
  });

  it("箇条書きや番号のマーカーも取り除く", () => {
    expect(extractExampleLine("1. A — B")?.startsWith("A")).toBe(true);
    expect(extractExampleLine("- A — B")?.startsWith("A")).toBe(true);
    expect(extractExampleLine("・A — B")?.startsWith("A")).toBe(true);
  });

  it("区切り記号を全角ダッシュに正規化する", () => {
    // LLMは — / – / - を気分で使い分けるので、表示前に揃える
    expect(extractExampleLine("A – B")).toBe("A — B");
    expect(extractExampleLine("A - B")).toBe("A — B");
  });

  it("コードフェンスの行を無視する", () => {
    const out = "```\nHe postponed it. — 彼は延期した。\n```";
    expect(extractExampleLine(out)).toBe("He postponed it. — 彼は延期した。");
  });

  it("説明文が混ざっていても例文行を拾う", () => {
    const out = "はい、例文を作成しました。\n\nHe postponed it. — 彼は延期した。";
    expect(extractExampleLine(out)).toBe("He postponed it. — 彼は延期した。");
  });

  it("区切りが無ければnullを返す", () => {
    // 形式が不正なら採用しない
    expect(extractExampleLine("He postponed the meeting.")).toBeNull();
    expect(extractExampleLine("")).toBeNull();
  });
});

describe("sentenceUsesWord", () => {
  it("単語をそのまま含む例文を通す", () => {
    expect(sentenceUsesWord("He will postpone it. — 彼は延期する。", "postpone")).toBe(
      true,
    );
  });

  it("語尾変化した単語も通す", () => {
    // LLMは活用形で出してくる。原形一致だけだと弾いてしまう
    expect(sentenceUsesWord("He postponed it. — 彼は延期した。", "postpone")).toBe(true);
    expect(
      sentenceUsesWord("He is postponing it. — 彼は延期している。", "postpone"),
    ).toBe(true);
  });

  it("無関係な例文を弾く", () => {
    expect(sentenceUsesWord("The cat sleeps well. — 猫はよく眠る。", "postpone")).toBe(
      false,
    );
  });

  it("和訳側に単語が出ていても英文側で判定する", () => {
    expect(
      sentenceUsesWord("The cat sleeps. — postpone は延期する。", "postpone"),
    ).toBe(false);
  });

  it("短い単語も判定できる", () => {
    expect(sentenceUsesWord("I run every day. — 毎日走る。", "run")).toBe(true);
    expect(sentenceUsesWord("The cat sleeps. — 猫は眠る。", "run")).toBe(false);
  });
});

describe("extractJson", () => {
  it("素のJSONを読める", () => {
    expect(extractJson('{"japanese": "延期する"}')).toEqual({ japanese: "延期する" });
  });

  it("コードフェンス付きのJSONを読める", () => {
    const out = '```json\n{"japanese": "延期する", "part_of_speech": "動詞"}\n```';
    expect(extractJson(out)?.part_of_speech).toBe("動詞");
  });

  it("説明文が前後についていても読める", () => {
    const out = 'はい、以下が結果です:\n{"japanese": "延期する"}\nご確認ください。';
    expect(extractJson(out)).toEqual({ japanese: "延期する" });
  });

  it("壊れたJSONはnullを返す", () => {
    expect(extractJson("{japanese: 延期する")).toBeNull();
    expect(extractJson("これはJSONではありません")).toBeNull();
  });

  it("JSON配列はnullを返す", () => {
    // オブジェクトを期待しているので配列は受け付けない
    expect(extractJson("[1, 2, 3]")).toBeNull();
  });
});

describe("looksJapanese", () => {
  it("かなを含めば日本語とみなす", () => {
    expect(looksJapanese("延期する")).toBe(true);
    expect(looksJapanese("りんご")).toBe(true);
  });

  it("漢字のみでも日本語とみなす", () => {
    // 「会議」「延期」など漢字だけの和訳は正当なので弾いてはいけない
    expect(looksJapanese("会議")).toBe(true);
  });

  it("英語のみは日本語とみなさない", () => {
    expect(looksJapanese("postpone")).toBe(false);
    expect(looksJapanese("")).toBe(false);
  });
});
