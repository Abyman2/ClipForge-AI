"""Hardware detection and profiling module.

Inspects host hardware (Intel Core i7-1255U, Iris Xe graphics, disk space)
and sets safe compute profiles.
"""

import os
import platform
import shutil
import sys
from typing import Any, Dict


def get_os_label() -> str:
    """Return accurately resolved OS name, correctly identifying Windows 11."""
    if platform.system() == "Windows":
        try:
            win_ver = sys.getwindowsversion()
            # Windows 11 begins at build 22000
            if win_ver.major == 10 and win_ver.build >= 22000:
                return f"Windows 11 ({platform.machine()})"
            return f"Windows {platform.release()} ({platform.machine()})"
        except Exception:
            return f"Windows {platform.release()} ({platform.machine()})"
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def get_disk_headroom(path: str = ".") -> Dict[str, float]:
    """Return disk total, used, and free space in gigabytes."""
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
        }
    except Exception:
        return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0}


def get_hardware_profile() -> Dict[str, Any]:
    """Inspect system hardware and return safe execution parameters."""
    cpu_count = os.cpu_count() or 4
    disk_info = get_disk_headroom(".")

    profile = {
        "os": get_os_label(),
        "cpu_model": platform.processor() or "Intel Core i7-1255U",
        "logical_cores": cpu_count,
        "recommended_worker_threads": min(4, max(1, cpu_count - 2)),
        "gpu_type": "Intel Iris Xe Integrated (CPU Fallback)",
        "cuda_available": False,
        "recommended_device": "cpu",
        "recommended_compute_type": "int8",
        "recommended_whisper_model": "base",
        "ffmpeg_encoder": "libx264",
        "disk_free_gb": disk_info["free_gb"],
        "storage_constrained": disk_info["free_gb"] < 25.0,
    }

    # Check for optional CUDA capability safely
    try:
        import torch

        if torch.cuda.is_available():
            vram_gb = round(
                torch.cuda.get_device_properties(0).total_memory / (1024**3), 2
            )
            profile["cuda_available"] = True
            profile["gpu_type"] = f"{torch.cuda.get_device_name(0)} ({vram_gb} GB VRAM)"
            if vram_gb >= 4.0:
                profile["recommended_device"] = "cuda"
                profile["recommended_compute_type"] = "float16"
                profile["ffmpeg_encoder"] = "h264_nvenc"
    except ImportError:
        pass

    return profile

