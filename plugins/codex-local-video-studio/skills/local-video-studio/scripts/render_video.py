#!/usr/bin/env python3
"""Render an editable JSON storyboard to MP4, WAV narration, and SRT captions."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TAU = math.tau


@dataclass
class AudioChunk:
    path: Path | None
    duration: float
    caption: str


def fail(message: str) -> None:
    raise ValueError(message)


def load_storyboard(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read storyboard: {exc}")
    if data.get("version") != 1:
        fail("storyboard version must be 1")
    video = data.get("video")
    scenes = data.get("scenes")
    if not isinstance(video, dict):
        fail("video must be an object")
    if not isinstance(scenes, list) or not scenes:
        fail("scenes must be a non-empty array")

    width = int(video.get("width", 1080))
    height = int(video.get("height", 1920))
    fps = int(video.get("fps", 30))
    if not 320 <= width <= 3840 or not 320 <= height <= 3840:
        fail("video width and height must be between 320 and 3840")
    if width % 2 or height % 2:
        fail("video width and height must be even for H.264 output")
    if not 12 <= fps <= 60:
        fail("video fps must be between 12 and 60")

    seen: set[str] = set()
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            fail(f"scene {index + 1} must be an object")
        scene_id = str(scene.get("id", f"scene-{index + 1}"))
        if scene_id in seen:
            fail(f"duplicate scene id: {scene_id}")
        seen.add(scene_id)
        duration = float(scene.get("duration", 4.0))
        if not 0.5 <= duration <= 60:
            fail(f"scene {scene_id} duration must be between 0.5 and 60 seconds")
        visual = scene.get("visual", "rings")
        if visual not in {
            "rings", "bars", "timeline", "checklist", "quote", "image",
            "hero", "diagram", "process", "comparison", "chart", "scale", "evidence", "recap",
        }:
            fail(f"scene {scene_id} has unsupported visual: {visual}")
        items = scene.get("items", [])
        if items and (not isinstance(items, list) or len(items) > 5):
            fail(f"scene {scene_id} items must be an array with at most 5 entries")
        for key in ("audio", "background_image"):
            value = scene.get(key)
            if value and not resolve_asset(path.parent, str(value)).is_file():
                fail(f"scene {scene_id} {key} not found: {value}")

    music = data.get("music", {})
    if music.get("path") and not resolve_asset(path.parent, str(music["path"])).is_file():
        fail(f"music file not found: {music['path']}")
    return data


def resolve_asset(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Missing dependency imageio-ffmpeg. Run bootstrap.ps1 first.") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_checked(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message[-4000:])


def normalize_audio(source: Path, target: Path) -> None:
    run_checked([
        ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(target),
    ])


def synthesize(text: str, target: Path, narration: dict[str, Any], temp: Path) -> None:
    from synthesize_speech import synthesize_to_wav

    raw_wav = temp / f"{target.stem}-speech.wav"
    synthesize_to_wav(text, raw_wav, narration, temp)
    normalize_audio(raw_wav, target)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as reader:
        return reader.getnframes() / reader.getframerate()


def silence_frames(seconds: float, rate: int = 22050) -> bytes:
    return b"\x00\x00" * max(0, round(seconds * rate))


def split_caption(text: str, max_units: int = 18) -> list[str]:
    """Split narration into short readable phrases without word-level timing."""
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    pieces = [piece.strip() for piece in re.split(r"(?<=[。！？!?；;，,])", text) if piece.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        units = len(piece.replace(" ", "")) if not re.search(r"[A-Za-z]", piece) else len(piece.split()) * 2
        current_units = len(current.replace(" ", "")) if not re.search(r"[A-Za-z]", current) else len(current.split()) * 2
        if current and current_units + units > max_units:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}{piece}" if not re.search(r"[A-Za-z]", text) else f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks or [text]


def timed_caption_chunks(start: float, duration: float, text: str) -> list[tuple[float, float, str]]:
    chunks = split_caption(text)
    if not chunks:
        return []
    weights = [max(1, len(re.sub(r"\s+", "", chunk))) for chunk in chunks]
    total_weight = sum(weights)
    cursor = start
    result: list[tuple[float, float, str]] = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        chunk_duration = duration * weight / total_weight
        end = start + duration if index == len(chunks) - 1 else cursor + chunk_duration
        result.append((cursor, end, chunk))
        cursor = end
    return result


def prepare_audio(data: dict[str, Any], storyboard: Path, temp: Path) -> tuple[list[float], Path | None, list[tuple[float, float, str]]]:
    narration = data.get("narration", {})
    narration_enabled = bool(narration.get("enabled", True))
    lead_in = max(0.0, float(narration.get("lead_in", 0.25)))
    lead_out = max(0.0, float(narration.get("lead_out", 0.35)))
    chunks: list[AudioChunk] = []

    for index, scene in enumerate(data["scenes"]):
        caption = str(scene.get("narration", "")).strip()
        normalized = temp / f"scene-{index + 1:03d}.wav"
        if scene.get("audio"):
            normalize_audio(resolve_asset(storyboard.parent, str(scene["audio"])), normalized)
            chunks.append(AudioChunk(normalized, wav_duration(normalized), caption))
        elif narration_enabled and caption:
            synthesize(caption, normalized, narration, temp)
            chunks.append(AudioChunk(normalized, wav_duration(normalized), caption))
        else:
            chunks.append(AudioChunk(None, 0.0, caption))

    durations: list[float] = []
    captions: list[tuple[float, float, str]] = []
    cursor = 0.0
    has_audio = any(chunk.path for chunk in chunks)
    combined = temp / "narration.wav" if has_audio else None

    writer = wave.open(str(combined), "wb") if combined else None
    if writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(22050)

    try:
        for scene, chunk in zip(data["scenes"], chunks):
            minimum = float(scene.get("duration", 4.0))
            duration = max(minimum, lead_in + chunk.duration + lead_out if chunk.path else minimum)
            durations.append(duration)
            if writer:
                writer.writeframes(silence_frames(lead_in))
                if chunk.path:
                    with wave.open(str(chunk.path), "rb") as reader:
                        writer.writeframes(reader.readframes(reader.getnframes()))
                    if chunk.caption:
                        captions.extend(timed_caption_chunks(cursor + lead_in, chunk.duration, chunk.caption))
                writer.writeframes(silence_frames(max(0.0, duration - lead_in - chunk.duration)))
            cursor += duration
    finally:
        if writer:
            writer.close()
    return durations, combined, captions


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(path: Path, captions: list[tuple[float, float, str]]) -> None:
    blocks = []
    for index, (start, end, text) in enumerate(captions, 1):
        blocks.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8-sig")


def parse_color(value: str, fallback: str):
    from PIL import ImageColor
    try:
        return ImageColor.getrgb(value)
    except ValueError:
        return ImageColor.getrgb(fallback)


def load_font(spec: str, base: Path, size: int, bold: bool = False):
    from PIL import ImageFont
    candidates: list[Path] = []
    if spec and spec != "auto":
        candidates.append(resolve_asset(base, spec))
    if platform.system() == "Windows":
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates.extend([
            windows_fonts / ("msyhbd.ttc" if bold else "msyh.ttc"),
            windows_fonts / "simhei.ttf",
            windows_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
        ])
    candidates.extend([
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ])
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


def wrap_text(draw, text: str, font, max_width: int) -> str:
    paragraphs = str(text).splitlines() or [""]
    output: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            output.append("")
            continue
        words = paragraph.split(" ") if " " in paragraph else list(paragraph)
        separator = " " if " " in paragraph else ""
        current = ""
        for word in words:
            candidate = word if not current else current + separator + word
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    output.append(current)
                current = word
        if current:
            output.append(current)
    return "\n".join(output)


def ease_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def fitted_text(draw, text: str, spec: str, base: Path, start_size: int, minimum_size: int, max_width: int, max_height: int, spacing: int):
    size = start_size
    while size >= minimum_size:
        font = load_font(spec, base, size, bold=True)
        wrapped = wrap_text(draw, text, font, max_width)
        box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font, wrapped
        size -= max(2, start_size // 18)
    font = load_font(spec, base, minimum_size, bold=True)
    return font, wrap_text(draw, text, font, max_width)


def blend_color(first: tuple[int, int, int], second: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * amount) for a, b in zip(first, second))


def cover_image(image, width: int, height: int, zoom: float):
    from PIL import Image
    ratio = max(width / image.width, height / image.height) * zoom
    resized = image.resize((math.ceil(image.width * ratio), math.ceil(image.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def render_scene(
    data: dict[str, Any], scene: dict[str, Any], progress: float, index: int, total: int,
    base: Path, width: int, height: int, caption_text: str = "",
):
    from PIL import Image, ImageDraw

    style = data.get("style", {})
    scale = width / 1080
    bg = parse_color(str(data.get("video", {}).get("background", "#08111F")), "#08111F")
    bg_alt = parse_color(str(style.get("background_alt", "#102743")), "#102743")
    text_color = parse_color(str(style.get("text", "#F8FAFC")), "#F8FAFC")
    muted = parse_color(str(style.get("muted", "#AFC0D4")), "#AFC0D4")
    card = parse_color(str(style.get("card", "#122A45")), "#122A45")
    accent = parse_color(str(scene.get("accent", style.get("accent", "#57E3FF"))), "#57E3FF")
    image = Image.new("RGB", (width, height), bg)
    base_draw = ImageDraw.Draw(image)
    for band in range(40):
        y0 = round(height * band / 40)
        y1 = round(height * (band + 1) / 40)
        amount = 0.08 + 0.16 * band / 39
        base_draw.rectangle((0, y0, width, y1), fill=blend_color(bg, bg_alt, amount))

    if scene.get("background_image"):
        with Image.open(resolve_asset(base, str(scene["background_image"]))) as source:
            image = cover_image(source.convert("RGB"), width, height, 1.0 + progress * 0.025)
        overlay = Image.new("RGBA", (width, height), (3, 10, 22, 158))
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = round(78 * scale)
    opacity = round(255 * ease_out(min(1.0, progress / 0.13)))
    rise = round((1 - ease_out(min(1.0, progress / 0.20))) * 34 * scale)
    font_spec = str(style.get("font", "auto"))
    kicker_font = load_font(font_spec, base, max(15, round(27 * scale)), bold=True)
    body_font = load_font(font_spec, base, max(19, round(34 * scale)))
    item_font = load_font(font_spec, base, max(20, round(38 * scale)), bold=True)
    small_font = load_font(font_spec, base, max(16, round(28 * scale)))
    caption_font = load_font(font_spec, base, max(19, round(35 * scale)), bold=True)

    # A restrained grid and one glow establish depth without competing with content.
    grid_step = max(60, round(135 * scale))
    for x in range(margin, width, grid_step):
        draw.line((x, 0, x, height), fill=(*muted, 10), width=1)
    for y in range(0, height, grid_step):
        draw.line((0, y, width, y), fill=(*muted, 9), width=1)
    glow_x = round(width * (0.78 + 0.04 * math.sin(progress * TAU)))
    glow_y = round(height * 0.31)
    for ring in range(5, 0, -1):
        radius = round((80 + ring * 55) * scale)
        draw.ellipse((glow_x - radius, glow_y - radius, glow_x + radius, glow_y + radius), outline=(*accent, 8 + ring * 5), width=max(1, round(3 * scale)))

    kicker = str(scene.get("kicker", scene.get("role", ""))).strip().upper()
    if kicker:
        pill_width = min(width - 2 * margin, round((95 + len(kicker) * 18) * scale))
        draw.rounded_rectangle((margin, round(88 * scale), margin + pill_width, round(142 * scale)), radius=round(27 * scale), fill=(*accent, 35), outline=(*accent, 70), width=max(1, round(2 * scale)))
        draw.text((margin + round(22 * scale), round(100 * scale)), kicker, font=kicker_font, fill=(*accent, opacity))

    headline_font, headline = fitted_text(
        draw, str(scene.get("headline", "")), font_spec, base, max(34, round(78 * scale)),
        max(28, round(50 * scale)), width - 2 * margin, round(300 * scale), round(16 * scale),
    )
    headline_y = round(190 * scale) + rise
    draw.multiline_text((margin, headline_y), headline, font=headline_font, fill=(*text_color, opacity), spacing=round(16 * scale), stroke_width=max(1, round(1.2 * scale)), stroke_fill=(0, 0, 0, opacity // 2))
    headline_box = draw.multiline_textbbox((margin, headline_y), headline, font=headline_font, spacing=round(16 * scale))
    content_y = max(round(565 * scale), headline_box[3] + round(42 * scale))
    visual_bottom = height - round(430 * scale)

    body = str(scene.get("body", "")).strip()
    if body:
        wrapped_body = wrap_text(draw, body, body_font, width - 2 * margin)
        draw.multiline_text((margin, content_y), wrapped_body, font=body_font, fill=(*muted, round(opacity * 0.92)), spacing=round(12 * scale))
        body_box = draw.multiline_textbbox((margin, content_y), wrapped_body, font=body_font, spacing=round(12 * scale))
        content_y = min(body_box[3] + round(34 * scale), round(780 * scale))

    items = [str(item) for item in scene.get("items", [])]
    visual = str(scene.get("visual", "hero"))
    reveal = lambda item_index: ease_out(max(0.0, min(1.0, progress * 1.85 - item_index * 0.16)))

    if visual in {"hero", "rings"}:
        cx, cy = width // 2, round((content_y + visual_bottom) / 2)
        radius = min(round(245 * scale), max(round(120 * scale), (visual_bottom - content_y) // 3))
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*accent, 24), outline=(*accent, 170), width=max(2, round(5 * scale)))
        for node_index in range(6):
            angle = progress * 0.55 + node_index * TAU / 6
            orbit = radius * (1.30 + 0.08 * math.sin(progress * TAU + node_index))
            nx, ny = cx + math.cos(angle) * orbit, cy + math.sin(angle) * orbit
            draw.line((cx, cy, nx, ny), fill=(*accent, 45), width=max(1, round(2 * scale)))
            nr = round(12 * scale)
            draw.ellipse((nx - nr, ny - nr, nx + nr, ny + nr), fill=(*accent, 220))
        highlight = str(scene.get("highlight", "?"))
        highlight_font = load_font(font_spec, base, max(42, round(95 * scale)), bold=True)
        draw.text((cx, cy), highlight, font=highlight_font, fill=(*text_color, opacity), anchor="mm")

    elif visual in {"diagram", "process"}:
        nodes = items[:4] or ["输入", "机制", "结果"]
        available = max(1, visual_bottom - content_y)
        node_height = min(round(120 * scale), available // max(1, len(nodes)) - round(22 * scale))
        for item_index, item in enumerate(nodes):
            p = reveal(item_index)
            y = content_y + item_index * (node_height + round(28 * scale))
            x_shift = round((1 - p) * 50 * scale)
            draw.rounded_rectangle((margin + x_shift, y, width - margin, y + node_height), radius=round(28 * scale), fill=(*card, round(225 * p)), outline=(*accent, round(90 + 90 * p)), width=max(1, round(2 * scale)))
            badge_x = margin + x_shift + round(48 * scale)
            badge_y = y + node_height // 2
            badge_r = round(22 * scale)
            draw.ellipse((badge_x - badge_r, badge_y - badge_r, badge_x + badge_r, badge_y + badge_r), fill=(*accent, round(255 * p)))
            draw.text((badge_x, badge_y), str(item_index + 1), font=small_font, fill=(*bg, round(255 * p)), anchor="mm")
            draw.text((badge_x + round(52 * scale), badge_y), item, font=item_font, fill=(*text_color, round(255 * p)), anchor="lm")
            if item_index + 1 < len(nodes):
                arrow_x = width // 2
                arrow_y = y + node_height + round(14 * scale)
                draw.line((arrow_x, y + node_height, arrow_x, arrow_y + round(10 * scale)), fill=(*accent, round(160 * p)), width=max(2, round(4 * scale)))

    elif visual == "comparison":
        labels = items[:2] or ["一侧", "另一侧"]
        gap = round(26 * scale)
        panel_width = (width - 2 * margin - gap) // 2
        panel_height = max(round(280 * scale), visual_bottom - content_y)
        for item_index, item in enumerate(labels):
            p = reveal(item_index)
            x = margin + item_index * (panel_width + gap)
            draw.rounded_rectangle((x, content_y, x + panel_width, content_y + panel_height), radius=round(34 * scale), fill=(*card, round(220 * p)), outline=(*accent, round((80 if item_index else 150) * p)), width=max(2, round(3 * scale)))
            number_font = load_font(font_spec, base, max(36, round(76 * scale)), bold=True)
            draw.text((x + round(34 * scale), content_y + round(36 * scale)), f"0{item_index + 1}", font=number_font, fill=(*accent, round(90 * p)))
            wrapped = wrap_text(draw, item, item_font, panel_width - round(60 * scale))
            draw.multiline_text((x + round(30 * scale), content_y + round(150 * scale)), wrapped, font=item_font, fill=(*text_color, round(255 * p)), spacing=round(12 * scale))
            wave_y = content_y + round(panel_height * 0.72)
            wavelength = round((92 if item_index == 0 else 46) * scale)
            amplitude = round((20 if item_index == 0 else 31) * scale)
            wave_points = []
            for px in range(x + round(24 * scale), x + panel_width - round(24 * scale), max(2, round(5 * scale))):
                phase = (px - x) / max(1, wavelength) * TAU + progress * TAU * 0.35
                wave_points.append((px, wave_y + math.sin(phase) * amplitude))
            if len(wave_points) > 1:
                draw.line(wave_points, fill=(*accent, round(190 * p)), width=max(2, round(4 * scale)), joint="curve")
            draw.line((x + round(28 * scale), content_y + panel_height - round(46 * scale), x + panel_width - round(28 * scale), content_y + panel_height - round(46 * scale)), fill=(*muted, round(65 * p)), width=max(1, round(2 * scale)))

    elif visual in {"chart", "bars"}:
        raw_points = scene.get("data", [])
        points: list[tuple[str, float]] = []
        if isinstance(raw_points, list):
            for point in raw_points[:5]:
                if isinstance(point, dict):
                    try:
                        points.append((str(point.get("label", "")), float(point.get("value", 0))))
                    except (TypeError, ValueError):
                        pass
        if not points:
            points = [(item, float(i + 1)) for i, item in enumerate(items[:5] or ["A", "B", "C", "D"])]
        max_value = max((value for _, value in points), default=1) or 1
        chart_height = max(round(300 * scale), visual_bottom - content_y - round(70 * scale))
        gap = round(18 * scale)
        bar_width = (width - 2 * margin - gap * (len(points) - 1)) // max(1, len(points))
        for point_index, (label, value) in enumerate(points):
            p = reveal(point_index)
            bar_height = chart_height * max(0.02, value / max_value) * p
            x = margin + point_index * (bar_width + gap)
            y = content_y + chart_height - bar_height
            draw.rounded_rectangle((x, y, x + bar_width, content_y + chart_height), radius=round(18 * scale), fill=(*accent, round(95 + 140 * p)))
            label_font = load_font(font_spec, base, max(14, round(24 * scale)), bold=True)
            draw.text((x + bar_width // 2, content_y + chart_height + round(18 * scale)), label, font=label_font, fill=(*muted, round(255 * p)), anchor="ma")

    elif visual in {"scale", "timeline"}:
        labels = items[:4] or ["起点", "变化", "结果"]
        y = round((content_y + visual_bottom) / 2)
        draw.line((margin, y, width - margin, y), fill=(*accent, 150), width=max(3, round(6 * scale)))
        for item_index, item in enumerate(labels):
            p = reveal(item_index)
            x = round(margin + item_index * (width - 2 * margin) / max(1, len(labels) - 1))
            radius = round((13 + 17 * p) * scale)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*accent, round(255 * p)), outline=(*text_color, round(100 * p)), width=max(1, round(2 * scale)))
            wrapped = wrap_text(draw, item, small_font, round(190 * scale))
            draw.multiline_text((x, y + round(55 * scale)), wrapped, font=small_font, fill=(*text_color, round(255 * p)), anchor="ma", align="center", spacing=round(7 * scale))

    elif visual in {"evidence", "recap", "checklist"}:
        source_label = str(scene.get("source_label", "EVIDENCE" if visual == "evidence" else "KEY TAKEAWAYS"))
        draw.text((margin, content_y), source_label, font=kicker_font, fill=(*accent, opacity))
        start_y = content_y + round(58 * scale)
        for item_index, item in enumerate(items[:4]):
            p = reveal(item_index)
            y = start_y + item_index * round(116 * scale)
            draw.rounded_rectangle((margin, y, width - margin, y + round(88 * scale)), radius=round(22 * scale), fill=(*card, round(205 * p)), outline=(*accent, round(55 * p)), width=max(1, round(2 * scale)))
            cx, cy = margin + round(43 * scale), y + round(44 * scale)
            draw.ellipse((cx - round(17 * scale), cy - round(17 * scale), cx + round(17 * scale), cy + round(17 * scale)), fill=(*accent, round(240 * p)))
            symbol = "✓" if visual == "evidence" else str(item_index + 1)
            draw.text((cx, cy), symbol, font=small_font, fill=(*bg, round(255 * p)), anchor="mm")
            draw.text((cx + round(42 * scale), cy), item, font=item_font, fill=(*text_color, round(255 * p)), anchor="lm")

    elif visual == "quote":
        quote_font = load_font(font_spec, base, max(70, round(220 * scale)), bold=True)
        draw.text((width - margin, content_y), "“", font=quote_font, fill=(*accent, 90), anchor="ra")

    if caption_text:
        wrapped_caption = wrap_text(draw, caption_text, caption_font, width - 2 * margin - round(70 * scale))
        caption_box = draw.multiline_textbbox((0, 0), wrapped_caption, font=caption_font, spacing=round(9 * scale))
        caption_height = caption_box[3] - caption_box[1] + round(50 * scale)
        caption_y = height - round(155 * scale) - caption_height
        caption_width = min(width - 2 * margin, caption_box[2] - caption_box[0] + round(78 * scale))
        caption_x = (width - caption_width) // 2
        draw.rounded_rectangle((caption_x, caption_y, caption_x + caption_width, caption_y + caption_height), radius=round(22 * scale), fill=(2, 8, 18, 218), outline=(*accent, 65), width=max(1, round(2 * scale)))
        draw.multiline_text((width // 2, caption_y + round(22 * scale)), wrapped_caption, font=caption_font, fill=(*text_color, 255), anchor="ma", align="center", spacing=round(9 * scale))

    label = f"{index + 1:02d}  /  {total:02d}"
    draw.text((width - margin, round(105 * scale)), label, font=kicker_font, fill=(*muted, 145), anchor="ra")
    progress_width = round((width - 2 * margin) * ((index + progress) / total))
    draw.rounded_rectangle((margin, height - round(58 * scale), width - margin, height - round(49 * scale)), radius=round(5 * scale), fill=(*muted, 28))
    draw.rounded_rectangle((margin, height - round(58 * scale), margin + progress_width, height - round(49 * scale)), radius=round(5 * scale), fill=(*accent, 210))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def caption_at(captions: list[tuple[float, float, str]], timestamp: float) -> str:
    for start, end, text in captions:
        if start <= timestamp < end:
            return text
    return ""


def render_video(
    data: dict[str, Any], storyboard: Path, output: Path, durations: list[float],
    narration_wav: Path | None, captions: list[tuple[float, float, str]], draft: bool,
) -> None:
    video = data["video"]
    width = int(video.get("width", 1080))
    height = int(video.get("height", 1920))
    fps = int(video.get("fps", 30))
    if draft:
        ratio = min(1.0, 540 / width)
        width = max(320, round(width * ratio / 2) * 2)
        height = max(320, round(height * ratio / 2) * 2)
        fps = min(fps, 15)

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
    ]
    audio_inputs = 0
    if narration_wav:
        command.extend(["-i", str(narration_wav)])
        audio_inputs += 1
    music = data.get("music", {})
    music_path = str(music.get("path", "")).strip()
    if music_path:
        command.extend(["-stream_loop", "-1", "-i", str(resolve_asset(storyboard.parent, music_path))])
        audio_inputs += 1

    command.extend(["-map", "0:v:0", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"])
    if narration_wav and music_path:
        music_index = 2
        volume = max(0.0, min(1.0, float(music.get("volume", 0.1))))
        ducking = bool(music.get("ducking", True))
        if ducking:
            audio_filter = (
                f"[1:a]aformat=sample_rates=22050:channel_layouts=mono,highpass=f=80,acompressor=threshold=0.1:ratio=2:attack=20:release=220:makeup=1.15,asplit=2[nsc][nmix];"
                f"[{music_index}:a]aformat=sample_rates=22050:channel_layouts=mono,volume={volume}[m];"
                "[m][nsc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=450[md];"
                "[nmix][md]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.89[a]"
            )
        else:
            audio_filter = (
                f"[1:a]volume=1[n];[{music_index}:a]volume={volume}[m];"
                "[n][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.89[a]"
            )
        command.extend([
            "-filter_complex", audio_filter,
            "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-shortest",
        ])
    elif narration_wav:
        command.extend(["-map", "1:a:0", "-filter:a", "highpass=f=80,acompressor=threshold=0.1:ratio=2:attack=20:release=220:makeup=1.15,alimiter=limit=0.89", "-c:a", "aac", "-b:a", "160k", "-shortest"])
    elif music_path:
        volume = max(0.0, min(1.0, float(music.get("volume", 0.1))))
        command.extend(["-map", "1:a:0", "-filter:a", f"volume={volume}", "-c:a", "aac", "-b:a", "160k", "-shortest"])
    else:
        command.append("-an")
    command.extend(["-movflags", "+faststart", str(output)])

    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    transition = 0.35
    scene_cursor = 0.0
    try:
        for scene_index, (scene, duration) in enumerate(zip(data["scenes"], durations)):
            frame_count = max(1, round(duration * fps))
            for local_frame in range(frame_count):
                progress = local_frame / max(1, frame_count - 1)
                absolute_time = scene_cursor + local_frame / fps
                frame = render_scene(
                    data, scene, progress, scene_index, len(data["scenes"]), storyboard.parent,
                    width, height, caption_at(captions, absolute_time),
                )
                transition_frames = round(transition * fps)
                if scene_index + 1 < len(data["scenes"]) and transition_frames and local_frame >= frame_count - transition_frames:
                    blend_progress = (local_frame - (frame_count - transition_frames)) / transition_frames
                    next_frame = render_scene(data, data["scenes"][scene_index + 1], 0.0, scene_index + 1, len(data["scenes"]), storyboard.parent, width, height, "")
                    from PIL import Image
                    frame = Image.blend(frame, next_frame, ease_out(blend_progress))
                assert process.stdin is not None
                process.stdin.write(frame.tobytes())
            scene_cursor += duration
        assert process.stdin is not None
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
    except Exception as exc:
        process.kill()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        process.wait()
        output.unlink(missing_ok=True)
        if stderr.strip():
            raise RuntimeError(f"{exc}\nFFmpeg: {stderr[-4000:]}") from exc
        raise
    if return_code:
        output.unlink(missing_ok=True)
        raise RuntimeError(stderr[-4000:] or f"ffmpeg exited with code {return_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="validate only; no third-party packages required")
    parser.add_argument("--draft", action="store_true", help="render at up to 540px wide and 15 fps")
    args = parser.parse_args()
    storyboard = args.storyboard.resolve()
    data = load_storyboard(storyboard)
    if args.check:
        print(json.dumps({"valid": True, "scenes": len(data["scenes"])}, ensure_ascii=False))
        return 0

    try:
        import PIL  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Missing dependency Pillow. Run bootstrap.ps1 first.") from exc

    output = (args.output or storyboard.parent / "output" / "video.mp4").resolve()
    with tempfile.TemporaryDirectory(prefix="local-video-studio-") as temp_value:
        temp = Path(temp_value)
        durations, narration_wav, captions = prepare_audio(data, storyboard, temp)
        write_srt(output.with_suffix(".srt"), captions)
        render_video(data, storyboard, output, durations, narration_wav, captions, args.draft)
    print(json.dumps({
        "output": str(output),
        "subtitles": str(output.with_suffix(".srt")),
        "duration": round(sum(durations), 3),
        "scenes": len(durations),
        "draft": args.draft,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
