import { notFound } from "next/navigation";

import { Shell } from "@/components/Shell";
import { WordsView, type EditWordState } from "@/components/WordsView";
import { mockData } from "@/lib/mock";

export const dynamic = "force-dynamic";

/** モックでは保存しない。編集フォームの見た目だけ確認できればよい */
async function noop(): Promise<EditWordState> {
  "use server";
  return { error: "モック画面では保存しません（本番の /words で動きます）。" };
}

async function noRegenerate() {
  "use server";
  return { error: "モック画面ではLLMを呼びません。" };
}

export default function MockWords() {
  if (process.env.NODE_ENV === "production") notFound();

  const { words, records } = mockData();

  return (
    <Shell email="モックデータ（デザイン検討用）" current="words" base="/mock">
      <WordsView
        words={words}
        records={records}
        onUpdate={noop}
        onDelete={noop}
        onRegenerate={noRegenerate}
      />
    </Shell>
  );
}
