#!/usr/bin/env python3
"""Atomically deliver a validated MP4, then remove its marked temporary workdir."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

from runtime_paths import video_root as configured_video_root


MARKER_NAME = ".local-video-studio-workdir"
EXPECTED_MARKER = {"kind": "local-video-studio-workdir", "version": 1}
PARENT_MARKER_NAME = ".local-video-studio-parent"
EXPECTED_PARENT_MARKER = {"kind": "local-video-studio-parent", "version": 1}


def fail(message: str) -> None:
    raise RuntimeError(message)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_workdir(value: Path) -> Path:
    if value.is_symlink():
        fail(f"Refusing symlink work directory: {value}")
    workdir = value.resolve(strict=True)
    anchor = Path(workdir.anchor).resolve()
    home = Path.home().resolve()
    if workdir in {anchor, home} or len(workdir.parts) < 4:
        fail(f"Unsafe work directory: {workdir}")
    marker_path = workdir / MARKER_NAME
    if not marker_path.is_file():
        fail(f"Missing cleanup marker: {marker_path}")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Invalid cleanup marker: {exc}")
    if marker != EXPECTED_MARKER:
        fail(f"Unexpected cleanup marker contents: {marker_path}")
    return workdir


def validate_qc(report_path: Path, video: Path, allow_warnings: bool) -> dict[str, object]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read QC report: {exc}")
    if report.get("valid") is not True:
        fail("QC report is not valid")
    reported_path = report.get("path")
    if not reported_path or Path(str(reported_path)).resolve() != video:
        fail("QC report does not belong to the supplied video")
    warnings = report.get("warnings", [])
    if warnings and not allow_warnings:
        fail(f"QC warnings must be resolved before cleanup: {warnings}")
    expected_bytes = report.get("bytes")
    if not isinstance(expected_bytes, int) or expected_bytes <= 0:
        fail("QC report has no valid byte count")
    if video.stat().st_size != expected_bytes:
        fail("Video changed after QC")
    return report


def validate_quality(report_path: Path, storyboard: Path) -> dict[str, object]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read storyboard quality report: {exc}")
    if report.get("valid") is not True or int(report.get("score", 0)) < 80:
        fail("Storyboard quality gate did not pass")
    if report.get("errors"):
        fail(f"Storyboard quality report still has errors: {report['errors']}")
    expected_hash = hashlib.sha256(storyboard.read_bytes()).hexdigest()
    if report.get("storyboard_sha256") != expected_hash:
        fail("Storyboard changed after quality review")
    return report


def atomic_copy(source: Path, destination: Path, overwrite: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        fail(f"Destination already exists: {destination}")
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    try:
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source.stat().st_size or temporary.stat().st_size <= 0:
            fail("Delivered copy failed size verification")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def remove_empty_managed_parent(parent: Path) -> bool:
    """Remove the known work parent only when no other jobs or files remain."""
    if parent.name != ".local-video-studio-work" or not parent.is_dir():
        return False
    marker = parent / PARENT_MARKER_NAME
    if not marker.is_file():
        return False
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if value != EXPECTED_PARENT_MARKER:
        return False
    remaining = [item for item in parent.iterdir() if item.name != PARENT_MARKER_NAME]
    if remaining:
        return False
    marker.unlink()
    try:
        parent.rmdir()
    except OSError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--qc-report", required=True, type=Path)
    parser.add_argument("--quality-report", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--subtitle-destination", type=Path)
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    workdir = validate_workdir(args.work_dir)
    video = args.video.resolve(strict=True)
    report_path = args.qc_report.resolve(strict=True)
    quality_path = args.quality_report.resolve(strict=True)
    storyboard = (workdir / "storyboard.json").resolve(strict=True)
    destination = args.destination.resolve()
    video_root = configured_video_root().resolve()
    managed_root = (video_root / ".local-video-studio-work").resolve()
    if not is_within(workdir, managed_root):
        fail(f"Work directory must be under {managed_root}")
    if not is_within(destination, video_root) or destination == video_root:
        fail(f"Final destination must be under {video_root}")
    if not video.is_file() or not is_within(video, workdir):
        fail("Video must be a file inside the marked work directory")
    if not report_path.is_file() or not is_within(report_path, workdir):
        fail("QC report must be a file inside the marked work directory")
    if not quality_path.is_file() or not is_within(quality_path, workdir):
        fail("Quality report must be a file inside the marked work directory")
    if is_within(destination, workdir):
        fail("Final destination must be outside the work directory")
    if destination.suffix.lower() != ".mp4":
        fail("Final destination must use the .mp4 extension")

    report = validate_qc(report_path, video, args.allow_warnings)
    quality = validate_quality(quality_path, storyboard)
    atomic_copy(video, destination, args.overwrite)

    subtitle_destination: Path | None = None
    if args.subtitle_destination:
        subtitle_source = video.with_suffix(".srt")
        if not subtitle_source.is_file():
            fail(f"Requested subtitle file does not exist: {subtitle_source}")
        subtitle_destination = args.subtitle_destination.resolve()
        if is_within(subtitle_destination, workdir):
            fail("Subtitle destination must be outside the work directory")
        atomic_copy(subtitle_source, subtitle_destination, args.overwrite)

    managed_parent = workdir.parent
    try:
        shutil.rmtree(workdir)
    except OSError as exc:
        fail(f"Final MP4 was delivered, but temporary cleanup failed: {exc}")
    if workdir.exists():
        fail(f"Temporary cleanup did not remove: {workdir}")
    parent_removed = remove_empty_managed_parent(managed_parent)

    result = {
        "video": str(destination),
        "subtitles": str(subtitle_destination) if subtitle_destination else None,
        "duration": report.get("duration"),
        "video_stream": report.get("video"),
        "warnings": report.get("warnings", []),
        "quality_score": quality.get("score"),
        "temporary_artifacts_removed": True,
        "empty_work_parent_removed": parent_removed,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
