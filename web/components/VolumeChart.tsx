"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/lib/types";

import { CHART_AXIS_WIDTH } from "./AccuracyChart";

/**
 * 日別の学習量
 *
 * 正答率の折れ線だけでは「1問だけ解いて正解した日」が100%として立ち上がり、
 * 好調に見えてしまう。**何問解いたか**を並べて置くことで、その誤読を防ぐ。
 */
export function VolumeChart({ points }: { points: DailyPoint[] }) {
  const data = points.map((p) => ({
    date: p.date.slice(5), // "08-15"
    total: p.total,
    correct: p.correct,
  }));

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="currentColor"
            opacity={0.12}
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          {/* 目盛りに単位を付けない。「40問」は幅を食って軸からはみ出すので、
              単位は見出しとツールチップ側で示す */}
          <YAxis
            tick={{ fontSize: 11 }}
            width={CHART_AXIS_WIDTH}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: "var(--color-accent)", opacity: 0.08 }}
            formatter={(value, _name, item) => {
              const payload = item?.payload as { correct?: number } | undefined;
              return [`${value}問`, `正解 ${payload?.correct ?? 0}`];
            }}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Bar
            dataKey="total"
            fill="var(--color-accent)"
            opacity={0.75}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
