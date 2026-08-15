# 設計書: 認証とデプロイ（Phase 6）

- 作成日: 2026-08-15
- 対象機能: F-10 認証（Googleログイン）／ F-08 のデプロイ
- 前提: Phase 1〜5 完了（Python 93件・TypeScript 24件のテストがパス、ローカルでダッシュボード動作確認済み）

---

## 1. このPhaseのゴール

**ダッシュボードに Google ログインを付け、RLSポリシーを書き、Vercel に公開する。**

Phase 5 で「認証が無い状態では公開しない」と決めた制約を、ここで解除する。

### 現在の状態と、変えるもの

|                      | Phase 5（現在）                 | Phase 6（完了後）                                             |
| -------------------- | ------------------------------- | ------------------------------------------------------------- |
| Web → Supabase      | `service_role`（RLSバイパス） | **`anon` + ログインセッション**（RLS適用）            |
| RLSポリシー          | 無し（全拒否）                  | `user_id = auth.uid()`                                      |
| `words.user_id` 等 | NULL                            | **自分のUUID**                                          |
| Mac → Supabase      | `service_role`                | `service_role`（変更なし。ただし `user_id` を付けて送る） |
| 公開URL              | 無し                            | **あり**                                                |

**Web側から `service_role` キーを完全に取り除くのが、このPhaseの本質。**

### やらないこと（明示）

- Macアプリ側のログインUI → 手元でしか動かないので `service_role` のままでよい
- 複数ユーザー対応 → 単一ユーザー前提（SPEC 2節）。ただしRLSの構造上、
  他人がログインしても**自分のデータは一切見えない**
- Web からの単語編集・テスト受験 → SPEC 1.3 で対象外

---

## 2. 全体の流れ

```
[1] Google Cloud Console で OAuth クライアントを作る
        ↓ Client ID / Secret
[2] Supabase の Authentication で Google プロバイダを有効化
        ↓
[3] Web にログイン画面を付ける（@supabase/ssr）
        ↓ ローカルでログインできることを確認
[4] 自分の UUID を確認し、既存行の user_id を埋める
        ↓
[5] RLS ポリシーを書く
        ↓ Web が anon キーで読めることを確認
[6] Mac アプリが user_id を付けて送るようにする
        ↓
[7] Vercel にデプロイ
        ↓
[8] Supabase のリダイレクトURLに本番URLを追加
```

**順序が重要。** ポリシー（[5]）を先に書くと、`user_id` がNULLのまま（[4]未実施）なので
自分のデータすら見えなくなって混乱する。

---

## 3. 認証の仕組み

### 3-1. なぜ `@supabase/ssr` が要るか

Supabase Auth のセッションは既定でブラウザの `localStorage` に入る。
しかし Next.js の Server Component は**サーバーで動く**ので `localStorage` を読めない。

そこで `@supabase/ssr` を使い、セッションを **Cookie** に保存する。
Cookie ならリクエストと一緒にサーバーへ送られるので、Server Component からも
「今ログインしているのは誰か」が分かる。

```
ブラウザ ──Cookie付きリクエスト──> Server Component ──> Supabase
                                    （anonキー + そのユーザーのセッション）
                                              ↓
                                    RLS が user_id = auth.uid() で絞る
```

### 3-2. クライアントを2種類作る

| ファイル                       | 用途                         | 使う場所                           |
| ------------------------------ | ---------------------------- | ---------------------------------- |
| `web/lib/supabase/client.ts` | ブラウザ用                   | ログインボタン（Client Component） |
| `web/lib/supabase/server.ts` | サーバー用（Cookie読み取り） | ダッシュボード（Server Component） |

両方とも **`anon` キー**を使う。`service_role` はもう使わない。

`web/lib/supabase.ts`（Phase 5 で作った `service_role` 版）は**削除する。**
残しておくと、いつか誰かが import して穴が開く。

### 3-3. 環境変数の変更

`web/.env.local` を入れ替える。

```diff
- SUPABASE_URL=https://xxxxx.supabase.co
- SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
+ NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
+ NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...
```

`NEXT_PUBLIC_` が付くのは**設計どおり**。`anon` キーはブラウザに出て良いキーで、
実際の防御はRLSが担う。ログインボタンはブラウザ側で Supabase Auth を呼ぶため、
この2つはブラウザから見える必要がある。

