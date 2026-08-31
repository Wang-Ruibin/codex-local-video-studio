#!/usr/bin/env python3
"""Render and inspect a one-second cross-platform MP4 smoke fixture."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "codex-local-video-studio" / "skills" / "local-video-studio" / "scripts"


def run(script: str, *arguments: str) -> dict[str, object]:
    result = subprocess.run([sys.executable, str(SCRIPTS / script), *arguments], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else {}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="local-video-smoke-") as temp_value:
        work = Path(temp_value)
        assets = work / "assets"
        output = work / "output"
        assets.mkdir()
        output.mkdir()
        storyboard = work / "storyboard.json"
        storyboard.write_text(json.dumps({
            "version": 1,
            "video": {"title": "Smoke", "width": 320, "height": 320, "fps": 12, "background": "#07111F"},
            "style": {"font": "auto", "text": "#F8FAFC", "muted": "#AFC0D4", "accent": "#57E3FF", "card": "#122A45"},
            "narration": {"enabled": False},
            "music": {"path": "", "volume": 0.8, "ducking": False},
            "scenes": [{
                "id": "smoke", "role": "hook", "duration": 1.0, "kicker": "SMOKE",
                "headline": "Cross-platform render", "body": "Windows and Linux",
                "narration": "", "visual": "hero", "highlight": "OK", "accent": "#57E3FF",
            }],
        }, ensure_ascii=False), encoding="utf-8")
        run(
            "generate_bgm.py", "--storyboard", str(storyboard), "--output", str(assets / "bgm.wav"),
            "--duration", "1", "--mood", "tech", "--volume", "0.8", "--update-storyboard",
        )
        video = output / "video.mp4"
        rendered = run("render_video.py", str(storyboard), "--output", str(video))
        report = run(
            "inspect_video.py", str(video), "--report", str(output / "qc.json"),
            "--contact-sheet", str(output / "contact-sheet.png"),
        )
        if not report.get("valid") or not video.is_file():
            raise RuntimeError("Smoke render did not produce a valid MP4")
        print(json.dumps({
            "valid": True,
            "platform": sys.platform,
            "duration": rendered.get("duration"),
            "video": report.get("video"),
            "audio": report.get("audio"),
        }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"smoke error: {exc}", file=sys.stderr)
        raise SystemExit(1)
