"use client";

import { useState } from "react";

import { AccuracyChart } from "@/components/AccuracyChart";
import { StreakHeatmap } from "@/components/StreakHeatmap";
import { VolumeChart } from "@/components/VolumeChart";
import type { DailyPoint } from "@/lib/types";

/**
 * 学習履歴のグラフ（期間切替つき）
 *
 * 期間を変えるたびにサーバーへ問い合わせない。**1年分の日別集計だけを受け取り、
 * 表示範囲はここで切り出す。** 回答ログそのものを渡すと数千行がブラウザに乗るが、
 * 日別に畳んでおけば1年でも365行で済む。
 */

const RANGES = [
  { days: 30, label: "30日" },
  { days: 90, label: "90日" },
  { days: 365, label: "1年" },
] as const;

export function HistorySection({
  points,
  counts,
  today,
  firstDate,
}: {
  /** 1年分の日別集計（古い順） */
  points: DailyPoint[];
  /** 日付 → 回答数 */
  counts: Record<string, number>;
  today: string;
  /** 最初に回答した日。まだ無ければ null */
  firstDate: string | null;
}) {
  const [days, setDays] = useState<number>(30);

  const visible = points.slice(-days);
  const weeks = Math.ceil(days / 7);

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold">学習の履歴</h2>
        <div className="flex gap-1.5">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              onClick={() => setDays(range.days)}
              className={`rounded-full px-2.5 py-1 text-xs transition ${
                days === range.days
                  ? "bg-accent text-surface-raised"
                  : "bg-accent-weak text-ink-mute hover:text-ink"
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <Block title="正答率の推移">
        <AccuracyChart points={visible} />
      </Block>

      <Block title="学習量">
        <VolumeChart points={visible} />
      </Block>

      <Block title="学習の記録">
        <StreakHeatmap counts={counts} today={today} weeks={weeks} />
      </Block>

      <p className="-mt-6 text-xs text-ink-weak">
        {firstDate
          ? `記録開始: ${firstDate}。回答履歴は消さずに貯め続けるので、使うほど過去に遡れます。`
          : "まだ回答がありません。"}
      </p>
    </div>
  );
}

function Block({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-3 text-[13px] font-semibold text-ink-mute">{title}</h3>
      {children}
    </section>
  );
}
