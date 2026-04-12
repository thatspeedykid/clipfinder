# ClipFinder Changelog

---

## v1.3.2 — Current Release
*April 2026*

### 🐛 Censor Tab Fixed
- **`WhisperModelC` typo fixed** — the class is `WhisperModel`, the `C` on the end doesn't exist. This caused an `AttributeError` immediately, fell back to whisper.cpp which has no word timestamps, resulting in out-of-sync or missing censoring
- **`_FWC` undefined variable fixed** — even if the import hadn't crashed, `_fwc = _FWC(...)` would have thrown `NameError` since the variable was named `_FW` on the line above
- **GPU device detection added to Censor** — was hardcoded to CPU even on AMD/NVIDIA/Intel GPUs. Now calls `_detect_whisper_device()` same as the main transcription path
- **Better fallback logging** — now clearly logs which fallback path was taken so issues are easier to diagnose

### 🖼️ Pexels & Pixabay API Keys Added
- Two new thumbnail search providers added to Settings → AI Provider API Keys
- Pexels and Pixabay keys integrate with the Thumbnail Finder tab for more image sources
- Image API keys correctly have no ＋ multi-key button (only AI providers need key rotation)

### 🎨 Settings UI Alignment Fixed (Again, Properly)
- Extra key rows (↳ Key 2, ↳ Key 3) now match primary row width exactly
- Right side of extra rows mirrors primary rows: blank spacer where "Get key →" is, blank label where hint text is, ✕ where ＋ is
- No more extra rows stretching wider than primary rows

---

## v1.3.1
*April 2026*

### 🔑 Smart Key Rotation & Rate Limit Overhaul
- Keys shuffled randomly every run — no more always hammering Key 1 first
- Per-key cooldown timestamps — rate-limited keys skipped until 62s reset window passes
- Gemini model splitting — multiple keys assigned different model versions (1.5-flash / 2.0-flash) with separate RPM buckets
- Smart retry waits — calculates minimum time until next key resets instead of hardcoded 30/60/90s delays

### 📤📥 Encrypted Key Export / Import
- Export All Keys and Import All Keys buttons in the AI Provider API Keys section header
- Password-encrypted `.cfkeys` file — portable between installs, safe to back up
- Import automatically applies all keys including extras and refreshes the UI

### 🐛 Bug Fixes
- OpenRouter `NoneType` crash fixed — empty choices list no longer kills the run
- OpenRouter dead model list auto-resets when all models marked unavailable
- Settings key row alignment rebuilt using character-unit Label widths

---

## v1.3
*April 2026*

### Major Features
- **AI Music Removal tab** — Demucs stem separation, fully local, no API needed
- **Segment-aware clip accuracy** — verification pass using actual transcript text
- **Multi-key support per provider** — Key 2, Key 3 via ＋ button in Settings
- **Key rotation in `_call_provider`** — tries all keys before marking provider as RL
- **OpenRouter model rotation** — skips 404 dead models per session
- **Rate limit overhaul** — sequential task dispatch, global RL tracking, provider fallback
- **Names field** — shared between Normal and Interview mode
- **Progress bar for all operations**

### Fixes & Polish
- Censor queue fixed — correctly unpacks `(vid, out, clips)` tuple
- Groq 413 fix — prompts >20k chars truncated before sending
- Better download quality — VP9 preferred, `merge_output_format=mp4`
- Auto Edit uses GPU encoder
- Censor timing — 0.15s pre-roll for exact hits
- Cancel works everywhere including retry sleep
- Gemini 1.5 Flash set as default (1,500 RPD vs 20 RPD for 2.5 Flash)

---

## v1.2
*March 2026*

- **Auto Edit sub-tab** — silence removal with word-boundary cuts, GPU encoder
- **VOD Mode** — 8x concurrent fragment downloads, saves to `vod/` subfolder
- **Smart Auto Whisper** — picks model by video duration + GPU availability
- **Floating log panel** — Toplevel window, 500 message buffer
- **2-column clip grid** — wider cards, more readable layout
- **Smart file naming** — standardized across all export types
- **Kick API naming** — correct streamer/title from Kick API v2
- **AI response fence stripping** — removes backtick wrappers from any provider

---

## v1.1
*February 2026*

- **Hybrid clip detection** — FFmpeg audio energy peaks + AI analysis combined
- **In-app update checker** — orange banner on launch if newer version available
- **Donate button** added to footer

---

## v1.0 — Initial Release
*January 2026*

- AI clip detection with Gemini, Groq, OpenRouter
- GPU transcription (faster-whisper CUDA + openai-whisper CPU fallback)
- 16:9 and 9:16 export with face-tracking crop (mediapipe)
- Built-in yt-dlp downloader (YouTube, Twitch, Twitter/X, Kick)
- Tweet generator with tone selector
- Auto word censor (beep, silence, or custom MP3)
- Thumbnail finder (Unsplash, DuckDuckGo, Bing, Pixabay)
- Image Studio — duplicate finder + Real-ESRGAN upscaler
- Settings tab — API keys, whisper model, output folders, module installer
