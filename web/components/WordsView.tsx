"use client";

import { useMemo, useState } from "react";

import type { WordRow } from "@/lib/types";
import { countTags, filterWords } from "@/lib/words";

/**
 * 単語一覧
 *
 * 絞り込みはサーバーに問い合わせず、手元の配列で行う（数百語までは十分速い）。
 * 判定ロジックは `lib/words.ts` の純粋関数に置いてテスト済み。
 */
export function WordsView({ words }: { words: WordRow[] }) {
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState<string | null>(null);

  const tags = useMemo(() => countTags(words), [words]);
  const visible = useMemo(
    () => filterWords(words, { query, tag }),
    [words, query, tag],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="英単語・和訳で検索"
          className="min-w-0 flex-1 rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm placeholder:text-ink-weak focus:border-accent focus:outline-none"
        />
      </div>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <TagChip
            label="すべて"
            count={words.length}
            active={tag === null}
            onClick={() => setTag(null)}
          />
          {tags.map((item) => (
            <TagChip
              key={item.tag}
              label={item.tag}
              count={item.count}
              active={tag === item.tag}
              onClick={() => setTag(item.tag)}
            />
          ))}
        </div>
      )}

      {visible.length === 0 ? (
        <p className="py-8 text-center text-sm text-ink-weak">
          条件に合う単語がありません。
        </p>
      ) : (
        /* カードで囲まない。行そのものが単位なので、外枠は階層を1段無駄にする */
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-ink-weak">
              <th className="pb-2 font-normal">英単語</th>
              <th className="pb-2 font-normal">和訳</th>
              <th className="pb-2 font-normal">品詞</th>
              <th className="pb-2 font-normal">タグ</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((word) => (
              <tr key={word.id} className="border-b border-border/60 align-top">
                <td className="py-2.5 pr-3 font-medium">{word.english}</td>
                <td className="py-2.5 pr-3 text-ink-mute">{word.japanese}</td>
                <td className="py-2.5 pr-3 text-xs text-ink-weak whitespace-nowrap">
                  {word.part_of_speech ?? "—"}
                </td>
                <td className="py-2.5 text-xs text-ink-weak whitespace-nowrap">
                  {word.tag || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="text-xs text-ink-weak">
        {visible.length === words.length
          ? `${words.length}語`
          : `${visible.length} / ${words.length}語`}
      </p>
    </div>
  );
}

function TagChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-xs transition ${
        active
          ? "bg-accent text-surface-raised"
          : "bg-accent-weak text-ink-mute hover:text-ink"
      }`}
    >
      {label}
      <span className="ml-1.5 opacity-70">{count}</span>
    </button>
  );
}
