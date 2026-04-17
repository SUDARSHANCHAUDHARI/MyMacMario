a = Analysis(
    ["desktop_mario_mac.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["simpleaudio.functionchecks", "pynput.keyboard._darwin"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Desktop Mario Mac",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Desktop Mario Mac",
)
app = BUNDLE(
    coll,
    name="Desktop Mario Mac.app",
    icon=None,
    bundle_identifier="com.sudarshan.mymacmario",
)
