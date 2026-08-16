/**
 * 単語一覧の絞り込み
 *
 * `lib/stats.ts` と同じ方針で、SupabaseもReactもimportしない純粋関数にする。
 * 数百語まではサーバーに問い合わせず、ここで絞る方が速い。
 */
import type { WordRow } from "./types";

export type WordFilter = {
  query: string;
  /** null は「すべて」 */
  tag: string | null;
};

/**
 * 検索語とタグで絞り込む。
 *
 * 検索は**英単語と和訳の両方**を対象にする。どちらで思い出すか分からないため。
 * 大文字小文字と前後の空白は無視する。
 */
export function filterWords(words: WordRow[], filter: WordFilter): WordRow[] {
  const query = filter.query.trim().toLowerCase();
  const { tag } = filter;

  return words.filter((word) => {
    if (tag !== null && word.tag !== tag) return false;
    if (!query) return true;
    return (
      word.english.toLowerCase().includes(query) ||
      word.japanese.toLowerCase().includes(query)
    );
  });
}

/**
 * 使われているタグと語数を、多い順に返す。タグなしは含めない。
 *
 * Python の `Store.list_tags()` と同じ並び（件数の降順 → タグ名の昇順）。
 */
export function countTags(words: WordRow[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const word of words) {
    if (!word.tag) continue;
    counts.set(word.tag, (counts.get(word.tag) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
}
