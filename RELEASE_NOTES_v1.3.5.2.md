# ✂ ClipFinder v1.3.5.2 — Hotfix

> Fix for broken AI provider imports on some Windows machines.

## 🐛 Fixes

- **`ImportError: cannot import name 'Groq' from 'groq' (unknown location)`** — Python was loading a cached broken version of groq/openai/google-genai from an unknown system location instead of ClipFinder's own packages. Now clears `sys.modules` cache for all provider packages before every import, forcing a fresh load from the correct PKGS_DIR.
- All provider imports (Groq, OpenAI, OpenRouter, Gemini) now wrapped in try/except with clear error messages pointing to Update All Packages.
- `_ensure_pkgs_on_path()` now always puts PKGS_DIR at position 0 (not just if missing) and calls `importlib.invalidate_caches()` every time.

## ⬆️ Update

Click **⬇ Download Now** in the orange banner, or go to **Settings → Update Modules → Update All Packages**.

*[@MarsScumbags](https://x.com/MarsScumbags)*