> Phase 5 の `.env.example` に書いた「`NEXT_PUBLIC_` を付けてはいけない」は
> `service_role` に対する注意。`anon` には当てはまらない。この違いを
> `.env.example` のコメントにも明記する。

---

## 4. RLSポリシー

### 4-1. まず自分のUUIDを確認する

ローカルでGoogleログインを済ませたあと、Supabase ダッシュボードの
**Authentication → Users** に自分の行ができる。そこの `UID` をコピーする。

### 4-2. 既存行に `user_id` を埋める（SQL Editor）

```sql
-- <YOUR-UUID> を自分のUIDに置き換える
update words            set user_id = '<YOUR-UUID>' where user_id is null;
update learning_records set user_id = '<YOUR-UUID>' where user_id is null;
update answer_log       set user_id = '<YOUR-UUID>' where user_id is null;
```

Phase 4 で「NULLで送っておき、Phase 6 でUPDATE 1回で埋める」と決めていた作業。

### 4-3. ポリシーを書く（SQL Editor）

```sql
-- words
create policy "自分の単語のみ参照" on words
  for select using (auth.uid() = user_id);

-- learning_records
create policy "自分の学習記録のみ参照" on learning_records
  for select using (auth.uid() = user_id);

-- answer_log
create policy "自分の回答履歴のみ参照" on answer_log
  for select using (auth.uid() = user_id);
```

**`select` だけにする。** Web は読み取り専用（SPEC 1.3で編集は対象外）なので、
書き込みポリシーを作る必要が無い。書けないものは壊せない。

Macアプリは `service_role` なのでポリシーの影響を受けず、従来どおり書き込める。

### 4-4. これで何が守られるか

| 状況                   | 結果                                                                      |
| ---------------------- | ------------------------------------------------------------------------- |
| 未ログインでURLを開く  | ログイン画面にリダイレクト。データは1行も返らない                         |
| 他人がGoogleでログイン | ログインはできるが、`auth.uid()` が違うので**空のダッシュボード** |
| `anon` キーが漏れる  | RLSが守るので実害なし                                                     |

---

## 5. ログイン画面

### 5-1. 画面構成

```
web/app/
├── page.tsx           ダッシュボード（要ログイン）
├── login/page.tsx     ログイン画面
└── auth/callback/route.ts   OAuthの戻り先
```

- `login/page.tsx` … 「Googleでログイン」ボタン1つだけ
- `auth/callback/route.ts` … Googleから戻ってきた認可コードをセッションに交換する
- `middleware.ts` … 未ログインなら `/login` へ飛ばす。セッションの更新も担う

### 5-2. ダッシュボード側の変更

```typescript
// 変更前（Phase 5）
const data = await fetchDashboardData();   // service_role で全件

// 変更後（Phase 6）
const supabase = await createServerClient();
const { data: { user } } = await supabase.auth.getUser();
if (!user) redirect("/login");
const data = await fetchDashboardData(supabase);  // RLSが自動で自分の行だけに絞る
```

**クエリに `where user_id = ...` を書く必要はない。** RLSがDB側で足す。
これがRLSの利点で、書き忘れによる漏洩が起き得ない。

`web/lib/stats.ts`（集計）は**一切変更しない。** データの取り方が変わるだけで、
計算は同じ。Phase 5 で層を分けておいた効果がここで出る。

---

## 6. Macアプリ側の変更

### 6-1. `user_id` を付けて送る

RLSポリシーが `user_id` で判定するようになるため、Macアプリが送る行にも
`user_id` が入っていないと、Web側から見えない。

`.env` に追加:

```
SUPABASE_USER_ID=<YOUR-UUID>
```

`SupabaseClient` が upsert 時に全行へこの値を付ける。

> Macアプリ側でGoogleログインを実装する案もあるが、メニューバーアプリに
> ブラウザ認証フローを載せるのは重い。**手元でしか動かないアプリなので、
> UUIDを設定ファイルに書くだけで十分**と判断する。

### 6-2. pull にもフィルタを足す

`service_role` はRLSをバイパスするため、他人の行まで取ってきてしまう
（単一ユーザーなので現状は無害だが、構造として正しくない）。
`fetch_since` に `user_id` の条件を足す。

