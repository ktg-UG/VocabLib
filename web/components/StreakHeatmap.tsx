/**
 * 学習の記録（GitHubの草のようなカレンダー）
 *
 * 専用ライブラリを足さず、CSS grid で 7×N のマス目を並べて自前で作る。
 * 依存を1つ減らせるうえ、このくらいの表示なら実装量も大差ない。
 */

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEKS = 12;

/**
 * 濃さはアクセント1色の不透明度だけで表す。
 * 色相を増やすと「青→緑」のような意味の無い変化が生まれるため。
 */
function shade(count: number): string {
  if (count === 0) return "bg-border";
  if (count < 3) return "bg-accent/25";
  if (count < 8) return "bg-accent/45";
  if (count < 15) return "bg-accent/70";
  return "bg-accent";
}

export function StreakHeatmap({
  counts,
  today,
}: {
  counts: Record<string, number>;
  today: string; // JSTの今日 "YYYY-MM-DD"
}) {
  const todayMs = Date.parse(`${today}T00:00:00Z`);
  // 週の始まりを日曜に揃える（最終列に今日が入るように後ろから逆算する）
  const todayWeekday = new Date(todayMs).getUTCDay();
  const startMs = todayMs - (todayWeekday + (WEEKS - 1) * 7) * DAY_MS;

  const weeks: { date: string; count: number }[][] = [];
  for (let w = 0; w < WEEKS; w++) {
    const week: { date: string; count: number }[] = [];
    for (let d = 0; d < 7; d++) {
      const ms = startMs + (w * 7 + d) * DAY_MS;
      const date = new Date(ms).toISOString().slice(0, 10);
      week.push({ date, count: ms > todayMs ? -1 : (counts[date] ?? 0) });
    }
    weeks.push(week);
  }

  return (
    <div className="overflow-x-auto">
      <div className="flex gap-1">
        {weeks.map((week, i) => (
          <div key={i} className="flex flex-col gap-1">
            {week.map((day) => (
              <div
                key={day.date}
                title={day.count < 0 ? day.date : `${day.date}: ${day.count}問`}
                className={`h-3 w-3 rounded-[3px] ${
                  day.count < 0 ? "opacity-0" : shade(day.count)
                }`}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-1 text-xs text-ink-weak">
        <span>少</span>
        {[0, 2, 7, 14, 20].map((n) => (
          <span key={n} className={`h-3 w-3 rounded-[3px] ${shade(n)}`} />
        ))}
        <span>多</span>
      </div>
    </div>
  );
}
