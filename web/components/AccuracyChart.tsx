"use client";

// Recharts はブラウザ側のDOM計測に依存するため Client Component にする。
// データは Server Component が集計済みのものを props で渡す
// （このファイルは Supabase に触らない = キーが混入する余地がない）。

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/lib/types";

export function AccuracyChart({ points }: { points: DailyPoint[] }) {
  // 回答が無い日は線を引かない（0%として繋ぐと「全問不正解の日」に見えてしまう）
  const data = points.map((p) => ({
    date: p.date.slice(5), // "08-15"
    accuracy: p.total > 0 ? Math.round(p.accuracy) : null,
    total: p.total,
  }));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.12} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" width={44} />
          <Tooltip
            // 型注釈は付けない。Recharts 側の型（value は undefined になり得る）を
            // 推論させ、ここで絞り込む
            formatter={(value, _name, item) => {
              const payload = item?.payload as { total?: number } | undefined;
              return [
                typeof value === "number" ? `${value}%` : "回答なし",
                `${payload?.total ?? 0}問`,
              ];
            }}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Line
            type="monotone"
            dataKey="accuracy"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 2 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
