#!/usr/bin/env python3
"""VocabLib エントリーポイント"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

from src.app import main

if __name__ == "__main__":
    main()
