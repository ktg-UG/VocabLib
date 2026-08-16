import { AccuracyChart } from "@/components/AccuracyChart";
import { ErrorPanel, Section, Shell } from "@/components/Shell";
import { DueCountsPanel } from "@/components/DueCountsPanel";
import { StreakHeatmap } from "@/components/StreakHeatmap";
import { VolumeChart } from "@/components/VolumeChart";
import { SummaryCards } from "@/components/SummaryCards";
import { WeakWordsTable } from "@/components/WeakWordsTable";
import {
  answersByDate,
  currentStreak,
  dailyAccuracy,
  dueCounts,
  jstToday,
  overallStats,
  weakWords,
} from "@/lib/stats";
import { fetchDashboardData } from "@/lib/supabase/data";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

// 毎回最新のデータを見たいので、ビルド時に固定させない。
// （Cache Components は有効化していないため、この従来モデルの指定が効く）
export const dynamic = "force-dynamic";

export default async function Page() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // proxy.ts でも弾いているが、ここでも確認する。
  // 認証は1箇所の設定ミスで丸ごと無効になるので、二重にしておく。
  if (!user) redirect("/login");

  let data;
  try {
    // RLS が auth.uid() で自動的に絞るため、user_id の条件は書かなくてよい
    data = await fetchDashboardData(supabase);
  } catch (error) {
    return (
      <Shell email={user.email} current="dashboard">
        <ErrorPanel message={error instanceof Error ? error.message : String(error)} />
      </Shell>
    );
  }

  const { words, answers, records } = data;

  if (answers.length === 0 && words.length === 0) {
    return (
      <Shell email={user.email} current="dashboard">
        <p className="text-sm text-ink-mute">
          まだデータがありません。Macアプリで単語を登録して同期してください。
        </p>
      </Shell>
    );
  }

  const overall = overallStats(answers);
  const streak = currentStreak(answers);
  const daily = dailyAccuracy(answers, 30);
  const heatmap = Object.fromEntries(answersByDate(answers));
  const weak = weakWords(answers, words, 10);
  const due = dueCounts(records);

  return (
    <Shell email={user.email} current="dashboard">
      <SummaryCards
        cards={[
          { label: "通算", value: `${overall.total}問`, sub: `正解 ${overall.correct}` },
          { label: "正答率", value: `${overall.accuracy.toFixed(1)}%` },
          { label: "連続学習", value: `${streak}日` },
          { label: "登録単語", value: `${words.length}語` },
        ]}
      />

      <Section title="正答率の推移" note="直近30日">
        <AccuracyChart points={daily} />
      </Section>

      <Section title="学習量" note="直近30日">
        <VolumeChart points={daily} />
      </Section>

      <Section title="学習の記録" note="直近12週">
        <StreakHeatmap counts={heatmap} today={jstToday()} />
      </Section>

      <Section title="苦手な単語">
        <WeakWordsTable words={weak} />
      </Section>

      <Section title="復習の予定">
        <DueCountsPanel counts={due} />
      </Section>
    </Shell>
  );
}
