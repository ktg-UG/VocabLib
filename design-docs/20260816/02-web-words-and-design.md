# 設計書: Webの単語管理とデザイン刷新（Phase 9）

- 作成日: 2026-08-16
- 対象機能: デザイン方針の確立 / Webの単語一覧・編集・削除・登録 / Webからのオートフィルと例文再生成
- 前提: Phase 1〜8 完了（Python 165件 / TypeScript 24件のテストがパス・登録25語・全語 `TOEIC` タグ）

---

## 1. なぜこのPhaseをやるか

### 1-1. 出典: 実際に使って出た不満

**この設計書の要求はすべて、開発者が実際にアプリを使ってから `memo.txt` に書き溜めた
フィードバックが出典である。** 機能を思いつきで足しているのではない。

> - ビジュアルもう少し凝ろうか？
> - 今白黒だからもっとスマートな色を使う 青とか？**AIで作った感が残るUIは嫌だ**
> - ライブラリの追加 登録した単語の可視化 表形式だけじゃなくて木構造のような…
> - 単語の削除・編集UI（`soft_delete_word()` は実装済みなのに呼び出す画面が無い）
> - webの方に一括登録機能あるといいかもね

### 1-2. 今すぐやる必要がある理由

Phase 8 で **Macの「単語一覧...」を削除した**。SPEC 1.4 の役割分担どおりだが、
その結果 **登録済みの単語を画面で確認する手段が1つも無い**。
誤登録に気付く方法も、直す方法も無い。ここを塞ぐのが最優先。

### 1-3. デザインを先に決める理由

Phase 8 で使った原則の言い換えになる。

> スキーマに触るものはUIより先。画面が増えてからデータ構造を変える方が高くつく。

**デザインも同じ。** 単語一覧を今の見た目で作ってから配色とタイポを変えると、
ダッシュボードと一覧の両方を書き直すことになる。
**トークンを先に決め、新しい画面はその上に建てる。**

### 1-4. 開発者との確認で確定したこと（2026-08-16）

| 論点 | 決定 |
| ---- | ---- |
| スコープ | デザイン方針 → 単語一覧・編集・削除 |
| Webからの新規登録 | **1語ずつの登録もやる**（一括登録は今回やらない） |
| 編集できる項目 | 和訳 / 品詞 / タグ / **例文（再生成ボタン）**。英単語は不可 |
| Webのオートフィル | **やる**（当初は見送る予定だったが、例文の再生成でどのみちLLM経路が要るため） |

### やること

| ID  | 内容 | 層 |
| --- | ---- | -- |
| 9-1 | デザイントークンの定義と既存ダッシュボードへの適用 | web |
| 9-2 | 単語一覧ページ（検索・タグ絞り込み） | web |
| 9-3 | 編集（和訳・品詞・タグ）と削除 | web / supabase |
| 9-4 | 1語ずつの新規登録 | web / supabase |
| 9-5 | RLSポリシーの追加と `learning_records` 自動生成トリガー | supabase |
| 9-6 | Webからの LLM 呼び出し（和訳オートフィル / 例文の再生成） | web |

### やらないこと（明示）

- **Webからの一括登録** … 長時間処理をブラウザでどう待たせるかの設計が別途要る。
  Macの `import_words` で足りている
- **WebからのOllamaフォールバック** … 原理的に不可能（6-1 参照）
- **木構造での可視化** … `memo.txt` にある希望だが、25語では見て楽しい構造にならない。
  タグが数種類に増えてから再検討する
- **Webからの出題・回答** … SPEC 4.1 の F-11。引き続き対象外
- **ダークモードの作り込み** … トークンは両対応で定義するが、配色の詰めは片方に集中する

---

## 2. デザイン方針（9-1）

### 2-1. 「AIっぽいUI」の正体

`memo.txt` に、何がそう見えるかまで分解済み。**これを設計要件として扱う。**

| 症状 | 対策 |
| ---- | ---- |
| 全部を同じ角丸カードに入れている → 情報の階層が消える | カードを使う場所を決める。表・リストは素で置く |
| フォントサイズが2〜3種類しかない | 5段階の階層を定義し、**数字を主役にする** |
| グレー基調＋1色アクセント | 彩度を落とした青を1色、**面積を小さく**使う |
| 見出しに絵文字 | 使わない |
| 余白が均一で密度のメリハリがない | 「まとまりの中」と「まとまりの間」で余白を変える |

