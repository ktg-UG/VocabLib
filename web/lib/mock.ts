/**
 * デザイン検討用のダミーデータ
 *
 * 実データは25語・回答数十件しかなく、**この密度ではUIの良し悪しを判断できない**。
 * グラフも一覧もヒートマップも「スカスカ」以外の情報が出てこないため、
 * 半年くらい使い込んだ状態を再現して、その上でデザインを詰める。
 *
 * - 本番では使わない（`/mock` は開発時のみ表示される）
 * - **乱数は固定シード**。リロードのたびに数字が動くと、デザインの変化なのか
 *   データの変化なのか分からなくなる
 */
import type { AnswerRow, RecordRow, WordRow } from "./types";

/** [英単語, 和訳, 品詞, タグ] */
const WORD_BANK: [string, string, string, string][] = [
  ["be indicative of", "〜を示す", "熟語", "TOEIC"],
  ["yield", "産出する、もたらす", "動詞", "TOEIC"],
  ["proximity to", "〜への近さ", "熟語", "TOEIC"],
  ["intimate", "親密な", "形容詞", "TOEIC"],
  ["exhaustive", "徹底的な、網羅的な", "形容詞", "TOEIC"],
  ["incorporation", "法人設立、組み入れ", "名詞", "TOEIC"],
  ["remainder of", "〜の残り", "熟語", "TOEIC"],
  ["principle", "原則、信条", "名詞", "TOEIC"],
  ["laws take effect", "法律が施行される", "熟語", "TOEIC"],
  ["courier service", "宅配便業者", "名詞", "TOEIC"],
  ["pertinent to", "〜に関連のある", "熟語", "TOEIC"],
  ["residue", "残留物", "名詞", "TOEIC"],
  ["interim", "暫定の、中間の", "形容詞", "TOEIC"],
  ["indefinitely", "無期限に", "副詞", "TOEIC"],
  ["vulnerable", "脆弱な、傷つきやすい", "形容詞", "TOEIC"],
  ["rear of", "〜の後方", "熟語", "TOEIC"],
  ["expedite", "迅速に処理する", "動詞", "TOEIC"],
  ["remains", "残り物、遺跡", "名詞", "TOEIC"],
  ["extend an invitation to", "〜を招待する", "熟語", "TOEIC"],
  ["recession", "景気後退、不況", "名詞", "TOEIC"],
  ["barely", "かろうじて", "副詞", "TOEIC"],
  ["upend", "ひっくり返す、覆す", "動詞", "TOEIC"],
  ["resilience", "回復力", "名詞", "TOEIC"],
  ["testimonials", "推薦の言葉、顧客の声", "名詞", "TOEIC"],
  ["unanimously in favor of", "満場一致で賛成して", "熟語", "TOEIC"],
  ["itinerary", "旅程表", "名詞", "TOEIC"],
  ["consecutive", "連続した", "形容詞", "TOEIC"],
  ["prospective", "見込みのある", "形容詞", "TOEIC"],
  ["adjacent to", "〜に隣接した", "熟語", "TOEIC"],
  ["reimburse", "払い戻す", "動詞", "TOEIC"],
  ["tentative", "仮の、暫定的な", "形容詞", "TOEIC"],
  ["subsidiary", "子会社", "名詞", "TOEIC"],
  ["comply with", "〜に従う", "熟語", "TOEIC"],
  ["surplus", "余剰、黒字", "名詞", "TOEIC"],
  ["preliminary", "予備の", "形容詞", "TOEIC"],
  ["delegate", "委任する", "動詞", "TOEIC"],
  ["premises", "敷地、建物", "名詞", "TOEIC"],
  ["waive", "放棄する", "動詞", "TOEIC"],
  ["outstanding", "未払いの、傑出した", "形容詞", "TOEIC"],
  ["forthcoming", "来たるべき", "形容詞", "TOEIC"],

  ["quarterly earnings", "四半期決算", "名詞", "ビジネス"],
  ["stakeholder", "利害関係者", "名詞", "ビジネス"],
  ["leverage", "活用する", "動詞", "ビジネス"],
  ["procurement", "調達", "名詞", "ビジネス"],
  ["due diligence", "適正評価", "名詞", "ビジネス"],
  ["margin", "利益率", "名詞", "ビジネス"],
  ["scalable", "拡張性のある", "形容詞", "ビジネス"],
  ["overhead", "間接費", "名詞", "ビジネス"],
  ["retention", "維持、定着", "名詞", "ビジネス"],
  ["onboarding", "受け入れ研修", "名詞", "ビジネス"],
  ["escalate", "上位に引き継ぐ", "動詞", "ビジネス"],
  ["mitigate", "緩和する", "動詞", "ビジネス"],
  ["allocate", "割り当てる", "動詞", "ビジネス"],
  ["consolidate", "統合する", "動詞", "ビジネス"],
  ["incentive", "報奨、動機付け", "名詞", "ビジネス"],
  ["turnover", "離職率、売上高", "名詞", "ビジネス"],
  ["benchmark", "基準、指標", "名詞", "ビジネス"],
  ["proprietary", "独占的な、自社専用の", "形容詞", "ビジネス"],
  ["feasible", "実行可能な", "形容詞", "ビジネス"],
  ["in accordance with", "〜に従って", "熟語", "ビジネス"],

  ["deploy", "配備する、展開する", "動詞", "IT"],
  ["latency", "遅延", "名詞", "IT"],
  ["throughput", "処理量", "名詞", "IT"],
  ["redundant", "冗長な", "形容詞", "IT"],
  ["deprecate", "非推奨にする", "動詞", "IT"],
  ["idempotent", "べき等の", "形容詞", "IT"],
  ["concurrency", "並行性", "名詞", "IT"],
  ["provision", "供給する、用意する", "動詞", "IT"],
  ["rollback", "巻き戻し", "名詞", "IT"],
  ["bottleneck", "隘路、ボトルネック", "名詞", "IT"],
  ["scaffold", "雛形を作る", "動詞", "IT"],
  ["throttle", "制限する", "動詞", "IT"],
  ["persist", "永続化する", "動詞", "IT"],
  ["mutable", "変更可能な", "形容詞", "IT"],
  ["granular", "粒度の細かい", "形容詞", "IT"],

  ["errand", "使い走り、用事", "名詞", "日常"],
  ["chore", "雑用", "名詞", "日常"],
  ["leftover", "残り物", "名詞", "日常"],
  ["commute", "通勤する", "動詞", "日常"],
  ["grocery", "食料品", "名詞", "日常"],
  ["appliance", "家電製品", "名詞", "日常"],
  ["laundry", "洗濯物", "名詞", "日常"],
  ["tidy up", "片付ける", "熟語", "日常"],
  ["run out of", "〜を切らす", "熟語", "日常"],
  ["drop by", "立ち寄る", "熟語", "日常"],
  ["hang out", "遊ぶ、たむろする", "熟語", "日常"],
  ["put off", "延期する", "熟語", "日常"],
  ["pick up", "受け取る、迎えに行く", "熟語", "日常"],
  ["stop by", "立ち寄る", "熟語", "日常"],
  ["sort out", "整理する、解決する", "熟語", "日常"],

  ["symptom", "症状", "名詞", "医療"],
  ["prescription", "処方箋", "名詞", "医療"],
  ["chronic", "慢性の", "形容詞", "医療"],
  ["dosage", "服用量", "名詞", "医療"],
  ["inflammation", "炎症", "名詞", "医療"],
  ["diagnose", "診断する", "動詞", "医療"],
  ["outpatient", "外来患者", "名詞", "医療"],
  ["side effect", "副作用", "名詞", "医療"],
];

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * 固定シードの疑似乱数（mulberry32）
 *
 * `Math.random()` だとリロードのたびにグラフが変わり、
 * 「デザインを変えたから見え方が変わったのか」が判断できなくなる。
 */
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

