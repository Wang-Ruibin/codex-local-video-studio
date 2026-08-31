# Windows and Linux setup

The workflow shares one storyboard, renderer, BGM generator, quality gate, and finalizer across platforms. Only path resolution, runtime location, and speech synthesis differ.

## Common configuration

- `LOCAL_VIDEO_STUDIO_ROOT`: absolute directory for temporary jobs and final MP4 files.
- `LOCAL_VIDEO_STUDIO_CACHE`: optional absolute directory for the shared Python virtual environment and cached FFmpeg binary.
- Without an output override, the default is `~/Videos/local-video-studio`.

Create the shared runtime with:

```shell
python scripts/bootstrap.py
```

Use `python3` instead of `python` when that is the system command on Linux. Resolve the runtime interpreter with:

```shell
python scripts/runtime_paths.py --runtime-python
```

## Windows

Example PowerShell configuration:

```powershell
$env:LOCAL_VIDEO_STUDIO_ROOT = "D:\video"
python scripts/bootstrap.py
```

Provider `auto` uses Windows SAPI. The default Simplified Chinese voice is `Microsoft Huihui Desktop - Chinese (Simplified)`. Configure another installed voice with `narration.voice_windows`.

Codex sandboxes may block SAPI COM access. When synthesis returns access-denied or an invalid-registry error inside the sandbox but installed voices are visible, rerun only the render command with narrow approval outside the sandbox.

## Linux

Example Bash configuration:

```bash
export LOCAL_VIDEO_STUDIO_ROOT="$HOME/Videos/local-video-studio"
python3 scripts/bootstrap.py
```

Provider `auto` prefers Piper when both a `piper` executable and `PIPER_MODEL` are available; otherwise it uses `espeak-ng` or `espeak`.

For the baseline backend, install eSpeak with the distribution package manager, for example:

```bash
sudo apt-get install espeak-ng
```

Set `narration.voice_linux` to an installed eSpeak voice such as `zh` or `en`. Set `narration.rate_wpm` to control speed.

For higher-quality offline speech, install Piper separately, select a voice model whose license fits the intended publication, and export its absolute path:

```bash
export PIPER_MODEL="$HOME/.local/share/piper/voice.onnx"
```

The plugin does not download a voice model automatically because model and training-data licenses vary. A scene-level `audio` file remains the most predictable option for a specific human or studio voice.
