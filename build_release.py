"""
Build script for Freakuency.

Usage:
    python build_release.py          # build only
    python build_release.py --zip    # build + create zip for distribution
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
SPEC_FILE = ROOT / "build.spec"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist" / "Freakuency"
VERSION = "0.3.0-alpha"


def clean():
    """Remove previous build artifacts."""
    print("[1/3] Cleaning old build artifacts ...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


def build():
    """Run PyInstaller."""
    print("[2/3] Building with PyInstaller ...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--noconfirm"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("\n*** BUILD FAILED ***")
        sys.exit(1)

    # Remove the intermediate build dir so nobody runs the wrong exe
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    # Copy extra files next to the exe (outside _internal)
    for fname in ("cleanup_driver.bat", "README_DIST.txt"):
        src = ROOT / fname
        if src.exists():
            dest_name = "README.txt" if fname == "README_DIST.txt" else fname
            shutil.copy2(src, DIST_DIR / dest_name)

    print(f"\nBuild complete -> {DIST_DIR}")


def make_zip():
    """Zip the dist folder for distribution."""
    zip_name = f"Freakuency-v{VERSION}-win64.zip"
    zip_path = ROOT / zip_name
    print(f"[3/3] Packaging -> {zip_name} ...")

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in DIST_DIR.rglob("*"):
            if file.is_file():
                arcname = Path("Freakuency") / file.relative_to(DIST_DIR)
                zf.write(file, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Done! {zip_name} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Build Freakuency release")
    parser.add_argument("--zip", action="store_true", help="Create distributable zip")
    args = parser.parse_args()

    clean()
    build()

    if args.zip:
        make_zip()
    else:
        print("[3/3] Skipping zip (use --zip to create one)")

    print("\nAll done!")


if __name__ == "__main__":
    main()
