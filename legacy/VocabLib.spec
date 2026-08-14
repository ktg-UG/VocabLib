# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.'), ('credentials.json', '.')],
    hiddenimports=['src.app', 'src.config', 'src.sheets_client', 'src.ollama_client', 'src.spaced_repetition'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir モード: EXE にはバイナリ/データを含めず、COLLECT で配置する
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VocabLib',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VocabLib',
)

app = BUNDLE(
    coll,
    name='VocabLib.app',
    icon=None,
    bundle_identifier='com.yujikatagi.vocablib',
    info_plist={
        'LSUIElement': True,
        'CFBundleShortVersionString': '0.1.0',
        'NSHighResolutionCapable': True,
    },
)
