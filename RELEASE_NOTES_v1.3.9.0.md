# ClipFinder v1.3.9.0

**Release date:** July 7, 2026

A stability + clip-quality release: the AI model lists are refreshed and verified, clip selection is meaningfully smarter, the launch freeze is gone, and two auto-updater crashes are fixed.

## What's New

### ✂️ Better Clips
Clip selection got a real upgrade beyond just the prompt:
- **Clean cuts** — clips now snap to actual sentence boundaries, so they no longer start or end mid-word or mid-thought.
- **Correct length, guaranteed** — the 60–160 second rule is now enforced in code. Short clips are extended toward the ideal length, over-long ones are trimmed, and clips that can't form a real moment are dropped.
- **No more duplicates** — clips that overlap heavily (found by different providers or in different sections) are merged, keeping the best-scored version.
- **Best clips first** — results are ranked by score, then by their hook / engagement / value / shareability sub-scores.

### 🤖 Refreshed AI Models
- Dead Groq models that were throwing errors (`llama-3.1-70b-versatile`, `llama3-8b-8192`) removed.
- Added `openai/gpt-oss-120b` / `gpt-oss-20b` so the app keeps working after the current Llama models are retired in August 2026.
- OpenRouter list cleaned of nonexistent IDs and updated to current free models (Qwen3-Next 80B, Gemma 4, Nemotron).
- Every model ID checked against the live provider catalogs.

## Bug Fixes

- **Auto-updater fixed** — two crashes that caused "Download Now" to fail for some users (depending on how a release was packaged and where the app was installed) are resolved.
- **Whisper hallucinations fixed** — the repeated "Go. Go. Go." style loops in transcripts are suppressed.
- **~5-second launch freeze fixed** — the app no longer loads the entire AI/ML stack on startup just to check what's installed. It opens fast now.
- **Provider info now displays** — the "Get free key" link and provider notes that never showed up are fixed.
- **Cleaner logs** — a transcript section with no clip-worthy moment is no longer reported as a red error.
- **Readable text** — secondary UI text that was too dark to read comfortably is fixed.

## Upgrading

⚠️ **One-time manual update may be needed.** The auto-updater fixes only apply from v1.3.9.0 forward. If you're on an older version and "Download Now" fails, download this release manually **once** — after that, auto-update will work normally.

Existing users otherwise receive this update automatically on next launch.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
