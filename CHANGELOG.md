# ClipFinder Changelog

---

## v1.3.5 — Current Release
*April 2026*

### ⚡ In-App Auto-Updater
- "Download Now" in update banner downloads new clipfinder.py directly from GitHub
- Verifies file is valid Python before replacing anything
- Sets .force_install flag so splash runs for new packages on relaunch
- Progress popup with status — "Open in Browser" button kept as fallback

### 📺 YouTube 1080p
- yt-dlp updated to 2026.3.17
- bgutil-ytdlp-pot-provider PO token plugin auto-installed at first launch
- Portable Node.js v20 auto-downloaded to AppData (no system install needed)
- Downloads now return format=303+251 (1080p VP9) instead of format=18 (360p)

### ⬇️ Download Quality
- Platform-specific strategies: Twitch chunked, TikTok bytevc1 no-watermark, Twitter/X with cookie guide
- Each failed attempt logs why it failed and what client it's trying next
- ✅ Got: 1080p format=303+251 logged on success

### 🍪 Browser Cookie Auto-Extract
- Settings → Cookies: browser dropdown (Chrome/Firefox/Edge/Brave/Opera/Safari)
- yt-dlp reads cookies directly from browser database — no extension needed
- Works for YouTube HD, Kick, Twitter/X

### 🎤 Interview Mode
- Fixed silent crash on Find Clips (was calling missing interview_names_box)
- Removed redundant second names box — uses Names: field for both modes
- AI reads speaker names from video filename automatically
- Interview prompt updated to infer names from title/transcript if field blank

### 🖼 Thumbnail Finder
- DuckDuckGo image search (ddgs) — zero setup, finds real streamers/celebs
- Image Type: Portrait/solo · Group photo · Stream screenshot · Any
- Portrait mode: headshot query bias + tall layout filter
- Stock mode uses Unsplash (optional key)
- HD/SD quality toggle

### ✂ Clip Finder UI
- Clips default to unchecked — user picks what to export
- Select All / Deselect All split into two separate orange buttons
- Transcribe Only button removed from Clip Finder tab

### 🐛 Fixes
- Gemini JSON parse error on object-wrapped or preamble responses
- AI hallucinating "Mizkif" from hardcoded example in prompt
- Interview mode silent crash on Find Clips
- bgutil showing gray in Settings (underscore vs dash key mismatch)
- YouTube cookiefile being stripped from every attempt
- Pillow broken install detection (PIL.Image check instead of PIL)
- X/Twitter 403 now shows clear 4-step cookie fix guide

### 📦 Dependencies
- Added: ddgs, bgutil-ytdlp-pot-provider, portable Node.js v20

---

## v1.3.4 — Current Release
*April 2026*

### ⚡ Parallel AI Processing
- Transcript now split across every available API key simultaneously — each key handles its own section in parallel
- Short transcripts: race mode (all primaries compete, first wins)
- Long transcripts: extra keys unlock proportionally (~150 lines/worker)
- Gemini cooldown fixed: 90s for RPM limit, escalates to 60min only on repeat 429
- OpenRouter model-level 429: skips dead model, tries next model immediately
- Live rate-limit countdown in Settings provider dots (yellow = limited, red = dead, green = ready)
- Key pool always logged: `Key pool: X total, Y ready, Z on cooldown`

### 📝 Transcript Tab
- Split into two sub-tabs: **Transcript & Tweet** | **Burn Subtitles (Beta)**
- Tweet generator: single Generate produces 3 options (Drama / Viral / Thread opener)
- Each tweet option in its own tab, independently editable with character counter
- Smarter hashtags — reads transcript for real names, never generates irrelevant gaming tags

### 🔤 Burn Subtitles (Beta)
- New sub-tab — transcribe and burn subtitles from one place, no tab switching needed
- Word-level Whisper timestamps for accurate sync
- Pause detection — subtitles clear during silence gaps
- Karaoke word-highlight mode with custom highlight color
- Font, color, outline, background box, position grid, 5 style presets
- TikTok preset: 3 words at a time
- Live preview from a real frame extracted from your video

### ⬇️ Downloader
- Single URL field removed — one DOWNLOAD LINKS text area, paste multiple URLs one per line
- One **⬇ Download All** button (removed duplicate Download Queue button)

