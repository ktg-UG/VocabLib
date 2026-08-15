"""エントリポイント

    uv run python -m src.main
"""
from __future__ import annotations

import logging

from . import config
from .db.store import Store
from .ui.menubar import VocabLibApp


def main() -> None:
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # SDKのINFOログ（HTTPリクエスト詳細など）でアプリ自身のログが埋もれるため抑える。
    # 警告・エラーは引き続き出す。
    for noisy in ("httpx", "httpcore", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    store = Store(config.DB_PATH)
    try:
        VocabLibApp(store).run()
    finally:
        store.close()


if __name__ == "__main__":
    main()
