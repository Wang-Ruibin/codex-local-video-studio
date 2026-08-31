---
name: local-video-studio
description: Create complete code-driven videos locally on Windows or Linux from a topic, document, post, or storyboard, including research, scripting, editable motion graphics, automatic procedural BGM, offline narration, subtitles, MP4 rendering, and media QC. Use for explainers, product updates, list videos, quote videos, data stories, and other typography- or asset-led videos. Do not route requests whose essential result requires photorealistic text-to-video, avatar lip-sync, or fabricated live-action footage.
---

# Local Video Studio

Produce a checked MP4 without requiring the user to create a project, run commands, open a video-generation website or editor GUI, or provide an account or API key. Use an internal temporary working folder and remove it automatically after successful delivery so the final MP4 is the only retained artifact by default. The deterministic renderer uses Python, Pillow, a locally cached FFmpeg binary, procedural audio, and an offline narration backend. Perform the whole workflow after an ordinary natural-language request; expose implementation choices only when they affect the result.

Resolve every `scripts/` and `references/` path relative to the directory containing this `SKILL.md`, regardless of the current working directory.

## Choose the production mode

- Use the standard code-driven mode for source-to-video, explainers, product demos made from screenshots, animated cards, lists, quotes, charts, and recurring formats.
- Use user-supplied images and audio when realism or a specific identity matters. Keep those files inside the project `assets/` folder and reference them with relative paths.
- Treat image generation as an optional enhancement. A video must remain producible with typography, shapes, charts, screenshots, and supplied assets if image generation is unavailable.
- Stop and explain the boundary when the request fundamentally needs realistic generated motion, exact lip-sync, or a synthetic actor. Do not silently substitute a remote generation service.

## Build the video

1. Acquire and verify the content before scripting:
   - For a supplied link, open the page and inspect its text and visible media. If direct access fails, search the exact URL, post ID, title, or distinctive phrases and record that a secondary copy was used.
   - Treat relevant outbound links as part of the source, not as optional footnotes. Expand short links and tracking redirects, read the canonical landing page, then follow its essential citations when they materially support the video. For posts, articles, PDFs, or pages with outbound references, read [references/source-research.md](references/source-research.md) before research.
   - For a topic, search current primary or authoritative sources. Cross-check consequential or time-sensitive claims and retain source URLs in `source.md`.
   - Distinguish sourced facts from interpretation. Never make a source appear to say something it does not.
2. Infer the intended audience, platform, aspect ratio, duration, language, and call to action from available context. Make reasonable defaults when they do not materially change the result: 9:16, 1080x1920, 30 fps, 30-60 seconds, and the source language. Ask only when a missing choice would materially change the video.
3. Choose paths automatically:
   - Read [references/platform-setup.md](references/platform-setup.md) when configuring or troubleshooting a platform.
   - Resolve `<video-root>` with `python <skill-root>/scripts/runtime_paths.py --video-root`. `LOCAL_VIDEO_STUDIO_ROOT` overrides the default on both Windows and Linux.
   - Use `<video-root>/.local-video-studio-work/<short-slug>-<timestamp>/` as the internal working folder.
   - Honor an explicitly requested final path only when it remains under `<video-root>`; otherwise use `<video-root>/<short-slug>-<timestamp>.mp4`.
   - Create the temporary folder with `python <skill-root>/scripts/new_project.py <work-dir>`. This adds the marker required for safe cleanup. Never initialize over an existing `storyboard.json`, and never ask the user to perform this setup.
4. Write `source.md` with the seed source, resolved outbound links, source hierarchy, access notes, a claim-to-source map, concise factual digest, and asset provenance. Preserve uncertainty; do not invent quotes, metrics, or claims.
5. Rewrite `storyboard.json` as a sequence of purposeful scenes. Give the first scene a concrete hook, make one claim per scene, keep important text inside safe margins, and end with a clear payoff or call to action. Read [references/storyboard-schema.md](references/storyboard-schema.md) when authoring or debugging the manifest.
   - For science, technology, history, health, and other explanatory topics, also read [references/science-explainer-quality.md](references/science-explainer-quality.md) and assign each scene a narrative `role`.
   - Build a causal visual explanation rather than a sequence of text cards. Use at least three genuinely different visual modes and keep on-screen words complementary to narration.
6. Put licensed or user-provided assets under `assets/`. Never hotlink remote media in a deliverable. Record attribution in `source.md` when required. Use code-native diagrams and charts for mechanisms and evidence. Use the built-in image generation capability only when one or two original concept illustrations materially improve spatial understanding or atmosphere; keep their art direction consistent and do not use generated images as factual evidence.
7. Ensure the shared local runtime exists with `python <skill-root>/scripts/bootstrap.py`, then resolve `<runtime-python>` with `python <skill-root>/scripts/runtime_paths.py --runtime-python`. Request any required network or install authorization at execution time; do not turn dependency setup into user instructions. Narration provider `auto` selects Windows SAPI on Windows and Piper or eSpeak on Linux. In the Codex Windows sandbox, SAPI may require narrow escalation because the sandbox blocks speech COM access; treat an access error as a boundary issue, not as a missing voice.
8. Add BGM automatically unless the user explicitly requests silence:
   - Read [references/music-direction.md](references/music-direction.md), infer the video's overall mood and energy from the verified content and storyboard, and do not ask the user to choose a genre when a reasonable choice is available.
   - Prefer a user-supplied, reusable local track only when its rights and provenance are clear. Otherwise generate an original local instrumental bed and update the storyboard:

     ```shell
     <runtime-python> <skill-root>/scripts/generate_bgm.py --storyboard <work-dir>/storyboard.json --output <work-dir>/assets/bgm.wav --mood <selected-mood> --update-storyboard
     ```

   - Use `--mood auto` only as a fallback; semantic judgment should select among `calm`, `bright`, `tech`, `tense`, `cinematic`, `playful`, and `neutral`.
