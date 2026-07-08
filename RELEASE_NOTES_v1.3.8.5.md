# ClipFinder v1.3.8.5

**Release date:** June 5, 2026

## Bug Fixes

### Fix 1 — Export folder auto-create
- `_do_export` now creates the output folder automatically before calling ffmpeg
- Improved error logging — destination path shown explicitly so failures are easier to diagnose

### Fix 2 — Dead AI models removed
- **Gemini:** removed `gemini-2.0-flash` (discontinued June 1 2026)
- **Groq:** removed `mixtral-8x7b-32768` (deprecated March 2025) and `llama3-8b-8192` (deprecated May 2025)
- **OpenRouter:** updated to currently-active free models — `qwen3-235b-a22b:free`, `nemotron-3-nano-30b-a3b:free`, `gemma-3-27b-it:free`, updated Llama slugs
- Fixes broken Transcript and Post Studio generation for affected providers

### Fix 3 — Whisper hallucination loops ("Go. Go. Go.")
- Added `condition_on_previous_text=False` — main culprit, was feeding looping output back as context
- Added `compression_ratio_threshold=2.4` — detects and drops repetitive segments
- Added `no_speech_threshold=0.6` — drops segments Whisper isn't confident are real speech
- Added `log_prob_threshold=-0.7` — drops garbled/low-confidence hallucinated output
- Added `vad_threshold=0.6` — more aggressively filters silence before it reaches Whisper
- Added `--no-fallback` for whisper.cpp — prevents temperature retry that generates filler hallucinations
- Applies to both whisper.cpp and faster-whisper paths

### Fix 4 — Update banner floating outside app window
- Replaced floating `Toplevel` banner with an inline `tk.Frame` at the bottom of the main window
- Banner no longer floats over other apps or outside the ClipFinder window
- Same look, stays inside the app, dismissable with ✕

## Upgrading

Existing users will receive this update automatically on next launch.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