export type MockData = {
  words: WordRow[];
  answers: AnswerRow[];
  records: RecordRow[];
};

/**
 * 半年ほど使い込んだ状態を作る。
 *
 * 実際の学習は毎日きれいに続かないので、**サボった週**と
 * **詰め込んだ週**を混ぜる。均一なデータだとヒートマップも折れ線も
 * 現実には起こらない見え方になり、デザインの検証にならない。
 */
export function mockData(now = Date.now()): MockData {
  const random = rng(20260816);
  const today = Math.floor(now / DAY_MS) * DAY_MS;
  const startedAt = today - 180 * DAY_MS;

  const words: WordRow[] = WORD_BANK.map(([english, japanese, pos, tag], i) => {
    // 登録日をばらけさせる（全部同時に登録した状態は現実的でない）
    const createdAt = startedAt + Math.floor((i / WORD_BANK.length) * 150) * DAY_MS;
    return {
      id: `mock-${i}`,
      english,
      japanese,
      part_of_speech: pos,
      tag,
      example_sentence:
        i % 3 === 0
          ? `They will ${english.split(" ")[0]} the plan next week. — 彼らは来週その計画を${japanese.split("、")[0]}。`
          : null,
      created_at: iso(createdAt),
      updated_at: iso(createdAt),
      deleted: false,
    };
  });

  // 単語ごとの「定着度」。低いほど間違えやすい
  const mastery = words.map(() => 0.45 + random() * 0.5);

  // 最近登録してまだ一度も出題されていない単語。
  // 「未学習」が0だと復習予定パネルの3項目のうち1つが常に空になり、
  // その状態でレイアウトを判断してしまう
  const unlearnedFrom = words.length - 12;

  const answers: AnswerRow[] = [];
  for (let d = 120; d >= 0; d--) {
    const dayStart = today - d * DAY_MS;

    // 週ごとにやる気が変わる。3週に1度はほとんど手を付けない週にする
    const week = Math.floor(d / 7);
    const slump = week % 3 === 2;
    const weekday = new Date(dayStart).getUTCDay();
    const weekend = weekday === 0 || weekday === 6;

    // 5分ごとに出題するアプリなので、続いている日はそれなりの数になる
    let count = Math.round((slump ? 6 : 34) * (weekend ? 0.6 : 1) * (0.5 + random()));
    if (slump && random() < 0.6) count = 0;
    if (!slump && random() < 0.08) count = 0; // 忙しくて飛ばした日

    for (let i = 0; i < count; i++) {
      const index = Math.floor(random() * unlearnedFrom);
      // 新しく登録した単語ほど間違えやすくする
      const age = (dayStart - Date.parse(words[index].created_at)) / DAY_MS;
      if (age < 0) continue;
      const chance = Math.min(0.95, mastery[index] + Math.min(age, 120) / 300);

      answers.push({
        id: `mock-answer-${answers.length}`,
        word_id: words[index].id,
        is_correct: random() < chance,
        answered_at: iso(dayStart + 9 * 3600_000 + Math.floor(random() * 12 * 3600_000)),
      });
    }
  }

  const records: RecordRow[] = words.map((word, i) => {
    const seen = answers.filter((a) => a.word_id === word.id).length;
    const correct = answers.filter((a) => a.word_id === word.id && a.is_correct).length;

    // 未学習・期限切れ・今週分がすべて画面に出るよう散らす
    const bucket = i % 7;
    const nextReview =
      seen === 0
        ? null
        : bucket === 0
          ? today - (1 + Math.floor(random() * 12)) * DAY_MS   // 期限切れ
          : bucket <= 3
            ? today + Math.floor(random() * 7) * DAY_MS        // 今週
            : today + (8 + Math.floor(random() * 60)) * DAY_MS; // 先

    return {
      word_id: word.id,
      next_review: nextReview === null ? null : iso(nextReview),
      total_correct: correct,
      total_seen: seen,
    };
  });

  return { words, answers, records };
}
