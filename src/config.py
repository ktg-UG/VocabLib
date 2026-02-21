"""設定ファイル"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# PyInstallerでバンドルされた場合のパスを取得
if getattr(sys, 'frozen', False):
    # PyInstallerでバンドルされている場合
    ROOT_DIR = Path(sys._MEIPASS)
else:
    # 通常のPythonスクリプトとして実行されている場合
    ROOT_DIR = Path(__file__).parent.parent

# .envファイルを読み込み
load_dotenv(ROOT_DIR / ".env")

# Google Sheets設定
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# PyInstallerでバンドルされた場合の認証ファイルパスの処理
if getattr(sys, 'frozen', False):
    # バンドルされている場合、credentials.jsonは一時ディレクトリから読み込む
    GOOGLE_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        str(ROOT_DIR / "credentials.json")
    )
    # token.jsonは書き込み可能なユーザーディレクトリに保存
    GOOGLE_TOKEN_PATH = os.path.expanduser("~/Library/Application Support/VocabLib/token.json")
    # ディレクトリを作成
    os.makedirs(os.path.dirname(GOOGLE_TOKEN_PATH), exist_ok=True)
else:
    # 開発環境ではプロジェクトルートに保存
    GOOGLE_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        str(ROOT_DIR / "credentials.json")
    )
    GOOGLE_TOKEN_PATH = str(ROOT_DIR / "token.json")

GOOGLE_SHEET_RANGE = os.getenv("GOOGLE_SHEET_RANGE", "シート1!A:B")

# Ollama設定
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")

# アプリ設定
QUIZ_INTERVAL_MINUTES = int(os.getenv("QUIZ_INTERVAL_MINUTES", "5"))
QUIZ_INTERVAL_SECONDS = QUIZ_INTERVAL_MINUTES * 60
AUTO_START_QUIZ = os.getenv("AUTO_START_QUIZ", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# アイコン設定（オプション）
APP_ICON = os.getenv("APP_ICON", "📚")

# Ollama / プリジェネ設定
OLLAMA_PREGEN_INTERVAL_SECONDS = int(os.getenv("OLLAMA_PREGEN_INTERVAL_SECONDS", "270"))
OLLAMA_MODEL_BATCH_SIZE = int(os.getenv("OLLAMA_MODEL_BATCH_SIZE", "4"))
OLLAMA_CACHE_MAX = int(os.getenv("OLLAMA_CACHE_MAX", "50"))
# nice値（生成プロセス実行時に使う。サーバ常駐なら不要）
OLLAMA_BATCH_NICE = int(os.getenv("OLLAMA_BATCH_NICE", "10"))
