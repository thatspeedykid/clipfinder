# ✂ ClipFinder
### AI Drama Clip Extractor — v1.3.4

> Built by [@MarsScumbags](https://x.com/MarsScumbags) for the streaming & drama clip game.  
> Find, cut, censor, and export viral clips from any VOD — fully automated, locally run, free AI.

---

## 🚀 What It Does

- **⚡ Parallel AI Clip Finding** — splits your transcript across every API key simultaneously, each key analyses its own section in parallel. 2–5× faster with multiple keys.
- **🎙 GPU Transcription** — whisper.cpp (AMD/Intel Vulkan ⚡) or faster-whisper (NVIDIA CUDA ⚡)
- **✂ One-Click Export** — 16:9, 9:16 vertical, or both with GPU encoding
- **🔄 Auto Edit** — silence removal with word-boundary cuts
- **🎵 Music Removal** — Demucs AI stem separation, fully local, multi-file queue
- **🔇 Word Censor** — bleeps/silences banned words, multi-file queue
- **⬇ Batch Downloader** — paste multiple URLs, downloads in order (YouTube, Twitch, Twitter/X, Kick, TikTok)
- **🐦 Tweet Generator** — 3 different tweet options from your transcript (Drama / Viral / Thread opener)
- **🔤 Burn Subtitles** *(Beta)* — burn captions onto video with word-level sync, karaoke mode, style presets
- **🖼 Thumbnail Finder** *(Beta)* — DuckDuckGo image search, finds real streamer/celeb photos, no API key needed
- **💾 Session Save/Load** — save and restore clip sessions without re-analysing
- **🎨 Image Studio** — duplicate finder + Real-ESRGAN upscaler

---

## 📦 Installation

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases/latest)
2. Run it — installs to `AppData\Local\ClipFinder\`
3. Launch ClipFinder
4. **First launch** — orange splash screen auto-installs all required packages. Takes 2–5 min. Once only.
5. Go to **Settings → AI Provider API Keys** and add at least one free key
6. Go to **Settings → Core Dependencies** and install **ffmpeg** + **whisper.cpp**

> No Python install required. No manual package setup. The app handles everything.

---

## 🔑 Free API Keys

| Provider | Free Tier | Used For | Link |
|---|---|---|---|
| Google Gemini | 1,500 req/day | Clip finding & tweets | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Groq | High limits | Clip finding & tweets | [console.groq.com](https://console.groq.com/keys) |
| OpenRouter | 200+ req/day | Clip finding & tweets | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Unsplash | 50 req/hr | Thumbnail stock mode only | [unsplash.com/developers](https://unsplash.com/oauth/applications) |

**Pro tip:** Add 2–3 keys per provider via the ＋ button in Settings. ClipFinder splits the transcript across all your keys in parallel — more keys = faster results and less load per key.

---

## ⚡ How Parallel AI Works

ClipFinder splits your video transcript across every available API key at the same time:

- **Short clips** → race mode: all primary keys get the same chunk, first response wins
- **Long VODs** → split mode: each key handles its own section of the transcript simultaneously
- Results from all keys are merged and deduplicated at the end

With 3 Gemini + 2 Groq + 1 OpenRouter = **6 workers running in parallel**. Much faster, much less rate-limit stress per key.

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

GPU transcription requires **whisper.cpp** — install via Settings → Core Dependencies.

---

## 🔄 Keeping Updated

Settings → Update Modules → **Update All Packages** → restart.  
The app checks for new versions automatically and shows a banner when one is available.

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## ☕ Support

[@MarsScumbags](https://x.com/MarsScumbags) · [github.com/thatspeedykid/clipfinder](https://github.com/thatspeedykid/clipfinder)  
[Buy me a coffee](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD)
