# VocabLib - 英単語暗記メニューバーアプリ

macOSのメニューバーに常駐し、5分おきに英単語の4択クイズをポップアップ表示するアプリケーションです。

## 機能

- 📚 Google Spread Sheetから英単語を自動取得
- 🤖 Ollamaを使った自然な4択問題生成（オプション）
- ⏰ 5分間隔で自動的にクイズを出題
- 🍎 macOSメニューバーに常駐
- 📊 学習統計の記録

## セットアップ

### 1. 必要なソフトウェア

- Python 3.11以上
- [uv](https://github.com/astral-sh/uv) - 高速Pythonパッケージマネージャー
- Ollama（オプション：より高度な問題生成に使用）

### 2. uvのインストール

```bash
# Homebrewでインストール
brew install uv

# または
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. プロジェクトのセットアップ

```bash
# リポジトリをクローン（または作成）
cd /path/to/VocabLib

# 依存関係をインストール
uv sync
```

### 4. Ollamaのインストール（オプション）

より高度な問題生成を使いたい場合：

```bash
# Homebrewでインストール
brew install ollama

# Ollamaを起動
ollama serve

# モデルをダウンロード（別ターミナルで）
ollama pull llama2
```

### 5. Google Sheets APIの設定

#### Google Cloud Consoleでの設定

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「ライブラリ」から「Google Sheets API」を検索して有効化
4. 「認証情報」→「認証情報を作成」→「OAuth クライアント ID」を選択
5. アプリケーションの種類を「デスクトップアプリ」として作成
6. 作成した認証情報のJSONをダウンロード
7. ダウンロードしたファイルを `credentials.json` としてプロジェクトルートに保存

#### スプレッドシートの作成

1. [Google Sheets](https://sheets.google.com/)で新しいスプレッドシートを作成
2. 以下の形式でデータを入力：

| A列（英単語） | B列（日本語訳） |
|--------------|----------------|
| apple        | りんご          |
| book         | 本             |
| computer     | コンピューター   |
| study        | 勉強する        |
| water        | 水             |

3. スプレッドシートのURLからIDをコピー
   - URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
   - `SPREADSHEET_ID`の部分をコピー

### 6. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成：

```bash
# .env.exampleをコピー
cp .env.example .env
```

`.env`ファイルを編集：

```bash
# Google Sheets設定
GOOGLE_SHEET_ID=あなたのスプレッドシートID
GOOGLE_CREDENTIALS_PATH=./credentials.json

# Ollama設定（オプション）
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# アプリ設定
QUIZ_INTERVAL_MINUTES=5
```

## 起動方法

```bash
# uvで実行
uv run python main.py

# または仮想環境をアクティベートして実行
source .venv/bin/activate
python main.py
```

メニューバーに📚アイコンが表示されます。

### 初回起動時

1. Google認証画面がブラウザで開きます
2. Googleアカウントでログイン
3. アクセスを許可
4. 認証情報が `token.json` に保存されます（次回から不要）

## 使い方

### メニュー項目

- **今すぐクイズ**: すぐにクイズを表示
- **自動クイズ: オン/オフ**: 定期的なクイズのオン/オフを切り替え
- **単語を再読み込み**: Google Sheetsから単語リストを再読み込み
- **統計**: 正解率などの学習統計を表示
- **終了**: アプリを終了

### クイズの回答

1. ポップアップウィンドウが表示されたら、1-4の数字を入力
2. 「回答」ボタンをクリック
3. 正解/不正解の通知が表示されます

## 自動起動の設定

macOS起動時に自動的にVocabLibを起動するには：

### 方法1: ログイン項目に追加

1. 起動スクリプトを作成：

```bash
# start_vocablib.command を作成
cat > ~/start_vocablib.command << 'EOF'
#!/bin/bash
cd /Users/YOUR_USERNAME/C_personal/VocabLib
/opt/homebrew/bin/uv run python main.py
EOF

chmod +x ~/start_vocablib.command
```

2. 「システム環境設定」→「一般」→「ログイン項目」
3. 「+」ボタンをクリックして、`start_vocablib.command`を追加

### 方法2: LaunchAgent（推奨）


```bash
# ~/Library/LaunchAgents/com.vocablib.plist を作成
cat > ~/Library/LaunchAgents/com.vocablib.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vocablib</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>/Users/YOUR_USERNAME/C_personal/VocabLib/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/C_personal/VocabLib</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/vocablib.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/vocablib.error.log</string>
</dict>
</plist>
EOF

# LaunchAgentを読み込む
launchctl load ~/Library/LaunchAgents/com.vocablib.plist

# 停止したい場合
# launchctl unload ~/Library/LaunchAgents/com.vocablib.plist
```

## プロジェクト構造

```
VocabLib/
├── .env                  # 環境変数（gitignoreに含まれる）
├── .env.example          # 環境変数のサンプル
├── .gitignore
├── credentials.json      # Google API認証情報（gitignoreに含まれる）
├── token.json           # Google認証トークン（自動生成）
├── main.py              # エントリーポイント
├── pyproject.toml       # プロジェクト設定
├── README.md
├── .venv/               # 仮想環境（自動生成）
└── src/
    ├── __init__.py
    ├── app.py           # メインアプリケーション
    ├── config.py        # 設定
    ├── sheets_client.py # Google Sheets連携
    └── ollama_client.py # Ollama連携
```

## トラブルシューティング

### Q: クイズが表示されない

**確認事項:**
- `.env`ファイルが正しく設定されているか
- `credentials.json`が存在するか
- スプレッドシートIDが正しいか
- Google Sheetsに単語データが入力されているか

**デバッグ方法:**
```bash
# ターミナルでログを確認しながら起動
uv run python main.py
```

### Q: Google認証でエラーが出る

- `credentials.json`が正しいOAuth 2.0クライアントIDのものか確認
- `token.json`を削除して再認証を試す
- Google Cloud Consoleで「Google Sheets API」が有効になっているか確認

### Q: 「単語が読み込まれていません」エラー

- スプレッドシートが正しく共有されているか確認（OAuth認証の場合は自分のアカウント）
- スプレッドシートのシート名が `Sheet1` であるか確認
  - 別の名前の場合は`.env`で`GOOGLE_SHEET_RANGE`を変更

### Q: メニューバーアイコンが表示されない

- macOSのアクセシビリティ権限を確認
- Pythonのバージョンを確認: `python --version`（3.11以上）
- rumpsが正しくインストールされているか: `uv run python -c "import rumps; print(rumps.__version__)"`

### Q: Ollama関連のエラー

Ollamaは**オプション**です。現在のコードではシンプルな問題生成を使用しているため、Ollamaがなくても動作します。

## 開発

### 依存関係の追加

```bash
uv add パッケージ名
```

### コードの整形

```bash
uv run black src/
uv run isort src/
```

## 今後の改善予定

- [x] 基本的なメニューバーアプリ
- [x] Google Sheets連携
- [x] 学習統計機能
- [ ] Ollamaを使った高度な問題生成
- [ ] 間違えた単語の復習機能
- [ ] クイズ間隔のカスタマイズUI
- [ ] ダークモード対応のポップアップデザイン
- [ ] 音声読み上げ機能
- [ ] データベースに学習履歴を保存

## ライセンス

MIT License

