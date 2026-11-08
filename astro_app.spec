# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("data/ephemeris/de440s.bsp", "data/ephemeris"),
        ("src/astrochart/interpretation_rules.json", "astrochart"),
    ] + collect_data_files("tzdata"),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AstroBirthChart",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, upx=False,
    console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="AstroBirthChart",
)
