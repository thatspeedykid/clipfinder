<div align="center">

<img src="assets/logo.png" alt="ClipFinder Logo" width="120"/>

# ClipFinder — AI Drama Clip Extractor

**Find, cut, and caption viral moments from any stream or video — automatically.**

[![Version](https://img.shields.io/badge/Version-1.1-FF6B1A?style=for-the-badge)](https://github.com/thatspeedykid/clipfinder/releases/latest)
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
- ✂️ **Smart Export** — 16:9, 9:16 vertical, or both simultaneously with GPU acceleration
- 🎙️ **GPU Transcription** — whisper.cpp with Vulkan for AMD/Intel, CUDA for NVIDIA
- 🔇 **Auto Censor** — beep, silence, or custom MP3 over banned words
- ⬇️ **Built-in Downloader** — Kick, Twitch, YouTube, Twitter/X via yt-dlp
- 🖼️ **Thumbnail Finder** — search and download thumbnails via Unsplash
- 🐦 **Tweet Generator** — AI-written viral tweets from your transcript
- 🎬 **Studio** — trim, preview, and manage clips before export
- 📺 **Interview Mode** — tracks who's speaking for multi-person interviews

---

## Download

**[⬇ Download ClipFinder_Setup.exe — Latest Release](https://github.com/thatspeedykid/clipfinder/releases/latest)**

- Windows 10/11 64-bit only
- No Python required — everything included
- ~200MB installer

---

## First Time Setup

1. Run `ClipFinder_Setup.exe` → installs to Program Files + Desktop shortcut
2. Open ClipFinder
3. Go to **⚙ Settings → API Keys** and add your keys (all free):

| Provider | What It's For | Free Tier | Get Key |
|----------|--------------|-----------|---------|
| **Gemini** | Clip finding — best for long videos | 15 req/min | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Groq** | Tweets + fast inference | 30 req/min | [console.groq.com](https://console.groq.com) |
| **OpenRouter** | Fallback + extra free models | Varies | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Unsplash** | Thumbnail search | 50 req/hr | [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications) |

> **You only need one AI key to get started.** Groq or Gemini recommended. Unsplash is optional — only needed for the Thumbnails tab.

4. Click **Save & Apply** — no restart needed

### How to get each API key

<details>
<summary><b>🔑 Gemini (Google) — Best for clip finding</b></summary>

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key and paste it into ClipFinder → Settings → Gemini

Free tier: 15 requests/min, 1500 requests/day — plenty for daily use.
</details>

<details>
<summary><b>🔑 Groq — Best for tweets and fast responses</b></summary>

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Go to **API Keys** → **Create API Key**
4. Copy the key and paste it into ClipFinder → Settings → Groq

Free tier: 30 requests/min — fastest inference available.
</details>

<details>
<summary><b>🔑 OpenRouter — Free models fallback</b></summary>

1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up and go to **Keys** → **Create Key**
3. Copy the key and paste it into ClipFinder → Settings → OpenRouter

Free tier: multiple free models available, no credit card needed.
</details>

<details>
<summary><b>🔑 Unsplash — Thumbnail search (optional)</b></summary>

1. Go to [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications)
2. Sign in or create a free account
3. Click **New Application** → accept terms
4. Fill in app name (e.g. "ClipFinder") and description
5. Scroll down and copy your **Access Key**
6. Paste it into ClipFinder → Settings → Unsplash

Free tier: 50 requests/hour — more than enough for thumbnail searching.
</details>

### Optional but recommended
- **Settings → Core Dependencies → Install ffmpeg** (auto-downloads ~90MB)
- **Settings → Core Dependencies → Install whisper.cpp (GPU)** — AMD/Intel GPU transcription

---

## How to Use

### Find Clips
1. Paste a URL or browse to a video file
2. Add context (who's in it, what's the drama)
3. Hit **▶ FIND CLIPS**
4. Review AI suggestions, adjust timestamps if needed
5. Select clips → **✂ EXPORT SELECTED**

### Generate Tweet
1. Transcribe your video first
2. Go to **📝 Transcript** tab
3. Add context, pick a tone (Drama / Tea / Breaking / Hype)
4. Hit **⚡ GENERATE TWEET**

### Censor Audio
- Toggle **🔇 Censor** in the export bar
- Choose Beep, Silence, or custom MP3
- Manage word list in the **🔇 Censor** tab

---

## GPU Transcription

| GPU | Method | Speed |
|-----|--------|-------|
| AMD (RX 5000+) | whisper.cpp + Vulkan | ~10x realtime |
| Intel Arc / iGPU | whisper.cpp + Vulkan | ~5x realtime |
| NVIDIA | faster-whisper + CUDA | ~15x realtime |
| Any CPU | faster-whisper int8 | ~3x realtime |

Install via **Settings → Core Dependencies**.

---

## Building from Source

Requires Python 3.12.

```bash
git clone https://github.com/thatspeedykid/clipfinder
cd clipfinder
pip install -r requirements.txt
python clipfinder.py
```

To build the installer (requires Python 3.12 + [NSIS](https://nsis.sourceforge.io)):
```bash
build_installer.bat
"C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```

---

## Changelog

### v1.1 — April 2026 — Initial Release
- AI clip detection with Gemini, Groq, OpenRouter
- GPU transcription (AMD/Intel Vulkan, NVIDIA CUDA)
- 16:9 and 9:16 export with face tracking
- Built-in downloader (Kick, Twitch, YouTube, Twitter/X)
- Tweet generator with tone selection
- Auto-censor with custom word lists
- Thumbnail finder via Unsplash
- Studio tab, Interview mode
- One-click dependency installer

**Known issues in v1.0** (fixed in v1.1):
- Both export only saves 16:9, vertical skipped
- Update All permission errors on locked packages
- imagehash not detected in deps panel after install
- Settings missing browse buttons for output folders
- Transcript log button unresponsive

### v1.1 — Coming Soon
- Hybrid clip detection (FFmpeg audio energy + AI)
- In-app update notifications
- All v1.0 known issues fixed

---

## Support

If ClipFinder helps your channel, consider buying me a coffee!

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue?style=for-the-badge&logo=paypal)](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD)

Follow for clips and updates: [@MarsScumbags](https://x.com/MarsScumbags)

---

## License

MIT — free to use, modify, and distribute. Credit appreciated.



