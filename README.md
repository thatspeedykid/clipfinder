<div align="center">

<img src="assets/logo.png" alt="ClipFinder Logo" width="120"/>

# ClipFinder — AI Drama Clip Extractor

**Find, cut, and caption viral moments from any stream or video — automatically.**

[![Version](https://img.shields.io/badge/Version-1.3-FF6B1A?style=for-the-badge)](https://github.com/thatspeedykid/clipfinder/releases/latest)
[![Download](https://img.shields.io/github/v/release/thatspeedykid/clipfinder?color=FF6B1A&label=Download&style=for-the-badge)](https://github.com/thatspeedykid/clipfinder/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-orange?style=for-the-badge)](LICENSE)
[![Twitter](https://img.shields.io/badge/@MarsScumbags-000000?style=for-the-badge&logo=x)](https://x.com/MarsScumbags)

<img src="assets/preview.webp" alt="ClipFinder Preview" width="900"/>

</div>

---

## What is ClipFinder?

ClipFinder is a Windows desktop app that uses AI to automatically find the best drama, tea, and highlight moments in stream VODs and videos. Point it at any video, hit Find Clips, and get timestamped clips scored for virality — ready to export as 16:9 or 9:16 vertical for TikTok/Reels.

Built by [@MarsScumbags](https://x.com/MarsScumbags) for drama clip channels.

---

## Features

- 🤖 **AI Clip Detection** — Gemini, Groq, and OpenRouter find the best moments automatically
- 🎯 **Accurate Descriptions** — titles/descriptions match what's actually said in each clip
- 👥 **Names Field** — tell the AI who's in the video for better titles
- 🎬 **Hybrid Detection** — FFmpeg audio energy peaks + AI
- ⚡ **Auto Edit** — CapCut-style silence removal with word-boundary cuts
- 🎵 **AI Music Removal** — strip background music, keep vocals (Demucs, runs locally)
- 📼 **VOD Mode** — 8x parallel downloads for Twitch/Kick/YouTube VODs
- ✂️ **Smart Export** — 16:9, 9:16 vertical, or both with GPU acceleration
- 🎙️ **Smart Auto Whisper** — picks best model based on video length + GPU
- 🔇 **Auto Censor** — beep, silence, or custom MP3 over banned words
- ⬇️ **Built-in Downloader** — Kick, Twitch, YouTube, Twitter/X with smart naming
- 🖼️ **Thumbnail Finder** — Unsplash + Google Images
- 🐦 **Tweet Generator** — AI-written viral tweets
- 🔔 **Update Checker** — notified when new version drops

---

## Download

**[⬇ Download ClipFinder_Setup.exe — v1.3 Latest](https://github.com/thatspeedykid/clipfinder/releases/latest)**

- Windows 10/11 64-bit only
- No Python required — everything included
- ~110MB installer

---

## First Time Setup

1. Run `ClipFinder_Setup.exe` → installs + Desktop shortcut
2. Open ClipFinder
3. Go to **⚙ Settings → API Keys** and add your keys (all free):

| Provider | What It's For | Free Tier | Get Key |
|----------|--------------|-----------|---------|
| **Gemini** | Clip finding — best quality | 1,500 req/day | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Unsplash** | Thumbnail search | 50 req/hr | [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications) |
| **Groq** | Tweets + fast inference | High limits | [console.groq.com](https://console.groq.com) |
| **OpenRouter** | Fallback + 50+ free models | Varies | [openrouter.ai/keys](https://openrouter.ai/keys) |

4. Click **Save & Apply** — no restart needed

<details>
<summary><b>🔑 How to get each API key</b></summary>

**Gemini:** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Sign in → Create API Key

**Groq:** [console.groq.com](https://console.groq.com) → Sign up → API Keys → Create

**OpenRouter:** [openrouter.ai](https://openrouter.ai) → Sign up → Keys → Create

**Unsplash:** [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications) → New Application → Access Key
</details>

---

## How to Use

### Find Clips
1. Paste a URL or browse to a video file
2. Add context + names (who's in the video)
3. Hit **▶ FIND CLIPS**
4. Review 2-column clip grid, adjust timestamps if needed
5. Select clips → **✂ EXPORT SELECTED**

### Auto Edit
Go to **Clip Finder → ⚡ Auto Edit** sub-tab. Load video, pick silence mode, hit **RUN AUTO EDIT**. Transcribes, detects silence, cuts on word boundaries, exports clean.

### Music Removal
Go to **🎵 Music Removal** tab. Install Demucs via Settings first, then load video and hit **REMOVE MUSIC**. Strips background music, keeps vocals.

### VOD Mode
**⬇ Downloader** → enable **📼 VOD Mode** → paste URL. Saves to `vod/` folder with 8x speed.

---

## File Naming

| Type | Format |
|------|--------|
| Downloaded | `Streamer - Clip Title - ClipFinder.mp4` |
| Exported clip | `Clip Title - ClipFinder - Part 1.mp4` |
| Auto Edit | `VideoName - AutoEdit - ClipFinder.mp4` |
| Music Removed | `VideoName - NoMusic - ClipFinder.mp4` |
| 9:16 vertical | `Clip Title - ClipFinder - Part 1 9x16.mp4` |

---

## GPU Transcription

| GPU | Method | Speed |
|-----|--------|-------|
| AMD (RX 5000+) | whisper.cpp + Vulkan | ~10x realtime |
| Intel Arc | whisper.cpp + Vulkan | ~5x realtime |
| NVIDIA | faster-whisper + CUDA | ~15x realtime |
| CPU | faster-whisper int8 | ~3x realtime |

---

## What's Coming in v1.4

- ✂️ **Mini Editor** — trim handles, captions overlay, crop/resize, face-focus portrait
- ⬇️ **VOD Timestamp Range** — download only `00:10:00-00:15:00` from a VOD
- 🖼️ **Thumbnail Finder Overhaul** — Kick direct lookup + Gemini image search
- 🔄 **Auto-updater** — one-click update from inside the app

---

## Changelog

### v1.3 — April 2026 — Current Stable
- 🎵 AI Music Removal — Demucs, local, GPU accelerated
- 🎯 Segment-aware clip accuracy — descriptions match actual clip content
- 👥 Names field — AI uses real names in titles/descriptions
- ⚡ Rate limiting overhaul — sequential tasks, global RL tracking, Gemini 1.5 Flash
- 🔧 Censor queue fixed
- 📊 Progress bar for every operation
- 📦 Settings module status dots, faster open
- 🏷️ Better file naming (AutoEdit suffix, NA uploader fix)
- 🎨 Encoder detecting label fixed, interview names unified

### v1.2 — April 2026
- ⚡ Auto Edit sub-tab — silence removal with word-boundary cuts
- 📼 VOD Mode — 8x concurrent downloads
- 🎙️ Smart Auto Whisper
- 📋 Floating log panel
- 🗂️ 2-column clip grid
- 🏷️ Smart file naming
- 🎨 Tabs stretched, orange tab colors
- AI response backtick parsing fixed

### v1.1 — April 2026
- Hybrid clip detection (FFmpeg energy + AI)
- In-app update checker
- Donate button

### v1.0 — April 2026 — Initial Release
- AI clip detection, GPU transcription, 16:9/9:16 export
- Built-in downloader, tweet generator, auto-censor

---

## Support

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue?style=for-the-badge&logo=paypal)](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD)

Follow for clips and updates: [@MarsScumbags](https://x.com/MarsScumbags)

---

## License

MIT — free to use, modify, and distribute. Credit appreciated.
