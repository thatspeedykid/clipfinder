# ✂ ClipFinder
### AI Drama Clip Extractor — v1.3.5

> Built by [@MarsScumbags](https://x.com/MarsScumbags) for the streaming & drama clip game.  
> Find, cut, censor, and export viral clips from any VOD — fully automated, locally run, free AI.

---

## 🚀 What It Does

- **⚡ Parallel AI Clip Finding** — splits transcript across every API key simultaneously. More keys = faster results.
- **📺 YouTube 1080p Downloads** — bgutil PO token plugin handles YouTube's restrictions automatically
- **🎙 GPU Transcription** — whisper.cpp (AMD/Intel Vulkan ⚡) or faster-whisper (NVIDIA CUDA ⚡)
- **✂ One-Click Export** — 16:9, 9:16 vertical, or both with GPU encoding
- **🔄 Auto Edit** — silence removal with word-boundary cuts
- **🎵 Music Removal** — Demucs AI stem separation, fully local, multi-file queue
- **🔇 Word Censor** — bleeps/silences banned words, multi-file queue
- **⬇ Batch Downloader** — paste multiple URLs (YouTube, Twitch, Twitter/X, Kick, TikTok)
- **🐦 Tweet Generator** — 3 tweet options from transcript (Drama / Viral / Thread)
- **🔤 Burn Subtitles** *(Beta)* — word-level sync, karaoke mode, style presets
- **🖼 Thumbnail Finder** *(Beta)* — DuckDuckGo image search, finds real streamer/celeb photos, no API key
- **💾 Session Save/Load** — restore clip sessions without re-analysing
- **🔁 Auto-Updater** — app updates itself in one click, no new installer needed

---

## 📦 Installation

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases/latest)
2. Run it — installs to `AppData\Local\ClipFinder\`
3. Launch ClipFinder
4. **First launch** — orange splash auto-installs all packages including YouTube PO token plugin + portable Node.js. Takes 3–6 min. Once only.
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

**Pro tip:** Add 2–3 keys per provider via the ＋ button in Settings. ClipFinder splits the transcript across all keys in parallel.

---

## ⚡ How Parallel AI Works

- **Short clips** → race mode: all primary keys get the same chunk, first response wins
- **Long VODs** → split mode: each key handles its own section simultaneously
- Results merged and deduplicated at the end

3 Gemini + 2 Groq + 1 OpenRouter = **6 workers in parallel**.

---

## 📺 YouTube 1080p

YouTube requires PO tokens since 2024. ClipFinder handles this automatically:

1. First launch installs `bgutil-ytdlp-pot-provider` plugin
2. Downloads portable Node.js v20 to AppData (no system install, no admin rights)
3. Plugin hooks into yt-dlp silently — all YouTube downloads get proper 1080p+ quality

No configuration needed.

---

## ⚙️ System Requirements

| | |
|---|---|
| **OS** | Windows 10/11 64-bit |
| **RAM** | 4GB min · 8GB recommended |
| **GPU** | Optional — AMD RX 5000+, NVIDIA, Intel Arc |
| **Disk** | ~500MB app + packages on first run |

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

When a new version is available, an orange banner appears at the bottom of the app. Click **⬇ Download Now** — the app updates itself automatically and relaunches.

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## ☕ Support

[@MarsScumbags](https://x.com/MarsScumbags) · [github.com/thatspeedykid/clipfinder](https://github.com/thatspeedykid/clipfinder)  
[Buy me a coffee](https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD)
