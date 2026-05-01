# ClipFinder Changelog

## v1.3.6 — May 2026

### 🎯 Vision Mode (NEW)
- Added **🎯 Vision Mode** button next to Normal/Interview
- Samples video frames every 30 seconds and sends to Gemini Vision API for visual analysis
- Can detect clothing ("girl in white shirt"), scenes ("outdoor"), content type ("gambling"), emotions ("funny reaction moments") — anything visual that transcript can't see
- Instructions box placeholder updates automatically based on selected mode:
  - Normal: `ignore last hour · skip gambling · focus on drama · only clips of [name] (transcript-based only)`
  - Vision: `girl in white shirt · gambling scenes · outdoor moments · funny reactions (visual AI — sees the video)`
- Automatically rotates through all Gemini keys AND all models (2.5-flash → 2.5-flash-lite → 2.0-flash) on 503/429 errors
- Falls back gracefully to normal transcript analysis if Vision Mode fails
- Warning popup on first click explains tradeoffs (2-5x slower, uses Gemini quota)

### ⚡ GPU Transcription — NVIDIA (Complete Rework)
- Completely reworked NVIDIA GPU support — replaced faster-whisper/ctranslate2 entirely
- Now uses **whisper.cpp cuBLAS binary** — same proven approach as AMD Vulkan, just NVIDIA build
- No CUDA toolkit required — only needs NVIDIA GPU driver
- Settings → **Install NVIDIA CUDA Support** downloads ~150MB cuBLAS binary automatically
- Eliminates ctranslate2/cuDNN version compatibility issues permanently
- Supports GTX 900 series and newer (CUDA Compute Capability 5.0+)
- Transcript tab also uses GPU transcription (same code path as Clip Finder tab)

### ⚡ GPU Transcription — AMD Vulkan (Fixes)
- Fixed whisper.cpp binary download — now correctly downloads Vulkan build with ggml-vulkan.dll
- Added ggml-vulkan.dll verification after extraction — auto-retries with correct binary if missing
- Fixed unsupported flags (-ngl, --gpu-device) that caused whisper.cpp to exit silently
- Fixed cancelled flag so reader threads stop immediately on cancel/close
- Whisper process now killed properly when app closes
- RX 6600 XT confirmed working at 73% GPU, ~10min for 106min video with medium model
- Emulated progress bar for whisper.cpp (estimates based on ~0.35x realtime for GPU)
- Whisper.cpp stderr now shown in ClipFinder log window for debugging

### 🤖 AI Provider Improvements
- **Gemini**: Removed dead gemini-1.5-flash-latest model (404 — permanently shut down)
- **Gemini**: Updated model list to gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash
- **Gemini**: 404 errors now caught and fall through to next model
- **Gemini**: max_output_tokens raised from 4096 → 8192 across all calls
- **Gemini**: Added JSON-only instruction prefix to every call to reduce markdown fence wrapping
- **Groq**: Reordered models — llama-3.3-70b-versatile first (32k context) instead of 8b
- **Groq**: Model rotation on 429 — tries next model instead of hammering same model
- **All providers**: Removed 30/60/90s waits — immediately tries next provider on failure

### 📝 JSON Parser Improvements
- Added intelligent truncated JSON repair — tracks bracket depth to extract all complete objects
- Even when Gemini hits token limit mid-response, recovers all clips written before cutoff
- Parser now handles responses starting with [ directly (no fences) correctly
- Strips ALL markdown fence variants (```json, ```JSON, bare ```)

### 📝 Instructions Box (formerly Context)
- Renamed "Context:" → "Instructions:" in Clip Finder tab
- Mode-aware placeholder text that changes when switching modes
- Instructions sent at TOP and BOTTOM of AI prompt as MANDATORY EDITOR INSTRUCTIONS
- Time-range filtering, topic filtering, and person filtering all work via transcript text
- Visual instructions work in Vision Mode only

### 🐦 Tweet Generator Improvements
- Tabs renamed: Option 1/2/3 → Hot Take / Quote / Announcement
- All 3 tabs now use the same selected tone with different angles
- Added Exaggerate mode — multi-line storytelling format with escalating drama
- Fixed KeyError crash that silently broke the Transcript tab
- Removed hardcoded streamer names from hashtag rules (was hallucinating Mizkif/KSI/xQc)
- Hashtags now only use names actually mentioned in the transcript

### 📥 Downloader Improvements
- **Instagram**: Added gallery-dl fallback when yt-dlp fails (Stories/private content)
- **Instagram**: Skips web client — goes straight to best[ext=mp4] with cookies
- **Instagram**: Friendly error messages for login required and locked browser cookie DB
- **Browser cookies**: Supported browsers: Chrome, Firefox, Edge, Brave, Opera, Safari
- **File renaming**: Fixed bug where ANY file containing "NA" in folder got renamed
- File renaming now only touches the specific downloaded file

### 🎬 Clip Finding Improvements
- Added UNIQUENESS rule: every clip must be a different moment with a different title
- Clips spread across full transcript — different timestamps, topics, people

### 🛠 Bug Fixes
- Fixed Transcript tab not loading (KeyError in _refresh_tweet_tones)
- Fixed _ensure_tab_built NameError on Settings tab click
- Fixed download auto-load path not sticking after tab switch
- Fixed Demucs launcher UTF-8 encoding error
- Fixed duplicate except clause in rename logic
- Fixed Vision Mode not finding Gemini keys
- Added os.add_dll_directory() for proper Windows DLL search path
- Log window right-click menu: Copy Selection / Copy All / Clear Log

---

## Contributors
- [RageTear](https://x.com/Ragetear_Thex) — NVIDIA GPU testing and troubleshooting for v1.3.6

---

## v1.3.5.x — April 2026
- Initial whisper.cpp Vulkan GPU support for AMD/Intel
- NVIDIA CUDA via faster-whisper (replaced in v1.3.6)
- Multi-key Gemini support with key rotation
- Parallel AI dispatch across providers
- Interview mode, censor tab, subtitle burning
- Auto-updater via GitHub releases