### 2-2. トークン（`app/globals.css`）

Tailwind v4 なので `@theme` に定義し、コンポーネントはトークンだけを参照する。
**個別のコンポーネントに生の色を書かない**（後で一括変更できなくなるため）。

```css
@theme {
  /* 面: 背景 → カード → 罫線 の3段だけ。増やすと使い分けが曖昧になる */
  --color-surface:        #fbfbfa;
  --color-surface-raised: #ffffff;
  --color-border:         #e6e4e0;

  /* 文字: 主・副・弱の3段 */
  --color-ink:      #1c1b19;
  --color-ink-mute: #5f5c57;
  --color-ink-weak: #918d86;

  /* アクセント: 彩度を落とした青。面積は小さく使う */
  --color-accent:      #3f5f8f;
  --color-accent-weak: #eef2f8;

  /* 状態: 正誤の2色のみ。これ以上増やさない */
  --color-positive: #3d7a5c;
  --color-negative: #a4544a;
}
```

タイポグラフィは5段階。**数字だけは1段大きく、字幅を揃える**（`tabular-nums`）。

| 用途 | サイズ | 太さ |
| ---- | ------ | ---- |
| ページ見出し | 24px | 600 |
| セクション見出し | 15px | 600 |
| 本文 | 14px | 400 |
| 補足・ラベル | 12px | 400 |
| 指標の数値 | 32px | 600 / `tabular-nums` |

背景をわずかに温かみのある白（`#fbfbfa`）にし、カードだけ純白にする。
これだけで「カードが浮いている」ことが色で伝わり、**枠線と影に頼らなくて済む**。

### 2-3. カードを使う場所

- **使う**: 指標（通算正答率・連続日数・登録語数）、グラフ
- **使わない**: 苦手単語の表、単語一覧。**行そのものが単位**なので、
  外枠で囲うと情報の階層が1段無駄になる

---

## 3. 単語一覧（9-2）

### 3-1. 画面

`/words`。ヘッダーにダッシュボード（`/`）との行き来を置く。

```
単語一覧                                      [+ 単語を追加]

[ 検索: 英単語・和訳 ]   [ すべて ▾ ] [ TOEIC 25 ]

英単語                和訳                    品詞    タグ
─────────────────────────────────────────────────────────
be indicative of     〜を示す                熟語    TOEIC    [編集]
yield                産出する、もたらす        動詞    TOEIC    [編集]
...
                                                       25語
```

- 検索は**英単語と和訳の両方**を対象にする（どちらで思い出すか分からないため）
- タグはボタン列で切り替える（種類が少ないうちはプルダウンより速い）
- 並びは `created_at` 昇順（登録順）。ソート機能は付けない
- **ページングもしない。** 数百語まではクライアント側の絞り込みで足りる

### 3-2. データ取得

`fetchDashboardData()` が既に `words` を全件取っているので、**新しい取得処理は要らない**。
一覧ページも同じ関数を使う。

絞り込みは純粋関数として `lib/words.ts` に置き、`lib/stats.ts` と同じくテストする。

```ts
export function filterWords(
  words: WordRow[],
  { query, tag }: { query: string; tag: string | null },
): WordRow[]
```

- 大文字小文字を無視する
- 前後の空白を無視する
- 空クエリは全件

---

## 4. 書き込み（9-3 / 9-4）

### 4-1. Server Actions で書く（`updated_at` をサーバーで作る）

**ブラウザから直接 Supabase に書かない。** 理由は `updated_at`。

同期はこの値のLWWで衝突を解決している（SPEC 12.6）。ブラウザの時計が数分ずれていると、
**Webでの編集がMacの古い値に負けて消える**。Server Action ならVercelのサーバー時計で
生成でき、`new Date().toISOString()` を信用してよい。

