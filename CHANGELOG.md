# ClipFinder Changelog

---

## v1.3.2 — Current Release
*April 2026*

### 🚀 Self-Installing — No More Manual Package Setup
- **Pre-launch auto-installer** — on first run ClipFinder automatically downloads and installs all 19 required packages before the app opens. Orange splash screen shows live progress. Never need to manually install anything.
- **Smart package checks** — only installs what's missing or broken. Subsequent launches are instant.
- **Flag-file update system** — clicking Update in Settings writes a flag. On next launch, only flagged packages reinstall in a fresh subprocess with zero Windows file lock (WinError 5) errors.
- **Force-kill on X** — closing the app fully releases all file locks instantly so updates apply cleanly on next launch.

### 📋 Batch Download Queue
- New **BATCH QUEUE** section at the top of the Downloader tab
- Paste one URL per line — downloads run in order automatically
- Live `(1/4) downloading...` progress counter
- No popup per item — just logs `✅ Saved: filename` for each
- Cancel button stops the queue after current download finishes
- Clear button to wipe the list

### 🐛 Bug Fixes
- **curl_cffi submodule errors fixed** — `No module named 'curl_cffi.aio'` and `curl_cffi.const` errors resolved via meta path finder that stubs any missing curl_cffi submodule at import time
- **WhisperModelC typo fixed** — Censor tab was crashing immediately (`WhisperModelC` → `WhisperModel`). Also fixed `_FWC` undefined variable and added proper GPU device detection
- **Download cancel clears progress bar** — hitting Cancel no longer leaves a stuck bar
- **Demucs torchaudio not found fixed** — launcher script now injects PKGS_DIR into sys.path before importing
- **pydantic_core.core_schema missing** — groq/openai/tweet gen auto-repaired on next launch
- **Package detection improved** — modules page now correctly shows broken packages as ○ instead of ✅
- **Update banner stays visible** — new version notification repositions every 500ms, survives minimize/move

### 🎨 UI
- Queue moved to top of Downloader tab for easy access
- Splash screen background processes hidden (no black cmd windows)
- Animated progress bar with live package name during install

---

## v1.3.1
*April 2026*

### 🔑 Smart Key Rotation
- Keys shuffle randomly every run
- Per-key 62s cooldown tracking
- Gemini model splitting across keys for separate RPM buckets
- Smart retry waits — calculates minimum time until next key resets

### 📤📥 Encrypted Key Export / Import
- Password-encrypted `.cfkeys` file
- Export/Import buttons in AI Provider API Keys header
- Pexels and Pixabay added as thumbnail providers

### 🐛 Fixes
- OpenRouter NoneType crash fixed
- OpenRouter dead model list auto-resets
- Settings key row alignment fixed

---

## v1.3
*April 2026*

- AI Music Removal tab (Demucs, fully local)
- Multi-key support per provider with ＋ button
- Key rotation on rate limit
- OpenRouter model rotation
- Segment-aware clip verification
- Names field for AI context
- Progress bar for all operations

---

## v1.2
*March 2026*

- Auto Edit sub-tab — silence removal, GPU encoder
- VOD Mode — 8x concurrent fragment download
- Floating log panel
- Kick API v2 naming

---

## v1.1
*February 2026*

- Hybrid clip detection — audio peaks + AI
- In-app update checker — orange banner on launch

---

## v1.0 — Initial Release
*January 2026*

- AI clip detection (Gemini, Groq, OpenRouter)
- GPU transcription (faster-whisper CUDA + whisper.cpp Vulkan)
- 16:9 and 9:16 export with face tracking
- yt-dlp downloader (YouTube, Twitch, Twitter/X, Kick)
- Tweet generator, Word censor, Thumbnail finder, Image Studio
