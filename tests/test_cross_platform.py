from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "codex-local-video-studio" / "skills" / "local-video-studio" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CrossPlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = load_module("runtime_paths", SCRIPTS / "runtime_paths.py")

    def run_script(self, script: str, *arguments: str, env: dict[str, str] | None = None, expected: int = 0):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), *arguments],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        return result

    def test_video_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            expected = Path(temp_value).resolve()
            actual = self.paths.video_root(env={"LOCAL_VIDEO_STUDIO_ROOT": str(expected)})
            self.assertEqual(actual, expected)

    def test_cache_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            home = Path(temp_value).resolve()
            windows = self.paths.cache_root(env={}, system="Windows", home=home)
            linux = self.paths.cache_root(env={}, system="Linux", home=home)
            self.assertEqual(windows.parts[-4:], ("AppData", "Local", "Codex", "local-video-studio"))
            self.assertEqual(linux.parts[-3:], (".cache", "codex", "local-video-studio"))

    def test_bgm_quality_gate_and_safe_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            base = Path(temp_value).resolve()
            video_root = base / "videos"
            work = video_root / ".local-video-studio-work" / "test-job"
            env = os.environ.copy()
            env["LOCAL_VIDEO_STUDIO_ROOT"] = str(video_root)

            self.run_script("new_project.py", str(work), env=env)
            source = work / "source.md"
            source.write_text(
                "# Source and provenance\n\n## Claim map\n\n- Claim -> https://example.com/source\n\n"
                "## Factual digest\n\n- Verified test fact.\n",
                encoding="utf-8",
            )
            self.run_script(
                "generate_bgm.py",
                "--storyboard", str(work / "storyboard.json"),
                "--output", str(work / "assets" / "bgm.wav"),
                "--duration", "1",
                "--mood", "calm",
                "--update-storyboard",
                env=env,
            )
            with wave.open(str(work / "assets" / "bgm.wav"), "rb") as reader:
                self.assertEqual(reader.getnchannels(), 1)
                self.assertGreater(reader.getnframes(), 0)

            quality = work / "output" / "storyboard-quality.json"
            self.run_script(
                "review_storyboard.py", str(work / "storyboard.json"),
                "--source", str(source), "--report", str(quality), env=env,
            )
            quality_data = json.loads(quality.read_text(encoding="utf-8"))
            self.assertTrue(quality_data["valid"])
            self.assertGreaterEqual(quality_data["score"], 80)
            self.run_script("render_video.py", str(work / "storyboard.json"), "--check", env=env)

            video = work / "output" / "video.mp4"
            video.write_bytes(b"test-mp4-payload")
            qc = work / "output" / "qc.json"
            qc.write_text(json.dumps({
                "valid": True,
                "path": str(video.resolve()),
                "bytes": video.stat().st_size,
                "duration": 1.0,
                "video": {"codec": "h264", "width": 320, "height": 320, "fps": 12},
                "warnings": [],
            }), encoding="utf-8")
            destination = video_root / "finished.mp4"
            self.run_script(
                "finalize_video.py",
                "--work-dir", str(work), "--video", str(video),
                "--qc-report", str(qc), "--quality-report", str(quality),
                "--destination", str(destination), env=env,
            )
            self.assertTrue(destination.is_file())
            self.assertFalse(work.exists())
            self.assertFalse((video_root / ".local-video-studio-work").exists())

    def test_speech_cli_is_importable(self) -> None:
        result = self.run_script("synthesize_speech.py", "--help")
        self.assertIn("Windows or Linux", result.stdout)


if __name__ == "__main__":
    unittest.main()
