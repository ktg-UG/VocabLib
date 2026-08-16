"""設定ファイルの探索のテスト

`.app` にすると `.env` の置き場所が変わる。**どちらを読むかを取り違えると、
Geminiも同期も黙って無効になる**（実際に v1 の残骸を踏んだ）ので、
順序を固定してテストで守る。
"""
from pathlib import Path

import pytest

from src import config


@pytest.fixture
def env_files(tmp_path, monkeypatch):
    """リポジトリ側とApplication Support側の場所を差し替える"""
    repo = tmp_path / "repo"
    support = tmp_path / "support"
    repo.mkdir()
    support.mkdir()

    monkeypatch.setattr(config, "ROOT_DIR", repo)
    monkeypatch.setattr(config, "APP_SUPPORT_DIR", support)
    return repo, support


def test_どちらも無ければNone(env_files):
    """設定が無くてもアプリは起動する（LLMと同期が無効になるだけ）"""
    assert config.find_env_file() is None


def test_リポジトリ側だけあればそれを読む(env_files):
    repo, _ = env_files
    (repo / ".env").write_text("A=1")

    assert config.find_env_file() == repo / ".env"


def test_ApplicationSupport側だけあればそれを読む(env_files):
    """配布した .app ではこちらが使われる（バンドル内に .env は無いため）"""
    _, support = env_files
    (support / ".env").write_text("A=1")

    assert config.find_env_file() == support / ".env"


def test_両方あればリポジトリ側を優先する(env_files):
    """開発中に古い設定ファイルがリポジトリの .env を黙って隠さないため。
    Application Support に v1 の残骸が残っていて実際に踏んだ"""
    repo, support = env_files
    (repo / ".env").write_text("A=1")
    (support / ".env").write_text("A=2")

    assert config.find_env_file() == repo / ".env"


def test_ディレクトリは設定ファイルとみなさない(env_files):
    """.env という名前のディレクトリがあっても load_dotenv に渡さない"""
    repo, support = env_files
    (repo / ".env").mkdir()
    (support / ".env").write_text("A=1")

    assert config.find_env_file() == support / ".env"


def test_DBはApplicationSupportに置く():
    """.app にしても、データの場所は変わらない（バンドルの外）"""
    assert config.DEFAULT_DB_PATH.parent == config.APP_SUPPORT_DIR
    assert Path.home() in config.DEFAULT_DB_PATH.parents
