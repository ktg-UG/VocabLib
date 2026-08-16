"use client";

import { useActionState } from "react";

import { parseWordInput } from "@/lib/tags";

export const PARTS_OF_SPEECH = [
  "名詞",
  "動詞",
  "形容詞",
  "副詞",
  "前置詞",
  "接続詞",
  "代名詞",
  "間投詞",
  "熟語",
] as const;

export type AddWordState = { error?: string; added?: string };

/**
 * 単語の新規登録フォーム
 *
 * Macの追加フォームと同じ考え方にする。英単語欄に `incorporation #TOEIC` と
 * 書けばタグに分かれる（規則は `lib/tags.ts` = `src/tags.py` と共通）。
 *
 * 保存処理は Server Action に渡す。ブラウザから直接Supabaseに書かないのは、
 * `updated_at` をサーバー時計で作るため（ブラウザの時計がずれていると
 * 同期のLWWでMacの古い値に負けて編集が消える）。
 */
export function AddWordForm({
  action,
  disabledReason,
}: {
  action: (state: AddWordState, formData: FormData) => Promise<AddWordState>;
  disabledReason?: string;
}) {
  const [state, formAction, pending] = useActionState(action, {});

  return (
    <form action={formAction} className="flex max-w-lg flex-col gap-4">
      <Field
        label="英単語"
        hint="`yield #TOEIC` のように書くとタグが付きます"
      >
        <input
          name="english"
          required
          autoComplete="off"
          placeholder="incorporation #TOEIC"
          onBlur={(event) => {
            // `#` 記法をその場でタグ欄に反映して、何が登録されるか見せる
            const [english, tag] = parseWordInput(event.target.value);
            if (!tag) return;
            const form = event.target.form;
            if (!form) return;
            event.target.value = english;
            const tagInput = form.elements.namedItem("tag");
            if (tagInput instanceof HTMLInputElement) tagInput.value = tag;
          }}
          className={inputClass}
        />
      </Field>

      <Field label="和訳">
        <input name="japanese" required autoComplete="off" className={inputClass} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="品詞">
          <select name="part_of_speech" defaultValue="" className={inputClass}>
            <option value="">未設定</option>
            {PARTS_OF_SPEECH.map((pos) => (
              <option key={pos} value={pos}>
                {pos}
              </option>
            ))}
          </select>
        </Field>

        <Field label="タグ">
          <input name="tag" autoComplete="off" className={inputClass} />
        </Field>
      </div>

      {state.error && (
        <p className="rounded-md border border-negative/30 bg-negative/5 px-3 py-2 text-xs text-negative">
          {state.error}
        </p>
      )}
      {state.added && (
        <p className="rounded-md border border-positive/30 bg-positive/5 px-3 py-2 text-xs text-positive">
          「{state.added}」を登録しました。
        </p>
      )}
      {disabledReason && (
        <p className="text-xs text-ink-weak">{disabledReason}</p>
      )}

      <div>
        <button
          type="submit"
          disabled={pending || Boolean(disabledReason)}
          className="rounded-md bg-accent px-5 py-2 text-sm font-medium text-surface-raised transition hover:opacity-90 disabled:opacity-40"
        >
          {pending ? "登録中..." : "登録する"}
        </button>
      </div>
    </form>
  );
}

const inputClass =
  "w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm placeholder:text-ink-weak focus:border-accent focus:outline-none";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs text-ink-mute">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-ink-weak">{hint}</span>}
    </label>
  );
}
