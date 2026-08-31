#!/usr/bin/env python3
"""Inspect an MP4 with FFmpeg and create a machine-readable report and contact sheet."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Missing dependency imageio-ffmpeg. Run bootstrap.ps1 first.") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def parse_duration(text: str) -> float | None:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def parse_streams(text: str) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    video_line = next((line for line in text.splitlines() if "Stream #" in line and "Video:" in line), None)
    audio_line = next((line for line in text.splitlines() if "Stream #" in line and "Audio:" in line), None)
    video = None
    audio = None
    if video_line:
        resolution = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", video_line)
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s+fps", video_line)
        codec_match = re.search(r"Video:\s*([^,\s]+)", video_line)
        video = {
            "codec": codec_match.group(1) if codec_match else None,
            "width": int(resolution.group(1)) if resolution else None,
            "height": int(resolution.group(2)) if resolution else None,
            "fps": float(fps_match.group(1)) if fps_match else None,
        }
    if audio_line:
        codec_match = re.search(r"Audio:\s*([^,\s]+)", audio_line)
        rate_match = re.search(r"(\d+)\s+Hz", audio_line)
        audio = {
            "codec": codec_match.group(1) if codec_match else None,
            "sample_rate": int(rate_match.group(1)) if rate_match else None,
        }
    return video, audio


def detect(video_path: Path, has_audio: bool) -> str:
    command = [ffmpeg_exe(), "-hide_banner", "-i", str(video_path), "-vf", "blackdetect=d=0.8:pix_th=0.10"]
    if has_audio:
        command.extend(["-af", "silencedetect=n=-45dB:d=1.5,volumedetect"])
    command.extend(["-f", "null", "-"])
    result = run(command)
    return result.stderr + result.stdout


def parse_ranges(text: str, kind: str) -> list[dict[str, float]]:
    if kind == "black":
        matches = re.finditer(r"black_start:(\d+(?:\.\d+)?)\s+black_end:(\d+(?:\.\d+)?)\s+black_duration:(\d+(?:\.\d+)?)", text)
        return [{"start": float(m.group(1)), "end": float(m.group(2)), "duration": float(m.group(3))} for m in matches]
    starts = [float(value) for value in re.findall(r"silence_start:\s*(\d+(?:\.\d+)?)", text)]
    ends = [(float(end), float(duration)) for end, duration in re.findall(r"silence_end:\s*(\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?)", text)]
    ranges = []
    for index, (end, duration) in enumerate(ends):
        start = starts[index] if index < len(starts) else max(0.0, end - duration)
        ranges.append({"start": start, "end": end, "duration": duration})
    return ranges


def create_contact_sheet(video_path: Path, duration: float, target: Path, count: int = 6) -> None:
    from PIL import Image, ImageDraw, ImageFont

    target.parent.mkdir(parents=True, exist_ok=True)
    times = [duration * (index + 0.5) / count for index in range(count)]
    with tempfile.TemporaryDirectory(prefix="local-video-qc-") as temp_value:
        temp = Path(temp_value)
        frames: list[tuple[float, Image.Image]] = []
        for index, timestamp in enumerate(times):
            frame_path = temp / f"frame-{index:02d}.png"
            result = run([
                ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
                "-i", str(video_path), "-frames:v", "1", "-vf", "scale=360:-2", str(frame_path),
            ])
            if result.returncode == 0 and frame_path.is_file():
                with Image.open(frame_path) as frame:
                    frames.append((timestamp, frame.convert("RGB").copy()))
        if not frames:
            raise RuntimeError("FFmpeg could not extract contact-sheet frames")

        columns = 3
        rows = math.ceil(len(frames) / columns)
        cell_width = max(frame.width for _, frame in frames)
        cell_height = max(frame.height for _, frame in frames) + 36
        sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "#07101E")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default(size=18)
        for index, (timestamp, frame) in enumerate(frames):
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            sheet.paste(frame, (x, y))
            draw.text((x + 8, y + frame.height + 7), f"{timestamp:.1f}s", fill="#F8FAFC", font=font)
        sheet.save(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    args = parser.parse_args()
    video_path = args.video.resolve()
    if not video_path.is_file():
        raise RuntimeError(f"Video not found: {video_path}")

    probe = run([ffmpeg_exe(), "-hide_banner", "-i", str(video_path), "-f", "null", "-"])
    probe_text = probe.stderr + probe.stdout
    duration = parse_duration(probe_text)
    video_stream, audio_stream = parse_streams(probe_text)
    if duration is None or video_stream is None:
        raise RuntimeError("Could not parse a valid video stream")

    detection = detect(video_path, audio_stream is not None)
    black = parse_ranges(detection, "black")
    silence = parse_ranges(detection, "silence") if audio_stream else []
    mean_match = re.search(r"mean_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", detection)
    max_match = re.search(r"max_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", detection)
    mean_volume = None if not mean_match or mean_match.group(1) == "-inf" else float(mean_match.group(1))
    max_volume = None if not max_match or max_match.group(1) == "-inf" else float(max_match.group(1))

    warnings: list[str] = []
    if black:
        warnings.append(f"Detected {len(black)} black segment(s) lasting at least 0.8 seconds")
    if audio_stream is None:
        warnings.append("No audio stream")
    elif max_volume is not None and max_volume > -0.5:
        warnings.append("Audio peak is close to clipping")
    elif max_volume is not None and max_volume < -12:
        warnings.append("Audio peak is unusually quiet")
    if silence:
        longest = max(item["duration"] for item in silence)
        if longest >= 3:
            warnings.append(f"Detected a long silent segment ({longest:.1f}s)")

    report = {
        "valid": True,
        "path": str(video_path),
        "bytes": video_path.stat().st_size,
        "duration": round(duration, 3),
        "video": video_stream,
        "audio": audio_stream,
        "mean_volume_db": mean_volume,
        "max_volume_db": max_volume,
        "black_segments": black,
        "silence_segments": silence,
        "warnings": warnings,
    }
    report_path = (args.report or video_path.with_name("qc.json")).resolve()
    sheet_path = (args.contact_sheet or video_path.with_name("contact-sheet.png")).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    create_contact_sheet(video_path, duration, sheet_path)
    print(json.dumps({"report": str(report_path), "contact_sheet": str(sheet_path), **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
