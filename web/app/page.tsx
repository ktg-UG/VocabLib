import { AccuracyChart } from "@/components/AccuracyChart";
import { DueCountsPanel } from "@/components/DueCountsPanel";
import { StreakHeatmap } from "@/components/StreakHeatmap";
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
      <Shell email={user.email}>
        <ErrorPanel message={error instanceof Error ? error.message : String(error)} />
      </Shell>
    );
  }

  const { words, answers, records } = data;

  if (answers.length === 0 && words.length === 0) {
    return (
      <Shell email={user.email}>
        <p className="text-sm text-black/60 dark:text-white/60">
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
    <Shell email={user.email}>
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

function Shell({
  children,
  email,
}: {
  children: React.ReactNode;
  email?: string;
}) {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">VocabLib</h1>
          <p className="text-xs text-black/50 dark:text-white/50">
            {email ?? "学習ダッシュボード"}
          </p>
        </div>
        <form action="/auth/signout" method="post">
          <button
            type="submit"
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs text-black/60 transition hover:bg-black/[0.04] dark:border-white/15 dark:text-white/60 dark:hover:bg-white/[0.06]"
          >
            ログアウト
          </button>
        </form>
      </header>
      <div className="flex flex-col gap-8">{children}</div>
    </main>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-semibold">
        {title}
        {note && (
          <span className="text-xs font-normal text-black/40 dark:text-white/40">
            {note}
          </span>
        )}
      </h2>
      {children}
    </section>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
      <p className="text-sm font-semibold text-red-600 dark:text-red-400">
        データを取得できませんでした
      </p>
      <p className="mt-1 text-xs break-words text-black/60 dark:text-white/60">
        {message}
      </p>
    </div>
  );
}
