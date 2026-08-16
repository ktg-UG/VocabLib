"""py2app のビルド設定

    uv run python setup.py py2app       # 配布用   → dist/VocabLib.app
    uv run python setup.py py2app -A    # 開発用（エイリアスモード・高速）

`-A` は実体を参照するだけなので配布できないが、バンドル固有の問題
（設定ファイルのパス・データファイルの欠落）を早く見つけるのに使える。

**このファイルは配布物に鍵を含めない。** v1 は `datas=[('.env', '.')]` で
`.env` と `credentials.json` をバンドルに焼き込んでおり、配布物を渡した瞬間に
APIキーが渡る状態だった。v2 は `~/Library/Application Support/VocabLib/.env`
から読む（`src/config.py` の `find_env_file()`）。
"""
from setuptools import setup
from setuptools.dist import Distribution


class _NoInstallRequires(Distribution):
    """`install_requires` を持たない Distribution。

    py2app は `install_requires` があると
    `install_requires is no longer supported` で構築を拒否する
    （`py2app/build_app.py`）。ところが setuptools は
    `pyproject.toml` の `[project] dependencies` を自動でここに入れてしまうため、
    何も書いていないのに毎回ぶつかる。

    依存はもともと uv が `pyproject.toml` から解決しており、
    バンドルへの同梱は `packages` で指定している。**ビルド時にここを使う必要が無い**ので、
    設定を読み込んだ直後に空にする。
    """

    def parse_config_files(self, *args, **kwargs):
        super().parse_config_files(*args, **kwargs)
        self.install_requires = []

APP = ["launcher.py"]

OPTIONS = {
    # ここに挙げたものは site-packages.zip に固められず、**ディレクトリのまま**
    # コピーされる。`src` を外すと `src/db/schema.sql` が同梱されず、
    # 起動直後にDBを作れずに落ちる（zipに入るのは .py だけのため）。
    #
    # 今後 `src/` に .py 以外のファイルを足すときは、ここが効いているかを確認する。
    "packages": [
        "src",
        "rumps",
        "dotenv",
        "supabase",
        "requests",
    ],
    # `google` は名前空間パッケージ（__init__.py が無い）で、py2app の
    # モジュール探索が `No module named 'google'` で落ちる。
    # `packages` に入れず、import の追跡に任せる
    # （google-genai には同梱が要るデータファイルが無いため、これで足りる）。
    "includes": ["google.genai"],
    "plist": {
        "CFBundleName": "VocabLib",
        "CFBundleDisplayName": "VocabLib",
        "CFBundleIdentifier": "com.vocablib.app",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        # メニューバー常駐アプリなので Dock に出さない（Cmd+Tab にも出ない）。
        # 外すと、常駐しているだけなのに Dock を1枠占有し続ける。
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
}

# `setup_requires=["py2app"]` は書かない。
# setuptools 84 で非推奨の fetch_build_eggs 経路に入り、ビルドが
# `install_requires is no longer supported` で落ちる。
# py2app は開発依存として入れてあるので、その場で取りに行く必要が無い。
setup(
    name="VocabLib",
    app=APP,
    options={"py2app": OPTIONS},
    distclass=_NoInstallRequires,
)
