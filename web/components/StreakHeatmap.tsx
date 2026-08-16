"use client";

import { useEffect, useRef } from "react";

/**
 * 学習の記録（GitHubの草のようなカレンダー）
 *
 * 専用ライブラリを足さず、CSS grid で 7×N のマス目を並べて自前で作る。
 * 依存を1つ減らせるうえ、このくらいの表示なら実装量も大差ない。
 *
 * **軸に何が並んでいるかを必ず書く。** マス目だけ出すと
 * 「縦横が何を表しているのか分からない」という状態になる（実際にそう指摘された）。
 */

const DAY_MS = 24 * 60 * 60 * 1000;

// マス目の実寸。曜日ラベル・月ラベル・マスの3つを同じ数値から組み立てる。
// ここが1pxでもずれると、行を下るほど曜日ラベルが実際の行から離れていく
// （最初の実装は CELL=13 と gap-1(4px)+w-3(12px)=16px が食い違い、
//  7行で18pxずれていた）
const CELL = 12;
const GAP = 4;
const MONTH_ROW = 16;

/**
 * 濃さはアクセント1色の不透明度だけで表す。
 * 色相を増やすと「青→緑」のような意味の無い変化が生まれるため。
 */
function shade(count: number): string {
  if (count === 0) return "bg-border";
  if (count < 5) return "bg-accent/25";
  if (count < 15) return "bg-accent/45";
  if (count < 30) return "bg-accent/70";
  return "bg-accent";
}

export function StreakHeatmap({
  counts,
  today,
  weeks: weekCount = 12,
}: {
  counts: Record<string, number>;
  today: string; // JSTの今日 "YYYY-MM-DD"
  /** 何週分さかのぼるか。長い期間は横スクロールで見る */
  weeks?: number;
}) {
  // 横に溢れたときは右端（＝直近）を見せる。
  // 左端から表示すると、1年表示で「直近8週が隠れ、一番古い週から見える」という
  // 見たいものと逆の状態になる
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [weekCount]);

  const todayMs = Date.parse(`${today}T00:00:00Z`);
  // 週の始まりを日曜に揃える（最終列に今日が入るように後ろから逆算する）
  const todayWeekday = new Date(todayMs).getUTCDay();
  const startMs = todayMs - (todayWeekday + (weekCount - 1) * 7) * DAY_MS;

  const weeks: { date: string; count: number }[][] = [];
  for (let w = 0; w < weekCount; w++) {
    const week: { date: string; count: number }[] = [];
    for (let d = 0; d < 7; d++) {
      const ms = startMs + (w * 7 + d) * DAY_MS;
      const date = new Date(ms).toISOString().slice(0, 10);
      week.push({ date, count: ms > todayMs ? -1 : (counts[date] ?? 0) });
    }
    weeks.push(week);
  }

  // 月が変わる列にだけ月名を出す。
  // ラベルの文字幅（約20px）は1列の幅（16px）より広いので、隣り合う列に
  // 両方出すと重なって読めなくなる。**3列以上あけて**から次を出す
  // （月初が列の先頭に来ると 5月・6月 が隣同士になり、実際に潰れていた）
  const MIN_LABEL_GAP = 3;
  let lastLabeled = -MIN_LABEL_GAP;
  const monthLabels = weeks.map((week, i) => {
    if (i === 0) return "";
    const month = Number(week[0].date.slice(5, 7));
    const previous = Number(weeks[i - 1][0].date.slice(5, 7));
    if (month === previous || i - lastLabeled < MIN_LABEL_GAP) return "";
    lastLabeled = i;
    return `${month}月`;
  });

  return (
    <div>
      <p className="mb-2 text-xs text-ink-weak">
        {`横軸は週（左が${weekCount}週前・右が今週）、縦軸は曜日。1マスが1日で、濃いほどその日の回答数が多い。`}
      </p>

      {/* 週数が増えると横に伸びるのでスクロールさせる。
          曜日ラベルは一緒に流れないよう、スクロール領域の外に置く */}
      <div className="flex gap-2">
        {/* 曜日は7つとも書く。GitHubの草が月・水・金だけなのはマスが小さくて
            7つ並べると潰れるからで、行間隔が16pxあるここでは当てはまらない。
            間引くと「なぜこの3つなのか」を読み手に考えさせるだけ損 */}
        <div
          className="flex shrink-0 flex-col text-[10px] text-ink-weak"
          style={{ marginTop: MONTH_ROW, gap: GAP }}
        >
          {["日", "月", "火", "水", "木", "金", "土"].map((label) => (
            <span key={label} style={{ height: CELL, lineHeight: `${CELL}px` }}>
              {label}
            </span>
          ))}
        </div>

        <div ref={scroller} className="min-w-0 overflow-x-auto pb-1">
          <div className="inline-block">
            <div className="flex" style={{ gap: GAP, height: MONTH_ROW }}>
              {monthLabels.map((label, i) => (
                <span
                  key={i}
                  className="shrink-0 text-[10px] whitespace-nowrap text-ink-weak"
                  style={{ width: CELL }}
                >
                  {label}
                </span>
              ))}
            </div>

            <div className="flex" style={{ gap: GAP }}>
              {weeks.map((week, i) => (
                <div key={i} className="flex shrink-0 flex-col" style={{ gap: GAP }}>
                  {week.map((day) => (
                    <div
                      key={day.date}
                      title={
                        day.count < 0 ? day.date : `${day.date}: ${day.count}問`
                      }
                      style={{ width: CELL, height: CELL }}
                      className={`shrink-0 rounded-[3px] ${
                        day.count < 0 ? "opacity-0" : shade(day.count)
                      }`}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1 text-xs text-ink-weak">
        <span>0問</span>
        {[0, 3, 10, 20, 40].map((n) => (
          <span
            key={n}
            style={{ width: CELL, height: CELL }}
            className={`shrink-0 rounded-[3px] ${shade(n)}`}
          />
        ))}
        <span>40問+</span>
      </div>
    </div>
  );
}
