# ClipFinder v1.3.7.1 — Hotfix

## 🔧 Pre-bundled Packages (Fix for fresh Windows installs)

Faster-whisper, openai-whisper, demucs, and torch are now **pre-installed in the installer** — no more failed installs on fresh Windows.

Previously these would fail to install automatically due to:
- torch requiring specific index URLs not used by default pip
- demucs depending on torch being present first
- Large download timeouts on first launch

Now they're bundled directly — transcription and music removal work immediately after install with zero setup.

Everything else (Gemini, Groq, yt-dlp, etc) still auto-installs in the background on first launch as before.

> Note: Installer is larger (~2-3GB) due to bundled torch CPU wheels. This is a one-time download.
