# ClipFinder v1.3.8.1 — Bug Fix Release

## 🐛 Bug Fixes

### Music Removal — Fixed ffmpeg merge failure
Music removal was failing with exit code `4294967294` on Windows when trying to merge the demucs output back with the original video. The issue was using an MP3 intermediate file for the audio stems — ffmpeg would reject MP3 encoding in certain audio configurations. Fixed by using WAV as the intermediate format (lossless, always accepted) and only encoding to AAC in the final video merge step.

Also added:
- Output folder auto-creation (`Segmented` folder now created if it doesn't exist)
- ffmpeg stderr logging on failure so errors are visible in the log instead of being swallowed silently

### Post Studio — Settings "+ Add Key" button fixed
The button to add extra API keys was showing a clipped unicode `＋` character that appeared as a broken line/dash. Replaced with a proper `+ Add Key` text button with correct sizing so it's always fully visible.

### Post Studio — Left panel width
Left panel width tuned so spice toggles (`🔥 Drama · 📰 Breaking · 🤯 Exaggerate · 🎣 Clickbait`) are split into two rows and never get clipped.

---

## What's in v1.3.8 (if you missed it)

- **Post Studio** — full social media post generator with algo score system
- **2026 algo rules** for X, TikTok, Instagram, YouTube Shorts built in
- **Algo Score System** — every post scored 1-10 with hover tooltip
- **Smart key rotation** — Groq primary, Gemini reserved for transcription
- **Duplicate download fix** — same-named clips get `(1)`, `(2)` suffixes
- **Pre-bundled installer** — torch, faster-whisper, demucs ship with installer
