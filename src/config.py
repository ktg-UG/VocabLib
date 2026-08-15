"""設定値

`.env` があれば読み込み、無ければ既定値を使う。
アプリ内の設定値はすべてこのモジュールに集約し、各所で `os.getenv` を呼ばない。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent

# .env が無くても load_dotenv はエラーにならない（既定値で動く）
load_dotenv(ROOT_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    """整数の環境変数を読む。空文字や不正値なら既定値にフォールバックする"""
    raw = os.getenv(name, "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


# ── データベース ──────────────────────────────────────────────────────────
# 既定はmacOSの標準的なアプリデータ置き場。
# VOCABLIB_DB_PATH で上書きできる（開発時に本番DBを汚さないため）。
DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "VocabLib" / "vocablib.db"
DB_PATH = Path(os.getenv("VOCABLIB_DB_PATH") or DEFAULT_DB_PATH).expanduser()

# ── 出題 ──────────────────────────────────────────────────────────────────
QUIZ_INTERVAL_MINUTES = _env_int("QUIZ_INTERVAL_MINUTES", 5)
QUIZ_INTERVAL_SECONDS = QUIZ_INTERVAL_MINUTES * 60
CHOICE_COUNT = _env_int("CHOICE_COUNT", 4)
AUTO_START_QUIZ = _env_bool("AUTO_START_QUIZ", True)

# ── LLM ───────────────────────────────────────────────────────────────────
# 1段目: Gemini（APIキーが無ければこの段は自動的に飛ばされる）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.7-flash"

# 2段目: ローカルLLM（Ollama）
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "").strip() or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or "gemma3:4b"

# 例文生成はワーカースレッドで動くので長めでよい
LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 20.0)
# オートフィルはモーダルダイアログの合間に走りメインスレッドを止めるので短くしたい。
# ただしGemini APIはデッドライン10秒未満を 400 で拒否するため、これ以上は縮められない
# （縮めると1段目が毎回弾かれ、常にローカルLLMに落ちてしまう）。
AUTOFILL_TIMEOUT_SECONDS = _env_float("AUTOFILL_TIMEOUT_SECONDS", 10.0)

# ── Supabase同期 ──────────────────────────────────────────────────────────
# どちらか未設定なら同期は丸ごと無効になる（オフライン専用アプリとして動く）。
# service_role キーはRLSを無視する管理者権限。.env の外に出さないこと。
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SYNC_INTERVAL_MINUTES = _env_int("SYNC_INTERVAL_MINUTES", 10)

# 送信する行に付ける所有者ID（Supabase Authが発行したUUID）。
# Web側のRLSポリシーが `auth.uid() = user_id` で判定するため、
# これが入っていないとWebから見えない。
# 確認方法: Supabase SQL Editor で `select id, email from auth.users;`
SUPABASE_USER_ID = os.getenv("SUPABASE_USER_ID", "").strip()

# ── ログ ──────────────────────────────────────────────────────────────────
# DEBUG にすると、どの段がなぜ失敗して次に落ちたかまで出る
LOG_LEVEL = os.getenv("LOG_LEVEL", "").strip().upper() or "INFO"

# ── 表示 ──────────────────────────────────────────────────────────────────
APP_TITLE = "📚"          # メニューバーに出る文字
PANEL_WIDTH = 340
PANEL_HEIGHT = 200
PANEL_MARGIN = 16
