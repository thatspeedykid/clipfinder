# ClipFinder Changelog

---

## v1.3.1 — Current Release
*April 2026*

### 🔑 Smart Key Rotation & Rate Limit Overhaul
- Keys are now **shuffled randomly** at the start of each run — no more always hammering Key 1 first across back-to-back sessions
- **Per-key cooldown timestamps** — when a key gets rate-limited, the exact time is recorded. Before retrying, ClipFinder checks if the 62-second reset window has passed and skips cooling keys automatically
- **Gemini model splitting** — with multiple Gemini keys, each key is assigned a different model version (gemini-1.5-flash, gemini-2.0-flash, etc.). These have completely separate RPM buckets, effectively multiplying your throughput
- **Smart retry waits** — instead of hardcoded 30/60/90s delays, the retry loop calculates the exact time until the next key resets and waits only that long
- Ready keys are always tried before cooling keys, cooling keys are tried in order of soonest reset

### 📤📥 Encrypted Key Export / Import
- New **Export All Keys** and **Import All Keys** buttons in the AI Provider API Keys section header
- Keys are encrypted with a user-set password using SHA-256 derived XOR cipher
- Saves as `.cfkeys` file — portable between installs, safe to back up
- Import automatically applies all keys including extra keys (Key 2, Key 3) and refreshes the UI
- Useful for switching machines or backing up your key setup

### 🐛 Bug Fixes
- **OpenRouter `NoneType` crash fixed** — when `_r.choices` returned an empty list (malformed response), `choices[0]` would crash. Now checks for empty choices and skips to next model
- **OpenRouter dead model reset** — if all models get marked dead in a session, the dead list now auto-clears and retries fresh instead of failing permanently
- **Settings UI alignment fixed** — AI Provider key rows now use character-unit Label widths instead of pixel-width frames with `pack_propagate(False)`. This permanently fixes the left/right column clipping that appeared at different window sizes and DPI settings
- **Version bump** — all version strings updated to 1.3.1

---

## v1.3 — Stable
*April 2026*

### Major Features
- **AI Music Removal tab** — Demucs stem separation, runs fully locally, no API needed. Models: htdemucs (best), mdx_extra (faster), htdemucs_ft (fine-tuned)
- **Segment-aware clip accuracy** — verification pass rewrites clip descriptions using actual transcript text from within each clip's timestamp range
- **Multi-key support per provider** — add Key 2, Key 3 etc. via ＋ button in Settings. Keys rotate automatically on rate limit
- **Key rotation in `_call_provider`** — tries all keys before marking provider as rate-limited
- **OpenRouter model rotation** — skips 404 dead models per session, never retries them
- **Rate limit overhaul** — sequential task dispatch with 5s gap, global RL tracking, provider fallback chain
- **Names field** — shared between Normal and Interview mode, helps AI identify who is speaking
- **Progress bar for all operations** — unified status bar with determinate/indeterminate modes

### Fixes & Polish
- Censor queue fixed — correctly unpacks `(vid, out, clips)` tuple
- AutoEdit filename suffix standardized
- NA uploader fix in downloader
- Encoder detecting label fixed
- Groq 413 fix — prompts >20k chars truncated before sending
- Better download quality — VP9 preferred, `merge_output_format=mp4`
- Auto Edit uses GPU encoder instead of libx264 CRF 23
- Censor timing — 0.15s pre-roll for exact and segment-level hits
- Cancel works everywhere — checked at every major step including retry sleep (1s chunks)
- Gemini 1.5 Flash set as default (1,500 RPD free vs 20 RPD for 2.5 Flash)

---

## v1.2
*March 2026*

- **Auto Edit sub-tab** — silence removal with word-boundary cuts, GPU encoder
- **VOD Mode** — 8x concurrent fragment downloads, saves to `vod/` subfolder
- **Smart Auto Whisper** — picks model by video duration + GPU availability
- **Floating log panel** — Toplevel window, 500 message buffer
- **2-column clip grid** — wider cards, more readable layout
- **Stretched tabs** with orange active tab colors
- **Smart file naming** — standardized across all export types
- **Kick API naming** — correct streamer/title from Kick API v2
- **AI response fence stripping** — removes ` ```json ``` ` wrappers from any provider

---

## v1.1
*February 2026*

- **Hybrid clip detection** — FFmpeg audio energy peaks + AI analysis combined
- **In-app update checker** — orange banner on launch if newer version available
- **Donate button** added to footer

---

## v1.0 — Initial Release
*January 2026*

- AI clip detection with Gemini, Groq, OpenRouter
- GPU transcription (faster-whisper CUDA + openai-whisper CPU fallback)
- 16:9 and 9:16 export with face-tracking crop (mediapipe)
- Built-in yt-dlp downloader (YouTube, Twitch, Twitter/X, Kick)
- Tweet generator with tone selector
- Auto word censor (beep, silence, or custom MP3)
- Thumbnail finder (Unsplash, DuckDuckGo, Bing, Pixabay)
- Image Studio — duplicate finder + Real-ESRGAN upscaler
- Settings tab — API keys, whisper model, output folders, module installer
