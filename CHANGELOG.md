# ClipFinder Changelog

## v1.2 — April 2026 — Stable Release

### New Features
- Auto Edit sub-tab inside Clip Finder — Whisper transcription + word-boundary silence cuts + CRF encode
- Auto Edit button in clip export bar — silence removal on selected AI-found clips
- VOD Mode in Downloader — 8x concurrent fragments, auto vod/ subfolder, toggle + auto-detect
- Smart Auto Whisper — picks tiny/base/small/medium based on video duration + GPU
- Floating log panel — Toplevel overlay, stays on top, buffers 500 messages, all tabs
- Floating update notification — numeric version compare, only shows when newer version exists
- 2-column clip grid — wider cards, readable titles and descriptions
- Smart file naming — Streamer/Title - ClipFinder - Part N.mp4 for all exports
- Kick API filename — pulls streamer slug + clip title from Kick API v2
- Unified API key layout — all 4 providers identical row layout, correct order
- Tabs stretched to fill full width
- Tab colors — selected orange/black, unselected dark/orange
- Sub-tabs inside Clip Finder — AI Clips | Auto Edit switcher
- Version shown in header (v1.2) and status bar (ClipFinder 1.2 · @MarsScumbags)
- Window icon fix — loads clipfinder.ico directly, no temp file race condition

### Bug Fixes
- AI response parsing — multiline code fence stripping with re.MULTILINE
- Output folder persists on restart via trace_add
- Transcript tab no longer requires output folder (need_outdir=False)
- Whisper auto model maps to base, not ggml-auto.bin
- mediapipe 0.10+ API compatibility
- Audio energy analysis vid variable scope fixed
- Both export (16:9 + 9:16) fixed for censor mode
- imagehash detection fixed in Core Dependencies
- Update All permission errors fixed for locked .pyd files
- Duration detection uses ffmpeg stderr (works on all file types)

### Known Issues
- Censor queue not processing queued videos
- Auto Edit transcription returns 0 words on some files (falls back to energy peaks)

---

## v1.1 — April 2026

### New Features
- Hybrid clip detection — FFmpeg audio energy peaks + AI scoring
- In-app update checker — silent check on launch
- Donate button in Settings
- App icon in header

### Bug Fixes
- Both export (16:9 + 9:16) fixed
- Browse buttons for output/download folders in Settings
- imagehash detection fixed
- Permission errors on Update All
- Cookies status live-updating in Downloader

---

## v1.0 — April 2026 — Initial Release

- AI clip detection via Gemini, Groq, OpenRouter
- GPU transcription — AMD/Intel Vulkan via whisper.cpp, NVIDIA CUDA via faster-whisper
- 16:9 and 9:16 export with mediapipe face tracking
- Built-in downloader — Kick, Twitch, YouTube, Twitter/X via yt-dlp
- Tweet generator — Drama/Tea/Breaking/Hype tones
- Auto-censor — beep, silence, custom MP3
- Studio tab — AI upscaling EDSR 4x
- Interview mode — multi-speaker detection
- One-click dependency installer in Settings
