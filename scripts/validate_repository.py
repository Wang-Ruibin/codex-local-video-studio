#!/usr/bin/env python3
"""Validate repository structure without depending on Codex-internal packages."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "codex-local-video-studio"
PLUGIN = ROOT / "plugins" / PLUGIN_NAME


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def heading_levels(path: Path) -> list[int]:
    return [len(match.group(1)) for line in path.read_text(encoding="utf-8").splitlines() if (match := re.match(r"^(#{1,6})\s+", line))]


def main() -> int:
    manifest_path = PLUGIN / ".codex-plugin" / "plugin.json"
    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    require(manifest["name"] == PLUGIN_NAME, "Plugin name must match its folder")
    require(re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]) is not None, "Version must be strict semver")
    require(manifest.get("author", {}).get("name") == "Wang-Ruibin", "Author attribution is incorrect")
    require(manifest.get("interface", {}).get("developerName") == "misakimei0331", "Developer display name is incorrect")
    require(manifest.get("skills") == "./skills/", "Skill discovery path is incorrect")
    prompts = manifest.get("interface", {}).get("defaultPrompt", [])
    require(isinstance(prompts, list) and 1 <= len(prompts) <= 3, "defaultPrompt must contain 1-3 prompts")
    require(all(len(prompt) <= 128 for prompt in prompts), "A default prompt exceeds 128 characters")

    require(marketplace.get("name") == PLUGIN_NAME, "Marketplace name is incorrect")
    entries = marketplace.get("plugins", [])
    require(len(entries) == 1 and entries[0]["name"] == PLUGIN_NAME, "Marketplace must expose one matching plugin")
    require(entries[0]["source"]["path"] == f"./plugins/{PLUGIN_NAME}", "Marketplace source path is incorrect")
    require(PLUGIN.is_dir(), "Marketplace plugin path does not exist")

    skill = PLUGIN / "skills" / "local-video-studio" / "SKILL.md"
    skill_text = skill.read_text(encoding="utf-8")
    require(skill_text.startswith("---\n"), "Skill frontmatter is missing")
    require(re.search(r"^name:\s*local-video-studio\s*$", skill_text, re.M) is not None, "Skill name is incorrect")
    require(re.search(r"^description:\s*.+$", skill_text, re.M) is not None, "Skill description is missing")

    all_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)
    placeholder = "[" + "TODO:"
    require(placeholder not in all_text, "Unfinished TODO placeholder found")
    require("Copyright (c) 2026 Wang-Ruibin" in (ROOT / "LICENSE").read_text(encoding="utf-8"), "License attribution is incorrect")

    english = ROOT / "README.md"
    chinese = ROOT / "README.zh-CN.md"
    require(chinese.name in english.read_text(encoding="utf-8"), "English README does not link Chinese README")
    require(english.name in chinese.read_text(encoding="utf-8"), "Chinese README does not link English README")
    require(heading_levels(english) == heading_levels(chinese), "README heading levels are not structurally paired")

    python_files = list(ROOT.rglob("*.py"))
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    print(json.dumps({
        "valid": True,
        "plugin": str(PLUGIN.relative_to(ROOT)),
        "python_files": len(python_files),
        "readme_headings": len(heading_levels(english)),
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, json.JSONDecodeError, SyntaxError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        raise SystemExit(1)