**この変更は `SupabaseClient` の中だけで完結させる。**
`SyncEngine` は `user_id` を知らないままにできるので、Phase 4 で書いた
テスト21件は1つも直さずに済む。

---

## 7. Vercelへのデプロイ

### 7-1. 手順

1. https://vercel.com にGitHubアカウントでログイン
2. **Add New → Project** → このリポジトリを選択
3. **Root Directory を `web` に設定**（リポジトリ直下はPythonなので、これを忘れると失敗する）
4. Environment Variables に2つ登録
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
5. Deploy

> **`SUPABASE_SERVICE_ROLE_KEY` はVercelに登録しない。** Phase 6 完了後のWebは
> 一切使わない。登録しておくと「いつか誰かが使う」余地を残すことになる。

### 7-2. Supabase側のリダイレクトURL設定

**Authentication → URL Configuration** に本番URLを追加する。

- **Site URL**: `https://<project>.vercel.app`
- **Redirect URLs**（2つ登録する）:
  - `https://<project>.vercel.app/auth/callback`
  - `http://localhost:3000/auth/callback` … ローカル開発用に残す

これを忘れるとログイン後に「Redirect URL not allowed」で弾かれる。

### 7-3. Google Cloud Console 側

OAuthクライアントの「承認済みのリダイレクトURI」には
**Supabaseのコールバックだけ**を入れる（Vercelではない）。

```
https://<project-ref>.supabase.co/auth/v1/callback
```

Google → Supabase → 自分のアプリ、という流れなので、Googleから見た戻り先は
Supabaseになる。ここは混乱しやすい。

---

## 8. 追加する依存

| パッケージ        | 用途                                                                   |
| ----------------- | ---------------------------------------------------------------------- |
| `@supabase/ssr` | Cookieベースのセッション管理（Server Componentから認証状態を読むため） |

Python側の追加は無し。

---

## 9. テスト方針

**このPhaseで自動テストは増やさない。**

- 認証フローはブラウザのリダイレクトとCookieが絡み、自動化の費用対効果が悪い
- RLSは「DBが本当に絞るか」を実際のSupabaseで確認するしかない
- `web/lib/stats.ts` は変更しないので、既存の24件がそのまま回帰テストになる
- Mac側の `SyncEngine` も変更しないので、既存の21件がそのまま効く

既存テスト（Python 93件 / TypeScript 24件）が**全て通り続けること**を確認する。

---

## 10. 完了の定義（DoD）

### ローカル

1. `npm run dev` で `/` を開くと `/login` にリダイレクトされる
2. 「Googleでログイン」でログインでき、ダッシュボードが表示される
3. 表示される数字がPhase 5 と同じ（RLS導入でデータが欠けていない）
4. ログアウトすると `/login` に戻り、`/` を直接開いても入れない

### RLS

5. Supabase の SQL Editor で `set role anon;` してから `select * from words;` を実行すると**0行**
6. ブラウザのDevTools → Network で、リクエストに `service_role` キーが含まれていない
7. `web/` 配下を `grep -r "SERVICE_ROLE" web/` しても**何も出ない**（`.env.local` を除く）

### Macアプリ

8. 単語を追加 → 同期 → Supabaseの `words.user_id` に自分のUUIDが入っている
9. Web を再読み込みすると、その単語が反映されている
10. Python 93件・TypeScript 24件のテストが全て通る

### 本番

11. Vercel の URL を開くとログイン画面が出る
12. ログインするとダッシュボードが表示される
13. **スマホから開いて操作できる**
14. シークレットウィンドウでURLを開くと、ログインを求められデータが見えない

確認結果は `development-logs/YYYYMMDD-devlogs.md` に記録する。

---

## 11. 完了後にやること

- SPEC.md の F-08 を「実装済（公開中）」、F-10 を「実装済」に更新
- SPEC.md 7節の環境変数を更新（Web側を `NEXT_PUBLIC_*` に、Mac側に `SUPABASE_USER_ID` を追加）
- SPEC.md 8.1 の TBD「Vercelデプロイ手順」を確定内容で埋める
- SPEC.md 12.6（同期仕様）の `user_id` の記述を「NULL」から実装内容に更新
- SPEC.md に本番URLを記載
- `src/db/supabase_schema.sql` にRLSポリシーを追記（クラウド側スキーマの記録として）
