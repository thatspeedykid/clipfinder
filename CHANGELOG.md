# ClipFinder Changelog

## v1.4.0.0 — September 2026 (the revamp)

### 🔄 Update system (rewritten)
- Package registry with per-package policy (latest / compatible range / keep), groups that must move together (pydantic + pydantic-core, numba + llvmlite, …), protected packages, conflict detection and one-click Repair
- Updates are **staged, import-tested in isolation and swapped in at the next start** (RECORD-driven file moves, rollback on failure); single-instance lock so a running copy is never updated underneath itself
- App self-update: validated `clipfinder.py`, timestamped backup, one-click rollback, auto-rollback guard if the new version fails to start; background update check
- Isolated **Demucs engine** (own venv with its own PyTorch) instead of importing torch/demucs into the app process
- Settings → **Update Center** replaces "Update All Packages"; yt-dlp is no longer hard-pinned; `curl-cffi` range 0.10–0.16; startup installs only what is missing

### ⬇️ Downloader
- **Kick VOD/clip downloads fixed** for the new UUIDv7 ids and `web.kick.com` API (Chrome-impersonated requests, public HLS master)
- **YouTube:** JS runtime for yt-dlp (Node ≥ 22, portable Node 24 downloaded on demand; ignores the EOL Node 20 older builds installed); removed ios/web client hacks and the bgutil plugin
- Audio-only downloads no longer forced through `-c:a aac` (mp3 was broken); rename keeps the real extension; cancel stops the retry loop; `_cftmp_*` partials cleaned; queue summary counts real successes; host-based site detection; browser cookies actually passed to yt-dlp; `outdir` NameError in the Instagram fallback
- Twitch: anonymous first (stale cookies caused HTTP 401), friendly "video does not exist"
- **Auto-transcribe** checkbox (exclusive with auto-load)
- **Channel browser** (Downloader → Browse channels): Kick VODs/Clips, Twitch VODs/Clips, YouTube Streams/Videos/Shorts with thumbnails; Kick tab removed from Clip Finder

### 🚀 Post Studio (rewritten)
- Master caption prompt (TikTok / Instagram / YouTube Shorts / X), strict output contract + tolerant parser, hard-rule enforcement and rules-check panel, editable Event & creator rules block (SeeEx is the default content; clearing it retires the event everywhere) with event mode, creator tag reminders, iteration buttons, version history, per-person handle memory; provider order Gemini → OpenRouter → Groq
- Removed the old 3-option tweet generator (orphaned code that raised NameError)

### 🤖 AI
- Groq: `llama-3.3-70b` / `llama-3.1-8b` (shut down 2026-08-16) → `gpt-oss-120b/20b`, `qwen3.8-27b`; Gemini 3.5-flash-lite / 3.8-flash with per-family thinking config; OpenRouter free list rebuilt (`openrouter/free` router)
- google-genai 2.x, groq 1.x, openai 3.x call shapes (`_gemini_complete`, `_groq_complete`, `_openrouter_complete`), None-safe responses, retired-model and rate-limit fallthrough
- Groq free-tier prompt budgeting (8K tokens/min): smaller chunks, transcript trimmed instead of the instructions

### 🎨 Theme v2
- Per-monitor DPI awareness + scaled pixel constants, Windows 11 dark title bar/caption colors, WCAG-AA palette, active-tab underline, hover/focus polish, accent presets (Settings → Appearance, restart to apply)

### 🎬 Features & fixes
- 9:16 face tracking via OpenCV YuNet (OpenCV 5 removed Haar cascades, mediapipe's legacy API is gone); no runtime pip install
- Music Removal on the isolated engine: progress, cancel, summary, engine status
- ~150 audited defects fixed across transcription, Auto Edit, Censor, Clip Finder, export/queue/subtitles, Editor, Studio, Thumbnails, Settings (see git log for the per-area commits): invalid whisper.cpp flag (`-vth`) that forced CPU fallback, stale cancel flags, atomic config writes with `.bak`, PBKDF2 key export, heatmap crash, placeholder text sent to the AI, censor word matching ("Scunthorpe"), download-complete popup NameError, and more
- Launch: ~10 s hang removed (no eager ML imports, no unpinned installs on the UI path)

### 📦 Build & release
- `tools/release_version.py` is the single source of truth for the version; CI fails on any mismatch and verifies the version inside the built installer
- Slimmer installer (heavy optional packages install on demand); uninstaller removes package caches
- Node/Python pins updated (embedded Python 3.12.x)

## v1.3.9.0 — July 2026

### 🤖 AI Providers — Refreshed & Verified
- Removed decommissioned Groq models: `llama-3.1-70b-versatile` (dead since Jan 2025) and `llama3-8b-8192` (dead since Aug 2025) — these were returning 400 errors
- Added `openai/gpt-oss-120b` and `openai/gpt-oss-20b` as future-proof successors (`llama-3.x` versatile/instant deprecate Aug 16 2026)
- OpenRouter: removed dead/nonexistent IDs (`qwen3.6-plus`, `gemma-3-12b-it`, `mistral-small-3.1`); added verified `qwen3-next-80b`, `gemma-4-31b`, `nemotron-nano-9b`
- Every model ID verified against the live Groq + OpenRouter catalogs
- Synced `clipfinder_core.py` model list to match (it was even further out of date)

### ✂️ Better Clips — Selection Overhaul
- Clip cuts now **snap to real sentence boundaries** — no more mid-word or mid-thought starts/ends
- The 60–160s length rule is now **enforced in code**, not just requested in the prompt: too-short clips are extended toward the ideal length, over-long clips are trimmed, and clips that can't form a real moment are dropped
- **Overlapping near-duplicate clips** (from different providers/chunks) are merged, keeping the higher-scored one
- Clips are ranked by score, then by the hook/engagement/value/shareability sub-scores
- Fixed a broken "verify descriptions" pass that silently did nothing and could overwrite the AI's summary with a raw transcript fragment

### 🐛 Bug Fixes
- **Auto-updater:** fixed a crash (`UnboundLocalError` on `tag`) that broke updates for anyone updating to a release with `clipfinder.py` attached as an asset
- **Auto-updater:** fixed a crash (`NameError` on `shutil`) when `clipfinder.py` isn't in the default folder
- **Transcription:** fixed whisper "Go. Go. Go." hallucination loops — added logprob threshold + no-fallback (whisper.cpp) and `no_speech` / `compression_ratio` / `condition_on_previous_text` (faster-whisper)
- **AI provider UI:** fixed the provider note and "Get free key" URL never displaying (an infinite recursion swallowed by a bare `except`)
- **AI analysis:** an empty transcript section is no longer logged as an error with 3 wasted retries — it's recognized as "no clip here" after one cross-check

### ⚡ Performance
- Fixed the **~5-second freeze on every launch** — startup no longer imports the entire ML stack (torch, OpenCV, whisper) just to check packages exist; it uses `importlib.find_spec` instead

### 🎨 UI
- Fixed unreadable secondary text — the muted label color was darker than the tertiary one (inverted contrast); it's now properly legible on the dark background

> **Note:** the auto-updater fixes only take effect from v1.3.9.0 onward. If your current version's auto-update fails, download this release manually once — future updates will work automatically.

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