```
"use server" の中で:
    1. createClient()（Cookieのセッションを読む）
    2. auth.getUser() で本人確認
    3. update / insert に updated_at = new Date().toISOString() を必ず入れる
    4. revalidatePath("/words")
```

RLSも同じセッションで効くので、`user_id` の条件はここでも書かない。

### 4-2. 編集

編集する項目は **和訳 / 品詞 / タグ / 例文** の4つ。

**英単語は編集させない。** 綴りが変わるのは実質「別の単語」であり、
学習履歴（`answer_log`）が別語の記録として残ってしまう。
綴りを間違えたときは削除して登録し直す。

- 和訳は自由入力
- 品詞は Mac と同じ9種のプルダウン（`PARTS_OF_SPEECH` と同じ並び）
- タグは自由入力。`normalize_tag()` と同じ規則を TypeScript で実装する
  （**Python版とテストで同じケースを通す**。片方だけ直る事故を防ぐため）
- 例文は自由入力に加えて **［再生成］ボタン**（6-3）。
  `memo.txt` の「LLMがハズレを出したとき、キャッシュされたら直せない」への対応

### 4-3. 削除

**ユーザーから見た動作は「消える」**（一覧からも出題からも消え、統計の登録語数も減る）。
内部的には `deleted = true` と `updated_at` を立てる論理削除で、行そのものは残す。

**なぜ行ごと消さないか。** 同期は「`updated_at` が前回より新しい行」を pull する仕組み
（SPEC 12.6）。行を物理削除すると **Macには何も届かない**。結果:

```
Supabase: 行が消える
Mac:      削除を知る手段が無いので単語が残ったまま
  ↓ 次のpush
Supabase: Macが持っている単語が復活する   ← 消したはずなのに戻る
```

墓標（`deleted = true`）はこれを防ぐためにある。

- 確認ダイアログを出す
- 回答履歴（`answer_log`）は消さない。過去の統計は保たれる
- 削除後、Macは次のpullで `deleted = 1` を受け取り出題対象から外す

### 4-4. 新規登録

入力は **英単語 / 和訳 / 品詞 / タグ**。Macの追加フォームと同じ考え方にする。

```
英単語  [ incorporation        ] ［オートフィル］
和訳    [ 法人設立、組み入れ      ]
品詞    [ 名詞            ▼ ]
タグ    [ TOEIC                ]
                        ［キャンセル］［保存］
```

- 英単語欄で `incorporation #TOEIC` と書けばタグに分かれる（`parse_word_input` と同じ規則）
- ［オートフィル］で和訳と品詞を埋める（6-2）。**失敗したら空欄のまま手入力**
- 重複の扱いはMacと揃える。同じ (英単語, 和訳) は登録できない
  （Supabase側のユニーク制約のエラーを拾って表示する）

---

## 5. Supabase側（9-5）

### 5-1. RLSポリシーの追加

Phase 6 では「select だけにする。書けないものは壊せない」と決めたが、
SPEC 1.4 でWebが編集・削除を担うと決めたため、この判断を**変更する**。

```sql
-- 自分の行だけ更新できる（編集・論理削除の両方がこれで通る）
create policy "update own words" on words
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 自分の行だけ追加できる
create policy "insert own words" on words
  for insert with check (auth.uid() = user_id);
```

`user_id` を書き忘れると `with check` で弾かれるので、既定値を入れておく。

```sql
alter table words alter column user_id set default auth.uid();
```

**`delete` ポリシーは作らない。** これは「単語を削除できない」という意味ではない。
削除は 4-3 の論理削除（`update` ポリシーで通る）で行うため、
**SQLの `DELETE` を許す必要が無い**というだけ。

むしろ物理削除を許すと、4-3 に書いた「消したはずの単語がMacから復活する」経路を
自分で開けることになる。**使わない権限は与えない。**

### 5-2. `learning_records` を自動生成するトリガー

Webから単語を登録すると、`words` の行だけができて `learning_records` が無い状態になりうる。
**これは v1 で実際に起きたバグ**（例文の保存に失敗する原因。SPEC 12.4 / `test_store.py`）。

PostgRESTは1リクエスト1文なので、2テーブルへのinsertをアプリ側で並べても
トランザクションにならない。**トリガーでDB側に寄せる。**

