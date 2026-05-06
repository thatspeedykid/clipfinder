# 🎬 ClipFinder v1.3.7
**AI-Powered Drama Clip Extractor for Streamers & Content Creators**

> Built by [@MarsScumbags](https://twitter.com/MarsScumbags) — find viral moments in seconds, not hours.

---

## ✨ What is ClipFinder?

ClipFinder watches your VODs so you don't have to. Drop in a URL or a local video, hit Find Clips, and AI analyzes the transcript — and now the video itself with Vision Mode — to surface the most viral, dramatic, and shareable moments. Fully timestamped and ready to export.

---

## 🚀 Key Features

### 🎯 Vision Mode *(v1.3.6+)*
Go beyond the transcript. Vision Mode samples frames from your video and sends them to Gemini Vision AI to understand what's *visually* happening.

- **"Girl in white shirt"** — finds her in the video
- **"Gambling/casino scenes"** — detects them visually
- **"Funny reaction moments"** — understands facial expressions and context
- **"Outdoor scenes"** — knows where they are

> ⚠️ Takes 2-5x longer than Normal mode. Best for videos under 60 minutes. Requires a Gemini API key.

### ⚡ GPU-Accelerated Transcription
| GPU | Method | Speed |
|-----|--------|-------|
| AMD RX 400+ | whisper.cpp Vulkan | ~10x realtime |
| NVIDIA GTX 900+ | whisper.cpp cuBLAS | ~8-12x realtime |
| Intel (integrated) | whisper.cpp Vulkan | ~3-5x realtime |
| CPU only | faster-whisper int8 | ~2-3x realtime |

No CUDA toolkit required — ClipFinder bundles everything it needs.

### 🤖 Multi-Provider AI with Smart Fallback
ClipFinder uses multiple free AI APIs in parallel and rotates automatically:
- **Google Gemini** (free, huge context — best for long VODs)
- **Groq** (free, fast — llama-3.3-70b with 32k context)
- **OpenRouter** (free tier, multiple models)

When one provider is rate-limited, it instantly rotates to the next — no waiting.

### ⚡ Smart Transcribe *(NEW in v1.3.7)*
Enable the **⚡ Smart Transcribe** checkbox to make whisper.cpp physically stop transcribing at your cutoff point — not just filter after the fact. "Ignore last hour" on a 109min video transcribes only 49min instead of all 109min.

Off by default. Hover over it for a tooltip.

### 📝 Smart Instructions Box
Tell the AI exactly what to find or skip:
- `ignore the last hour` — skips final hour by timestamp
- `skip gambling content` — filters gambling mentions
- `only clips of Aishah` — focuses on specific person
- `focus on drama between X and Y` — targets interactions

Time-based filtering (all modes):
- `ignore last hour` — strips final hour before AI sees transcript
- `skip last 30 minutes` — strips final 30min
- `ignore first 30 minutes` — strips opening section

In **Vision Mode**, also works for visual instructions:
- `girl in white shirt`
- `outdoor scenes only`
- `funny reaction moments`

### 🐦 Tweet Generator
Instantly generate viral tweets from any clip:
- **🔥 Hot Take** — punchy opinion/reaction angle
- **💬 Quote** — pull quote with commentary
- **📢 Announcement** — breaking news style hook
- **🤯 Exaggerate** — over-the-top multi-line storytelling

Tone modes: Drama · Tea · Breaking · Hype · Exaggerate

### 📥 Multi-Platform Downloader
Downloads from YouTube, Twitch, Kick, X/Twitter, TikTok, Instagram and more.
Supports browser cookies (Chrome/Firefox/Edge/Brave/Opera/Safari) and cookies.txt.

---

## 🛠 Installation

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases)
2. Run the installer — no Python, CUDA toolkit, or dependencies required
3. Launch ClipFinder — installs everything automatically on first run

### GPU Setup (Optional but Recommended)
- **AMD/Intel**: Settings → Core Dependencies → **Install whisper.cpp (GPU)**
- **NVIDIA**: Settings → Core Dependencies → **Install NVIDIA CUDA Support**

### AI API Keys (Free)
Settings → AI Providers — add keys for any of these:
- [Google Gemini](https://aistudio.google.com/apikey) — free, recommended, add up to 3 keys
- [Groq](https://console.groq.com) — free
- [OpenRouter](https://openrouter.ai) — free tier

---

## 📋 How to Use

### Finding Clips
1. **Video** — paste a URL or browse to a local file
2. **Instructions** — optionally tell the AI what to find or skip
3. **Mode** — Normal (transcript), Interview (Q&A format), or 🎯 Vision (visual analysis)
4. **Names** — add streamer/person names to help AI identify speakers
5. Hit **▶ FIND CLIPS** — transcription + AI runs automatically
6. Review suggestions, select clips, hit **EXPORT SELECTED**

### Tweet Generator
1. Run a transcription first (Transcript tab or after Find Clips)
2. Go to **Transcript** tab → scroll down to Tweet Generator
3. Pick a tone mode, hit **⚡ Generate Tweet**
4. Three variations appear — copy your favorite and post

### Downloader
1. Go to **Downloader** tab
2. Paste URL(s) — one per line
3. Select quality and output folder
4. Hit **⬇ Download**
5. Video auto-loads into Clip Finder after download

---

## 🔧 Settings Overview

| Setting | Description |
|---------|-------------|
| AI Providers | Add/manage Gemini, Groq, OpenRouter API keys |
| Whisper Model | tiny/base/small/medium — bigger = more accurate, slower |
| GPU Transcription | Toggle GPU on/off per run |
| Cookies | Browser selection or cookies.txt path for authenticated downloads |
| Core Dependencies | Install/update ffmpeg, whisper.cpp, Python packages |

---

## 📊 System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8GB minimum, 16GB recommended for medium/large models
- **Storage**: 2-5GB for models and packages
- **GPU**: Optional but strongly recommended
  - AMD: Vulkan-capable (RX 400 series+)
  - NVIDIA: CUDA 5.0+ (GTX 900 series+, RTX series)
- **Internet**: Required for downloads and AI API calls

---

## 🐛 Known Issues

- Instagram Stories require login cookies — use Settings → Cookies → select your browser (must be logged in to Instagram in that browser)
- Vision Mode is compute-intensive — best on videos under 60 minutes on free Gemini tier
- OpenRouter free tier has very limited context — Gemini recommended for long VODs
- First GPU transcription may take longer as model loads into VRAM

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ by [@thatspeedykid](https://github.com/thatspeedykid) for [@MarsScumbags](https://twitter.com/MarsScumbags)*

*Special thanks to [RageTear](https://x.com/Ragetear_Thex) for helping test and troubleshoot NVIDIA GPU support — fellow clipper, real one. 🙏*
