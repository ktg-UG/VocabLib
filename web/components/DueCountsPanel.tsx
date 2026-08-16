import type { DueCounts } from "@/lib/types";

export function DueCountsPanel({ counts }: { counts: DueCounts }) {
  const items = [
    { label: "期限切れ", value: counts.overdue, accent: "text-negative" },
    { label: "今週の復習", value: counts.withinWeek, accent: "" },
    { label: "未学習", value: counts.unlearned, accent: "" },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="text-xs text-ink-weak">{item.label}</div>
          <div className={`text-2xl font-semibold ${item.accent}`}>
            {item.value}
            <span className="ml-0.5 text-sm font-normal text-ink-weak">語</span>
          </div>
        </div>
      ))}
    </div>
  );
}
