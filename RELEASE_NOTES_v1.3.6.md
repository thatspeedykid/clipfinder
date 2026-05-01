# ClipFinder v1.3.6 — Release Notes

**Released:** May 2026

---

## 🎯 Vision Mode — ClipFinder Can Now See Your Video

The biggest feature in v1.3.6. Normal mode reads the transcript — Vision Mode actually looks at your video.

Set your instructions to things like:
- `girl in white shirt`
- `gambling or casino scenes`
- `funny reaction moments`
- `outdoor scenes`

ClipFinder samples a frame every 30 seconds, sends them to Gemini Vision, and uses what it sees to guide clip selection. It automatically rotates through all your Gemini keys and models if one hits a limit.

> Switch to 🎯 Vision mode with the new button next to Normal/Interview. A warning will explain the tradeoffs before it runs.

---

## ⚡ NVIDIA GPU — Finally Fixed

NVIDIA GPU transcription has been completely reworked from the ground up.

**Before:** faster-whisper + ctranslate2 + cuDNN version hell = never worked reliably

**Now:** whisper.cpp cuBLAS binary — the same proven approach we use for AMD Vulkan, just the NVIDIA build. No CUDA toolkit required. No Python packages. Just your NVIDIA driver.

Go to **Settings → Core Dependencies → Install NVIDIA CUDA Support** and it downloads the ~150MB binary automatically. Works on GTX 900 series and up.

*Thanks to [RageTear](https://x.com/Ragetear_Thex) for enduring weeks of debugging to get this working.*

---

## 🤯 Exaggerate Tweet Mode

New tone mode in the Tweet Generator. Writes each tweet as a dramatic multi-line story that builds line by line:

```
🚨 STREAMER'S SECRET EXPOSED TO FAMILY 😳
She was hiding her OnlyFans from everyone 👀
Another streamer outed her to her brother 💔
Months of silence and arguments followed 💸🔥
But her success changed their tune fast ⚡

#StreamerName #Exposed #Drama
```

Pro-streamer always, never mean-spirited.

---

## 🤖 AI Improvements

- **Gemini 1.5 removed** — all 1.5 models are shut down (were causing 404 errors). Now using gemini-2.5-flash as primary
- **Groq model rotation** — when llama-3.3-70b hits rate limit, automatically tries mixtral then llama-3.1-8b instead of waiting
- **Truncated JSON repair** — when Gemini hits its token limit mid-response, ClipFinder now recovers all complete clips instead of failing the whole section
- **No more 30/60/90s waits** — providers rotate instantly on failure

---

## 📥 Instagram Downloads

Added gallery-dl as a fallback for Instagram when yt-dlp fails (Stories, private content). Installs automatically on first use.

Browser cookie support now works properly for Brave/Chrome even when the browser is open.

---

## 🛠 Bug Fixes

- Transcript tab was silently broken (KeyError on exaggerate mode) — fixed
- Files in download folder with "NA" in the name were being renamed — fixed
- Gemini was wrapping responses in ```json fences — fixed with explicit prefix instruction
- Window title bar now shows correct version number dynamically

---

## Upgrade Notes

- **Auto-updater**: If you have v1.3.5.x, the app will prompt you to update automatically
- **NVIDIA users**: After updating, go to Settings → Install NVIDIA CUDA Support to get the new cuBLAS binary
- **No breaking changes** — all existing settings, API keys, and downloaded models carry over

---

*Full changelog: [CHANGELOG.md](CHANGELOG.md)*
*Issues / feedback: [GitHub Issues](https://github.com/thatspeedykid/clipfinder/issues)*