```sql
create or replace function create_learning_record()
returns trigger language plpgsql security definer as $$
begin
  insert into learning_records (word_id, user_id, ease_factor, updated_at)
  values (new.id, new.user_id, 2.5, new.created_at)
  on conflict (word_id) do nothing;   -- Macのpushと衝突しても無害
  return new;
end;
$$;

create trigger words_create_learning_record
  after insert on words
  for each row execute function create_learning_record();
```

- `on conflict do nothing` なので、Macのpush（`words` → `learning_records` の順）でも壊れない
- `security definer` にすることで、`learning_records` に insert ポリシーを作らずに済む
- **どの経路から `words` が入っても学習記録が必ず存在する**、という不変条件がDBで保証される

### 5-3. Webで登録した単語がMacに届くまで

```
Web: words に insert（トリガーが learning_records も作る）
  ↓ Macの次回pull（順序は words → learning_records → answer_log）
Mac: apply_remote_word() で words に入る
     apply_remote_record() で learning_records に入る
  ↓
出題対象になる（get_next_word は words と learning_records をJOINするため、
両方揃って初めて出題される）
```

pullの順序が既に `words` 先なので、**同期エンジンの変更は不要**。

---

## 6. WebからのLLM呼び出し（9-6）

### 6-1. Macとの決定的な違い: 3段フォールバックが使えない

Macは Gemini → Ollama → ローカル生成 の3段（SPEC 12.5）。
**Webでは2段目が原理的に不可能。** Ollamaは開発者のMacの `localhost:11434` で動いており、
Vercelのサーバーからは到達できない。

```
Mac : Gemini → Ollama → ローカル生成   （必ず何かが返る）
Web : Gemini → 失敗を表示して手入力      （空欄のまま保存できる）
```

**これは仕様として受け入れる。** Web側で「必ず何か返す」ために品質の低い文字列を
でっち上げても、覚える助けにならないものがDBにキャッシュされるだけで害になる。
失敗したことを正直に見せて手入力させる方がよい。

### 6-2. 置き場所と鍵

- 呼び出しは **Server Action**（`"use server"`）。ブラウザからGeminiを直接呼ばない
- `GEMINI_API_KEY` は Vercel の環境変数に置き、**`NEXT_PUBLIC_` を付けない**
  （付けるとブラウザのバンドルに焼き込まれ、鍵が公開される）
- キー未設定でもアプリは動く。［オートフィル］ボタンを無効にするだけ
  （Mac側でGemini未設定でも動くのと同じ考え方）
- `export const maxDuration = 30;` を置く。Geminiはデッドライン10秒未満を400で拒否するため
  （SPEC 12.5）、Vercelの既定10秒では**余裕が無い**

### 6-3. 移植するもの

`src/llm/` のうち、Webに要るのは以下だけ。**3段フォールバックの司令塔は移植しない**
（2段目が無いので分岐が不要）。

| Python | TypeScript | 用途 |
| ------ | ---------- | ---- |
| `parsing.extract_json` | `extractJson` | コードフェンス付きの出力からJSONを取る |
| `parsing.looks_japanese` | `looksJapanese` | 和訳が英語のまま返る事故を弾く |
| `parsing.extract_example_line` | `extractExampleLine` | 「英文 — 和訳」の行を取り出す |
| `parsing.sentence_uses_word` | `sentenceUsesWord` | **例文が対象単語を含むか**検証する |

> **二重管理の事故を防ぐ手当て。** これらは `web/lib/llm/parsing.ts` に置き、
> `web/lib/llm/parsing.test.ts` で **`tests/test_llm_parsing.py` と同じケースを通す**。
> 片方だけ直る事態を、テストの対応で検出できるようにする。
> タグの `normalize_tag` でも同じ手を使う（4-2）。

### 6-4. 例文の再生成

編集画面の［再生成］で `generateExampleSentence(english, japanese)` を呼ぶ。

1. Geminiに投げる
2. `extractExampleLine` → `sentenceUsesWord` で検証する
3. 通ったら `example_sentence` と `updated_at` を更新する
4. **検証に落ちたら保存せず「生成できませんでした」と出す**
   （対象単語を含まない例文をキャッシュすると、覚える助けにならない）

