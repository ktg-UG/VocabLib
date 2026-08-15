type Card = {
  label: string;
  value: string;
  sub?: string;
};

export function SummaryCards({ cards }: { cards: Card[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-xl border border-black/10 bg-black/[0.02] p-4 dark:border-white/10 dark:bg-white/[0.03]"
        >
          <div className="text-xs text-black/60 dark:text-white/60">{card.label}</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">{card.value}</div>
          {card.sub && (
            <div className="mt-0.5 text-xs text-black/50 dark:text-white/50">
              {card.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
