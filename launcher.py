"""`.app` の入口

py2app は指定したスクリプトを `__main__` として直接実行するため、
`src/main.py` をそのまま指定すると相対 import が壊れる。

    ImportError: attempted relative import with no known parent package

`src.main` を**パッケージとして** import してから呼ぶ。
開発時の `uv run python -m src.main` はパッケージ経由なのでこの問題が起きず、
**ビルドして初めて出る**（実際に踏んだ）。
"""
from src.main import main

if __name__ == "__main__":
    main()
