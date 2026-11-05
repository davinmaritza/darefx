"""Build standalone Linux .AppImage package for DareFX."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

VERSION = "1.1.0"
APP_DIR = Path("build/appimage/DareFX.AppDir")
DIST_BIN = Path("dist/DareFX")
OUTPUT_APPIMAGE = Path(f"dist/DareFX-{VERSION}-x86_64.AppImage")
APPIMAGETOOL = Path("/tmp/appimagetool")


def main() -> None:
    if not DIST_BIN.exists():
        print(f"Error: Executable not found at {DIST_BIN}")
        sys.exit(1)

    if not APPIMAGETOOL.exists():
        print(f"Error: appimagetool not found at {APPIMAGETOOL}")
        sys.exit(1)

    # 1. Clean prior build
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    usr_bin = APP_DIR / "usr/bin"
    usr_bin.mkdir(parents=True, exist_ok=True)

    # 2. Copy Executable
    target_bin = usr_bin / "DareFX"
    print(f"Copying {DIST_BIN} -> {target_bin}")
    shutil.copy2(DIST_BIN, target_bin)
    target_bin.chmod(0o755)

    # 3. Copy Icon
    src_icon = Path("assets/logo/darefx-app-512.png")
    if src_icon.exists():
        shutil.copy2(src_icon, APP_DIR / "darefx.png")
        shutil.copy2(src_icon, APP_DIR / ".DirIcon")

    # 4. Desktop Entry File
    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=DareFX Trading Station
GenericName=Quantitative AI Multi-Asset Trading Terminal
Comment=Institutional-grade autonomous multi-asset trading terminal
Exec=DareFX
Icon=darefx
Terminal=false
Categories=Office;Finance;Development;
Keywords=forex;crypto;stocks;trading;quantitative;ai;
StartupNotify=true
"""
    (APP_DIR / "darefx.desktop").write_text(desktop_content, encoding="utf-8")

    # 5. AppRun script
    apprun_content = """#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/DareFX" "$@"
"""
    apprun_file = APP_DIR / "AppRun"
    apprun_file.write_text(apprun_content, encoding="utf-8")
    apprun_file.chmod(0o755)

    # 6. Execute appimagetool
    OUTPUT_APPIMAGE.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_APPIMAGE.exists():
        OUTPUT_APPIMAGE.unlink()

    env = dict(os.environ)
    env["ARCH"] = "x86_64"
    cmd = [str(APPIMAGETOOL), str(APP_DIR), str(OUTPUT_APPIMAGE)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, env=env, check=True)
    size_mb = OUTPUT_APPIMAGE.stat().st_size / (1024 * 1024)
    print(f"✅ AppImage created successfully: {OUTPUT_APPIMAGE} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
