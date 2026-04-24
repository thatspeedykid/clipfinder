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

---

## v1.3.3 — Current Release
*April 2026*

### 🔤 Burn Subtitles (Beta)
- New sub-tab inside Transcript tab — burn captions directly onto video
- Built-in transcription with word-level timestamps — no need to visit Transcript tab first
- Pause detection — subtitles clear during silence gaps
- Karaoke mode — each word highlights as spoken with customizable color
- Font, size, bold/italic, ALL CAPS, text/outline/background colors
- 3x3 position grid, 5 style presets (Standard, Karaoke, Cinematic, Minimal, TikTok)
- TikTok preset forces 3 words at a time
- Live preview from real video frame

### ⚡ Tweet Generator — 3 Options
- Single Generate click produces 3 different tweets (Drama / Viral / Thread opener)
- Smarter prompt: reads transcript for specific quotes, never generates #gaming unless relevant
- Hashtags match actual people named in context and transcript

### 📝 Transcript Tab
- Sub-tab structure: Transcript & Tweet | Burn Subtitles (Beta)
- Tweet output tabbed: Option 1 / Option 2 / Option 3

### 🐛 Fixes
- fonttools import detection fixed (fontTools capital T)

---

## v1.3.4 — Current Release
*April 2026*

### ⚡ Parallel AI Processing
- Transcript now split across every available API key simultaneously — each key handles its own section in parallel
- Short transcripts: race mode (all primaries compete, first wins)
- Long transcripts: extra keys unlock proportionally (~150 lines/worker)
- Gemini cooldown fixed: 90s for RPM limit, escalates to 60min only on repeat 429
- OpenRouter model-level 429: skips dead model, tries next immediately
- Live rate-limit countdown in Settings provider dots
- Key pool always logged: `Key pool: X total, Y ready, Z on cooldown`

### 📝 Transcript Tab
- Split into sub-tabs: Transcript & Tweet | Burn Subtitles (Beta)
- Tweet generator: single Generate produces 3 options (Drama / Viral / Thread opener)
- Each tweet option in its own tab, independently editable with char counter
- Smarter hashtags — reads transcript for names, never generates irrelevant gaming tags

### 🔤 Burn Subtitles (Beta)
- New sub-tab — transcribe and burn from one place, no switching tabs
- Word-level Whisper timestamps for accurate sync
- Pause detection — subtitles clear during silence
- Karaoke word-highlight mode
- Font, color, outline, background, position, 5 style presets
- TikTok preset: 3 words at a time
- Live preview from real video frame

### ⬇️ Downloader
- Single URL field removed — one DOWNLOAD LINKS text area, paste multiple URLs
- One Download All button (removed duplicate Download Queue)

### 🔇 Censor + 🎵 Music Removal
- Both tabs: multi-file text area with Browse Multiple and Use Clip Finder Video
- Music Removal: fixed stuck-at-starting bug (thread was never started)
- MOV/MKV/AVI: now re-encodes video stream instead of failing with -c:v copy

### 🖼 Thumbnail Finder (Beta)
- DuckDuckGo image search via ddgs — zero setup, no API key, finds real people
- Image Type selector: Portrait/solo · Group photo · Stream screenshot · Any
- Portrait mode uses tall layout + headshot query bias
- Stock photos mode uses Unsplash (optional free key)
- Quality toggle: HD / SD

### 💾 Session Save/Load
- Save/Load session buttons in Clip Finder export bar
- Saves all clips to clipfinder_session.json in AppData

### 🐛 Fixes
- self.log() 4-arg crash (merge conflict)
- fonttools detection (fontTools capital T)
- GPU duration showing 0s (ffprobe-style flags with ffmpeg binary)
- Gemini key rotation not working (all keys got 30-40min cooldown on first 429)
- OpenRouter NoneType crash on empty choices response
- MKV/MOV export producing 0kb files
- Music Removal stuck at "starting..." forever
- Subtitle preview FileNotFoundError (ffprobe not in bundle)
- Duplicate Download buttons
- Whisper GPU=False now explains why

### 📦 Dependencies
- Added: ddgs (DuckDuckGo image search)
