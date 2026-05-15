# ClipFinder v1.3.8
### AI-Powered Drama Clip Extractor + Social Media Post Generator

> Built for **@MarsScumbags** — the fastest way to go from raw VOD to viral post.

---

## What's New in v1.3.8 — Post Studio

ClipFinder now ships with **Post Studio**, a full social media content pipeline built directly into the app. Transcribe a clip, hit generate, and get algo-optimized posts for every platform in seconds — all grounded in the actual transcript, no hallucinations.

### 🚀 Post Studio
- **One click → 5 platforms** — X/Twitter, TikTok, Instagram, YouTube Shorts, YouTube (long)
- **Transcript-grounded** — every post is written from what was *actually* said, never hallucinated
- **Handle memory** — type a name once, handles are remembered forever across all platforms
- **Spice toggles** — 🔥 Drama · 📰 Breaking · 🤯 Exaggerate · 🎣 Clickbait
- **🔄 Regen per platform** — regenerate just one platform without touching the others
- **Auto-expanding output boxes** — boxes grow to fit content, no scrolling

### 🏆 Algo Score System (New)
Every generated post is automatically scored **1–10** against each platform's real 2026 algorithm weights:
- 🟢 **8-10** — solid, post it
- 🟡 **5-7** — decent, consider a regen
- 🔴 **1-4** — needs work, hit regen

Hover the score to see exactly why — "Missing reply-bait question", "hashtags too generic", etc. Built from the open-source xAI algorithm weights and platform-specific 2026 research.

### 📊 2026 Algorithm Research Baked In

**X/Twitter** — Reply chains score 150x a single like per the open-source xAI algorithm. Posts optimized for reply-chain bait, positive tone (Grok penalizes negativity), 1 hashtag max, zero links in post body.

**TikTok** — Caption written as a search query first. Keyword-optimized captions can push search traffic from 5% to 40% of total views. Save-bait CTA required. No hooks in caption — the video handles that.

**Instagram** — DM shares are the #1 algo signal (694,000 Reels shared via DM every minute). DM-bait and save-bait lines are mandatory. 3-5 mid-tier hashtags only — Mosseri confirmed 20-30 tags signals low quality.

**YouTube Shorts** — Title keyword-first, all elements semantically aligned per the Gemini semantic update (January 2026). Shorts can go viral weeks after posting — never delete them.

### 🔑 Smart Key Rotation
- **Groq primary** for generation (334 tokens/sec, 32k output — never truncates)
- **Gemini** reserved for transcription
- **OpenRouter** as backup
- Dynamic gap based on key count — more keys = shorter waits

---

## Core Features

### ✂ Clip Finder
AI-powered viral moment detection from Twitch, Kick, YouTube VODs and local files.

### 📝 Transcript
Full transcript with timestamps. One click to push to Post Studio.

### ⬇ Downloader
Downloads from any platform. **Duplicate clips now get `(1)`, `(2)` suffixes** — same title never fails silently again.

### 🖼 Thumbnails · 🔬 Studio · 🔇 Censor · 🎵 Music Removal
Full post-production suite for clips.

---

## Setup

1. Download `ClipFinder-Setup.exe` from [Releases](https://github.com/thatspeedykid/clipfinder/releases)
2. Run installer — torch, faster-whisper, demucs pre-bundled, no setup wait
3. Settings → add API keys:
   - **Gemini** (free — aistudio.google.com) for transcription
   - **Groq** (free — console.groq.com) for Post Studio
   - **OpenRouter** (optional)
4. Start clipping

---

*Made with 🔥 by [@MarsScumbags](https://twitter.com/MarsScumbags)*
