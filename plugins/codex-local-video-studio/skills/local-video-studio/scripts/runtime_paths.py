#!/usr/bin/env python3
"""Resolve cross-platform video and shared-runtime locations."""

from __future__ import annotations

import argparse
import os
import platform
from pathlib import Path
from typing import Mapping


VIDEO_ROOT_ENV = "LOCAL_VIDEO_STUDIO_ROOT"
CACHE_ROOT_ENV = "LOCAL_VIDEO_STUDIO_CACHE"


def _absolute_path(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {value}")
    return path.resolve()


def video_root(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    values = os.environ if env is None else env
    configured = values.get(VIDEO_ROOT_ENV, "").strip()
    if configured:
        return _absolute_path(configured, VIDEO_ROOT_ENV)
    base = (home or Path.home()).expanduser().resolve()
    return base / "Videos" / "local-video-studio"


def cache_root(
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    values = os.environ if env is None else env
    configured = values.get(CACHE_ROOT_ENV, "").strip()
    if configured:
        return _absolute_path(configured, CACHE_ROOT_ENV)
    current_system = system or platform.system()
    base_home = (home or Path.home()).expanduser().resolve()
    if current_system == "Windows":
        local_app_data = values.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data).resolve() if local_app_data else base_home / "AppData" / "Local"
        return base / "Codex" / "local-video-studio"
    xdg_cache = values.get("XDG_CACHE_HOME", "").strip()
    base = Path(xdg_cache).expanduser().resolve() if xdg_cache else base_home / ".cache"
    return base / "codex" / "local-video-studio"


def runtime_python(runtime: Path | None = None, system: str | None = None) -> Path:
    current_system = system or platform.system()
    venv = (runtime or cache_root()) / ".venv"
    return venv / ("Scripts/python.exe" if current_system == "Windows" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video-root", action="store_true")
    group.add_argument("--cache-root", action="store_true")
    group.add_argument("--runtime-python", action="store_true")
    args = parser.parse_args()
    if args.video_root:
        print(video_root())
    elif args.cache_root:
        print(cache_root())
    else:
        print(runtime_python())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
