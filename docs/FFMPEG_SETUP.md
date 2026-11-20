# ClipForge AI — FFmpeg & FFprobe Setup & Reproducibility Guide

**Document Version:** 1.0.0  
**Target Platform:** Windows 11 64-bit  
**Scope:** Stage 2.2 Media Ingestion & FFmpeg Integration  

---

## 1. Overview & Architectural Role

ClipForge AI relies on **FFmpeg** and **FFprobe** for local media ingestion, container inspection, standardized audio extraction (16kHz 16-bit mono PCM WAV for Whisper), and range-based media playback.

To prevent dependency conflicts and avoid modifying the host system's global `PATH` or registry, ClipForge uses a **portable, project-local unbundled installation** located in:

```text
tools/ffmpeg/bin/
├── ffmpeg.exe
├── ffprobe.exe
└── LICENSE.txt
```

> [!IMPORTANT]
> The `tools/ffmpeg/` directory is strictly ignored by Git (`.gitignore`). Binaries must never be committed to source control.

---

## 2. Installed Binary Identity & Provenance

| Parameter | Specification |
| :--- | :--- |
| **Upstream Provider** | [BtbN / FFmpeg-Builds (GitHub)](https://github.com/FFmpeg-Builds/FFmpeg-Builds) |
| **Release Channel** | Latest Master LGPL Build |
| **Archive Name** | `ffmpeg-master-latest-win64-lgpl.zip` |
| **Archive Download URL** | `https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip` |
| **Exact Version** | `N-129150-g7ddf7bc8a4-20261120` |
| **Compiler** | GCC 16.2.0 (crosstool-NG 1.29.0.36_fbb6372) |
| **Reported License** | **GNU Lesser General Public License v3.0 (LGPL v3)** |
| **Extracted Executables Size** | `ffmpeg.exe` (~132.3 MB), `ffprobe.exe` (~132.1 MB) |

---

## 3. Cryptographic Verification (SHA-256 Hashes)

Before using or replacing the binaries, verify their integrity against these SHA-256 checksums:

```text
tools/ffmpeg/bin/ffmpeg.exe
SHA-256: 93FB4A9E9141AD0F33801CDA4C36AE16C06451D2533397930C4CFBEBAC6A20CD

tools/ffmpeg/bin/ffprobe.exe
SHA-256: 3B5B5BCCDC1B12B262EFA4E41D732B886EFFE4FF0F16B0CF1B1795BD20F50C83
```

To compute hashes on Windows 11 PowerShell:
```powershell
Get-FileHash tools/ffmpeg/bin/ffmpeg.exe, tools/ffmpeg/bin/ffprobe.exe -Algorithm SHA256 | Format-List Path, Hash
```

---

## 4. Build Configuration & License Considerations

The build configuration was independently verified via `ffmpeg -version`:

```text
configuration: --prefix=/ffbuild/prefix --pkg-config-flags=--static --pkg-config=pkg-config
--cross-prefix=x86_64-w64-mingw32- --arch=x86_64 --target-os=mingw32 --enable-version3
--disable-debug --disable-w32threads --enable-pthreads --enable-iconv --enable-zlib
--enable-libxml2 --enable-libvmaf --enable-fontconfig --enable-libharfbuzz --enable-libfreetype
--enable-libfribidi --enable-lcms2 --enable-vulkan --enable-libdav1d --enable-libvorbis
--enable-librav1e --enable-librsvg --disable-libxcb --disable-xlib --disable-libpulse
--enable-gmp --enable-lzma --enable-liblcevc-dec --enable-opencl --enable-amf --enable-libaom
--disable-avisynth --enable-chromaprint --disable-libdavs2 --disable-libdvdread
--disable-libdvdnav --disable-libfdk-aac --enable-ffnvcodec --enable-cuda-llvm --disable-frei0r
--enable-libgme --enable-libkvazaar --enable-libaribb24 --enable-libaribcaption --enable-libass
--enable-libbluray --enable-libcurl --enable-libjxl --enable-libmp3lame --enable-libopus
--enable-libplacebo --enable-librist --enable-libssh --enable-libtheora --enable-libvpx
--enable-libwebp --enable-libzmq --enable-lv2 --enable-libvpl --enable-openal --enable-liboapv
--enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopenh264 --enable-libopenjpeg
--enable-libopenmpt --disable-librubberband --enable-schannel --enable-sdl2 --enable-libsnappy
--enable-libsoxr --enable-libsrt --enable-libsvtav1 --enable-libtwolame --enable-libuavs3d
--disable-libdrm --enable-vaapi --enable-vapoursynth --disable-libvidstab --enable-libvvenc
--disable-whisper --disable-libx264 --disable-libx265 --disable-libxavs2 --disable-libxvid
--enable-libzimg --disable-libzvbi
```

### Key Licensing Facts:
- **`--enable-version3`:** Builds under LGPL v3 terms.
- **`--disable-libx264` & `--disable-libx265`:** GPL-only video codecs are explicitly excluded.
- **`--enable-gpl`:** Not present (`False`).
- **Subprocess Isolation:** ClipForge AI interacts with `ffmpeg.exe` and `ffprobe.exe` exclusively as separate CLI subprocesses (`asyncio.create_subprocess_exec` / `subprocess.run`). No C-level static or dynamic linking into the Python package exists.
- **Redistribution Disclaimer:** Any entity redistributing compiled FFmpeg binaries must comply with LGPL requirements, including providing the accompanying license (`LICENSE.txt`) and access to source code. Build configuration flags alone do not substitute for comprehensive legal diligence.

---

## 5. Binary Discovery Mechanism in ClipForge

The backend module `clipforge/media/ffmpeg.py` locates binaries dynamically in this priority order:

1. **Explicit Custom Override:** Path supplied to `FFmpegInterface(custom_ffmpeg_path=...)` or configured via `CLIPFORGE_FFMPEG_PATH` in `.env`.
2. **Project-Local Binaries (Default):**
   - `Path.cwd() / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"`
   - `Path.cwd() / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"`
3. **System PATH Fallback:** Searched via `shutil.which("ffmpeg")` and `shutil.which("ffprobe")`.

If found, `FFmpegInterface.is_available()` returns `True`, and `/api/health` reports the tool versions.

---

## 6. How to Reproduce or Reinstall on a Fresh Machine

A new contributor can reproduce this exact setup by running the included automated installer script:

```powershell
# From the project root, inside the Python virtual environment:
.\.venv\Scripts\python scripts/install_ffmpeg.py
```

### Manual Steps:
1. Ensure at least **8.0 GB** of free disk space is available on drive `C:`.
2. Download `ffmpeg-master-latest-win64-lgpl.zip` from the BtbN releases page.
3. Extract `ffmpeg.exe`, `ffprobe.exe`, and `LICENSE.txt` into `tools/ffmpeg/bin/`.
4. Delete the downloaded `.zip` file immediately to conserve disk space.
5. Verify installation by running:
   ```powershell
   .\tools\ffmpeg\bin\ffmpeg.exe -version
   .\tools\ffmpeg\bin\ffprobe.exe -version
   ```
6. Run the integration test suite:
   ```powershell
   .\.venv\Scripts\pytest tests/unit/test_media_interface.py
   ```
