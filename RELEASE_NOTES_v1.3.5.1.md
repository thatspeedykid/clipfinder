# ✂ ClipFinder v1.3.5.1 — Hotfix

> Package installation fixes for fresh installs on Windows.

---

## ⬇️ Update

**Existing users:** Click **⬇ Download Now** in the orange banner — the app updates itself.  
**New install:** Download `ClipFinder-Setup.exe` from Releases.

---

## 🐛 Fixes

### demucs / openai-whisper not installing on fresh installs
`setuptools` is now the first package installed in the prelaunch splash. On some Windows 11 machines it was missing, causing `Cannot import 'setuptools.build_meta'` which silently blocked demucs and openai-whisper from installing at all.

### Package status showing gray when packages ARE installed
`demucs`, `openai-whisper`, `torch`, `torchaudio`, `mediapipe` and `faster-whisper` were being checked by trying to import them — which fails in isolation because they need their full dependency chain loaded first. Now checks for the dist-info folder directly in ClipFinder's pkgs directory instead.

### Prelaunch missing package detection fixed
Previously used system-wide `__import__()` checks which could succeed even when the package wasn't in ClipFinder's own pkgs folder. Now checks dist-info in PKGS_DIR specifically, so truly missing packages are always caught and reinstalled.

### Demucs incomplete install error
If demucs installs but is missing submodules (`No module named 'demucs.__main__'`), the error now shows a clear message: *"Go to Settings → Update Modules → Update All Packages, then restart ClipFinder"* instead of a raw 50-line traceback.

---

*[@MarsScumbags](https://x.com/MarsScumbags)*
