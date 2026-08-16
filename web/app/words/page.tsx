import { redirect } from "next/navigation";

import { ErrorPanel, Shell } from "@/components/Shell";
import { WordsView } from "@/components/WordsView";

import { deleteWord, regenerateExample, updateWord } from "../actions";
import { fetchDashboardData } from "@/lib/supabase/data";
import { isGeminiConfigured } from "@/lib/llm/gemini";
import { createClient } from "@/lib/supabase/server";

// 編集・削除の Server Action はこのページから呼ばれる
export const maxDuration = 30;

// 毎回最新のデータを見たいので、ビルド時に固定させない。
export const dynamic = "force-dynamic";

export default async function WordsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // proxy.ts でも弾いているが、ここでも確認する。
  // 認証は1箇所の設定ミスで丸ごと無効になるので、二重にしておく。
  if (!user) redirect("/login");

  let words;
  let records;
  try {
    // RLS が auth.uid() で自動的に絞るため、user_id の条件は書かなくてよい
    ({ words, records } = await fetchDashboardData(supabase));
  } catch (error) {
    return (
      <Shell email={user.email} current="words">
        <ErrorPanel message={error instanceof Error ? error.message : String(error)} />
      </Shell>
    );
  }

  if (words.length === 0) {
    return (
      <Shell email={user.email} current="words">
        <p className="text-sm text-ink-mute">
          まだ単語がありません。Macアプリで登録して同期してください。
        </p>
      </Shell>
    );
  }

  return (
    <Shell email={user.email} current="words">
      <WordsView
        words={words}
        records={records}
        onUpdate={updateWord}
        onDelete={deleteWord}
        onRegenerate={isGeminiConfigured() ? regenerateExample : undefined}
      />
    </Shell>
  );
}
