/**
 * LLM出力の抽出・検証
 *
 * **Python の `src/llm/parsing.py` の移植。**
 * v1で実際にLLMに殴られて育った検証をそのまま持ってきている。
 * 片方だけ直る事故を防ぐため、`parsing.test.ts` には
 * `tests/test_llm_parsing.py` と同じケースを並べてある。
 *
 * ここは純粋関数だけ。ネットワークにも環境変数にも触らない。
 */

/** LLMが使う可能性のある区切り記号（em dash / en dash / ハイフン） */
const DASH_PATTERN = /\s*[—–]\s*/;
const LEADING_MARKER = /^\s*(例[:：]|[-*・]|\d+[.)])\s*/;

/**
 * LLM出力から「英文 — 和訳」形式の行を1つ抽出し、区切りを ` — ` に正規化する。
 * 見つからなければ null（呼び出し側は採用しない）。
 */
export function extractExampleLine(out: string): string | null {
  for (const raw of out.trim().split("\n")) {
    let line = raw.trim();
    if (!line || line.startsWith("```")) continue;
    line = line.replace(LEADING_MARKER, "").trim();

    if (line.includes("—") || line.includes("–")) {
      return line.replace(DASH_PATTERN, " — ");
    }
    if (line.includes(" - ")) {
      return line.replace(" - ", " — ");
    }
  }
  return null;
}

/**
 * 例文の英語部分が対象単語を含むか検証する（語尾変化を許容）。
 *
 * LLMは平気で対象単語と無関係な例文を返す。これを通さないと、
 * 覚える助けにならない例文がDBにキャッシュされてしまう。
 */
export function sentenceUsesWord(sentence: string, word: string): boolean {
  const english = sentence.split(/—|–| - /)[0].toLowerCase();
  const tokens = word.toLowerCase().match(/[a-z]+/g) ?? [];

  // 意味を持つ語（4文字以上）を優先。無ければ全トークンで判定
  const significant = tokens.filter((t) => t.length >= 4);
  const targets = significant.length > 0 ? significant : tokens;

  return targets.some((token) => {
    // 語尾変化（-s / -ed / -ing 等）を許容するため末尾2文字を捨てて語幹とみなす
    const stem = token.slice(0, Math.max(4, token.length - 2));
    return english.includes(stem);
  });
}

/**
 * 出力からJSONオブジェクトを1つ抜き出す。
 * コードフェンスや前後の説明文が付いていても取り出せる。
 */
export function extractJson(out: string): Record<string, unknown> | null {
  let cleaned = out.trim().replace(/^```[a-zA-Z0-9]*\n/, "");
  cleaned = cleaned.replace(/\n```$/, "");

  const match = cleaned.match(/\{[\s\S]*\}/);
  const candidate = match ? match[0] : cleaned;

  try {
    const parsed: unknown = JSON.parse(candidate);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * かな・漢字を含むか（＝和訳として採用してよいか）。
 *
 * 小さいモデルは「日本語で」と指示しても英語をそのまま返すことがある。
 * ASCIIだけの出力は和訳ではないので弾く。
 *
 * かなを必須にはしない。「会議」「延期」のような漢字のみの和訳が
 * 正当に存在するため。
 */
export function looksJapanese(text: string): boolean {
  for (const ch of text) {
    if (ch >= "぀" && ch <= "ヿ") return true; // ひらがな・カタカナ
    if (ch >= "一" && ch <= "鿿") return true; // 漢字
  }
  return false;
}
