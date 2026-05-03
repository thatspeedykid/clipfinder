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

---

## v1.3.6.1 — May 2026

### 🏗 Cross-Platform Architecture
- Extracted `clipfinder_core.py` — shared AI logic, prompts, transcription, and analysis
- Windows behavior unchanged — core is imported transparently
- Lays groundwork for upcoming Mac and Linux releases
- App launches slightly faster — Python caches core module as `.pyc` separately
- Auto-updater now downloads `clipfinder_core.py` alongside `clipfinder.py`
- Graceful fallback if `clipfinder_core.py` missing — old shortcuts never break
- NSIS installer updated to bundle `clipfinder_core.py`

### 🐛 Bug Fixes
- **Decommissioned models**: Auto-detected and permanently removed when API returns 400 decommissioned — never retried across sessions. Applies to Groq, Gemini, OpenRouter
- **mixtral-8x7b-32768**: Pre-removed from Groq model list (decommissioned by Groq)
- **OpenCV numpy spam**: Fixed by adding pkgs to sys.path at line 3, before any imports
- **_ensure_tab_built NameError**: Fixed — now correctly uses self._ensure_tab_built with hasattr guard
- **Dead models persistence**: Saved to clipfinder_config.json, loaded on every startup

---

## v1.3.7 — May 2026

### 🚀 Auto-Bootstrap System (Cross-Version Update Fix)
- App now checks for `clipfinder_core.py` on EVERY launch before the window opens
- If missing or outdated: shows a mini splash screen, downloads core from GitHub, restarts automatically
- Users on any older version get core + vision_refs delivered automatically on next launch
- No manual action needed — seamless upgrade for everyone
- Also checks if `clipfinder.py` is newer than `clipfinder_core.py` — forces re-download if outdated
- Default vision reference images (Stake, Roobet, Rainbet) auto-downloaded to `vision_refs/` in background

### 🎯 Vision Mode — Pre-Filter Transcript (Major Improvement)
- Vision Mode now strips excluded content FROM the transcript before sending to AI
- Gambling sections identified visually → those transcript lines removed entirely
- AI never sees the excluded content → cleaner clips, faster processing, fewer tokens
- Consecutive excluded timestamps merged into continuous blocks (±3min gap = same block)
- 60s padding added before/after each excluded block for safety
- Log now shows: `🎯 Excluding 2 gambling block(s): 34:00-37:00, 44:30-50:00`
- Progress bar shows: `⏳ Vision filtered transcript — AI finding clips... (may look frozen, let it run)`

### ⚡ Smart Transcribe (NEW)
- New checkbox next to mode buttons: `⚡ Smart Transcribe`
- Off by default — opt in consciously
- When enabled: parses instructions for time cutoffs, passes `-d` flag to whisper.cpp
- Whisper.cpp physically stops transcribing at the cutoff — genuinely faster
- Example: "ignore last hour" on a 109min video → whisper stops at 49min (~2x faster)
- Hover over checkbox for tooltip explaining what it does

### 📋 Instruction-Based Transcript Filtering
- All modes now parse instructions for time-based filters before sending to AI
- Supported phrases:
  - `ignore last hour` / `ignore the last hour` / `skip last hour`
  - `ignore last 30 minutes` / `skip last 2 hours`
  - `ignore first 30 minutes` / `skip first hour`
- Log shows: `📋 Instruction filter: skipping last 1 hour → transcript ends at 1:09:00`
- Works in Normal, Interview, and Vision modes
- Fixed: filter now correctly updates `full_text` sent to AI (was using stale variable)

### 🎯 Vision Mode Reference Images
- New section in Settings: `🎯 Vision Mode — Reference Images` (above Update Modules)
- `📁 Open Reference Images Folder` button — drop screenshots to teach Vision what to find/avoid
- `🔍 Scan & Label New Images` — Gemini Vision auto-identifies and renames images
- Default references bundled: Stake, Roobet, Rainbet casino logos
- NSIS installer now bundles `vision_refs/` folder with default images

### 🤖 AI Provider Improvements
- Removed `gemini-2.0-flash` — deprecated, shuts down June 1 2026
- Model list now: `gemini-2.5-flash → gemini-2.5-flash-lite`
- Vision Mode progressive fallback: 30 frames → 15 frames → 10 frames on failure
- Fixed JSON fence stripping for Vision Mode responses (MULTILINE regex)
- Fixed frame count: hard cap of 60 applied before extraction, reduced to 30 with reference images

### 🛠 Bug Fixes
- Fixed `full_text = transcript` using unfiltered transcript (instruction filter had no effect)
- Fixed regex not matching `"ignore the last hour"` (no number pattern added)
- Fixed `_ref_images` used before assignment (scope error in Vision Mode)
- Fixed provider status flickering — debounced to 300ms, auto-refresh changed to 5 minutes
- Added manual `↺ Refresh Status` button in AI Provider Status section
- Startup lag reduced — prebuild deferred to 4s, provider refresh to 1.5s/2s
