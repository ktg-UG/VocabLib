# 設計書: Macアプリの .app 配布（Phase 10）

- 作成日: 2026-08-16
- 対象機能: `.app` バンドルの作成 / ログイン時の自動起動 / 設定ファイルの置き場所変更
- 前提: Phase 1〜9 完了（Python 169件 / TypeScript 79件のテストがパス・本番公開中）

---

## 1. なぜやるか

`memo.md` に最初期から残っていて、SPEC の未確定事項にも最も長く居座っている項目。

> Macの方のアプリに関して、今ローカルで実行してるだけだからアプリ化しようね

**毎回ターミナルから `uv run python -m src.main` を打つ状態では、使い続けられない。**
使われなければ回答も貯まらず、Phase 9 で作った統計もグラフも意味を持たない。
機能を足すより、まずここを塞ぐ方が効く。

### 開発者との確認で確定したこと（2026-08-16）

| 論点 | 決定 |
| ---- | ---- |
| ビルド方法 | **py2app**（rumps 公式ドキュメントが推奨。macOS専用でよい） |
| `.env` の場所 | **`~/Library/Application Support/VocabLib/.env`**（＝DBと同じ場所） |

### やること

| ID | 内容 |
| -- | ---- |
| 10-1 | `.env` の探索順を変える（アプリ内に鍵を焼き込まない） |
| 10-2 | `setup.py` と py2app の設定 |
| 10-3 | メニューバー常駐（Dockに出さない）の指定 |
| 10-4 | ビルド手順とログイン項目への登録を README / SPEC に記録 |

### やらないこと（明示）

- **コード署名・公証（notarization）** … Apple Developer Program（年間$99）が要る。
  自分のMacで動かすだけなので、初回だけ右クリック→開くで足りる
- **配布（他人に渡す）** … 単一ユーザー前提のアプリ（SPEC 9）。
  ただし**鍵を焼き込まない**ので、渡そうと思えば渡せる状態にはしておく
- **自動アップデート** … 手元でビルドし直せばよい
- **アイコンの作成** … 既定のままにする。必要になったら足す

---

## 2. `.env` の置き場所（10-1）

### 2-1. v1 は鍵を .app に焼き込んでいた

`legacy/VocabLib.spec` に残っている。

```python
datas=[('.env', '.'), ('credentials.json', '.')]
```

**配布物を渡した瞬間に鍵が渡る。** 今のv2で同じことをすると、
Gemini のAPIキーに加えて **Supabase の `service_role` キー**まで渡ることになる。
`service_role` は RLS をバイパスするので、影響が段違いに大きい。**繰り返さない。**

### 2-2. 探索順

`src/config.py` の現状はこうなっている。

```python
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")
```

`.app` にすると `__file__` はバンドルの中を指すので、**開発者の `.env` は永久に見つからない。**

探索順を2段にする。

```
1. <リポジトリルート>/.env                        ← 開発中はここ
2. ~/Library/Application Support/VocabLib/.env   ← 配布後はここ
```

**当初は逆順（Application Support を先）で設計したが、実装中に踏んで変更した。**

`~/Library/Application Support/VocabLib/` に **v1 の `.env` が残っていた**
（2026-02、Google Sheets 用）。Application Support を先に読む順序だと、
この古いファイルがリポジトリの `.env` を黙って隠し、
**Gemini のキーも Supabase の設定も読めない状態**になる（実際になった）。

さらに、配布後に `.env` をコピーすると2つのファイルが並存し、
「リポジトリ側を直したのに効かない」が起き続ける。

リポジトリを先にすれば、`.app` の `ROOT_DIR` はバンドルの中を指していて
そこに `.env` は無いので、**バンドルでは必ず Application Support が使われる**。
開発中はリポジトリ側が使われる。つまり
**どちらの環境でも、その環境の人が置いたファイルが読まれる。**

- 先に見つかった方だけを読む（どちらが効いているか分からない状態を作らない）
- どちらも無くてもアプリは起動する（LLMと同期が無効になるだけ。既存の設計どおり）
- **どのファイルを読んだかを起動ログに出す。**
  「設定したのに効かない」の原因調査が、ログ1行で終わるようにする

### 2-3. v1 の残骸

`~/Library/Application Support/VocabLib/` には v1 のファイルが残っている。

```
.env             ← v1のGoogle Sheets設定（2026-02）
token.json       ← Google OAuth のトークン
token.json.bak
stats.json       ← v1の統計（メモリ上のdictを書き出していたもの）
vocablib.lock
```

**`token.json` は今も有効な認証情報**の可能性がある。v2 は Google Sheets を
使わない（SPEC 1.3「Google Sheets連携はv2で廃止」）ので、消してよいはず。
ただし削除は開発者の判断に委ねる。

### 2-4. 初回の移行

ビルド後の初回だけ、手でコピーする。README とビルドスクリプトの出力に書く。

```bash
mkdir -p ~/Library/Application\ Support/VocabLib
cp .env ~/Library/Application\ Support/VocabLib/.env
```

DBと同じディレクトリなので、**バックアップ対象が1箇所にまとまる**という副次的な利点もある。

---

