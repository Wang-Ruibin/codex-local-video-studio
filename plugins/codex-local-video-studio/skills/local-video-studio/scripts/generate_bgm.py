#!/usr/bin/env python3
"""Generate a deterministic, royalty-unencumbered procedural BGM WAV."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TAU = math.tau
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)


@dataclass(frozen=True)
class Mood:
    bpm: int
    key_midi: int
    scale: tuple[int, ...]
    progression: tuple[int, ...]
    pad: float
    bass: float
    arp: float
    drums: float
    arp_division: int


MOODS: dict[str, Mood] = {
    "calm": Mood(72, 60, MAJOR, (0, 5, 3, 4), 0.19, 0.08, 0.055, 0.025, 2),
    "bright": Mood(108, 60, MAJOR, (0, 4, 5, 3), 0.13, 0.11, 0.12, 0.085, 2),
    "tech": Mood(112, 62, MINOR, (0, 5, 2, 6), 0.12, 0.13, 0.13, 0.075, 4),
    "tense": Mood(92, 62, MINOR, (0, 1, 5, 4), 0.15, 0.14, 0.065, 0.055, 2),
    "cinematic": Mood(78, 62, MINOR, (0, 5, 3, 6), 0.21, 0.12, 0.045, 0.045, 2),
    "playful": Mood(118, 67, MAJOR, (0, 3, 4, 0), 0.10, 0.10, 0.15, 0.09, 2),
    "neutral": Mood(92, 60, MAJOR, (0, 3, 5, 4), 0.16, 0.09, 0.075, 0.04, 2),
}

KEYWORDS: dict[str, tuple[str, ...]] = {
    "tense": ("risk", "warning", "danger", "threat", "crash", "fraud", "attack", "风险", "警告", "危机", "骗局", "暴跌", "攻击", "威胁"),
    "playful": ("funny", "cute", "game", "humor", "playful", "搞笑", "可爱", "游戏", "幽默", "轻松"),
    "tech": (" ai ", "code", "software", "github", "robot", "data", "api", "人工智能", "编程", "代码", "软件", "工具", "数据", "机器人", "技术"),
    "cinematic": ("story", "history", "journey", "future", "dream", "人物", "故事", "历史", "旅程", "未来", "变革", "梦想"),
    "calm": ("health", "learning", "guide", "nature", "sleep", "教程", "科普", "学习", "健康", "睡眠", "冥想", "自然"),
    "bright": ("launch", "success", "tips", "growth", "productivity", "发布", "成功", "榜单", "技巧", "效率", "增长", "推荐"),
}


def load_storyboard(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read storyboard: {exc}") from exc
    if not isinstance(value.get("scenes"), list) or not value["scenes"]:
        raise RuntimeError("Storyboard must contain scenes")
    return value


def choose_mood(data: dict[str, Any]) -> str:
    text = " " + json.dumps(data, ensure_ascii=False).lower() + " "
    scores = {mood: sum(text.count(keyword) for keyword in words) for mood, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"


def midi_frequency(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def scale_note(config: Mood, degree: int, octave: int = 0) -> int:
    scale_length = len(config.scale)
    scale_octave, index = divmod(degree, scale_length)
    return config.key_midi + config.scale[index] + 12 * (scale_octave + octave)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def synthesize(path: Path, mood_name: str, duration: float, seed: int, sample_rate: int) -> None:
    config = MOODS[mood_name]
    total_samples = round(duration * sample_rate)
    beat_seconds = 60.0 / config.bpm
    bar_seconds = beat_seconds * 4.0
    arp_seconds = beat_seconds / config.arp_division
    fade_seconds = min(1.2, duration / 5.0)
    state = (seed & 0x7FFFFFFF) or 1
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        buffer = array("h")

        for sample_index in range(total_samples):
            t = sample_index / sample_rate
            bar_index = int(t / bar_seconds)
            bar_phase = t - bar_index * bar_seconds
            degree = config.progression[bar_index % len(config.progression)]
            chord_notes = (
                scale_note(config, degree, 0),
                scale_note(config, degree + 2, 0),
                scale_note(config, degree + 4, 0),
            )

            pad_envelope = clamp(bar_phase / 0.45) * clamp((bar_seconds - bar_phase) / 0.55)
            pad_value = 0.0
            for note in chord_notes:
                frequency = midi_frequency(note)
                pad_value += math.sin(TAU * frequency * t) + 0.16 * math.sin(TAU * frequency * 2.0 * t)
            pad_value *= config.pad * pad_envelope / 3.48

            beat_phase = t % beat_seconds
            bass_note = scale_note(config, degree, -1)
            bass_envelope = 0.55 + 0.45 * math.exp(-3.5 * beat_phase / beat_seconds)
            bass_value = config.bass * bass_envelope * math.sin(TAU * midi_frequency(bass_note) * t)

            arp_index = int(t / arp_seconds)
            arp_phase = (t % arp_seconds) / arp_seconds
            arp_note = chord_notes[(arp_index + seed) % len(chord_notes)] + 12
            arp_envelope = math.exp(-5.2 * arp_phase)
            arp_frequency = midi_frequency(arp_note)
            arp_value = config.arp * arp_envelope * (
                math.sin(TAU * arp_frequency * t) + 0.22 * math.sin(TAU * arp_frequency * 2.0 * t)
            )

            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            noise = state / 1073741824.0 - 1.0
            kick_phase = beat_phase
            kick = 0.0
            if kick_phase < 0.22:
                kick_envelope = math.exp(-22.0 * kick_phase)
                kick_frequency = 52.0 + 58.0 * math.exp(-28.0 * kick_phase)
                kick = math.sin(TAU * kick_frequency * t) * kick_envelope
            beat_number = int(t / beat_seconds) % 4
            snare = noise * math.exp(-30.0 * beat_phase) if beat_number in (1, 3) and beat_phase < 0.16 else 0.0
            half_beat_phase = t % (beat_seconds / 2.0)
            hat = noise * math.exp(-75.0 * half_beat_phase) if half_beat_phase < 0.07 else 0.0
            drum_value = config.drums * (0.72 * kick + 0.34 * snare + 0.13 * hat)

            pulse = 1.0 - 0.16 * math.exp(-8.0 * beat_phase / beat_seconds)
            value = (pad_value + bass_value + arp_value) * pulse + drum_value
            fade = clamp(t / fade_seconds) * clamp((duration - t) / fade_seconds)
            value = math.tanh(value * 1.28) * fade
            buffer.append(round(clamp(value, -0.92, 0.92) * 32767))

            if len(buffer) >= 8192:
                if sys.byteorder == "big":
                    buffer.byteswap()
                writer.writeframes(buffer.tobytes())
                buffer = array("h")

        if buffer:
            if sys.byteorder == "big":
                buffer.byteswap()
            writer.writeframes(buffer.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storyboard", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mood", choices=("auto", *MOODS.keys()), default="auto")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--volume", type=float)
    parser.add_argument("--update-storyboard", action="store_true")
    args = parser.parse_args()

    storyboard = args.storyboard.resolve()
    output = args.output.resolve()
    data = load_storyboard(storyboard)
    mood_name = choose_mood(data) if args.mood == "auto" else args.mood
    minimum_duration = sum(float(scene.get("duration", 4.0)) for scene in data["scenes"])
    duration = args.duration if args.duration is not None else max(15.0, minimum_duration * 1.3 + 8.0)
    if not 1.0 <= duration <= 900.0:
        raise RuntimeError("BGM duration must be between 1 and 900 seconds")
    if not 8000 <= args.sample_rate <= 48000:
        raise RuntimeError("Sample rate must be between 8000 and 48000 Hz")
    seed_text = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    seed = args.seed if args.seed is not None else int.from_bytes(hashlib.sha256(seed_text).digest()[:4], "big")

    synthesize(output, mood_name, duration, seed, args.sample_rate)
    narration_present = any(scene.get("narration") or scene.get("audio") for scene in data["scenes"])
    volume = args.volume if args.volume is not None else (0.10 if narration_present else 0.18)
    volume = clamp(volume, 0.0, 1.0)

    if args.update_storyboard:
        relative = os.path.relpath(output, storyboard.parent).replace("\\", "/")
        data["music"] = {
            "path": relative,
            "volume": round(volume, 3),
            "ducking": narration_present,
            "mood": mood_name,
            "generated": True,
        }
        storyboard.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "output": str(output),
        "mood": mood_name,
        "bpm": MOODS[mood_name].bpm,
        "duration": round(duration, 3),
        "seed": seed,
        "volume": round(volume, 3),
        "ducking": narration_present,
        "storyboard_updated": args.update_storyboard,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