9. Run the editorial quality gate after BGM updates the storyboard:

   ```shell
   <runtime-python> <skill-root>/scripts/review_storyboard.py <work-dir>/storyboard.json --source <work-dir>/source.md --report <work-dir>/output/storyboard-quality.json
   ```

   Revise until `valid` is true and `score` is at least 80. Do not bypass missing narrative roles, insufficient visual diversity, placeholder sources, unsupported charts, or excessive on-screen text.
10. Validate before rendering:

   ```shell
   <runtime-python> <skill-root>/scripts/render_video.py <work-dir>/storyboard.json --check
   ```

11. Render a draft first. Generate a contact sheet, inspect every scene, and revise layout, visual variety, contrast, pacing, caption density, and factual alignment before final rendering. Do not approve a draft that is merely technically valid.
12. Render the final MP4 and SRT. Generated or supplied BGM is mixed automatically, and the default sidechain ducking lowers it while narration is present:

   ```shell
   <runtime-python> <skill-root>/scripts/render_video.py <work-dir>/storyboard.json --output <work-dir>/output/video.mp4
   ```

13. Run structural and perceptual checks:

   ```shell
   <runtime-python> <skill-root>/scripts/inspect_video.py <work-dir>/output/video.mp4 --report <work-dir>/output/qc.json --contact-sheet <work-dir>/output/contact-sheet.png
   ```

14. Read `qc.json` and inspect `contact-sheet.png` visually. Fix clipped text, weak contrast, unsafe margins, accidental black frames, excessive silence, timing problems, misleading visuals; then rerender and recheck. Confirm that speech remains intelligible and BGM supports rather than competes with the message. Verify that the draft-to-final changes addressed observed problems. A successful encode alone is not completion.
15. After QC is valid with no unresolved warnings, finalize and purge the temporary folder:

   ```shell
   <runtime-python> <skill-root>/scripts/finalize_video.py --work-dir <work-dir> --video <work-dir>/output/video.mp4 --qc-report <work-dir>/output/qc.json --quality-report <work-dir>/output/storyboard-quality.json --destination <final-video-path>
   ```

   The finalizer first copies the MP4 to a temporary sibling of the destination, atomically installs it, verifies the work-directory marker and QC binding, and only then deletes the marked working folder. If finalization fails, keep the working folder until the problem is fixed; do not report cleanup as complete.

## Production rules

- Retain only the final MP4 by default. Delete the internal storyboard, source record, downloaded or generated asset copies, scene audio, SRT, QC JSON, contact sheet, and render scratch files after successful finalization.
- If the user explicitly requests subtitles, editable sources, a provenance report, or other sidecars, retain only those requested artifacts alongside the MP4. Do not ask whether to keep them when the user did not request them.
- Never move or delete the user's original source files. Copy required inputs into the marked temporary folder and only purge those copies.
- Never recursively clean an unmarked directory or substitute a broader parent directory for `<work-dir>`. Use `finalize_video.py`; do not improvise deletion commands.
- Keep every intermediate and retained video artifact under the resolved `<video-root>`. Never put render artifacts in the current code workspace.
- Match narration to visible claims. If offline TTS pronunciation is poor, rewrite for speech or use user-supplied scene audio; do not hide the defect under music.
- Prefer 5-12 scenes for short-form videos. Avoid rapid cuts that make a card unreadable.
- Default to restrained motion, a clear type hierarchy, and phrase-level captions. Use animation to reveal causal structure and direct attention, not as decoration.
- Never display the full narration as persistent body copy. Headlines, labels, arrows, highlights, and charts should carry the visual channel while narration carries the verbal explanation.
- Use `duration` as a minimum. With narration enabled, the renderer extends a scene to fit its spoken audio.
- Add locally generated instrumental BGM by default and keep it subordinate to narration. Do not download an arbitrary copyrighted track. Skip BGM only when the user requests silence or the content clearly requires unscored raw audio.
- Preserve the requested factual meaning when adapting source material. Clearly label dramatization, estimates, and illustrative data.
- Do not publish or upload unless the user explicitly asks; delivery ends with local artifacts by default.

## Handoff

Report the final MP4 path, actual duration and dimensions captured before cleanup, storyboard quality score, narration mode, and whether temporary artifacts were removed. Do not mention paths that were deleted. Keep setup details out of the handoff unless something failed. State explicitly when the output is motion graphics rather than generative live-action.
