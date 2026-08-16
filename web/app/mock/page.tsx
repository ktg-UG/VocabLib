import { notFound } from "next/navigation";

import { AccuracyChart } from "@/components/AccuracyChart";
import { DueCountsPanel } from "@/components/DueCountsPanel";
import { Section, Shell } from "@/components/Shell";
import { StreakHeatmap } from "@/components/StreakHeatmap";
import { SummaryCards } from "@/components/SummaryCards";
import { VolumeChart } from "@/components/VolumeChart";
import { WeakWordsTable } from "@/components/WeakWordsTable";
import { mockData } from "@/lib/mock";
import {
  answersByDate,
  currentStreak,
  dailyAccuracy,
  dueCounts,
  jstToday,
  overallStats,
  weakWords,
} from "@/lib/stats";

// デザイン検討用。**本番には出さない**（fakeデータを本物と見間違える事故を防ぐ）
export const dynamic = "force-dynamic";

export default function MockDashboard() {
  if (process.env.NODE_ENV === "production") notFound();

  const { words, answers, records } = mockData();

  const overall = overallStats(answers);
  const daily = dailyAccuracy(answers, 30);
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
        <WeakWordsTable words={weakWords(answers, words, 10)} />
      </Section>

      <Section title="復習の予定">
        <DueCountsPanel counts={dueCounts(records)} />
      </Section>
    </Shell>
  );
}