Macは次のpullで新しい例文を受け取る。

---

## 7. テスト方針

| ファイル | 追加するテスト |
| -------- | -------------- |
| `web/lib/words.test.ts`（新規） | `filterWords`: 英単語で一致 / 和訳で一致 / 大文字小文字を無視 / 前後空白を無視 / タグ絞り込み / 空クエリで全件 / 該当なし |
| `web/lib/tags.test.ts`（新規） | `normalizeTag` / `parseWordInput`: **Python版 `test_tags.py` と同じケース**を通す（前後空白・先頭 `#`・内側の空白・カンマ除去・空文字） |
| `web/lib/llm/parsing.test.ts`（新規） | `extractJson` / `looksJapanese` / `extractExampleLine` / `sentenceUsesWord`: **Python版 `test_llm_parsing.py` と同じケース**を通す |

Server Actions と画面は手動確認とする（Supabaseのセッションが要るため）。
**純粋関数だけをテストで固める**方針は `lib/stats.ts` と同じ。

Python側は変更が無いので、165件がそのまま通ること。

---

## 8. 完了の定義（DoD）

`uv run pytest` / `npx vitest run` / **`npm run build`** が通ることに加え、以下を手動で確認する。

> `npm run dev` は型検査が緩く、Phase 5 で本番ビルドだけが落ちた。
> **push前に必ず `cd web && npm run build`**（SPEC 8.1）。

### デザイン

1. ダッシュボードがトークンベースの配色になり、絵文字見出しが無い
2. 指標の数値が主役になっている（サイズと `tabular-nums`）
3. スマホ幅で崩れない

### 一覧

4. `/words` に25語が表示される
5. 英単語でも和訳でも検索できる
6. タグ「TOEIC」で絞り込める

### 編集・削除

7. 和訳・品詞・タグを編集して保存でき、再読み込み後も残っている
8. 英単語は編集できない（項目自体が無い）
9. 削除すると一覧から消える
10. **Macで「今すぐ同期」すると、編集内容がMac側に反映される**
11. 削除した単語がMacで出題されなくなる
12. 削除しても統計（過去の回答履歴）が残っている

### 登録

13. Webから単語を登録でき、一覧に出る
14. 同じ (英単語, 和訳) を登録しようとするとエラーが表示される
15. **Macで同期すると、Webで登録した単語が出題される**
    （= `learning_records` がトリガーで作られている）
16. 他人のセッション（シークレットウィンドウ）では登録も編集もできない

### オートフィル・例文

17. ［オートフィル］で和訳と品詞が埋まる
18. `incorporation #TOEIC` と入力するとタグ欄に分かれる
19. **APIキーが未設定でも画面が壊れず、ボタンが無効になるだけ**
20. 編集画面の［再生成］で例文が作り直される
21. 生成された例文が対象単語を含まない場合、保存されずエラーが出る
22. Macで同期すると、Webで再生成した例文がMac側の不正解時に表示される
23. **ブラウザのバンドルに `GEMINI_API_KEY` が含まれていない**
    （ビルド成果物を `grep` して確認する）

確認結果は `development-logs/YYYYMMDD-devlogs.md` に記録する。

---

## 9. 完了後にやること

- SPEC.md 4.1 に F-14「Webでの単語管理（一覧・編集・削除・登録）」を追加
- SPEC.md 12.8 のRLSポリシーを更新（select のみ → insert / update を追加した経緯と理由）
- SPEC.md 12.12 を新設し、**デザイントークン**と `learning_records` トリガーを記録
- SPEC.md 1.3 の「Webからの単語登録は対象外」を、1.4 と矛盾しない記述に改める
- 「UI・ビジュアルの作り込み」のTBDを完了にする
- SPEC.md 7.1 の Web 環境変数に `GEMINI_API_KEY` を追加（`NEXT_PUBLIC_` を付けない旨も）
- SPEC.md 12.5 に「Web側は2段フォールバックが使えない」ことを追記
- Phase 10 の候補: Webからの一括登録 / `.app` 配布 / 出題方向の切替 / 苦手単語の優先出題
