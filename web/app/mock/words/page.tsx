import { notFound } from "next/navigation";

import { Shell } from "@/components/Shell";
import { WordsView } from "@/components/WordsView";
import { mockData } from "@/lib/mock";

export const dynamic = "force-dynamic";

export default function MockWords() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <Shell email="モックデータ（デザイン検討用）" current="words" base="/mock">
      <WordsView words={mockData().words} />
    </Shell>
  );
}