### 🔇 Censor + 🎵 Music Removal
- Both tabs rebuilt with multi-file text area — Browse Multiple or paste paths
- **📋 Use Clip Finder Video** button on both tabs
- Music Removal: fixed critical bug where background thread was never started (stuck at "starting..." forever)
- MOV/MKV/AVI files now correctly re-encode when merging (was producing 0kb output with `-c:v copy`)

### 🖼 Thumbnail Finder (Beta)
- DuckDuckGo image search via `ddgs` library — zero setup, no API key, finds real streamers/celebs
- Image Type selector: 🧑 Portrait/solo · 👥 Group photo · 🖥 Stream screenshot · 🔀 Any
- Portrait mode uses tall layout filter + headshot query bias to avoid game screenshots
- Stock photos mode (toggle) uses Unsplash — optional free key in Settings
- Quality toggle: HD / SD

### 💾 Session Save / Load
- Save/Load session buttons in Clip Finder export bar
- Saves all clips (timestamps, titles, scores, filenames) to `clipfinder_session.json` in AppData
- Load Session restores instantly — no re-transcribing or re-analysing needed
- Warns before loading if a different video is currently loaded

### 🐛 Bug Fixes
- `self.log()` 4-arg crash — merge conflict left two message strings as separate args, crashed every AI run
- `fonttools` always showing as not installed — Python module is `fontTools` (capital T)
- GPU auto-model picking showing `Video 0s` — was using ffprobe-style flags with ffmpeg binary; fixed to parse `Duration:` from stderr
- Gemini key rotation broken — first 429 put ALL keys on 30-40min cooldown; now only specific key gets 90s cooldown, Keys 2 & 3 remain available
- OpenRouter `NoneType` crash — free models returning `choices = None` now silently skipped
- MKV/MOV/AVI export producing 0kb — GPU encoder can't stream-copy these containers; now re-encodes
- Music Removal stuck at "starting X video(s)..." — thread defined but never started after refactor
- Subtitle preview `FileNotFoundError` — ffprobe doesn't ship in the auto-downloaded bundle; now uses ffmpeg stderr parsing
- Duplicate Download buttons — both "Download Queue" and "Download All" showing at same time
- Whisper `GPU=False` now explains why: `⚠ whisper.cpp not installed` or `⚠ GPU not detected`

### 📦 Dependencies
- Added: `ddgs` (DuckDuckGo image search, auto-installed on first launch)

---

## v1.3.3
*April 2026*

### 🔤 Burn Subtitles (Beta) — Initial Release
- New sub-tab inside Transcript tab
- Built-in transcription, word-level timestamps, pause detection
- Karaoke mode, font/color/position controls, 5 style presets
- TikTok preset (3 words at a time), live preview

### ⚡ Tweet Generator — 3 Options
- Single Generate click produces 3 different tweets (Drama / Viral / Thread opener)
- Smarter prompt using actual transcript quotes, better hashtag logic

### 📝 Transcript Tab
- New sub-tab structure: Transcript & Tweet | Burn Subtitles

### 🐛 Fixes
- `fonttools` detection fixed (`fontTools` capital T)

---

## v1.3.2
*April 2026*

### 🚀 Self-Installing — No More Manual Package Setup
- Pre-launch auto-installer — on first run installs all required packages automatically
- Orange splash screen with live progress
- Smart package checks — only installs what's missing
- Flag-file update system — updates apply on next launch with zero file lock errors

### 📋 Batch Download Queue
- New BATCH QUEUE in Downloader tab — paste one URL per line
- Live progress counter, Cancel button, no popups per item

### 🐛 Bug Fixes
- `curl_cffi` submodule errors fixed
- `WhisperModelC` typo in Censor tab fixed
- Demucs `torchaudio` path injection fixed
- `pydantic_core` auto-repair on next launch
- Package detection showing broken packages correctly

---

## v1.3.1
*April 2026*

### 🔑 Smart Key Rotation
- Keys shuffle randomly every run
- Per-key 62s cooldown tracking
- Gemini model splitting across keys for separate RPM buckets

### 📤📥 Encrypted Key Export / Import
- Password-encrypted `.cfkeys` bundle
- Export/Import buttons in Settings

### 🐛 Fixes
- OpenRouter NoneType crash fixed
- OpenRouter dead model list auto-resets

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

### 🔧 Hotfix (re-release)
- Pillow broken install now shows friendly error with fix instructions instead of raw traceback
- Prelaunch installer now checks `PIL.Image` (not just `PIL`) so broken Pillow installs are detected and auto-reinstalled
