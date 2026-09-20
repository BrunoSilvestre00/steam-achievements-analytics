# PyInstaller spec para a distribuição Windows.
from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ


project_root = Path(SPECPATH)
datas = [
    (str(project_root / "steam_analytics" / "templates"), "steam_analytics/templates"),
    (str(project_root / "steam_analytics" / "static"), "steam_analytics/static"),
    (str(project_root / "steam_analytics" / "schema.sql"), "steam_analytics"),
]

a = Analysis(
    [str(project_root / "steam_analytics" / "desktop.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["howlongtobeatpy"],
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
    name="SAA",
    icon=str(project_root / "steam_analytics" / "static" / "assets" / "favicon.ico"),
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
    name="SteamAchievementAnalytics",
)
