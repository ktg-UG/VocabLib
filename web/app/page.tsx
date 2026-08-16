import { ErrorPanel, Section, Shell } from "@/components/Shell";
import { DueCountsPanel } from "@/components/DueCountsPanel";
import { HistorySection } from "@/components/HistorySection";
import { SummaryCards } from "@/components/SummaryCards";
import { WeakWordsTable } from "@/components/WeakWordsTable";
import {
  answersByDate,
  currentStreak,
  dailyAccuracy,
  dueCounts,
  jstToday,
  overallStats,
  toJstDate,
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
  // 1年分を渡し、表示範囲の切り出しはクライアントで行う（期間切替のたびに
  // 問い合わせないため。日別に畳んであるので365行で済む）
  const daily = dailyAccuracy(answers, 365);
  // 記録がいつから貯まっているかを見せる（回答ログは消さないので過去に遡れる）
  const firstDate =
    answers.length === 0
      ? null
      : toJstDate(
          answers.reduce((min, a) => (a.answered_at < min ? a.answered_at : min),
            answers[0].answered_at),
        );
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

      <HistorySection
        points={daily}
        counts={heatmap}
        today={jstToday()}
        firstDate={firstDate}
      />

      <Section title="苦手な単語">
        <WeakWordsTable words={weak} />
      </Section>

      <Section title="復習の予定">
        <DueCountsPanel counts={due} />
      </Section>
    </Shell>
  );
}
