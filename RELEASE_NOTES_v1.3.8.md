# ClipFinder v1.3.8 — Post Studio

## 🚀 Post Studio — Social Media Post Generator

The biggest feature drop yet. **Post Studio** is a full social media content pipeline built directly into ClipFinder. Go from raw VOD to viral posts across 5 platforms in under 60 seconds.

### How it works
1. Load your transcript (from current clip, paste it, or transcribe a video right in the tab)
2. Add the person's name — handles auto-fill from memory or get looked up automatically
3. Hit ⚡ GENERATE POSTS
4. Get complete, ready-to-paste posts for X, TikTok, Instagram, YT Shorts, and YouTube

Every post is grounded in your actual transcript. No hallucinations, no generic AI slop.

---

## 🏆 Algo Score System

Every post gets automatically scored 1–10 after generation based on each platform's real 2026 algorithm weights.

- **⬤ 8-10** green — ready to post
- **⬤ 5-7** yellow — solid but could be better
- **⬤ 1-4** red — hit that 🔄 Regen button

Hover the score badge to see the exact reason. Built from the open-source xAI algorithm repository and platform-specific research across all four platforms.

---

## 📊 2026 Algo Rules Per Platform

**X/Twitter**
- Reply chains score 150x a single like (confirmed xAI algorithm weights)
- Groq-powered for short punchy text — fastest generation
- Positive tone enforced (Grok actively reduces visibility for negative content)
- 1 hashtag, zero links in post body, reply-bait question mandatory

**TikTok**
- Caption = search query first — search now drives up to 40% of views
- Keywords matched to actual transcript content
- No hooks in caption (the video does that job)
- Save-bait CTA every time

**Instagram**
- DM-bait mandatory — 694,000 Reels shared via DM every minute, it's the #1 signal
- Save-bait mandatory — carries more algorithmic weight than likes
- 3-5 mid-tier hashtags (Mosseri: 20-30 tags = low quality signal)
- Handle woven into sentence naturally, not just tagged at end

**YouTube Shorts**
- Title keyword-first (what people actually search)
- Title/description/tags semantically aligned — Gemini semantic update Jan 2026
- Separate Shorts and long-form YouTube modes

---

## 🔑 Smart Multi-Key Generation

- **Groq primary** for all Post Studio generation — 334 tokens/sec, 32k output limit, never truncates
- **Gemini reserved for transcription** — stops rate limit conflicts between generation and transcription
- **OpenRouter** in rotation as backup
- Dynamic wait gap between calls based on number of available keys
- All Gemini + Groq + OpenRouter keys share load automatically

---

## 🐛 Bug Fixes

**Downloader — Duplicate clip names**
Same-named clips no longer get silently skipped. Downloads use a temp filename, then get renamed with `(1)`, `(2)` etc. Download the same VOD 10 times — they all save.

**Installer — Pre-bundled packages**
`torch`, `faster-whisper`, `demucs` and `openai-whisper` are bundled directly in the installer. Fresh Windows installs work immediately with no missing package errors.

---

> Note: Installer is ~2-3GB due to pre-bundled torch CPU wheels. One-time download.
