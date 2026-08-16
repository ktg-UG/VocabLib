"use client";

import { useActionState, useMemo, useRef, useState, useTransition } from "react";

import { PARTS_OF_SPEECH } from "@/components/AddWordForm";

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
export type EditWordState = { error?: string; saved?: boolean };

type WordAction = (
  state: EditWordState,
  formData: FormData,
) => Promise<EditWordState>;

export type RegenerateAction = (
  english: string,
  japanese: string,
) => Promise<{ sentence?: string; error?: string }>;

export function WordsView({
  words,
  records,
  onUpdate,
  onDelete,
  onRegenerate,
}: {
  words: WordRow[];
  records: RecordRow[];
  /** 省略するとモック（読み取り専用）として動く */
  onUpdate?: WordAction;
  onDelete?: WordAction;
  /** 省略すると例文の再生成ボタンを出さない（APIキー未設定など） */
  onRegenerate?: RegenerateAction;
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
              onUpdate={onUpdate}
              onDelete={onDelete}
              onRegenerate={onRegenerate}
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
  onUpdate,
  onDelete,
  onRegenerate,
}: {
  summary: WordSummary;
  open: boolean;
  onToggle: () => void;
  onUpdate?: WordAction;
  onDelete?: WordAction;
  onRegenerate?: RegenerateAction;
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

      {open &&
        (onUpdate && onDelete ? (
          <EditForm
            word={word}
            seen={seen}
            correct={correct}
            accuracy={accuracy}
            onUpdate={onUpdate}
            onDelete={onDelete}
            onRegenerate={onRegenerate}
          />
        ) : (
          <div className="grid gap-2 pb-3 pl-1 text-xs text-ink-mute">
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              <span>品詞: {word.part_of_speech ?? "未設定"}</span>
              <span>
                成績: {correct} / {seen}問
                {accuracy !== null && `（${Math.round(accuracy)}%）`}
              </span>
            </div>
            <p>
              {word.example_sentence ?? (
                <span className="text-ink-weak">
                  例文はまだありません（不正解のときに生成されます）
                </span>
              )}
            </p>
          </div>
        ))}
    </li>
  );
}

/**
 * 習熟度バー
 *
 * **覚えている単語ほど目立たなくする。** 全部を同じ濃さで塗ると、
 * 8割以上が緑で埋まって「どれが弱いか」がまったく分からない（実際にそうなった）。
 * 探しているのは弱い単語なので、そこにだけ色を残す。
 *
 * バーの長さだけでは 85% と 95% の差が数pxにしかならないため、数値も併記する。
 */
