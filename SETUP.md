# VocabLib セットアップガイド

## 簡単スタートガイド

### 1. Google Sheets APIの設定

#### Step 1: Google Cloud Consoleでプロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 右上の「プロジェクトを選択」→「新しいプロジェクト」をクリック
3. プロジェクト名を入力（例: VocabLib）して「作成」

#### Step 2: Google Sheets APIを有効化

1. 左メニューから「APIとサービス」→「ライブラリ」を選択
2. 検索バーで「Google Sheets API」を検索
3. 「Google Sheets API」をクリックして「有効にする」

#### Step 3: OAuth 2.0認証情報を作成

1. 左メニューから「APIとサービス」→「認証情報」を選択
2. 「認証情報を作成」→「OAuth クライアント ID」をクリック
3. 「同意画面を構成」をクリック（初回のみ）
   - User Type: 「外部」を選択して「作成」
   - アプリ名: VocabLib
   - ユーザーサポートメール: あなたのメールアドレス
   - デベロッパーの連絡先: あなたのメールアドレス
   - 「保存して次へ」（Scopesは何も追加しない）
   - テストユーザーに自分のGmailアドレスを追加
   - 「保存して次へ」
4. 再度「認証情報を作成」→「OAuth クライアント ID」
5. アプリケーションの種類: 「デスクトップアプリ」
6. 名前: VocabLib Desktop
7. 「作成」
8. JSONをダウンロード
9. ダウンロードしたファイルを `credentials.json` にリネームして、プロジェクトルートに配置

### 2. Google Sheetsスプレッドシートを作成

#### Step 1: 新しいスプレッドシートを作成

1. [Google Sheets](https://sheets.google.com/)を開く
2. 「新しいスプレッドシートを作成」（空白）

#### Step 2: データを入力

A列に英単語、B列に日本語訳を入力してください：

| A (英単語)    | B (日本語訳)          |
|--------------|---------------------|
| apple        | りんご               |
| book         | 本                  |
| study        | 勉強する             |
| water        | 水                  |
| computer     | コンピューター        |
| happy        | 幸せな、嬉しい        |
| run          | 走る                |
| beautiful    | 美しい              |
| friend       | 友達                |
| learn        | 学ぶ                |
| important    | 重要な              |
| understand   | 理解する             |
| question     | 質問                |
| answer       | 答え、答える         |
| create       | 作る、創造する        |

#### Step 3: スプレッドシートIDを取得

1. ブラウザのアドレスバーからURLをコピー
2. URLの形式: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0`
3. `SPREADSHEET_ID`の部分をコピー（長い英数字の文字列）

### 3. 環境変数の設定

`.env`ファイルを編集：

```bash
# Google Sheets設定
GOOGLE_SHEET_ID=あなたのスプレッドシートID  # ← ここに貼り付け
GOOGLE_CREDENTIALS_PATH=./credentials.json

# アプリ設定
QUIZ_INTERVAL_MINUTES=5

# Ollama設定（オプション）
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
```

### 4. Ollama のセットアップ（オプション）

Ollamaを使うと、クイズの不正解選択肢がAIによって生成され、より紛らわしく学習効果の高い問題になります。Ollamaなしでも動作しますが、選択肢はスプレッドシートからランダムに選ばれます。

#### Step 1: Ollama Desktop アプリをインストール

> **注意**: macOS 26 Tahoe では Homebrew版 Ollama の Metal GPU シェーダーが互換性の問題を起こすため、**Desktop アプリ版**を使用してください。

1. [Ollama公式サイト](https://ollama.com/)からDesktopアプリをダウンロード
2. `/Applications/Ollama.app` にインストール
3. アプリを起動

#### Step 2: モデルをダウンロード

```bash
ollama pull qwen2.5:1.5b
```

#### Step 3: 動作確認

```bash
curl http://localhost:11434/api/tags
```

モデル一覧が表示されればOKです。

### 5. アプリを起動

```bash
# プロジェクトディレクトリに移動
cd /Users/YOUR_USERNAME/C_personal/VocabLib

# 起動
uv run python main.py
```

### 6. 初回認証

1. ブラウザが自動的に開きます
2. Googleアカウントでログイン
3. 「このアプリは Google で確認されていません」と表示される場合：
   - 「詳細」をクリック
   - 「VocabLib（安全ではないページ）に移動」をクリック
   - これは自分で作った開発用アプリなので問題ありません
4. 「許可」をクリック
5. 認証が完了すると、ターミナルに「✓ XX個の単語を読み込みました」と表示されます

### 7. 使い方

1. メニューバーに📚アイコンが表示されます
2. アイコンをクリックして「自動クイズ: オフ」をクリック→「オン」に
3. すぐに最初のクイズが表示されます
4. 以降、5分ごとに自動的にクイズが表示されます

## よくある質問

### Q: 「credentials.jsonが見つかりません」エラー

A: `credentials.json`がプロジェクトルートにあるか確認してください。

```bash
ls -la | grep credentials.json
```

### Q: 「スプレッドシートにデータがありません」エラー

A: 
- スプレッドシートのシート名が「Sheet1」であることを確認
- A列とB列にデータが入力されているか確認
- 空行がある場合は削除

### Q: 認証ブラウザが開かない

A: 手動でURLを開いてください：
1. ターミナルに表示されるURLをコピー
2. ブラウザに貼り付けて開く

### Q: Ollamaに接続できない / 選択肢がランダムになる

A: 以下を確認してください：
1. Ollama Desktop アプリが起動しているか確認
2. モデルがインストールされているか確認: `ollama list`
3. `.env`の`OLLAMA_MODEL`がインストール済みモデルと一致しているか確認
4. Ollamaに接続できない場合、アプリは自動的にスプレッドシートからランダムに選択肢を生成するフォールバックモードで動作します

### Q: クイズの間隔を変更したい

A: `.env`ファイルの`QUIZ_INTERVAL_MINUTES`を変更：

```bash
# 10分おきにしたい場合
QUIZ_INTERVAL_MINUTES=10
```

## 単語の追加方法

1. Google Sheetsのスプレッドシートを開く
2. 新しい行にA列（英単語）、B列（日本語訳）を追加
3. VocabLibのメニューから「単語を再読み込み」をクリック
4. 新しい単語が追加されます

## サンプル単語リスト

より多くの単語を追加したい場合のサンプル（TOEICやTOEFL頻出語）：

### 基本動詞
- achieve - 達成する
- acquire - 獲得する
- analyze - 分析する
- apply - 適用する、応募する
- approach - 接近する、取り組む

### ビジネス英語
- agreement - 合意、契約
- benefit - 利益、恩恵
- budget - 予算
- colleague - 同僚
- deadline - 締め切り

### 形容詞
- appropriate - 適切な
- available - 利用可能な
- effective - 効果的な
- efficient - 効率的な
- significant - 重要な

これらをスプレッドシートに追加することで、より充実した学習ができます！
