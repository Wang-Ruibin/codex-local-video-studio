#!/usr/bin/env python3
"""Select a local Windows or Linux speech backend and synthesize a WAV file."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_checked(command: list[str], stdin_text: str | None = None) -> None:
    result = subprocess.run(command, input=stdin_text, capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message[-4000:] or f"Speech command exited with {result.returncode}")


def windows_sapi(text: str, output: Path, settings: dict[str, Any], temp: Path) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("Windows SAPI requires powershell.exe or pwsh")
    text_file = temp / f"{output.stem}.txt"
    text_file.write_text(text, encoding="utf-8")
    script = Path(__file__).with_name("synthesize_windows.ps1")
    voice = str(settings.get("voice_windows", settings.get("voice", ""))).strip()
    command = [
        powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-TextFile", str(text_file), "-OutputWav", str(output),
        "-Rate", str(int(settings.get("rate", 0))), "-Volume", str(int(settings.get("volume", 100))),
    ]
    if voice:
        command.extend(["-VoiceName", voice])
    run_checked(command)


def linux_piper(text: str, output: Path, settings: dict[str, Any]) -> None:
    executable = shutil.which(str(settings.get("piper_executable", "piper")))
    model = str(settings.get("piper_model", os.environ.get("PIPER_MODEL", ""))).strip()
    if not executable or not model:
        raise RuntimeError("Piper requires the piper executable and PIPER_MODEL or narration.piper_model")
    model_path = Path(model).expanduser().resolve()
    if not model_path.is_file():
        raise RuntimeError(f"Piper model not found: {model_path}")
    run_checked([executable, "--model", str(model_path), "--output_file", str(output)], stdin_text=text)


def linux_espeak(text: str, output: Path, settings: dict[str, Any]) -> None:
    executable = shutil.which("espeak-ng") or shutil.which("espeak")
    if not executable:
        raise RuntimeError("Linux narration requires Piper or espeak-ng/espeak; install one or supply scene audio")
    voice = str(settings.get("voice_linux", "zh")).strip() or "zh"
    rate_wpm = max(80, min(450, int(settings.get("rate_wpm", 185))))
    amplitude = max(0, min(200, int(float(settings.get("volume", 100)) * 2)))
    run_checked([executable, "-v", voice, "-s", str(rate_wpm), "-a", str(amplitude), "-w", str(output), text])


def synthesize_to_wav(text: str, output: Path, settings: dict[str, Any], temp: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    provider = str(settings.get("provider", "auto")).lower()
    system = platform.system()
    if provider == "auto":
        if system == "Windows":
            provider = "sapi"
        elif system == "Linux":
            provider = "piper" if shutil.which("piper") and (settings.get("piper_model") or os.environ.get("PIPER_MODEL")) else "espeak"
        else:
            raise RuntimeError(f"Unsupported narration platform: {system}")
    if provider == "sapi":
        if system != "Windows":
            raise RuntimeError("SAPI narration is only available on Windows")
        windows_sapi(text, output, settings, temp)
    elif provider == "piper":
        if system != "Linux":
            raise RuntimeError("This Piper adapter is currently supported on Linux")
        linux_piper(text, output, settings)
    elif provider in {"espeak", "espeak-ng"}:
        if system != "Linux":
            raise RuntimeError("eSpeak narration is only available on Linux")
        linux_espeak(text, output, settings)
        provider = "espeak"
    else:
        raise RuntimeError(f"Unsupported narration provider: {provider}")
    if not output.is_file() or output.stat().st_size <= 44:
        raise RuntimeError(f"Narration backend did not create a valid WAV: {output}")
    return provider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--voice-windows", default="Microsoft Huihui Desktop - Chinese (Simplified)")
    parser.add_argument("--voice-linux", default="zh")
    parser.add_argument("--rate", type=int, default=2)
    parser.add_argument("--rate-wpm", type=int, default=185)
    args = parser.parse_args()
    settings = vars(args)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="local-video-speech-") as temp_value:
        provider = synthesize_to_wav(args.text, args.output.resolve(), settings, Path(temp_value))
    print(provider)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
