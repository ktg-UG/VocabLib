# VocabLib アプリビルド手順

## 前提条件

Python 3.12を使用してください（3.13以降はpy2app/PyInstallerと互換性の問題がある場合があります）。

```bash
# Python 3.12をインストール
brew install python@3.12

# .python-versionで3.12を指定
echo "3.12" > .python-version

# 仮想環境を作成し直す
rm -rf .venv
uv venv
uv sync
```

## 1. PyInstallerのインストール

```bash
uv add --optional build pyinstaller
```

## 2. .appファイルのビルド

```bash
uv run pyinstaller --windowed --onefile --name VocabLib \
  --hidden-import src.app \
  --hidden-import src.config \
  --hidden-import src.sheets_client \
  --hidden-import src.ollama_client \
  main.py
```

ビルドされたアプリは `dist/VocabLib.app` に作成されます。

## 3. アプリのテスト

```bash
open dist/VocabLib.app
```

メニューバーにアイコンが表示されるはずです。

## 4. アプリのインストール

```bash
cp -r dist/VocabLib.app /Applications/
```

## 5. 自動起動の設定

### 方法A: システム環境設定（推奨）

1. **システム環境設定** → **一般** → **ログイン項目**
2. 「+」ボタンをクリック
3. `/Applications/VocabLib.app` を選択
4. 追加

### 方法B: LaunchAgent

`~/Library/LaunchAgents/com.yujikatagi.vocablib.plist` を作成:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yujikatagi.vocablib</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/VocabLib.app/Contents/MacOS/VocabLib</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

有効化:
```bash
launchctl load ~/Library/LaunchAgents/com.yujikatagi.vocablib.plist
```

## トラブルシューティング

### ビルドエラーが発生する場合

```bash
# buildディレクトリとdistディレクトリを削除
rm -rf build dist

# 再ビルド
python setup.py py2app
```

### Google認証ファイルが見つからない場合

`credentials.json` と `token.json` がアプリに含まれていない場合、
setup.pyの `DATA_FILES` に追加:

```python
DATA_FILES = [
    ('', ['credentials.json', 'token.json']),
]
```

### アプリが起動しない場合

コンソールログを確認:
```bash
open -a Console
```

または:
```bash
/Applications/VocabLib.app/Contents/MacOS/VocabLib
```
ターミナルから直接実行してエラーメッセージを確認。

## クリーンアップ

ビルド後の不要ファイルを削除:

```bash
rm -rf build dist
```
