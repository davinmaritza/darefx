"""Build Debian / Ubuntu / Linux Mint .deb package for DareFX."""

import os
from pathlib import Path
import shutil
import subprocess

VERSION = "1.0.0"
ARCH = "amd64"
PACKAGE_NAME = f"darefx_{VERSION}_{ARCH}"
BUILD_DIR = Path("build/deb_pkg") / PACKAGE_NAME
DIST_BIN = Path("dist/DareFX")
OUTPUT_DEB = Path(f"dist/darefx_{VERSION}_{ARCH}.deb")


def main():
    if not DIST_BIN.exists():
        print(f"Error: Executable not found at {DIST_BIN}")
        return

    # Clean prior build
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    # 1. Directory Structure
    debian_dir = BUILD_DIR / "DEBIAN"
    bin_dir = BUILD_DIR / "usr/bin"
    apps_dir = BUILD_DIR / "usr/share/applications"
    icons_dir = BUILD_DIR / "usr/share/pixmaps"

    debian_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    # 2. Control File
    control_content = f"""Package: darefx
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {ARCH}
Maintainer: Davin Maritza <davinmaritza@github.com>
Description: DareFX Quantitative AI Trading Station & Native Desktop Terminal
 Institutional-grade autonomous ML forex auto-trading terminal for EUR/USD.
 Built with PySide6, LightGBM, and Marcos López de Prado Triple Barrier Method.
"""
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    # 3. Copy Executable
    target_bin = bin_dir / "darefx"
    shutil.copy2(DIST_BIN, target_bin)
    target_bin.chmod(0o755)

    # 4. Copy Icon
    src_icon = Path("assets/logo/darefx-app-512.png")
    if src_icon.exists():
        shutil.copy2(src_icon, icons_dir / "darefx.png")

    # 5. Desktop Entry File
    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=DareFX Trading Station
GenericName=Quantitative AI Trading Terminal
Comment=Institutional-grade autonomous ML forex auto-trading terminal
Exec=/usr/bin/darefx
Icon=darefx
Terminal=false
Categories=Office;Finance;Development;
Keywords=forex;trading;mt5;quantitative;ai;lightgbm;
StartupNotify=true
"""
    (apps_dir / "darefx.desktop").write_text(desktop_content, encoding="utf-8")

    # 6. Build .deb package with dpkg-deb
    OUTPUT_DEB.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["dpkg-deb", "--build", "--root-owner-group", str(BUILD_DIR), str(OUTPUT_DEB)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"✅ Debian package created successfully: {OUTPUT_DEB} ({OUTPUT_DEB.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
