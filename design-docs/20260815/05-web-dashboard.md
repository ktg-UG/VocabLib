# 設計書: Webダッシュボード（Phase 5）

- 作成日: 2026-08-15
- 対象機能: F-08 Webダッシュボード（統計可視化 / Tier1）
- 前提: Phase 1〜4 完了（テスト93件パス、Supabase同期が実機で動作確認済み）

---

## 1. このPhaseのゴール

**Supabaseに溜まった学習データを、スマホ/PCのブラウザでグラフとして見られるようにする。**

表示する指標は SPEC 11.1 で確定済みの4種。

| # | 指標 | データ元 |
|---|---|---|
| 1 | 正答率の推移 | `answer_log` を日別集計 |
| 2 | 継続日数（streak）+ ヒートマップ | `answer_log` の日付 |
| 3 | 苦手単語 Top | `answer_log` × `words` |
| 4 | 復習予定数 | `learning_records.next_review` |

### やらないこと（明示）

- **Vercelへのデプロイ** → Phase 6 の後（理由は2節）
- Web からの単語追加・編集 → SPEC 1.3 で対象外
- Web でのテスト受験（Tier2） → SPEC 1.3 で対象外
- Googleログイン → Phase 6

---

## 2. 重要: このPhaseではデプロイしない

Phase 4 で3テーブルすべてに **RLSを有効化し、ポリシーを書いていない**。
つまり `anon` キーからは何も読めない。ダッシュボードがデータを読むには
`service_role` キー（RLSをバイパスする管理者権限）をサーバー側で使うことになる。

Next.js の Server Component ならキー自体はブラウザに出ないので、
**キーの漏洩は起きない。** しかし別の問題が残る。

> **認証が無い状態でVercelにデプロイすると、URLを知っている人は誰でも
> 学習データを見られる。**

SPEC 2節にも「Webは公開URLになるため認証で本人のみに限定する」と書いてある。
語彙の統計なので機微性は低いが、原則を崩す理由がない。

### 進め方

| Phase | やること |
|---|---|
| **5（今回）** | `npm run dev` でローカル起動して作り込む。**公開しない** |
| 6 | Googleログイン + RLSポリシーを入れる → **そのうえでVercelにデプロイ** |

こうすると「認証の無い公開URL」が一度も存在しない状態で進められる。

> 先にURLが欲しい場合は、Next.jsのmiddlewareで簡易パスワードをかける手もある。
> ただしPhase 6で作り直す使い捨ての実装になるので、推奨しない。

---

## 3. 技術スタック

| 区分 | 選定 | 理由 |
|---|---|---|
| フレームワーク | Next.js（App Router）/ TypeScript | SPEC 3節で確定済み。Vercelとの相性が最良 |
| スタイル | Tailwind CSS | Next.jsの標準セットアップに含まれる |
| グラフ | Recharts | Reactに素直に馴染む。SVGなのでスマホでも綺麗 |
| Supabase接続 | `@supabase/supabase-js` | 公式 |
| テスト | Vitest | 集計ロジック（純粋関数）のみ対象 |
| パッケージ管理 | npm | 標準。追加の学習コストがない |

### 配置

```
VocabLib/
├── src/          ← Macアプリ（Python）
└── web/          ← ダッシュボード（TypeScript）※新規
```

同一リポジトリに置く。別リポジトリに分けるほどの規模ではなく、
`SPEC.md` と `design-docs/` を共有できる利点の方が大きい。

`.gitignore` に以下を追加する。

```gitignore
web/node_modules/
web/.next/
web/.env.local
```

---

## 4. データの読み方

### 4-1. 接続はサーバー側だけ

```
ブラウザ ──> Next.js Server Component ──> Supabase
                （Vercel / ローカル）      service_role
```

- `service_role` キーは **`NEXT_PUBLIC_` を付けない**環境変数に置く。
  Next.jsは `NEXT_PUBLIC_` が付いた変数だけをブラウザに渡すので、
  この命名規則がそのまま防御になる。
