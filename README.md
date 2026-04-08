# ✂ ClipFinder
### AI Drama Clip Extractor — v1.3.1

> Built by [@MarsScumbags](https://x.com/MarsScumbags) for the streaming & drama clip game.  
> Find, cut, censor, and export viral clips from any VOD — fully automated, locally run, free AI.

---

## 🚀 What It Does

ClipFinder watches your video, transcribes it, and uses AI to find the moments worth clipping — arguments, callouts, reveals, confessions, rants. Then it exports them ready to post.

- **AI Clip Finding** — Gemini, Groq, and OpenRouter scan your transcript and pick the best moments
- **GPU Transcription** — whisper.cpp (AMD/Intel Vulkan) or faster-whisper (NVIDIA CUDA)
- **One-Click Export** — 16:9, 9:16 vertical, or both at once with GPU encoding
- **Auto Edit** — silence removal with word-boundary cuts for tight pacing
- **Music Removal** — Demucs AI stem separation, runs fully local, no API needed
- **Word Censor** — transcribes and bleeps/silences banned words, bulk queue support
- **Downloader** — yt-dlp for YouTube, Twitch, Twitter/X, Kick (Cloudflare bypass included)
- **Tweet Generator** — paste a transcript, get a viral tweet in your tone
- **Thumbnail Finder** — searches Unsplash, DuckDuckGo, Bing, Pixabay for HD images
- **Image Studio** — duplicate finder + AI upscaler (Real-ESRGAN)

---

## 📦 Installation

1. Download the latest installer from [Releases](https://github.com/thatspeedykid/clipfinder/releases/latest)
2. Run `ClipFinder-Setup.exe` — installs to `AppData\Local\ClipFinder\`
3. Launch ClipFinder
4. Go to **Settings → AI Provider API Keys** and add at least one free key
5. Go to **Settings → Update Modules** and click **Install All AI Packages**
6. Go to **Settings → Core Dependencies** and install **ffmpeg** + **whisper.cpp**

> No Python install required — ships with embedded Python 3.12.

---

## 🔑 Free API Keys (No Credit Card)

| Provider | Free Tier | Link |
|---|---|---|
| Google Gemini | 1,500 req/day · 15 req/min | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Groq | High limits · fastest inference | [console.groq.com](https://console.groq.com/keys) |
| OpenRouter | 200 req/day · 50+ free models | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Unsplash | 50 req/hr · thumbnail search | [unsplash.com/developers](https://unsplash.com/oauth/applications) |

**Pro tip:** Add 2–3 keys per provider. ClipFinder rotates through them automatically and each Gemini key is assigned a different model version so they hit separate rate limit buckets.

---

## ⚙️ System Requirements

| | |
|---|---|
| **OS** | Windows 10/11 64-bit |
| **RAM** | 4GB minimum · 8GB recommended |
| **GPU** | Optional — AMD RX 5000+, NVIDIA, or Intel Arc for acceleration |
| **Disk** | ~500MB app + ~2GB for Demucs (Music Removal) |
| **Python** | Embedded — no system Python required |

---

## 🎮 How To Use

### Find Clips
1. Paste a URL or click 📁 to load a video
2. Set your output folder
3. Add context (who's in it, what's the drama)
4. Hit **▶ FIND CLIPS**
5. Review suggestions, edit timestamps if needed
6. Hit **✂ EXPORT SELECTED**

### Auto Edit
Switch to the **Auto Edit** sub-tab to remove all silence and dead air from a video in one pass — no clip selection needed.

### Censor Words
Go to the **Censor** tab, set your word list, select a video, pick Beep / Silence / MP3, and hit **🔇 CENSOR**. Supports bulk queue for multiple videos.

### Remove Music
Go to the **Music Removal** tab, select your video, pick a Demucs model, and hit **🎵 REMOVE MUSIC**. Runs fully locally.

---

## 🧠 AI Provider Details

ClipFinder dispatches work across all providers simultaneously:

- **Gemini 1.5 Flash** — best for long videos (120k char context), 1,500 req/day free
- **Groq Llama** — fastest inference, great for short clips
- **OpenRouter** — 50+ free models, good fallback

**Multi-key rotation:** Keys are shuffled randomly each run. When a key hits a rate limit, its cooldown is tracked precisely and the next ready key is used. If all keys are cooling, ClipFinder waits only the minimum time needed — not a hardcoded delay.

---

## 📁 File Naming

| Type | Format |
|---|---|
| Downloaded | `Streamer - Clip Title - ClipFinder.mp4` |
| Exported clip | `Clip Title - ClipFinder - Part 1.mp4` |
| Auto Edit | `VideoName - AutoEdit - ClipFinder.mp4` |
| Music Removed | `VideoName - NoMusic - ClipFinder.mp4` |
| 9:16 vertical | `Clip Title - ClipFinder - Part 1 9x16.mp4` |

---

## 🛠️ GPU Support

| GPU | Transcription | Encoding |
|---|---|---|
| AMD RX 5000+ | whisper.cpp Vulkan ⚡ | h264_amf |
| NVIDIA | faster-whisper CUDA ⚡ | h264_nvenc |
| Intel Arc | whisper.cpp Vulkan ⚡ | h264_qsv |
| CPU fallback | faster-whisper int8 | libx264 CRF 18 |

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## ☕ Support

If ClipFinder saves you time, consider [buying me a coffee](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD).

[@MarsScumbags](https://x.com/MarsScumbags) · [github.com/thatspeedykid/clipfinder](https://github.com/thatspeedykid/clipfinder)
