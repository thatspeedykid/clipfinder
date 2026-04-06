# ClipFinder v1.0 — Release Notes

**Release Date:** April 2026  
**Type:** Initial Release

---

## What's New

ClipFinder v1.0 is the first public release of the AI Drama Clip Extractor.

### Core Features
- **AI Clip Detection** — Gemini, Groq, and OpenRouter automatically find the best drama moments
- **GPU Transcription** — whisper.cpp (AMD/Intel Vulkan) + faster-whisper (NVIDIA/CPU fallback)
- **Smart Export** — 16:9, 9:16 vertical, or Both simultaneously with GPU acceleration
- **Face Tracking** — Auto-centers face for 9:16 vertical crops via MediaPipe
- **Built-in Downloader** — Kick, Twitch, YouTube, Twitter/X via yt-dlp
- **Tweet Generator** — AI-written viral tweets with Drama/Tea/Breaking/Hype tones
- **Auto Censor** — Beep, silence, or custom MP3 over banned words with word-level timestamps
- **Thumbnail Finder** — Unsplash + fallback image search
- **Studio Tab** — AI upscaling (EDSR 4x), image enhancement
- **Interview Mode** — Multi-speaker clip detection with name tracking
- **One-click dependency installer** — ffmpeg, whisper.cpp, AI packages via Settings

### Technical
- Embedded Python 3.12 — no Python install required for end users
- Packages install to `AppData\Local\ClipFinder\pkgs\` — survive across updates
- AMD AMF / NVIDIA NVENC / Intel QSV GPU export acceleration
- Config and API keys preserved across reinstalls

---

## Known Issues

The following bugs are confirmed and will be fixed in v1.1:

- **Both export only outputs 16:9** — selecting Both (16:9 + 9:16) only saves the horizontal version. Vertical is skipped. Same issue affects censor export.
- **Update All permission errors** — updating packages while the app is running causes `[WinError 5] Access is denied` on locked `.pyd` files (affects google-genai, curl-cffi, opencv, soundfile, requests). Workaround: close and reopen ClipFinder then update.
- **imagehash not detected** in Core Dependencies panel even after successful install.
- **Double Install All button** — two buttons appear in Update Modules section, only one works.
- **Progress bar mismatch** — top bar shows "9/14 updated" but bottom shows "All packages updated (9/14)" — confusing wording.
- **Settings missing browse buttons** — Default Output and Download folder fields have no browse button.
- **Transcript log button unresponsive** — clicking the log toggle in Transcript tab does nothing.
- **Whisper auto model** — selecting Auto whisper model caused a 404 error trying to download `ggml-auto.bin`. Fixed in current `.py` but not yet in installer build.
- **Slow first launch** — encoder detection runs on startup causing a brief delay before UI is responsive.

---

## Installation

1. Download `ClipFinder_Setup.exe`
2. Run installer — installs to `AppData\Local\ClipFinder\` (no admin required)
3. Desktop + Start Menu shortcuts created
4. First launch: go to **⚙ Settings → API Keys** and add at least one free key

## System Requirements

- Windows 10/11 64-bit
- 4GB RAM minimum (8GB recommended for larger models)
- Internet connection for first-time package downloads
