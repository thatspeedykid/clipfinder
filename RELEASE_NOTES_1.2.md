# ClipFinder v1.2 — Release Notes

**Release Date:** April 2026
**Type:** Stable Release

---

## What's New

### ⚡ Auto Edit
The biggest addition in 1.2. Auto Edit lives inside the Clip Finder tab as its own sub-tab (`✂ AI Clips` | `⚡ Auto Edit`). Load any video, pick a silence removal mode, and hit RUN AUTO EDIT. It transcribes the video with Whisper, detects silence gaps, then cuts on exact word boundaries so you don't get sliced mid-word or mid-breath. One clean ffmpeg pass — no AV sync issues, no file bloat.

Three modes: Light (-45dB, long pauses only), Balanced (-35dB, recommended), Aggressive (-25dB, tight cuts).

There's also an **⚡ Auto Edit button** in the clip export bar that applies silence removal to your selected AI-found clips.

### 📼 VOD Mode
Full VOD support in the Downloader tab. Toggle VOD Mode to automatically route downloads to a `vod/` subfolder with 8 concurrent fragment downloads — making large Twitch/Kick VODs download much faster. Auto-detects VOD URLs without needing the toggle.

### 🎙️ Smart Auto Whisper
The Auto whisper setting now picks the best model based on your video length and GPU. Short clips get tiny/base, long VODs get small/medium, GPU users get bumped up automatically.

### 📋 Floating Log Panel
The log is now a proper floating window — sits on top of everything, works on every tab, buffers your full session history so you can open it any time and see what happened. Open with the `📋` button in the status bar or the Log button in the Transcript tab.

### 🔔 Smarter Update Notifications
Version comparison now uses numeric tuples so you'll only see the update banner when a genuinely newer version exists. Shows as a floating bar with a direct download button.

### 🗂️ 2-Column Clip Grid
Clip cards now display in 2 columns instead of 3. Cards are wider and fully readable — titles, descriptions, scores, and filenames no longer get cut off.

### 🏷️ Smart File Naming
All exported files now follow a clean consistent format:
- **Downloaded:** `Streamer - Clip Title - ClipFinder.mp4`
- **Exported clip:** `Clip Title - ClipFinder - Part 1.mp4`
- **9:16 vertical:** `Clip Title - ClipFinder - Part 1 9x16.mp4`
- **Auto Edit:** `Video Name - ClipFinder.mp4`

Kick downloads now pull the streamer slug and clip title directly from the Kick API instead of using the raw URL filename.

### ⚙️ Settings Overhaul
All 4 API providers use a unified aligned layout with a fixed name column so entry fields line up cleanly. Provider order matches: Gemini → Unsplash → Groq → OpenRouter.

### 🎨 UI Polish
- All main tabs stretch to fill full window width — no dead space
- Selected tab: orange background + black text
- Unselected tabs: dark background + orange text
- Version number shown in header and status bar

---

## Bug Fixes

- AI response parsing — multiline backtick fences now stripped correctly, reducing parse failures on Gemini responses
- Output folder persists on restart
- Transcript tab no longer requires output folder just to transcribe
- Whisper auto model no longer tries to download non-existent `ggml-auto.bin`
- mediapipe updated for 0.10+ API changes
- Audio energy analysis variable scope bug fixed
- Window icon fixed — no longer deletes temp file before Windows loads it
- Both export (16:9 + 9:16) fixed for censor export
- imagehash correctly detected in Core Dependencies panel

---

## Known Issues in v1.2

- Censor queue processing not working — fix in v1.3
- Auto Edit transcription returns 0 words on some files — falls back to energy peak clips

---

## System Requirements

- Windows 10/11 64-bit
- No Python required — embedded Python 3.12 included
- 4GB RAM minimum, 8GB recommended for large VODs
- GPU optional but recommended for transcription speed

