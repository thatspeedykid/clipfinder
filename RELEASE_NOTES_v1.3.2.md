# ✂ ClipFinder v1.3.2

> **Self-installing. Batch downloads. No more setup headaches.**

---

## ⬇️ Install / Update

| | |
|---|---|
| **New install** | Run `ClipFinder-Setup.exe` below ↓ |
| **Existing users** | Click **⬇ Download Now** in the orange banner inside the app, or update `clipfinder.py` directly |

---

## 🚀 What's New

### Everything Installs Automatically
On first launch you'll see this:

```
┌──────────────────────────────────────────┐
│  ✂  ClipFinder                           │
│  Installing 19 packages...               │
│  ████████████░░░░  (8/19) torch          │
│  (background processes are hidden)       │
└──────────────────────────────────────────┘
```

ClipFinder downloads and installs torch, faster-whisper, demucs, groq, and everything else automatically. Takes 2–5 minutes. After that, every launch is instant.

### Batch Download Queue
New queue box at the top of the Downloader tab. Paste a list of URLs, hit **Download Queue** — runs them all in order automatically.

### Bug Fixes
- **Kick clips working** — curl_cffi broken submodule errors (`aio`, `const`) resolved
- **Censor tab working** — WhisperModel typo that was crashing word-level transcription fixed
- **groq / tweet gen working** — pydantic_core corruption auto-repaired on launch
- **No more WinError 5** — all package updates run in a fresh subprocess, zero file lock errors
- **Download cancel works** — clears progress bar, stops queue
- **Update banner stays** — doesn't disappear when you minimize

---

*[@MarsScumbags](https://x.com/MarsScumbags) · [Full Changelog](CHANGELOG.md)*
