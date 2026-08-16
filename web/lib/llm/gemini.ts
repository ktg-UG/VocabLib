import "server-only";

/**
 * Gemini 呼び出し（サーバー専用）
 *
 * **Macとの決定的な違い: 2段目が無い。**
 * Macは Gemini → Ollama → ローカル生成 の3段だが（SPEC 12.5）、Ollamaは
 * 開発者のMacの localhost:11434 で動いており、Vercelのサーバーからは到達できない。
 * ここでは失敗を正直に返し、手入力してもらう。品質の低い文字列をでっち上げても、
 * 覚える助けにならないものがDBにキャッシュされるだけで害になる。
 *
 * `server-only` を付けているので、うっかりクライアントから import すると
 * ビルドが落ちる（APIキーがブラウザのバンドルに焼き込まれる事故を防ぐ）。
 */
import { extractExampleLine, extractJson, looksJapanese, sentenceUsesWord } from "./parsing";

const MODEL = process.env.GEMINI_MODEL?.trim() || "gemini-3.7-flash";
const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";

const MAX_MEANING_LENGTH = 40;
const MAX_POS_LENGTH = 10;

/** キー未設定でもアプリは動く。オートフィルのボタンを無効にするだけ */
export function isGeminiConfigured(): boolean {
  return Boolean(process.env.GEMINI_API_KEY?.trim());
}

export type WordInfo = {
  japanese: string;
  partOfSpeech: string | null;
};

async function complete(prompt: string, timeoutMs = 20_000): Promise<string | null> {
  const apiKey = process.env.GEMINI_API_KEY?.trim();
  if (!apiKey) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${ENDPOINT}/${MODEL}:generateContent`, {
      method: "POST",
      // キーはヘッダーで送る。URLに入れるとログや履歴に残りやすい
      headers: { "content-type": "application/json", "x-goog-api-key": apiKey },
      body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
      signal: controller.signal,
    });

    if (!response.ok) {
      // 429 はクォータ超過、503 はGoogle側の混雑。どちらも呼び出し側で
      // 「取得できませんでした」として扱う（握りつぶさずログには残す）
      console.warn(`Gemini 呼び出し失敗: ${response.status} ${await response.text()}`);
      return null;
    }

    const data = await response.json();
    const text: unknown =
      data?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text).join("");
    return typeof text === "string" && text.trim() ? text.trim() : null;
  } catch (error) {
    console.warn("Gemini 呼び出し失敗:", error);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 和訳と品詞を引く。取得できなければ null（空欄で手入力してもらう）。
 *
 * プロンプトは `src/llm/client.py` の `_lookup_prompt` と同じ文面。
 * 片方だけ変えると、MacとWebで違う品質の下書きが入ることになる。
 */
export async function lookupWord(english: string): Promise<WordInfo | null> {
  const raw = await complete(lookupPrompt(english));
  if (!raw) return null;

  const parsed = extractJson(raw);
  if (!parsed) return null;

  const japanese = String(parsed.japanese ?? "").trim();
  if (!japanese || japanese.length > MAX_MEANING_LENGTH) return null;
  // 英語のまま返ってきた場合はオートフィルとして役に立たない
  if (!looksJapanese(japanese)) return null;

  let partOfSpeech = String(parsed.part_of_speech ?? "").trim();
  if (partOfSpeech.length > MAX_POS_LENGTH) partOfSpeech = "";

  return { japanese, partOfSpeech: partOfSpeech || null };
}

/**
 * 例文を生成する。**対象単語を含まない例文は採用しない。**
 * Macと違い最終フォールバックは無いので、駄目なら null を返す。
 */
export async function generateExample(
  word: string,
  meaning: string,
): Promise<string | null> {
  const raw = await complete(examplePrompt(word, meaning));
  if (!raw) return null;

  const sentence = extractExampleLine(raw);
  if (!sentence) return null;
  if (!sentenceUsesWord(sentence, word)) return null;

  return sentence;
}

// ── プロンプト（src/llm/client.py と同じ文面） ─────────────────────────

function lookupPrompt(english: string): string {
  return `英単語「${english}」の最も一般的な日本語訳と品詞を1つだけ答えてください。

【必須ルール】
- 意味は最も基本的・頻出のもの**1つだけ**（複数書かない）
- 動詞は「〜する」の形、名詞は名詞のまま書くこと
- 品詞は次のいずれか1語: 名詞 / 動詞 / 形容詞 / 副詞 / 前置詞 / 接続詞 / 代名詞 / 間投詞 / 熟語
- 和訳は必ず自然な**日本語**で書くこと（中国語・英語は絶対に使わない）

以下のJSON形式のみを出力してください。説明文・コードブロックは不要:
{"japanese": "延期する", "part_of_speech": "動詞"}`;
}

function examplePrompt(word: string, meaning: string): string {
  return `英単語「${word}」（意味: ${meaning}）を使った、短くて記憶に残る英語の例文を1つ作ってください。

【必須ルール】
- 例文には必ず「${word}」を含めること（活用形・語形変化は可）
- 5〜8語程度の短い文にすること
- 具体的な情景が浮かぶ、覚えやすい内容にすること
- 和訳は必ず自然な**日本語**で書くこと（中国語は絶対に使わない）

出力は次の1行だけ。番号・説明・引用符は不要:
英語の例文 — 日本語訳

例: Cats abandon their owners daily. — 猫は毎日飼い主を見捨てる。
例: He postponed the meeting again. — 彼はまた会議を延期した。`;
}
