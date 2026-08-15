/**
 * ダッシュボードのデータ取得
 *
 * クエリに `where user_id = ...` を書いていないことに注目。
 * RLS ポリシー（`auth.uid() = user_id`）が DB 側で自動的に絞るため、
 * アプリ側の書き忘れによる漏洩が構造的に起きない。
 */
import type { SupabaseClient } from "@supabase/supabase-js";

import type { AnswerRow, RecordRow, WordRow } from "../types";

export type DashboardData = {
  words: WordRow[];
  answers: AnswerRow[];
  records: RecordRow[];
};

export async function fetchDashboardData(
  supabase: SupabaseClient,
): Promise<DashboardData> {
  // 集計は lib/stats.ts（純粋関数）でやるので、ここでは生データを取るだけ。
  const [words, answers, records] = await Promise.all([
    supabase.from("words").select("*").eq("deleted", false),
    supabase.from("answer_log").select("*"),
    supabase.from("learning_records").select("*"),
  ]);

  const error = words.error ?? answers.error ?? records.error;
  if (error) throw new Error(`Supabaseからの取得に失敗しました: ${error.message}`);

  return {
    words: (words.data ?? []) as WordRow[],
    answers: (answers.data ?? []) as AnswerRow[],
    records: (records.data ?? []) as RecordRow[],
  };
}
