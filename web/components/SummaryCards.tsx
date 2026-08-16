type Card = {
  label: string;
  value: string;
  sub?: string;
};

/**
 * 指標カード
 *
 * **数字を主役にする。** ラベルは小さく弱い色に落とし、値だけを大きく置く。
 * カードを使うのはここ（とグラフ）だけ。表やリストは素で並べる。
 */
export function SummaryCards({ cards }: { cards: Card[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border border-border bg-surface-raised px-4 py-3.5"
        >
          <div className="text-xs text-ink-weak">{card.label}</div>
          <div className="mt-1 text-[32px] leading-none font-semibold tracking-tight">
            {card.value}
          </div>
          {card.sub && <div className="mt-1.5 text-xs text-ink-weak">{card.sub}</div>}
        </div>
      ))}
    </div>
  );
}
