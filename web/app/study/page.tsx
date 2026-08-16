import { redirect } from "next/navigation";

import { ErrorPanel, Shell } from "@/components/Shell";
import { StudyView } from "@/components/StudyView";
import { fetchDashboardData } from "@/lib/supabase/data";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function StudyPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  let words;
  let records;
  try {
    ({ words, records } = await fetchDashboardData(supabase));
  } catch (error) {
    return (
      <Shell email={user.email} current="study">
        <ErrorPanel message={error instanceof Error ? error.message : String(error)} />
      </Shell>
    );
  }

  if (words.length === 0) {
    return (
      <Shell email={user.email} current="study">
        <p className="text-sm text-ink-mute">
          まだ単語がありません。「追加」タブかMacアプリで登録してください。
        </p>
      </Shell>
    );
  }

  return (
    <Shell email={user.email} current="study">
      <StudyView words={words} records={records} />
    </Shell>
  );
}
