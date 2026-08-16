/**
 * タグの正規化と入力書式のパース
 *
 * **Python の `src/tags.py` と同じ規則を実装している。**
 * 片方だけ直る事故を防ぐため、`tags.test.ts` には `tests/test_tags.py` と
 * 同じケースを並べてある。どちらかを変えるときは両方を直すこと。
 *
 * 1単語につきタグは1つ。空文字が「タグなし」を表す。
 */

/** 入力欄でタグを書き始める記号。`incorporation #TOEIC` のように使う */
export const TAG_PREFIX = "#";

/**
 * タグを保存できる形に整える。空文字は「タグなし」。
 *
 * - 前後の空白を除去する
 * - 先頭の `#` を取る
 * - 内側の空白は保つ（`TOEIC Part5` を1つのタグとして許す）
 * - 大文字小文字は変換しない（表示にそのまま使うため）
 * - カンマを除去する（一括インポートの区切り文字と衝突するため）
 */
export function normalizeTag(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .trim()
    .replace(/^#+/, "")
    .replace(/,/g, "")
    .trim();
}

/**
 * 英単語の入力を [英単語, タグ] に分ける。
 *
 * 英単語側に空白を含むフレーズ（`extend an invitation to`）があるため、
 * 空白ではなく **最初の `#`** で1回だけ分割する。
 */
export function parseWordInput(text: string): [string, string] {
  if (!text) return ["", ""];

  const index = text.indexOf(TAG_PREFIX);
  if (index === -1) return [text.trim(), ""];

  return [text.slice(0, index).trim(), normalizeTag(text.slice(index + 1))];
}
