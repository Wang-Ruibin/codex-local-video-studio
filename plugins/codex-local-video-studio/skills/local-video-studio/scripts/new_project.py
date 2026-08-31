#!/usr/bin/env python3
"""Create a local-video-studio project without overwriting existing work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MARKER = {"kind": "local-video-studio-workdir", "version": 1}
PARENT_MARKER = {"kind": "local-video-studio-parent", "version": 1}
PARENT_MARKER_NAME = ".local-video-studio-parent"


TEMPLATE = {
    "version": 1,
    "video": {
        "title": "为什么天空是蓝色的？",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "background": "#07111F",
    },
    "style": {
        "font": "auto",
        "text": "#F8FAFC",
        "muted": "#AFC0D4",
        "accent": "#57E3FF",
        "card": "#122A45",
        "background_alt": "#102743",
    },
    "narration": {
        "enabled": True,
        "provider": "auto",
        "voice_windows": "Microsoft Huihui Desktop - Chinese (Simplified)",
        "voice_linux": "zh",
        "rate": 2,
        "rate_wpm": 185,
        "volume": 100,
        "lead_in": 0.20,
        "lead_out": 0.30,
    },
    "music": {"path": "", "volume": 0.14, "ducking": True},
    "scenes": [
        {
            "id": "hook",
            "role": "hook",
            "duration": 3.5,
            "kicker": "一个日常谜题",
            "headline": "天空为什么是蓝色，\n而不是紫色？",
            "body": "答案藏在光与空气分子的碰撞里。",
            "narration": "天空为何蓝而不紫？答案藏在空气分子里。",
            "visual": "hero",
            "highlight": "?",
            "accent": "#58D8FF",
        },
        {
            "id": "context",
            "role": "question",
            "duration": 5.0,
            "kicker": "先看太阳光",
            "headline": "白光，其实是一整组颜色",
            "items": ["红光：波长更长", "蓝紫光：波长更短"],
            "narration": "太阳光看起来是白色，但它由不同波长的颜色组成。红光波长更长，蓝紫光波长更短。",
            "visual": "comparison",
            "accent": "#FFCC66",
        },
        {
            "id": "mechanism",
            "role": "mechanism",
            "duration": 7.0,
            "kicker": "瑞利散射",
            "headline": "短波长的光，\n更容易被散射",
            "items": ["太阳光进入大气", "撞上微小气体分子", "蓝光向各个方向散开"],
            "narration": "当太阳光进入大气，它会撞上远小于光波长的气体分子。这个过程对短波长更强，所以蓝光更容易向各个方向散开。",
            "visual": "diagram",
            "accent": "#57E3FF",
        },
        {
            "id": "evidence",
            "role": "evidence",
            "duration": 5.5,
            "kicker": "关键关系",
            "headline": "散射强度约与\n波长四次方成反比",
            "body": "图中数值用于说明趋势，不代表实测光谱。",
            "data": [
                {"label": "红", "value": 1.0},
                {"label": "黄", "value": 1.8},
                {"label": "绿", "value": 2.7},
                {"label": "蓝", "value": 5.5},
                {"label": "紫", "value": 8.0}
            ],
            "narration": "瑞利散射的强度大约与波长的四次方成反比。波长越短，散射增长得越快。",
            "visual": "chart",
            "accent": "#8B9CFF",
        },
        {
            "id": "implication",
            "role": "implication",
            "duration": 7.0,
            "kicker": "同一机制",
            "headline": "它也解释了\n红色日落",
            "items": ["正午：光程短，天空蓝", "日落：光程长，蓝光先被散走"],
            "narration": "同一个机制也解释了红色日落。太阳接近地平线时，光穿过更长的大气路径，蓝光先被散走，留下更多红橙光。",
            "visual": "comparison",
            "accent": "#FF8A5B",
        },
        {
            "id": "recap",
            "role": "recap",
            "duration": 5.0,
            "kicker": "三步记住",
            "headline": "蓝天，是短波光\n散射的结果",
            "items": ["白光进入大气", "短波蓝光散射更强", "我们从各方向看见蓝光"],
            "narration": "记住三步：白光进入大气，短波长的蓝光散射更强，我们因此从各个方向看见蓝色天空。",
            "visual": "recap",
            "accent": "#72F0C1",
        },
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    storyboard = project / "storyboard.json"
    if storyboard.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {storyboard}")

    (project / "assets").mkdir(parents=True, exist_ok=True)
    (project / "output").mkdir(parents=True, exist_ok=True)
    if project.parent.name == ".local-video-studio-work":
        parent_marker = project.parent / PARENT_MARKER_NAME
        if parent_marker.exists():
            try:
                existing = json.loads(parent_marker.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"Invalid managed parent marker: {exc}")
            if existing != PARENT_MARKER:
                raise SystemExit(f"Refusing unexpected managed parent marker: {parent_marker}")
        else:
            parent_marker.write_text(
                json.dumps(PARENT_MARKER, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    (project / ".local-video-studio-workdir").write_text(
        json.dumps(MARKER, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    storyboard.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project / "source.md").write_text(
        "# Source and provenance\n\n## Seed source\n\n- URL or original brief:\n- Author or publisher:\n- Publication date:\n- Access result:\n\n## Followed references\n\n- Record displayed, resolved, and canonical URLs plus why each matters.\n\n## Access notes\n\n- Record truncation, mirror use, unavailable media, paywalls, or unresolved links.\n\n## Claim map\n\n- Scene or claim -> supporting URL.\n\n## Factual digest\n\nReplace with a concise, evidence-backed digest before rendering.\n\n## Asset provenance\n\n- Record ownership, license, and reuse status for each external asset.\n",
        encoding="utf-8",
    )
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
