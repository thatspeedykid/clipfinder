# Changelog

## v1.1 — Coming Soon

### New Features
- Hybrid clip detection — FFmpeg audio energy analysis fed into AI for smarter clip selection
- In-app update checker — silent GitHub check on launch, non-intrusive bottom bar notification
- Donate button in Settings footer
- App icon in header

### Bug Fixes
- Both export (16:9 + 9:16) now correctly exports both formats including with censor
- Update All permission errors fixed for locked .pyd files
- imagehash correctly detected in Core Dependencies after install
- Single smart Install/Update button in Update Modules
- Progress bar and status message count mismatch fixed
- Browse buttons added for default output and download folders in Settings
- Transcript log button fixed
- Whisper auto model no longer tries to download non-existent ggml-auto.bin

---

## v1.0 — April 2026 — Initial Release

### Features
- AI clip detection using Gemini, Groq, and OpenRouter
- GPU transcription — whisper.cpp (AMD/Intel Vulkan) + faster-whisper (NVIDIA/CPU)
- Export 16:9, 9:16 vertical, or both simultaneously
- Face tracking for vertical 9:16 crop via MediaPipe
- Built-in downloader — Kick, Twitch, YouTube, Twitter/X
- Tweet generator with Drama / Tea / Breaking / Hype tones
- Auto-censor — beep, silence, or custom MP3
- Thumbnail finder via Unsplash
- Studio tab — AI upscaling (EDSR 4x)
- Interview mode — multi-speaker clip detection
- One-click dependency installer in Settings
- AMD AMF / NVIDIA NVENC / Intel QSV GPU export acceleration
- No Python required — embedded Python 3.12 bundled

### Known Issues (fixed in v1.1)
- Both export only saves horizontal version
- Update All permission errors on locked packages while app is running
- imagehash not detected in deps panel after install
- Double Install All button in Update Modules
- Progress bar / status message count mismatch
- Settings missing browse buttons for output folders
- Transcript log button unresponsive
- Whisper auto model caused 404 error on ggml-auto.bin
