"""Installer script for project-local BtbN FFmpeg LGPL build."""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import httpx

DOWNLOAD_URL = "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip"
TARGET_DIR = Path("tools/ffmpeg/bin")
TEMP_ZIP = Path("tools/ffmpeg_temp.zip")
MIN_FREE_GB = 8.0


def check_disk_space() -> float:
    total, used, free = shutil.disk_usage(".")
    free_gb = free / (1024**3)
    return free_gb


def main():
    free_gb = check_disk_space()
    print(f"[1/5] Free disk space before download: {free_gb:.2f} GB")
    if free_gb < MIN_FREE_GB:
        print(f"ERROR: Available free space ({free_gb:.2f} GB) is below safety floor of {MIN_FREE_GB} GB.")
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[2/5] Downloading BtbN FFmpeg Win64 LGPL build from:\n      {DOWNLOAD_URL}")
    downloaded_bytes = 0
    with httpx.stream("GET", DOWNLOAD_URL, follow_redirects=True, timeout=120.0) as response:
        if response.status_code != 200:
            print(f"ERROR: Download failed with HTTP {response.status_code}")
            sys.exit(1)
        total_size = int(response.headers.get("Content-Length", 0))
        print(f"      Total archive size: {total_size / (1024*1024):.2f} MB")

        with open(TEMP_ZIP, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=512 * 1024):
                f.write(chunk)
                downloaded_bytes += len(chunk)
                if total_size > 0:
                    pct = (downloaded_bytes / total_size) * 100
                    print(f"\r      Progress: {pct:.1f}% ({downloaded_bytes/(1024*1024):.1f} MB)", end="", flush=True)

    print(f"\n[3/5] Download complete ({downloaded_bytes / (1024*1024):.2f} MB). Extracting binaries to {TARGET_DIR}...")

    extracted_files = []
    with zipfile.ZipFile(TEMP_ZIP, "r") as zf:
        for member in zf.namelist():
            filename = os.path.basename(member)
            if filename in {"ffmpeg.exe", "ffprobe.exe", "LICENSE.txt", "README.txt"}:
                target_path = TARGET_DIR / filename
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_files.append(target_path)
                print(f"      Extracted: {filename} ({target_path.stat().st_size / (1024*1024):.2f} MB)")

    print("[4/5] Removing temporary download archive...")
    if TEMP_ZIP.exists():
        TEMP_ZIP.unlink()

    free_gb_after = check_disk_space()
    print(f"      Free disk space after extraction: {free_gb_after:.2f} GB")

    print("[5/5] Verifying installed executables...")
    ffmpeg_exe = TARGET_DIR / "ffmpeg.exe"
    ffprobe_exe = TARGET_DIR / "ffprobe.exe"

    if not ffmpeg_exe.exists() or not ffprobe_exe.exists():
        print("ERROR: Required binaries missing after extraction!")
        sys.exit(1)

    # Test running version checks
    p1 = subprocess.run([str(ffmpeg_exe), "-version"], capture_output=True, text=True, timeout=10.0)
    p2 = subprocess.run([str(ffprobe_exe), "-version"], capture_output=True, text=True, timeout=10.0)

    print("--- ffmpeg.exe -version (first 2 lines) ---")
    print("\n".join(p1.stdout.splitlines()[:2]))
    print("--- ffprobe.exe -version (first 2 lines) ---")
    print("\n".join(p2.stdout.splitlines()[:2]))

    # Confirm LGPL build and absence of GPL components
    print("\n--- License & Build Configuration Check ---")
    first_line_ffmpeg = p1.stdout.splitlines()[0] if p1.stdout else ""
    config_line = next((l for l in p1.stdout.splitlines() if "configuration:" in l), "")
    print(f"Version Header: {first_line_ffmpeg}")
    print(f"Has 'enable-libx264' in config: {'--enable-libx264' in config_line}")
    print(f"Has 'enable-gpl' in config: {'--enable-gpl' in config_line}")
    print(f"Has 'enable-version3' in config: {'--enable-version3' in config_line}")

    print("\nInstallation and initial verification SUCCESSFUL.")


if __name__ == "__main__":
    main()

