"use server";

import { revalidatePath } from "next/cache";

import type { AddWordState } from "@/components/AddWordForm";
import type { EditWordState } from "@/components/WordsView";
import { normalizeTag, parseWordInput } from "@/lib/tags";
import { createClient } from "@/lib/supabase/server";

/**
 * 単語を登録する。
 *
 * `updated_at` / `created_at` は **サーバー時計** で作る。ブラウザの時計が
 * 数分ずれていると、同期のLWW（SPEC 12.6）でMacの古い値に負けて
 * この登録内容が消える。
 *
 * `learning_records` の行はSupabase側のトリガーが作る。アプリ側で2回insertしても
 * PostgRESTでは1トランザクションにならず、「単語はあるが学習記録が無い」状態
 * （v1で実際に起きたバグ）を作りうるため。
 */
export async function addWord(
  _state: AddWordState,
  formData: FormData,
): Promise<AddWordState> {
  const supabase = await createClient();

  // Server Action は直接POSTできるので、UIで隠れていても必ずここで認証を確認する
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "ログインが必要です。" };

  const [english, tagFromInput] = parseWordInput(
    String(formData.get("english") ?? ""),
  );
  const japanese = String(formData.get("japanese") ?? "").trim();
  const partOfSpeech = String(formData.get("part_of_speech") ?? "").trim();
  const tag = normalizeTag(String(formData.get("tag") ?? "")) || tagFromInput;

  if (!english || !japanese) {
    return { error: "英単語と和訳はどちらも必須です。" };
  }

  const now = new Date().toISOString();
  const { error } = await supabase.from("words").insert({
    id: crypto.randomUUID(),
    user_id: user.id,
    english,
    japanese,
    part_of_speech: partOfSpeech || null,
    tag,
    created_at: now,
    updated_at: now,
    deleted: false,
  });

  if (error) {
    // 同じ (英単語, 和訳) はユニーク制約で弾かれる。Macの挙動と揃える
    if (error.code === "23505") {
      return { error: `「${english}（${japanese}）」は既に登録されています。` };
    }
    return { error: `登録できませんでした: ${error.message}` };
  }

  revalidatePath("/words");
  return { added: `${english} — ${japanese}` };
}


/**
 * 単語を編集する。
 *
 * **英単語は変更させない。** 綴りが変わるのは実質「別の単語」であり、
 * 過去の回答履歴（answer_log）が別語の記録として残ってしまう。
 * 綴りを間違えたときは削除して登録し直す。
 */
export async function updateWord(
  _state: EditWordState,
  formData: FormData,
): Promise<EditWordState> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "ログインが必要です。" };

  const id = String(formData.get("id") ?? "");
  const japanese = String(formData.get("japanese") ?? "").trim();
  const partOfSpeech = String(formData.get("part_of_speech") ?? "").trim();
  const tag = normalizeTag(String(formData.get("tag") ?? ""));
  const example = String(formData.get("example_sentence") ?? "").trim();

  if (!id) return { error: "対象の単語が特定できません。" };
  if (!japanese) return { error: "和訳は必須です。" };

  const { error } = await supabase
    .from("words")
    .update({
      japanese,
      part_of_speech: partOfSpeech || null,
      tag,
      example_sentence: example || null,
      // サーバー時計で作る。ブラウザの時計がずれていると同期のLWWで
      // Macの古い値に負け、この編集が消える（SPEC 12.6）
      updated_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (error) return { error: `保存できませんでした: ${error.message}` };

  revalidatePath("/words");
  return { saved: true };
}

/**
 * 単語を削除する（論理削除）。
 *
 * 行は残して `deleted = true` を立てる。物理削除すると
 * 「updated_at が新しい行」を拾う同期にはMacへ何も届かず、
 * 単語がMacに残ったまま次のpushで復活する。
 */
export async function deleteWord(
  _state: EditWordState,
  formData: FormData,
): Promise<EditWordState> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "ログインが必要です。" };

  const id = String(formData.get("id") ?? "");
  if (!id) return { error: "対象の単語が特定できません。" };

  const { error } = await supabase
    .from("words")
    .update({ deleted: true, updated_at: new Date().toISOString() })
    .eq("id", id);

  if (error) return { error: `削除できませんでした: ${error.message}` };

  revalidatePath("/words");
  return { saved: true };
}
