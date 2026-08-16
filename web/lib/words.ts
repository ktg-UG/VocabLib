/**
 * 単語一覧の絞り込み
 *
 * `lib/stats.ts` と同じ方針で、SupabaseもReactもimportしない純粋関数にする。
 * 数百語まではサーバーに問い合わせず、ここで絞る方が速い。
 */
import type { RecordRow, WordRow } from "./types";

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

/** 一覧の1行ぶん。単語そのものと、学習記録から導いた指標 */
export type WordSummary = {
  word: WordRow;
  /** 正答率 0-100。まだ出題されていなければ null */
  accuracy: number | null;
  seen: number;
  correct: number;
  /** 次回復習まで何日か。マイナスは期限切れ。未学習は null */
  dueInDays: number | null;
};

/**
 * 単語に学習記録を合流させる。
 *
 * 一覧で「どれが弱いか」を見るのに、行ごとの正答率が要る。
 * `stats.ts` の集計と違い、こちらは `learning_records` の累計をそのまま使う
 * （回答ログを全部走査しなくて済み、単語数が増えても重くならない）。
 */
export function summarizeWords(
  words: WordRow[],
  records: RecordRow[],
  now: Date = new Date(),
): WordSummary[] {
  const byWord = new Map(records.map((r) => [r.word_id, r]));

  return words.map((word) => {
    const record = byWord.get(word.id);
    const seen = record?.total_seen ?? 0;
    const correct = record?.total_correct ?? 0;

    let dueInDays: number | null = null;
    if (record?.next_review) {
      const diff = Date.parse(record.next_review) - now.getTime();
      // 切り上げにする。あと数時間なら「0日後」ではなく「1日後」と出したい
      dueInDays = Math.ceil(diff / (24 * 60 * 60 * 1000));
    }

    return {
      word,
      accuracy: seen === 0 ? null : (correct / seen) * 100,
      seen,
      correct,
      dueInDays,
    };
  });
}

/**
 * タグに色を割り当てる。
 *
 * タグは後から増えるので固定表を持てない。名前から決定的に色相を決める。
 * **彩度と明度は固定**し、色相だけ変える。派手にすると「AIっぽいUI」で
 * 挙げた「意味の無い色数の多さ」に逆戻りするため。
 */
export function tagHue(tag: string): number {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = (hash * 31 + tag.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % 360;
}
