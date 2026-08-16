"use client";

import { useMemo, useState } from "react";

import type { RecordRow, WordRow } from "@/lib/types";
import {
  countTags,
  filterWords,
  summarizeWords,
  tagHue,
  type WordSummary,
} from "@/lib/words";

/**
 * 単語一覧
 *
 * 絞り込みはサーバーに問い合わせず、手元の配列で行う（数百語までは十分速い）。
 * 判定ロジックは `lib/words.ts` の純粋関数に置いてテスト済み。
 *
 * 表は「英単語と和訳だけ」にしない。一覧を眺めたときに
 * **どれが弱いか・いつ復習が来るか**が分かることに価値がある。
 */
export function WordsView({
  words,
  records,
}: {
  words: WordRow[];
  records: RecordRow[];
}) {
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const tags = useMemo(() => countTags(words), [words]);
  const summaries = useMemo(() => {
    const filtered = filterWords(words, { query, tag });
    return summarizeWords(filtered, records);
  }, [words, records, query, tag]);

  return (
    <div className="flex flex-col gap-4">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="英単語・和訳で検索"
        className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm placeholder:text-ink-weak focus:border-accent focus:outline-none"
      />

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

      {summaries.length === 0 ? (
        <p className="py-10 text-center text-sm text-ink-weak">
          条件に合う単語がありません。
        </p>
      ) : (
        /* カードで囲まない。行そのものが単位なので、外枠は階層を1段無駄にする */
        <ul className="border-t border-border">
          {summaries.map((summary) => (
            <WordRowItem
              key={summary.word.id}
              summary={summary}
              open={openId === summary.word.id}
              onToggle={() =>
                setOpenId(openId === summary.word.id ? null : summary.word.id)
              }
            />
          ))}
        </ul>
      )}

      <p className="text-xs text-ink-weak">
        {summaries.length === words.length
          ? `${words.length}語`
          : `${summaries.length} / ${words.length}語`}
      </p>
    </div>
  );
}

function WordRowItem({
  summary,
  open,
  onToggle,
}: {
  summary: WordSummary;
  open: boolean;
  onToggle: () => void;
}) {
  const { word, accuracy, seen, correct, dueInDays } = summary;

  return (
    <li className="border-b border-border">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-baseline gap-3 py-2.5 text-left transition hover:bg-accent-weak/60"
      >
        {/* 英単語を主役に。和訳は一段弱い色に落とす */}
        <span className="min-w-0 flex-1">
          <span className="font-medium">{word.english}</span>
          <span className="ml-2 text-sm text-ink-mute">{word.japanese}</span>
        </span>

        {word.tag && <TagBadge tag={word.tag} />}

        <MasteryBar accuracy={accuracy} />

        <span className="w-16 shrink-0 text-right text-[11px] text-ink-weak">
          {formatDue(dueInDays)}
        </span>
      </button>

      {open && (
        <div className="grid gap-2 pb-3 pl-1 text-xs text-ink-mute">
          <div className="flex flex-wrap gap-x-5 gap-y-1">
            <span>品詞: {word.part_of_speech ?? "未設定"}</span>
            <span>
              成績: {correct} / {seen}問
              {accuracy !== null && `（${Math.round(accuracy)}%）`}
            </span>
          </div>
          <p className="text-ink-mute">
            {word.example_sentence ?? (
              <span className="text-ink-weak">
                例文はまだありません（不正解のときに生成されます）
              </span>
            )}
          </p>
        </div>
      )}
    </li>
  );
}

/**
 * 習熟度バー
 *
 * 数字を読ませるより、並べたときに弱い単語が目に飛び込む方が速い。
 * 色は正誤の2色だけを使い、閾値で切り替える（グラデーションにしない）。
 */
function MasteryBar({ accuracy }: { accuracy: number | null }) {
  if (accuracy === null) {
    return (
      <span className="w-14 shrink-0 text-right text-[11px] text-ink-weak">未学習</span>
    );
  }

  const color =
    accuracy >= 80 ? "bg-positive" : accuracy >= 50 ? "bg-accent" : "bg-negative";

  return (
    <span
      className="h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-border"
      title={`正答率 ${Math.round(accuracy)}%`}
    >
      <span
        className={`block h-full rounded-full ${color}`}
        style={{ width: `${Math.max(accuracy, 4)}%` }}
      />
    </span>
  );
}

/**
 * タグのバッジ
 *
 * 色相だけタグ名から決め、彩度・明度は固定する。
 * 派手にすると「意味の無い色数の多さ」に逆戻りするため、面積も小さく保つ。
 */
function TagBadge({ tag }: { tag: string }) {
  const hue = tagHue(tag);
  return (
    <span
      className="shrink-0 rounded-full px-2 py-0.5 text-[11px] whitespace-nowrap"
      style={{
        backgroundColor: `light-dark(hsl(${hue} 42% 92%), hsl(${hue} 30% 22%))`,
        color: `light-dark(hsl(${hue} 45% 32%), hsl(${hue} 55% 78%))`,
      }}
    >
      {tag}
    </span>
  );
}

function formatDue(days: number | null): string {
  if (days === null) return "—";
  if (days < 0) return `${-days}日超過`;
  if (days === 0) return "今日";
  return `${days}日後`;
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
