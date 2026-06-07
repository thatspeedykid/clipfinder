<div align="center">

<img src="assets/clipfinder_logo_512.png" width="120" alt="ClipFinder Logo"/>

# ClipFinder
### AI-Powered Clip Extractor & Social Media Engine
#### by [@MarsScumbags](https://linktr.ee/marsscumbags)

[![Version](https://img.shields.io/badge/version-1.3.8.4-orange)](https://github.com/thatspeedykid/clipfinder/releases)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/thatspeedykid/clipfinder/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Go from raw VOD to viral clip to posted content — without leaving the app.**

[⬇ Download](https://github.com/thatspeedykid/clipfinder/releases/latest) · [🐛 Report Bug](https://github.com/thatspeedykid/clipfinder/issues) · [Follow @MarsScumbags](https://linktr.ee/marsscumbags)

</div>

---

## What is ClipFinder?

ClipFinder is a Windows desktop app that uses AI to find, cut, process, and post viral moments from streaming VODs. It handles the entire workflow — from raw Twitch/Kick/YouTube VOD to ready-to-post social content — in one place.

Built by a drama content creator, for drama content creators.

---

## Screenshots

<table>
  <tr>
    <td align="center"><img src="assets/screenshot_1_clipfinder.png" width="400" alt="Clip Finder"/><br/><sub><b>Clip Finder</b></sub></td>
    <td align="center"><img src="assets/screenshot_2_clipfinder.png" width="400" alt="Transcript"/><br/><sub><b>Transcript</b></sub></td>
  </tr>
  <tr>
    <td align="center"><img src="assets/screenshot_3_clipfinder.png" width="400" alt="Post Studio"/><br/><sub><b>Post Studio</b></sub></td>
    <td align="center"><img src="assets/screenshot_4_clipfinder.png" width="400" alt="Settings"/><br/><sub><b>Settings</b></sub></td>
  </tr>
</table>

---

## ✂ Clip Finder

The core feature. Point it at a VOD URL or local file and it finds the best clips automatically.

- **AI clip detection** — finds the most viral/interesting moments using AI transcript analysis
- **Supports Twitch, Kick, YouTube, and local video files**
- **Vision Mode** — optionally excludes gambling/casino segments automatically using image detection
- **Smart transcription** — uses whisper.cpp with GPU acceleration (CUDA/ROCm/Vulkan) or falls back to CPU
- **Configurable clip length** — set min/max duration per clip
- **Batch export** — process multiple clips at once
- **Load into other tabs** — one click to send any clip to Censor, Music Removal, or Post Studio

---

## 🚀 Post Studio

Generate algo-optimized social posts from any clip transcript in seconds. Every post is grounded in what was actually said — no hallucinations, no generic AI slop.

### Platforms
| Platform | What it does |
|----------|-------------|
| **𝕏 Twitter** | Reply-bait question, handle in sentence, positive tone, 1 hashtag, 280 chars |
| **🎵 TikTok** | SEO search phrase first, save-bait CTA, niche hashtags, no hooks |
| **📸 Instagram** | DM-bait mandatory, save-bait mandatory, handle woven into sentence |
| **▶ YT Shorts** | Keyword-first title, 3 hashtags, semantically aligned |
| **▶ YouTube** | Full title + description + 10 tags, channel plug |

### Features
- **Handle memory** — type a name once, handles auto-save and auto-fill forever
- **Auto handle lookup** — Gemini looks up handles automatically if not saved
- **🔄 Regen per platform** — not happy with Instagram? Regenerate just that one
- **Spice toggles** — 🔥 Drama · 📰 Breaking · 🤯 Exaggerate · 🎣 Clickbait
- **Auto-expanding output boxes** — no scrolling, boxes grow to fit content

### 🏆 Algo Score System
Every generated post gets scored **1–10** after generation, based on the actual 2026 platform algorithm weights:
- 🟢 **8-10** — solid, post it now
- 🟡 **5-7** — decent, maybe regen
- 🔴 **1-4** — needs work, hit regen

Hover any score badge to see *exactly* why it scored that way. Built from the open-source xAI algorithm repo and 2026 research across all platforms.

### 2026 Algo Rules Baked In
**X/Twitter** — Reply chains score 150x a single like per the xAI algorithm. Grok actively penalizes negative tone. Zero links, 1 hashtag, reply-bait question mandatory.

**TikTok** — Keyword-optimized captions can push search traffic from 5% to 40% of views. No hooks in caption. Save-bait CTA required.

**Instagram** — 694,000 Reels are shared via DM every minute — DM-bait is the #1 algo signal. Save-bait mandatory. 3-5 mid-tier hashtags only.

**YouTube** — Title keyword-first, all elements semantically aligned per the Gemini update (January 2026).

### Smart Key Rotation
- **Groq primary** for generation — 334 tokens/sec, 32k output, never truncates
- **Gemini reserved** for transcription so it's never rate limited during generation
- **OpenRouter** as backup
- Multiple keys per provider rotate automatically — more keys = faster generation

---

## 📝 Transcript

- **Full transcript view** with timestamps from any clip
- **One click** to push transcript to Post Studio
- **Transcribe any video** right in the tab — load and go
- Uses whisper.cpp GPU by default, falls back to faster-whisper → openai-whisper

---

## ⬇ Downloader

Download clips from any platform directly in the app.

- **Supports Twitch, Kick, YouTube, Twitter/X, TikTok, Instagram**
- **Queue multiple downloads** — paste URLs one per line
- **Auto cookie support** — drops a cookies.txt for authenticated downloads
- **Duplicate handling** — same-named clips get `(1)`, `(2)` suffixes automatically, never silently fails
- **Gallery-dl fallback** for platforms that need it

---

## 🖼 Thumbnails

- Generate custom thumbnails for clips using AI image generation
- Multiple aspect ratios (16:9, 9:16, 1:1)
- Batch thumbnail creation

---

## 🔬 Studio

Clip management and enhancement tools.

- **Duplicate Finder** — scans a folder for duplicate/similar images and moves them to `/duplicates`
- **Sensitivity control** — Exact only, Similar, or Very similar matching
- **AI Upscaler** — Real-ESRGAN upscaling, runs fully locally after first install
- **Scale options** — 2x, 3x, or 4x upscale
- **Batch input** — load up to 5 images at once

---

## 🔇 Censor

AI-powered automatic profanity censoring.

- **Automatic word detection** — transcribes and finds profanity automatically
- **Custom word list** — add words to censor beyond the defaults
- **Bleep or mute** — choose your censoring style
- **Batch processing** — censor multiple files at once
- **Precise timing** — word-level timestamps for surgical censoring, no over-cutting

---

## 🎵 Music Removal

Remove background music while keeping vocals using Demucs AI.

- **HTDemucs model** — Meta's state-of-the-art source separation
- **Keep vocals only** — or keep other stems too
- **Batch processing** — queue multiple files
- **GPU accelerated** where available

---

## ⚙ Settings

- **Multi-provider API key management** — Gemini, Groq, OpenRouter, each with multiple keys
- **Auto-install** — all AI packages install automatically on first launch
- **whisper.cpp GPU** — install CUDA/ROCm/Vulkan whisper.cpp directly from settings
- **Whisper model selector** — tiny/base/small/medium/large
- **Output folder configuration**
- **Vision Mode** — configure casino/gambling detection reference images
- **Auto-update** — checks for new versions on launch

---

## Setup

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases/latest)
2. Run the installer — torch, faster-whisper, and demucs are **pre-bundled** (no setup wait)
3. Launch ClipFinder
4. Go to **Settings** → add API keys:
   - **[Gemini](https://aistudio.google.com)** (free) — transcription + AI clip detection
   - **[Groq](https://console.groq.com)** (free) — Post Studio generation
   - **[OpenRouter](https://openrouter.ai)** (optional) — backup provider
5. Paste a VOD URL → hit **▶ FIND CLIPS**

> **Note:** Installer is ~2-3GB due to pre-bundled AI models (torch CPU, faster-whisper, demucs). This is a one-time download — no waiting on first launch.

---

## Requirements

- **OS:** Windows 10 / 11
- **RAM:** 8GB+ recommended (16GB for larger models)
- **GPU:** Optional but recommended for transcription speed (NVIDIA/AMD/Intel)
- **Disk:** ~3GB for install + space for your clips

---

## Follow MarsScumbags

| Platform | Link |
|----------|------|
| 𝕏 Twitter | [@MarsScumbags](https://x.com/MarsScumbags) |
| TikTok | [@marsscumbags](https://tiktok.com/@marsscumbags) |
| YouTube | [@MarsScumbags](https://youtube.com/@MarsScumbags) |
| Instagram | [@marsscumbags](https://instagram.com/marsscumbags) |
| All links | [linktr.ee/marsscumbags](https://linktr.ee/marsscumbags) |

---

*ClipFinder is built for the streaming drama community. If it helps your channel, give a follow — that's all the payment needed.* 🔥