## 3. py2app の設定（10-2）

### 3-1. 依存の追加

```bash
uv add --dev py2app
```

**開発用の依存にする。** アプリの実行時には不要で、ビルドするときだけ使うため。

### 3-2. `setup.py`

py2app は `setup.py` を読む（`pyproject.toml` だけでは動かない）。

```python
APP = ["src/main.py"]
OPTIONS = {
    "packages": ["src", "rumps", "google", "supabase", "dotenv", "requests"],
    "plist": {
        "CFBundleName": "VocabLib",
        "CFBundleIdentifier": "com.vocablib.app",
        "CFBundleShortVersionString": "0.2.0",
        "LSUIElement": True,   # ← 3-3
        "NSHighResolutionCapable": True,
    },
}
```

### 3-3. `packages` に `src` を入れる理由（**一番壊しやすいところ**）

py2app は既定でPythonコードを `site-packages.zip` に固める。
**zipに入るのは `.py` だけで、`.sql` のようなデータファイルは落ちる。**

このアプリには該当ファイルがある。

```python
# src/db/store.py
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
```

落ちると **起動直後にDBを作れず落ちる**。しかも開発中は再現しないので気付きにくい。

`packages` に指定したものは zip ではなく**ディレクトリのまま**コピーされるので、
`schema.sql` も一緒に入る。`src` を必ず入れること。

> 同じ理由で、今後 `src/` 配下に `.py` 以外のファイルを置くときは
> ここが効いているかを確認する。

### 3-4. メニューバー常駐（10-3）

`LSUIElement: True` を指定すると、**Dockにアイコンが出ず、Cmd+Tabにも現れない**。
メニューバーだけに常駐する。rumps アプリではこれが標準の作法。

指定を忘れると、常駐アプリなのにDockを1枠占有し続ける。

### 3-5. ビルドコマンド

```bash
uv run python setup.py py2app        # 本番ビルド → dist/VocabLib.app
uv run python setup.py py2app -A     # 開発用（エイリアスモード・高速）
```

`-A` は実体を参照するだけなので**配布できない**が、
バンドル固有の問題（2-2 のパス、3-3 のデータファイル）を早く見つけるのに使える。

`build/` と `dist/` は `.gitignore` 済み（ルート限定の指定なので `legacy/` とは別扱い）。

---

## 4. 起動と自動起動（10-4）

### 4-1. 初回起動

署名していないので Gatekeeper に止められる。**初回だけ**次の操作が要る。

1. `dist/VocabLib.app` を `/Applications` に移動
2. **右クリック → 開く**（ダブルクリックでは「開発元を検証できません」で止まる）
3. 2回目以降はダブルクリックで起動する

### 4-2. ログイン時の自動起動

システム設定 → 一般 → ログイン項目 → `+` で `VocabLib.app` を追加する。

LaunchAgent（plist）は使わない。**ログイン項目の方が、GUIで消せるぶん元に戻しやすい**。
常駐アプリが意図せず起動し続ける状態は、plistの存在を忘れた頃に効いてくる。

---

## 5. テスト方針

`.env` の探索は純粋関数に切り出してテストする。

| ファイル | 追加するテスト |
| -------- | -------------- |
| `tests/test_config.py`（新規） | リポジトリ側があればそれを選ぶ / 無ければApplication Support側 / **両方あったらリポジトリ側を優先**（2-2の順序） / どちらも無ければ None |

ビルドそのものは自動テストしない（実行に数十秒かかり、CIも無いため）。
代わりに DoD で手動確認する。

---

## 6. 完了の定義（DoD）

`uv run pytest` が通ることに加えて、以下を手動で確認する。

### ビルド

1. `uv run python setup.py py2app` が成功し、`dist/VocabLib.app` ができる
2. `.app` の中に `.env` が**入っていない**（`grep -r` で鍵が出ないこと）
3. `.app` の中に `schema.sql` が**入っている**（3-3 の確認）

### 起動

4. `/Applications` に置いて右クリック→開くで起動する
5. **Dockにアイコンが出ない**。メニューバーにだけ出る
6. `~/Library/Application Support/VocabLib/.env` を読んでいる（起動ログの
   「設定を読み込みました: ...」で確認。**リポジトリ側を読んでいたら失敗**）
7. 既存のDB（24語）をそのまま読み、統計が表示される
8. 出題される
9. オートフィルが動く（＝Geminiのキーを読めている）
10. 「今すぐ同期」が成功する（＝Supabaseのキーを読めている）
11. `.env` を置かずに起動しても落ちない（LLMと同期が無効になるだけ）

### 自動起動

12. ログイン項目に追加して再ログインすると、自動で常駐する

確認結果は `development-logs/YYYYMMDD-devlogs.md` に記録する。

---

## 7. 完了後にやること

- SPEC.md 8.1 の起動方法を `.app` に更新（`uv run python -m src.main` は開発用として残す）
- SPEC.md 7 に `.env` の探索順を追記
- SPEC.md 未確定事項から「`.app` 配布手順」を完了にする
- README.md の実行方法にビルド手順を追記
- `memo.md` の「.app 配布」にチェックを入れる
