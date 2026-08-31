# Storyboard schema

`storyboard.json` is UTF-8 JSON. Paths are relative to the storyboard file unless absolute.

## Top-level fields

- `version`: must be `1`.
- `video`: `title`, `width`, `height`, `fps`, and `background`. Recommended delivery settings are 1080x1920 at 30 fps for vertical short-form and 1920x1080 at 30 fps for landscape.
- `style`: `font` (`auto`, a relative path, or an absolute font path), `text`, `muted`, `accent`, and `card`. Colors use CSS hex notation.
- `narration`: `enabled`, `provider` (`auto`, `sapi`, `piper`, or `espeak`), `voice_windows`, `voice_linux`, Windows `rate` from -10 to 10, Linux `rate_wpm`, `volume` from 0 to 100, plus `lead_in` and `lead_out` seconds. Linux Piper may use `piper_model` or `PIPER_MODEL`. When narration is disabled, scene `audio` files still play.
- `music`: local `path`, a `volume` multiplier normally 0.10-0.18 under speech, and `ducking` (default `true` when narration exists). Generated tracks may also record `mood` and `generated`; these are provenance hints and do not affect rendering.
- `scenes`: ordered scene objects. At least one is required.

## Scene fields

- `id`: stable, unique identifier.
- `role`: one of `hook`, `question`, `context`, `mechanism`, `evidence`, `example`, `implication`, `recap`, or `cta`. A high-quality explainer normally includes at least `hook`, `mechanism`, `evidence`, and `recap`.
- `duration`: minimum seconds, from 0.5 to 60. The renderer extends it if audio needs more time.
- `kicker`: short category label.
- `headline`: primary on-screen claim. `\n` forces a line break.
- `body`: brief supporting context, not a transcript of narration.
- `items`: up to five short list items.
- `narration`: spoken and captioned text for offline TTS.
- `audio`: optional user-supplied narration file. It replaces TTS for that scene.
- `background_image`: optional local PNG, JPEG, or WebP. The renderer crop-fills it and applies a dark readability overlay.
- `visual`: one of `hero`, `diagram`, `process`, `comparison`, `chart`, `scale`, `evidence`, `recap`, `rings`, `bars`, `timeline`, `checklist`, `quote`, or `image`.
- `data`: chart points such as `[{"label": "蓝", "value": 5.5}]`. State in `body` when values are illustrative rather than measured.
- `highlight`: short central symbol or value for a `hero` scene.
- `source_label`: compact human-readable source label for an `evidence` scene; keep the full URL in `source.md`.
- `accent`: optional scene-specific hex color.

Unknown fields are ignored so provenance or editorial notes can coexist with render fields.

## Editorial sizing

- Keep `kicker` under 24 characters, headlines under roughly 42 Chinese characters or 12 English words, and body text under 90 Chinese characters or 25 English words.
- Split dense explanations across scenes instead of shrinking type.
- Use `items` for parallel points, not paragraphs.
- Put exact citations and long URLs in `source.md`, not in the frame.
- Spoken text usually needs about 3-4 Chinese characters or 2-3 English words per second with the default voice. Captions are split automatically into short phrases timed across the scene narration.

## Example scene

```json
{
  "id": "proof",
  "duration": 5.5,
  "kicker": "WHY IT WORKS",
  "headline": "每一帧都可重复生成",
  "body": "同一份分镜可以修改、审阅和批量渲染。",
  "narration": "因为画面由代码生成，所以每一帧都可以重复渲染和审阅。",
  "visual": "timeline",
  "accent": "#57E3FF"
}
```
