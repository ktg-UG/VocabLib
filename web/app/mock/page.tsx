import { notFound } from "next/navigation";

import { DueCountsPanel } from "@/components/DueCountsPanel";
import { HistorySection } from "@/components/HistorySection";
import { Section, Shell } from "@/components/Shell";
import { SummaryCards } from "@/components/SummaryCards";
import { WeakWordsTable } from "@/components/WeakWordsTable";
import { mockData } from "@/lib/mock";
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

// デザイン検討用。**本番には出さない**（fakeデータを本物と見間違える事故を防ぐ）
export const dynamic = "force-dynamic";

export default function MockDashboard() {
  if (process.env.NODE_ENV === "production") notFound();

  const { words, answers, records } = mockData();

  const overall = overallStats(answers);
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

  return (
    <Shell email="モックデータ（デザイン検討用）" current="dashboard" base="/mock">
      <SummaryCards
        cards={[
          { label: "通算", value: `${overall.total}問`, sub: `正解 ${overall.correct}` },
          { label: "正答率", value: `${overall.accuracy.toFixed(1)}%` },
          { label: "連続学習", value: `${currentStreak(answers)}日` },
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
        <WeakWordsTable words={weakWords(answers, words, 10)} />
      </Section>

      <Section title="復習の予定">
        <DueCountsPanel counts={dueCounts(records)} />
      </Section>
    </Shell>
  );
}
