#!/usr/bin/env python3
"""Apply a deterministic quality gate to a science-explainer storyboard."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_ROLES = {"hook", "mechanism", "evidence", "recap"}
VALID_ROLES = REQUIRED_ROLES | {"question", "context", "implication", "example", "cta"}
VALID_VISUALS = {
    "hero", "diagram", "process", "comparison", "chart", "scale", "evidence", "recap",
    "rings", "bars", "timeline", "checklist", "quote", "image",
}
PLACEHOLDERS = ("replace with", "todo", "待补充", "placeholder", "示例内容")


def visible_units(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    return len(compact)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read storyboard: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Storyboard must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    storyboard = args.storyboard.resolve()
    data = load_json(storyboard)
    scenes = data.get("scenes", [])
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(scenes, list):
        scenes = []
        errors.append("scenes must be an array")

    if not 5 <= len(scenes) <= 12:
        errors.append("A shareable short explainer should contain 5-12 purposeful scenes")

    roles: list[str] = []
    visuals: list[str] = []
    total_duration = 0.0
    previous_visual = None
    repeated_visual_run = 0
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append(f"Scene {index + 1} is not an object")
            continue
        scene_id = str(scene.get("id", f"scene-{index + 1}"))
        role = str(scene.get("role", "")).strip()
        visual = str(scene.get("visual", "")).strip()
        headline = str(scene.get("headline", "")).strip()
        body = str(scene.get("body", "")).strip()
        narration = str(scene.get("narration", "")).strip()
        duration = float(scene.get("duration", 4.0))
        total_duration += duration
        roles.append(role)
        visuals.append(visual)

        if role not in VALID_ROLES:
            errors.append(f"Scene {scene_id} needs a valid narrative role")
        if visual not in VALID_VISUALS:
            errors.append(f"Scene {scene_id} needs a supported visual type")
        if not headline:
            errors.append(f"Scene {scene_id} has no headline")
        elif visible_units(headline) > 48:
            warnings.append(f"Scene {scene_id} headline is too dense")
        if not narration:
            errors.append(f"Scene {scene_id} has no narration")
        if visible_units(body) > 90:
            warnings.append(f"Scene {scene_id} body copy is too dense")
        if body and re.sub(r"\W", "", body.lower()) == re.sub(r"\W", "", narration.lower()):
            warnings.append(f"Scene {scene_id} duplicates narration as body text")
        items = scene.get("items", [])
        if isinstance(items, list):
            for item in items:
                if visible_units(str(item)) > 28:
                    warnings.append(f"Scene {scene_id} contains an overlong visual label")
                    break
        narration_units = visible_units(narration)
        if duration > 0 and narration_units / duration > 8.0:
            warnings.append(f"Scene {scene_id} narration is likely too dense for its minimum duration")
        if any(token in f"{headline} {body} {narration}".lower() for token in PLACEHOLDERS):
            errors.append(f"Scene {scene_id} still contains placeholder content")
        if visual == "chart" and not scene.get("data"):
            errors.append(f"Scene {scene_id} uses chart without data")

        if visual == previous_visual:
            repeated_visual_run += 1
            if repeated_visual_run >= 2:
                warnings.append(f"Visual type {visual} repeats for three consecutive scenes")
        else:
            repeated_visual_run = 0
            previous_visual = visual

    missing_roles = sorted(REQUIRED_ROLES - set(roles))
    if missing_roles:
        errors.append(f"Missing narrative roles: {', '.join(missing_roles)}")
    if roles and roles[0] != "hook":
        errors.append("The first scene must be the hook")
    if scenes and float(scenes[0].get("duration", 4.0)) > 4.5:
        warnings.append("The hook should resolve its first promise within 4.5 seconds")
    if roles and roles[-1] not in {"recap", "implication", "cta"}:
        errors.append("The final scene must deliver a recap, implication, or call to action")
    if len(set(visuals)) < 3:
        errors.append("Use at least three distinct visual explanation types")
    if not 20 <= total_duration <= 120:
        warnings.append("Total minimum duration is outside the usual 20-120 second explainer range")

    source_path = args.source.resolve()
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"Cannot read source record: {exc}")
    else:
        if not re.search(r"https?://", source_text):
            errors.append("Source record contains no verifiable URL")
        claim_section = re.search(r"## Claim map\s*(.*?)(?:\n## |\Z)", source_text, re.S | re.I)
        if not claim_section or not re.search(r"https?://", claim_section.group(1)):
            errors.append("Claim map does not connect video claims to URLs")
        if any(token in source_text.lower() for token in PLACEHOLDERS):
            errors.append("Source record still contains placeholders")

    score = max(0, 100 - 18 * len(errors) - 4 * len(warnings))
    valid = not errors and score >= 80
    report = {
        "valid": valid,
        "score": score,
        "storyboard": str(storyboard),
        "storyboard_sha256": hashlib.sha256(storyboard.read_bytes()).hexdigest(),
        "scene_count": len(scenes),
        "minimum_duration": round(total_duration, 3),
        "roles": roles,
        "visuals": dict(Counter(visuals)),
        "errors": errors,
        "warnings": warnings,
    }
    report_path = (args.report or storyboard.parent / "output" / "storyboard-quality.json").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), **report}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
