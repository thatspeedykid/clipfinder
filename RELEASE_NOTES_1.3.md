# ClipFinder v1.3 — Release Notes

**Release Date:** April 2026
**Type:** Stable Release

---

## What's New

### 🎵 AI Music Removal
New dedicated tab — strip copyrighted background music from any video while keeping vocals and speech. Powered by Meta's Demucs model running fully locally — no API needed, no upload. Uses HTDemucs, MDX Extra, or HTDemucs FT models. Install Demucs via Settings → Update Modules, then select your video and hit Remove Music. Outputs `VideoName - NoMusic - ClipFinder.mp4`.

### 🎯 Smarter AI Clip Accuracy
ClipFinder now runs a verification pass after AI clip selection — extracts only the transcript lines that fall within each clip's exact timestamp range and uses that as the description. Titles and descriptions now reflect what's actually said in the clip instead of pulling context from other parts of the video.

### 👥 Names Field
New Names field next to Context — type the streamers/people in the video (`Mizkif, xQc, HasanAbi`) and the AI uses those names in titles and descriptions instead of generic "the streamer" references. Works for both Normal and Interview mode from one shared field.

### ⚡ Rate Limiting Overhaul
Complete rewrite of the multi-provider dispatch system:
- Tasks now run **sequentially** with a 5s gap — stops all 3 providers getting hammered simultaneously
- **Global rate limit tracking** — when a provider is rate-limited, all tasks skip it instead of all piling on
- Each task **starts from its assigned provider** then falls back — true load distribution
- **Retry loop** — up to 3 retries with 30s/60s/90s cooldowns instead of giving up immediately
- **Gemini 1.5 Flash** now used by default — 1,500 requests/day free vs 20/day for 2.5 Flash
- Added high-limit free models for Groq and OpenRouter

### 🔧 Censor Queue Fixed
Queued videos now correctly use the stored video path and output folder from when they were added to the queue — was using the currently loaded video instead.

### 📦 Settings Overhaul
- ✅/○ status dots next to every module — see at a glance what's installed
- Reinstall section hidden when all packages are installed
- Demucs, torch, torchaudio added to module list
- Settings opens much faster — background pre-build, deferred package scanning, TTK style cached

### 📊 Progress Bar Everywhere
Progress bar now shows for every operation: Auto Edit, Export, Queue, Music Removal, Download — with percentage and current step.

### 🏷️ Better File Naming
- Auto Edit output: `VideoName - AutoEdit - ClipFinder.mp4`
- Downloads with `NA` uploader now extract channel name from URL
- Generic titles (master, playlist, index) replaced with stream description

### 🎨 UI Fixes
- Top bar no longer shows "Encoder: detecting..." after GPU detection completes
- Interview mode Names box replaced with shared Names field
- Settings tab loads faster on first open

---

## Bug Fixes
- OpenRouter response truncation — increased to 8192 tokens, detects and retries on truncation
- 503/UNAVAILABLE errors now treated same as rate limits (skip to next provider)
- Mistral model updated to current free endpoint
- torchcodec Windows DLL issue bypassed via torchaudio.load/save monkey-patch

---

## Known Issues
- Censor queue batch processing (multiple videos) — partial fix, single video works
- Auto Edit transcription returns 0 words on some file formats — falls back to energy peaks

---

## System Requirements
- Windows 10/11 64-bit
- No Python required — embedded Python 3.12 included
- 4GB RAM minimum, 8GB recommended
- GPU optional but recommended
- Demucs for Music Removal: ~2GB additional disk space
