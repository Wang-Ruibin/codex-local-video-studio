#!/usr/bin/env python3
"""Create or refresh the shared cross-platform Python runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import venv
from pathlib import Path

from runtime_paths import cache_root, runtime_python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path)
    args = parser.parse_args()
    runtime = (args.runtime_dir or cache_root()).expanduser().resolve()
    python = runtime_python(runtime)
    requirements = Path(__file__).with_name("requirements.txt")
    runtime.mkdir(parents=True, exist_ok=True)
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(runtime / ".venv")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        check=True,
    )
    check = subprocess.run(
        [str(python), "-c", "import PIL, imageio_ffmpeg; print(PIL.__version__); print(imageio_ffmpeg.get_ffmpeg_version())"],
        check=True,
        capture_output=True,
        text=True,
    )
    versions = [line.strip() for line in check.stdout.splitlines() if line.strip()]
    print(json.dumps({
        "runtime": str(runtime),
        "python": str(python),
        "pillow": versions[0] if versions else None,
        "ffmpeg": versions[1] if len(versions) > 1 else None,
        "platform": sys.platform,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
