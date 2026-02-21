"""
VocabLib - macOS Menu Bar App Setup
py2appを使用してmacOSアプリケーションをビルドするための設定
"""
from setuptools import setup

APP = ['main.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,  # アイコンファイル(.icns)があれば指定
    'plist': {
        'CFBundleName': 'VocabLib',
        'CFBundleDisplayName': 'VocabLib',
        'CFBundleIdentifier': 'com.yujikatagi.vocablib',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'LSUIElement': True,  # Dockに表示しない（メニューバーのみ）
        'LSBackgroundOnly': False,
    },
    'packages': ['rumps', 'src', 'google', 'googleapiclient', 'requests'],
    'includes': ['AppKit', 'google.oauth2', 'google.auth'],
    'excludes': ['tkinter', 'PyQt5', 'matplotlib'],  # 不要なパッケージを除外
}

setup(
    app=APP,
    name='VocabLib',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
