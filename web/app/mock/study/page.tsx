import { notFound } from "next/navigation";

import { Shell } from "@/components/Shell";
import { StudyView } from "@/components/StudyView";
import { mockData } from "@/lib/mock";

export const dynamic = "force-dynamic";

export default function MockStudy() {
  if (process.env.NODE_ENV === "production") notFound();

  const { words, records } = mockData();

  return (
    <Shell email="モックデータ（デザイン検討用）" current="study" base="/mock">
      <StudyView words={words} records={records} />
    </Shell>
  );
}
