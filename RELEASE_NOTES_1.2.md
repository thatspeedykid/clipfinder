# ClipFinder v1.2 — Release Notes

**Release Date:** April 2026
**Type:** Stable Release

---

## What's New in v1.2

### 🎬 Auto Edit Mode
ClipFinder now includes a CapCut-style Auto Edit mode. Select **Auto** in the mode selector and hit Find Clips — it automatically detects silence gaps, analyzes audio energy peaks for reaction moments, transcribes the video, and feeds everything into AI for smart clip selection. No manual timestamp hunting needed.

### 📼 VOD Mode
Full VOD support in the Downloader tab. Enable **VOD Mode** to automatically save long-form content to a separate `vod/` folder with 8 concurrent fragment downloads — turning a 30-minute download of a 10GB Twitch VOD into under 5 minutes. Auto-detects Twitch and Kick VOD URLs without needing the toggle.

### 🎙️ Smart Auto Whisper
The **Auto** whisper model setting now actually picks the best model for the job instead of defaulting to base. Short clips get `tiny` or `base`, long VODs get `small` or `medium`, and GPU users get bumped up a tier automatically.

### 🪟 Floating Log Panel
The log panel is now a proper floating overlay window — stays on top of everything, full width, works on every tab including Transcript. Open and close it with the `📋` button in the status bar or the Log button in the Transcript tab.

### 🔔 Smarter Update Notifications
The update checker now uses proper version number comparison so you'll only see the banner when a genuinely newer version exists. The notification is a floating overlay bar with a direct download button.

### ⚙️ Settings Overhaul
- All 4 API providers (Gemini, Unsplash, Groq, OpenRouter) now use a unified aligned layout
- Provider order matches the screenshot: Gemini → Unsplash → Groq → OpenRouter
- Browse buttons added for output and download folders
- Version number shown in header and status bar

---

## Bug Fixes

- **Both export** (16:9 + 9:16) now correctly saves both formats — including when Censor is enabled
- **Output folder** now persists correctly on restart
- **Transcript tab** no longer requires an output folder to be set just to transcribe
- **imagehash** now correctly detected in Core Dependencies panel
- **Update All** permission errors fixed for locked `.pyd` files
- **Whisper auto model** no longer tries to download non-existent `ggml-auto.bin`
- **mediapipe** updated to handle 0.10+ API changes
- **AI response parsing** improved — strips markdown backticks from provider responses
- **Hybrid energy analysis** `vid` variable scope fixed

---

## Known Issues

- Censor queue processing not working — fix coming in v1.3
- OpenRouter responses occasionally truncated on very long videos
- mediapipe face tracking falls back to center crop (API migration in progress)

---

## System Requirements

- Windows 10/11 64-bit
- No Python required — embedded Python 3.12 included
- 4GB RAM minimum (8GB recommended)
- GPU optional but recommended for transcription speed

