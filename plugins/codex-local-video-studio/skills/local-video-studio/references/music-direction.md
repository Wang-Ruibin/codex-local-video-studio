# Automatic music direction

Choose one coherent instrumental bed for a short video. Base the decision on the verified subject, emotional posture, narration pace, visual density, and desired viewer response—not on isolated keywords alone.

## Mood routing

- `calm`: tutorials, health, reflective explainers, education, nature, and careful step-by-step material. Slow pulse, warm harmony, low percussion.
- `bright`: recommendations, launches, productivity, positive lists, success, and optimistic calls to action. Upbeat major harmony and clear rhythm.
- `tech`: AI, software, data, engineering, tools, futuristic products, and analytical demos. Precise electronic pulse and minor/modal color.
- `tense`: risk alerts, scams, cybersecurity incidents, market danger, and urgent warnings. Restrained low pulse; never turn tragedy into spectacle.
- `cinematic`: history, biographies, transformation stories, big ideas, and emotionally paced narratives. Broad pads and sparse impacts.
- `playful`: humor, games, light lifestyle content, cute subjects, and intentionally informal videos. Bouncy rhythm and short plucks.
- `neutral`: mixed or factual material with no dominant emotional direction. Subtle unobtrusive bed.

When multiple moods fit, select the one that best supports the video's intended response. Use `neutral` when emotional scoring could distort a factual claim.

## Energy and mix

- Match tempo to edit density: slower for long explanatory cards, faster for short list items and rapid transitions.
- Generated BGM must be instrumental. Do not synthesize speech-like or attention-grabbing lead sounds under narration.
- With narration, start around `music.volume: 0.08-0.10` and keep `ducking: true`. For videos without speech, start around `0.18`.
- In educational and science explainers, clarity beats atmosphere. Use a sparse bed or omit music for a dense mechanism passage if it adds cognitive load.
- Reduce music further for dense speech, sensitive subjects, quiet voices, or many consonant-heavy technical terms.
- Do not use a dramatic mood merely to make ordinary information feel more important.

## Rights and retention

Prefer `generate_bgm.py` because it produces the waveform locally from code and does not copy a commercial recording. If the user supplies a track, copy it into the marked work directory, record its provenance, and do not assume that possession grants publication rights. The generated or copied BGM is an intermediate artifact and is removed after it is mixed into the final MP4 unless the user explicitly asks to retain it.