- Supabaseクライアントを作るコードは `server-only` パッケージ、または
  Server Component / Route Handler の中だけに置く。
  誤ってClient Componentから import したらビルド時に落ちるようにする。

`web/.env.local`（Git除外）:

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
```

Macアプリの `.env` と同じ値。**この2ファイル以外にキーを置かない。**

### 4-2. 集計はTypeScript側でやる

Postgresのビューや関数を作る案もあるが、**取ってきてTSで集計する**方針にする。

理由:
- `answer_log` は個人利用で1日数十件。年単位でも数万行に届かず、全件取得しても軽い
- SQLビューを足すとスキーマ変更になり、Phase 4 で作った同期の前提に触る
- 集計ロジックがTS側にあれば、そのまま純粋関数としてテストできる

> 目安として `answer_log` が1万行を超えたらSQL側（ビューまたはRPC）に移す。
> その判断ラインをSPECに書いておく。

---

## 5. 画面設計

1ページ（`/`）に収める。スマホで縦スクロールして全部見える形。

```
┌─────────────────────────────────────┐
│ VocabLib                            │
│ 最終更新 2026-08-15 18:30           │
├─────────────────────────────────────┤
│ ┌────────┬────────┬────────┬──────┐ │
│ │ 通算   │ 正答率 │ 連続   │ 登録 │ │  ← サマリーカード4枚
│ │ 156問  │ 82.1%  │ 5日    │ 42語 │ │
│ └────────┴────────┴────────┴──────┘ │
├─────────────────────────────────────┤
│ 正答率の推移（直近30日）             │
│   ╭─╮   ╭──╮                        │  ← 折れ線グラフ（Recharts）
│  ╭╯ ╰──╯  ╰─╮                       │
├─────────────────────────────────────┤
│ 学習の記録（直近12週）               │
│ □■■□■■■□■□■■■■□□■■■■□          │  ← ヒートマップ（自前のグリッド）
├─────────────────────────────────────┤
│ 苦手な単語                           │
│  1. postpone  延期する  誤答5 / 71% │  ← テーブル
│  2. ...                             │
├─────────────────────────────────────┤
│ 復習の予定                           │
│  期限切れ 12 / 今週 34 / 未学習 9   │
└─────────────────────────────────────┘
```

### ヒートマップは自前で作る

GitHubの草のようなカレンダー。専用ライブラリを足さず、
`grid` で7×N のマス目を並べるだけで十分。依存を1つ減らせる。

---

## 6. ディレクトリ構成

```
web/
├── app/
│   ├── layout.tsx          共通レイアウト（ダークモード対応）
│   ├── page.tsx            ダッシュボード本体（Server Component）
│   └── globals.css
├── components/
│   ├── SummaryCards.tsx
│   ├── AccuracyChart.tsx   ← Client Component（Rechartsが要求するため）
│   ├── StreakHeatmap.tsx
│   ├── WeakWordsTable.tsx
│   └── DueCounts.tsx
├── lib/
│   ├── supabase.ts         サーバー専用クライアント
│   ├── types.ts            DBの行の型
│   └── stats.ts            集計（純粋関数）← テスト対象
├── lib/stats.test.ts
├── .env.local              Git除外
└── package.json
```

**`lib/stats.ts` はSupabaseもReactもimportしない。**
Phase 1〜4で `srs` / `quiz` / `llm` / `sync` に対して守ってきた方針と同じで、
「データを受け取って計算するだけ」の層を独立させ、そこだけテストする。

---

## 7. 集計ロジック（`lib/stats.ts`）

```typescript
export type AnswerRow = {
  id: string;
  word_id: string;
  is_correct: boolean;
  answered_at: string;   // ISO8601 (UTC)
};

