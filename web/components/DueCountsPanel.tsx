import type { DueCounts } from "@/lib/types";

export function DueCountsPanel({ counts }: { counts: DueCounts }) {
  const items = [
    { label: "期限切れ", value: counts.overdue, accent: "text-red-600 dark:text-red-400" },
    { label: "今週の復習", value: counts.withinWeek, accent: "" },
    { label: "未学習", value: counts.unlearned, accent: "" },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="text-xs text-black/60 dark:text-white/60">{item.label}</div>
          <div className={`text-xl font-bold tabular-nums ${item.accent}`}>
            {item.value}
            <span className="ml-0.5 text-sm font-normal">語</span>
          </div>
        </div>
      ))}
    </div>
  );
}