function MasteryBar({ accuracy }: { accuracy: number | null }) {
  if (accuracy === null) {
    return (
      <span className="w-[68px] shrink-0 text-right text-[11px] text-ink-weak">
        未学習
      </span>
    );
  }

  const color =
    accuracy >= 80
      ? "bg-positive/35"   // 覚えている。視界から引っ込める
      : accuracy >= 50
        ? "bg-accent"
        : "bg-negative";

  return (
    <span className="flex w-[68px] shrink-0 items-center gap-1.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
        <span
          className={`block h-full rounded-full ${color}`}
          style={{ width: `${Math.max(accuracy, 4)}%` }}
        />
      </span>
      <span
        className={`w-7 text-right text-[11px] ${
          accuracy < 50 ? "text-negative" : "text-ink-weak"
        }`}
      >
        {Math.round(accuracy)}%
      </span>
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


/**
 * 行を開いたときの編集フォーム
 *
 * 英単語の入力欄を置いていないのは意図的。綴りを変えるのは実質「別の単語」で、
 * 過去の回答履歴が別語の記録として残ってしまうため、削除して登録し直す。
 */
function EditForm({
  word,
  seen,
  correct,
  accuracy,
  onUpdate,
  onDelete,
  onRegenerate,
}: {
  word: WordRow;
  seen: number;
  correct: number;
  accuracy: number | null;
  onUpdate: WordAction;
  onDelete: WordAction;
  onRegenerate?: RegenerateAction;
}) {
  const [updateState, update, updating] = useActionState(onUpdate, {});
  const [deleteState, remove, removing] = useActionState(onDelete, {});
  const [confirming, setConfirming] = useState(false);
  const [regenerating, startRegenerate] = useTransition();
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const exampleRef = useRef<HTMLTextAreaElement>(null);
  const japaneseRef = useRef<HTMLInputElement>(null);

  /**
   * 例文を作り直す。**その場では保存せず、欄に入れるだけ。**
   * 気に入らなければ保存せず捨てられるようにする
   * （ハズレを直すための機能なので、ハズレでまた上書きされては意味がない）。
   */
  const regenerate = () => {
    if (!onRegenerate) return;
    setRegenerateError(null);
    startRegenerate(async () => {
      const result = await onRegenerate(
        word.english,
        japaneseRef.current?.value ?? word.japanese,
      );
      if (result.error) {
        setRegenerateError(result.error);
        return;
      }
      if (exampleRef.current && result.sentence) {
        exampleRef.current.value = result.sentence;
      }
    });
  };

  const error = updateState.error ?? deleteState.error;

  return (
    <div className="pb-4 pl-1">
      <p className="mb-3 text-xs text-ink-weak">
        成績 {correct} / {seen}問
        {accuracy !== null && `（${Math.round(accuracy)}%）`}
        {"　"}登録 {word.created_at.slice(0, 10)}
      </p>

      <form action={update} className="grid gap-3 sm:grid-cols-2">
        <input type="hidden" name="id" value={word.id} />

        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-[11px] text-ink-weak">和訳</span>
          <input
            ref={japaneseRef}
            name="japanese"
            defaultValue={word.japanese}
            required
            className={editInput}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[11px] text-ink-weak">品詞</span>
          <select
            name="part_of_speech"
            defaultValue={word.part_of_speech ?? ""}
            className={editInput}
          >
            <option value="">未設定</option>
            {PARTS_OF_SPEECH.map((pos) => (
              <option key={pos} value={pos}>
                {pos}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[11px] text-ink-weak">タグ</span>
          <input name="tag" defaultValue={word.tag} className={editInput} />
        </label>

        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="flex items-center gap-2 text-[11px] text-ink-weak">
            例文
            {onRegenerate && (
              <button
                type="button"
                onClick={regenerate}
                disabled={regenerating}
                className="rounded border border-border px-1.5 py-0.5 text-[11px] text-ink-mute transition hover:text-ink disabled:opacity-40"
              >
                {regenerating ? "生成中..." : "再生成"}
              </button>
            )}
            {regenerateError && (
              <span className="text-negative">{regenerateError}</span>
            )}
          </span>
          <textarea
            ref={exampleRef}
            name="example_sentence"
            defaultValue={word.example_sentence ?? ""}
            rows={2}
            placeholder="不正解のときに自動生成されます"
            className={editInput}
          />
          {onRegenerate && (
            <span className="text-[11px] text-ink-weak">
              再生成しても保存は押すまで反映されません
            </span>
          )}
        </label>

        <div className="flex items-center gap-2 sm:col-span-2">
          <button
            type="submit"
            disabled={updating}
            className="rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-surface-raised transition hover:opacity-90 disabled:opacity-40"
          >
            {updating ? "保存中..." : "保存"}
          </button>
          {updateState.saved && !updating && (
            <span className="text-xs text-positive">保存しました</span>
          )}
          <span className="flex-1" />
          {confirming ? (
            <>
              <span className="text-xs text-ink-mute">削除しますか？</span>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded-md border border-border px-3 py-1.5 text-xs text-ink-mute"
              >
                やめる
              </button>
              <button
                type="submit"
                formAction={remove}
                disabled={removing}
                className="rounded-md bg-negative px-3 py-1.5 text-xs font-medium text-surface-raised disabled:opacity-40"
              >
                {removing ? "削除中..." : "削除する"}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-negative transition hover:bg-negative/5"
            >
              削除
            </button>
          )}
        </div>
      </form>

      {error && (
        <p className="mt-2 text-xs text-negative">{error}</p>
      )}
      <p className="mt-2 text-[11px] text-ink-weak">
        英単語は変更できません。綴りが違う場合は削除して登録し直してください
        （回答履歴が別の単語の記録として残ってしまうため）。
      </p>
    </div>
  );
}

const editInput =
  "w-full rounded-md border border-border bg-surface-raised px-2.5 py-1.5 text-sm placeholder:text-ink-weak focus:border-accent focus:outline-none";
