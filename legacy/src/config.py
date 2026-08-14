"""設定ファイル"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# PyInstallerでバンドルされた場合のパスを取得
if getattr(sys, 'frozen', False):
    # PyInstallerでバンドルされている場合
    ROOT_DIR = Path(sys._MEIPASS)
    # .envはApplication Supportに保存（書き込み可能な場所）
    APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "VocabLib"
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    USER_ENV = APP_SUPPORT_DIR / ".env"
    # まずApplication Supportの.envを読み込み、なければバンドル内の.envをコピー
    if not USER_ENV.exists():
        bundled_env = ROOT_DIR / ".env"
        if bundled_env.exists():
            import shutil
            shutil.copy(bundled_env, USER_ENV)
    load_dotenv(USER_ENV)
    # バンドル内の.envもフォールバックとして読み込み（override=Falseで上書きしない）
    load_dotenv(ROOT_DIR / ".env", override=False)
else:
    # 通常のPythonスクリプトとして実行されている場合
    ROOT_DIR = Path(__file__).parent.parent
    load_dotenv(ROOT_DIR / ".env")

# Google Sheets設定
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# PyInstallerでバンドルされた場合の認証ファイルパスの処理
if getattr(sys, 'frozen', False):
    # バンドル時は .env の相対パスを無視し、常にバンドル内の credentials.json を使う
    GOOGLE_CREDENTIALS_PATH = str(ROOT_DIR / "credentials.json")
    # token.jsonは書き込み可能なユーザーディレクトリに保存
    GOOGLE_TOKEN_PATH = str(APP_SUPPORT_DIR / "token.json")
else:
    # 開発環境ではプロジェクトルートに保存
    GOOGLE_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        str(ROOT_DIR / "credentials.json")
    )
    GOOGLE_TOKEN_PATH = str(ROOT_DIR / "token.json")

GOOGLE_SHEET_RANGE = os.getenv("GOOGLE_SHEET_RANGE", "シート1!A:B")

# 学習記録シート設定
LEARNING_SHEET_NAME = os.getenv("LEARNING_SHEET_NAME", "学習記録")

# 忘却曲線設定
INITIAL_EASE_FACTOR = float(os.getenv("INITIAL_EASE_FACTOR", "2.5"))
INCORRECT_RETRY_MINUTES = int(os.getenv("INCORRECT_RETRY_MINUTES", "5"))

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