export function toJstDate(iso: string): string;              // "2026-08-15"
export function dailyAccuracy(rows: AnswerRow[], days: number): DailyPoint[];
export function currentStreak(rows: AnswerRow[]): number;
export function weakWords(rows: AnswerRow[], words: WordRow[], limit: number): WeakWord[];
export function dueCounts(records: RecordRow[]): DueCounts;
```

### JSTの扱いが最大の落とし穴

`answered_at` はUTCで保存されている。日本時間の「1日」で区切るには
**+9時間してから日付を取り出す**必要がある。

Macアプリ側は `date(answered_at, '+9 hours')`（`src/db/store.py`）でやっている。
**Web側も同じ基準にしないと、両者で連続日数がずれる。**

深夜0〜9時（JST）の回答が前日に数えられてしまうのが典型的な事故なので、
テストで必ず押さえる。

### streakの定義もMacアプリと揃える

`Store.get_streak()` の仕様に合わせる。

- JST基準の連続日数
- **今日まだ未回答でも、昨日まで続いていれば継続扱い**（今日の分をこれからやる余地を残す）
- 直近の学習日が今日でも昨日でもなければ 0

---

## 8. テスト方針

`web/lib/stats.test.ts` を Vitest で。**ネットワークにもDBにも触らない。**

| テスト | 内容 |
|---|---|
| UTC→JSTの日付変換 | `2026-08-15T15:30:00Z` → `2026-08-16`（JSTでは翌日） |
| **JST深夜の回答が当日に数えられる** | `2026-08-15T20:00:00Z`（JST 8/16 5:00）→ `2026-08-16` |
| 日別正答率を計算できる | 同じ日の複数回答がまとまる |
| 回答が無い日は0件として並ぶ | グラフが途切れないこと |
| streakが連続日数を返す | |
| **今日未回答でも昨日まで続いていれば継続** | Macアプリと同じ挙動 |
| 2日以上空いたら0 | |
| 苦手単語が誤答数の多い順に並ぶ | |
| 全問正解の単語は苦手に出ない | |
| 復習予定数を区分できる | 期限切れ / 今週 / 未学習 |

Reactコンポーネントの描画テストはしない（見た目は手動確認で足りる）。

---

## 9. 追加する依存（npm）

CLAUDE.md の規約により、**導入前に開発者の承認を得る**。

| パッケージ | 用途 |
|---|---|
| `next` / `react` / `react-dom` | フレームワーク |
| `typescript` / `@types/*` | 型 |
| `tailwindcss` | スタイル |
| `recharts` | 折れ線グラフ |
| `@supabase/supabase-js` | Supabase接続 |
| `server-only` | サーバー専用モジュールの誤importをビルドで弾く |
| `vitest` | 集計ロジックのテスト |

`create-next-app` を使えば上から5つは自動で入る。

Node.js が必要（20以上）。未導入なら `brew install node`。

---

## 10. 完了の定義（DoD）

`npm test`（Vitest）が通ることに加え、以下を手動で確認する。

1. `npm run dev` で `http://localhost:3000` が開く
2. サマリーカード4枚に、Macアプリの「統計...」と**同じ数字**が出る
3. 正答率の推移グラフが描画される（回答が1日分しかなくても崩れない）
4. ヒートマップに学習した日が色付きで出る
5. 苦手単語がMacアプリの表示と同じ順で並ぶ
6. 復習予定数がMacアプリと一致する
7. Macアプリで回答 → 同期 → ブラウザを再読み込みすると数字が増える
8. スマホ幅（375px）で横スクロールが発生せず、全部読める
9. ブラウザの DevTools → Network / ソースを見て、**`service_role` キーがどこにも出ていない**
10. `answer_log` が0件でもエラーにならず「まだデータがありません」と出る

2 と 6 が特に重要。**Python側とTypeScript側で同じ集計結果になること**の確認で、
JSTの扱いがずれていればここで露見する。

確認結果は `development-logs/YYYYMMDD-devlogs.md` に記録する。

---

## 11. 完了後にやること

- SPEC.md の F-08 を「実装済（ローカルのみ / 未デプロイ）」に更新
- SPEC.md 3節に Web 側の技術スタック詳細（Next.js / Tailwind / Recharts / Vitest）を追記
- SPEC.md 7節に Web の環境変数（`web/.env.local`）を追記
- SPEC.md に「`answer_log` が1万行を超えたら集計をSQL側に移す」判断ラインを追記
- SPEC.md 12.1 のモジュール表に `web/` を追記
