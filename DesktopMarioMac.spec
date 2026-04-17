from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package_name in ("pygame", "simpleaudio"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass


a = Analysis(
    ["desktop_mario_mac.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="Desktop Mario Mac",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
app = BUNDLE(
    exe,
    name="Desktop Mario Mac.app",
    icon=None,
    bundle_identifier="com.sudarshan.mymacmario",
)
