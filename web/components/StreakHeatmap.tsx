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
const CELL = 13; // マス+隙間の1辺(px)。行ラベルの位置合わせに使う

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

  // 月が変わる列にだけ月名を出す（全列に出すと数字が潰れて読めない）
  const monthLabels = weeks.map((week, i) => {
    const month = Number(week[0].date.slice(5, 7));
    if (i === 0) return `${month}月`;
    const previous = Number(weeks[i - 1][0].date.slice(5, 7));
    return month === previous ? "" : `${month}月`;
  });

  return (
    <div>
      <p className="mb-2 text-xs text-ink-weak">
        {`横軸は週（左が${weekCount}週前・右が今週）、縦軸は曜日。1マスが1日で、濃いほどその日の回答数が多い。`}
      </p>

      <div className="overflow-x-auto pb-1">
        <div className="inline-flex gap-1.5">
          {/* 曜日ラベル。全部出すと窮屈なので月・水・金だけ */}
          <div
            className="flex flex-col text-[10px] text-ink-weak"
            style={{ marginTop: 16 }}
          >
            {["", "月", "", "水", "", "金", ""].map((label, i) => (
              <span
                key={i}
                className="flex items-center"
                style={{ height: CELL, lineHeight: `${CELL}px` }}
              >
                {label}
              </span>
            ))}
          </div>

          <div>
            <div className="flex gap-1">
              {monthLabels.map((label, i) => (
                <span
                  key={i}
                  className="text-[10px] text-ink-weak"
                  style={{ width: 12, height: 16 }}
                >
                  {label && <span className="whitespace-nowrap">{label}</span>}
                </span>
              ))}
            </div>

            <div className="flex gap-1">
              {weeks.map((week, i) => (
                <div key={i} className="flex flex-col gap-1">
                  {week.map((day) => (
                    <div
                      key={day.date}
                      title={
                        day.count < 0 ? day.date : `${day.date}: ${day.count}問`
                      }
                      className={`h-3 w-3 rounded-[3px] ${
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
          <span key={n} className={`h-3 w-3 rounded-[3px] ${shade(n)}`} />
        ))}
        <span>40問+</span>
      </div>
    </div>
  );
}
