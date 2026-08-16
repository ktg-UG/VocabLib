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

    # どの .env を読んだかを必ず1行出す。`.app` にすると設定ファイルの場所が
    # 変わるため、「設定したのに効かない」の原因調査がここで終わるようにする
    if config.ENV_FILE is None:
        logging.info(".env が見つかりません（既定値で動作します）")
    else:
        logging.info("設定を読み込みました: %s", config.ENV_FILE)
    logging.info("データベース: %s", config.DB_PATH)

    store = Store(config.DB_PATH)
    try:
        VocabLibApp(store).run()
    finally:
        store.close()


if __name__ == "__main__":
    main()
