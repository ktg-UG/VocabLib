import { redirect } from "next/navigation";

import { AddWordForm } from "@/components/AddWordForm";
import { Section, Shell } from "@/components/Shell";
import { isGeminiConfigured } from "@/lib/llm/gemini";
import { createClient } from "@/lib/supabase/server";

import { addWord, autofillWord } from "../actions";

// Server Action の実行時間の上限。Geminiのオートフィルを足したときに
// 既定の10秒では足りなくなるため、先に確保しておく（SPEC 12.5）
export const maxDuration = 30;
export const dynamic = "force-dynamic";

export default async function NewWordPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <Shell email={user.email} current="new">
      <Section title="単語を追加">
        {/* キーが無ければボタンごと出さない。押せるのに必ず失敗する状態を作らない */}
        <AddWordForm
          action={addWord}
          autofill={isGeminiConfigured() ? autofillWord : undefined}
        />
      </Section>
    </Shell>
  );
}
