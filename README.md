# ✂ ClipFinder
### AI Drama Clip Extractor — v1.3.2

> Built by [@MarsScumbags](https://x.com/MarsScumbags) for the streaming & drama clip game.  
> Find, cut, censor, and export viral clips from any VOD — fully automated, locally run, free AI.

---

## 🚀 What It Does

- **AI Clip Finding** — Gemini, Groq, OpenRouter scan your transcript and pick the best moments
- **GPU Transcription** — whisper.cpp (AMD/Intel Vulkan) or faster-whisper (NVIDIA CUDA)
- **One-Click Export** — 16:9, 9:16 vertical, or both with GPU encoding
- **Auto Edit** — silence removal with word-boundary cuts
- **Music Removal** — Demucs AI stem separation, fully local
- **Word Censor** — bleeps/silences banned words, bulk queue support
- **Batch Downloader** — paste a list of URLs, downloads in order (YouTube, Twitch, Twitter/X, Kick)
- **Tweet Generator** — viral tweet from transcript
- **Thumbnail Finder** — Unsplash, Pexels, Pixabay, DuckDuckGo, Bing
- **Image Studio** — duplicate finder + Real-ESRGAN upscaler

---

## 📦 Installation

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases/latest)
2. Run it — installs to `AppData\Local\ClipFinder\`
3. Launch ClipFinder
4. **First launch** — shows an orange splash screen and automatically installs all required packages. Takes 2–5 min. This only happens once.
5. Go to **Settings → AI Provider API Keys** and add at least one free key
6. Go to **Settings → Core Dependencies** and install **ffmpeg** + **whisper.cpp**

> No Python install required. No manual package setup. The app handles everything.

---

## 🔑 Free API Keys

| Provider | Free Tier | Link |
|---|---|---|
| Google Gemini | 1,500 req/day | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Groq | High limits | [console.groq.com](https://console.groq.com/keys) |
| OpenRouter | 200 req/day | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Unsplash | 50 req/hr | [unsplash.com/developers](https://unsplash.com/oauth/applications) |
| Pexels | Free | [pexels.com/api](https://www.pexels.com/api/) |
| Pixabay | Free | [pixabay.com/api](https://pixabay.com/api/docs/) |

**Pro tip:** Add 2–3 keys per AI provider via the ＋ button in Settings. ClipFinder rotates through them automatically.

---

## ⚙️ System Requirements

| | |
|---|---|
| **OS** | Windows 10/11 64-bit |
| **RAM** | 4GB min · 8GB recommended |
| **GPU** | Optional — AMD RX 5000+, NVIDIA, Intel Arc |
| **Disk** | ~500MB app + packages download on first run |
| **Internet** | Required on first launch to download packages |

---

## 🛠️ GPU Support

| GPU | Transcription | Encoding |
|---|---|---|
| AMD RX 5000+ | whisper.cpp Vulkan ⚡ | h264_amf |
| NVIDIA | faster-whisper CUDA ⚡ | h264_nvenc |
| Intel Arc | whisper.cpp Vulkan ⚡ | h264_qsv |
| CPU fallback | faster-whisper int8 | libx264 |

---

## 🔄 Keeping Updated

Settings → Update Modules → **Update All Packages** → restart ClipFinder.  
The update runs on next launch — packages install in background with no errors.

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## ☕ Support

[@MarsScumbags](https://x.com/MarsScumbags) · [github.com/thatspeedykid/clipfinder](https://github.com/thatspeedykid/clipfinder)  
[Buy me a coffee](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD)
