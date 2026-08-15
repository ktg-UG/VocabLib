import type { WeakWord } from "@/lib/types";

export function WeakWordsTable({ words }: { words: WeakWord[] }) {
  if (words.length === 0) {
    return (
      <p className="text-sm text-black/50 dark:text-white/50">
        まだ間違えた単語がありません。
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-black/50 dark:text-white/50">
            <th className="pb-2 font-normal">単語</th>
            <th className="pb-2 font-normal">意味</th>
            <th className="pb-2 text-right font-normal">誤答</th>
            <th className="pb-2 text-right font-normal">誤答率</th>
          </tr>
        </thead>
        <tbody>
          {words.map((word) => (
            <tr
              key={word.wordId}
              className="border-t border-black/5 dark:border-white/10"
            >
              <td className="py-2 font-medium">{word.english}</td>
              <td className="py-2 text-black/70 dark:text-white/70">{word.japanese}</td>
              <td className="py-2 text-right tabular-nums">
                {word.incorrect}/{word.total}
              </td>
              <td className="py-2 text-right tabular-nums">
                {Math.round(word.errorRate)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
