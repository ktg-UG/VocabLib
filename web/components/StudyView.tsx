"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { RecordRow, WordRow } from "@/lib/types";
import { countTags, summarizeWords, tagHue, type WordSummary } from "@/lib/words";

/**
 * 学習タブ（カード形式）
 *
 * **練習モード。回答を記録しない。**
 * `answer_log` に書かないので統計もSM-2の復習間隔も変わらない。
 * これは SPEC 1.4（出題はMac）を崩さないための線引きでもあり、
 * SM-2の計算をTypeScriptで再実装せずに済む（Python版とずれると復習間隔が壊れる）。
 */

type Scope = "all" | "weak" | "due" | "unlearned";

const SCOPES: { key: Scope; label: string }[] = [
  { key: "all", label: "すべて" },
  { key: "weak", label: "苦手" },
  { key: "due", label: "復習期限" },
  { key: "unlearned", label: "未学習" },
];

function inScope(summary: WordSummary, scope: Scope): boolean {
  switch (scope) {
    case "weak":
      return summary.accuracy !== null && summary.accuracy < 70;
    case "due":
      return summary.dueInDays !== null && summary.dueInDays <= 0;
    case "unlearned":
      return summary.seen === 0;
    default:
      return true;
  }
}

/** 固定シードのシャッフル（同じ順番を再現できるよう seed を持たせる） */
function shuffle<T>(items: T[], seed: number): T[] {
  const result = [...items];
  let a = seed;
  for (let i = result.length - 1; i > 0; i--) {
    a = (a * 1103515245 + 12345) & 0x7fffffff;
    const j = a % (i + 1);
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

export function StudyView({
  words,
  records,
}: {
  words: WordRow[];
  records: RecordRow[];
}) {
  const [scope, setScope] = useState<Scope>("all");
  const [tag, setTag] = useState<string | null>(null);
  const [seed, setSeed] = useState(1);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [reverse, setReverse] = useState(false);

  const tags = useMemo(() => countTags(words), [words]);

  const deck = useMemo(() => {
    const all = summarizeWords(words, records);
    const filtered = all.filter(
      (s) => inScope(s, scope) && (tag === null || s.word.tag === tag),
    );
    return shuffle(filtered, seed);
  }, [words, records, scope, tag, seed]);

  // 条件を変えるとカードが入れ替わるので、必ず先頭の表から始める
  useEffect(() => {
    setIndex(0);
    setFlipped(false);
  }, [scope, tag, seed]);

  const move = useCallback(
    (step: number) => {
      if (deck.length === 0) return;
      setIndex((i) => (i + step + deck.length) % deck.length);
      setFlipped(false);
    },
    [deck.length],
  );

  // キーボードで進められないとカード学習は続かない
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === " ") {
        event.preventDefault();
        setFlipped((f) => !f);
      } else if (event.key === "ArrowRight") {
        move(1);
      } else if (event.key === "ArrowLeft") {
        move(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);

  const current = deck[index];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        {SCOPES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            active={scope === item.key}
            onClick={() => setScope(item.key)}
          />
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        <Chip label="すべての分野" active={tag === null} onClick={() => setTag(null)} />
        {tags.map((item) => (
          <Chip
            key={item.tag}
            label={item.tag}
            active={tag === item.tag}
            onClick={() => setTag(item.tag)}
          />
        ))}
      </div>

      {deck.length === 0 ? (
        <p className="py-16 text-center text-sm text-ink-weak">
          条件に合う単語がありません。
        </p>
      ) : (
        <>
          <Card summary={current} flipped={flipped} reverse={reverse} />

          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => move(-1)}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-ink-mute transition hover:text-ink"
            >
              前へ
            </button>

            <button
              type="button"
              onClick={() => setFlipped((f) => !f)}
              className="flex-1 rounded-md bg-accent px-4 py-2 text-sm font-medium text-surface-raised transition hover:opacity-90"
            >
              {flipped ? "英語に戻す" : "答えを見る"}
            </button>

            <button
              type="button"
              onClick={() => move(1)}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-ink-mute transition hover:text-ink"
            >
              次へ
            </button>
          </div>

          <div className="flex items-center justify-between text-xs text-ink-weak">
            <span>
              {index + 1} / {deck.length}枚
            </span>
            <span className="flex gap-3">
              <button
                type="button"
                onClick={() => setReverse((r) => !r)}
                className="transition hover:text-ink"
              >
                {reverse ? "和訳 → 英単語" : "英単語 → 和訳"}
              </button>
              <button
                type="button"
                onClick={() => setSeed((s) => s + 1)}
                className="transition hover:text-ink"
              >
                シャッフル
              </button>
            </span>
          </div>

          <p className="text-center text-[11px] text-ink-weak">
            スペースでめくる / ←→ で移動。この画面の回答は記録されません。
          </p>
        </>
      )}
    </div>
  );
}

function Card({
  summary,
  flipped,
  reverse,
}: {
  summary: WordSummary;
  flipped: boolean;
  reverse: boolean;
}) {
  const { word } = summary;
  // 表に出すのは既定で英単語。reverse なら和訳から英語を思い出す（難易度が上がる）
  const front = reverse ? word.japanese : word.english;
  const back = reverse ? word.english : word.japanese;

  return (
    <div className="relative flex min-h-56 flex-col items-center justify-center rounded-xl border border-border bg-surface-raised px-6 py-10 text-center">
      {word.tag && (
        <span
          className="absolute top-3 left-3 rounded-full px-2 py-0.5 text-[11px]"
          style={{
            backgroundColor: `light-dark(hsl(${tagHue(word.tag)} 42% 92%), hsl(${tagHue(word.tag)} 30% 22%))`,
            color: `light-dark(hsl(${tagHue(word.tag)} 45% 32%), hsl(${tagHue(word.tag)} 55% 78%))`,
          }}
        >
          {word.tag}
        </span>
      )}
      {word.part_of_speech && (
        <span className="absolute top-3 right-3 text-[11px] text-ink-weak">
          {word.part_of_speech}
        </span>
      )}

      <p className="text-3xl font-semibold tracking-tight break-words">{front}</p>

      {flipped ? (
        <>
          <p className="mt-4 text-xl text-ink-mute break-words">{back}</p>
          {word.example_sentence && (
            <p className="mt-4 max-w-md text-xs leading-relaxed text-ink-weak">
              {word.example_sentence}
            </p>
          )}
        </>
      ) : (
        <p className="mt-4 text-xs text-ink-weak">スペースキーでめくる</p>
      )}
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
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
    </button>
  );
}
