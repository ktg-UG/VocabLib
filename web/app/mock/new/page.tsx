import { notFound } from "next/navigation";

import { AddWordForm, type AddWordState } from "@/components/AddWordForm";
import { Section, Shell } from "@/components/Shell";

export const dynamic = "force-dynamic";

/** モックでは保存しない。見た目の確認だけができればよい */
async function noop(): Promise<AddWordState> {
  "use server";
  return { error: "モック画面では保存しません。" };
}

export default function MockNewWord() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <Shell email="モックデータ（デザイン検討用）" current="new" base="/mock">
      <Section title="単語を追加">
        <AddWordForm
          action={noop}
          disabledReason="モック画面のため保存できません（本番の /words/new で動きます）"
        />
      </Section>
    </Shell>
  );
}
