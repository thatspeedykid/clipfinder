# ✂ ClipFinder v1.3.4

> **The Big Parallel Update · Multi-Queue Overhaul · Burn Subtitles Beta · Thumbnail Finder · AI Tweet Generator 3.0**

This is the largest ClipFinder update since launch. Nearly every tab has been touched.

---

## ⬇️ Install / Update

| | |
|---|---|
| **New install** | Run `ClipFinder-Setup.exe` below ↓ |
| **Existing users** | Click **⬇ Download Now** in the orange banner inside the app |

---

## ⚡ Clip Finder — Parallel AI Processing (Biggest Change)

Previously ClipFinder sent your entire transcript to one AI provider at a time. Now it **splits the transcript across every available API key simultaneously** — each key gets its own section and processes it in parallel. All results merge at the end.

**What this means in practice:**
- If you have 3 Gemini keys + 2 Groq keys + 1 OpenRouter key, that's **6 workers running at the same time**, each analysing a different part of the video
- Short transcripts (<40 lines) use **race mode** — all primary keys get the same chunk simultaneously, first response wins
- Long transcripts (300+ lines) **unlock extra keys** — extras join the pool proportionally based on how much content there is (~150 lines per worker)
- Result: clips found **2–5x faster**, far less load per key, and better coverage of the full video

**Smarter rate-limit handling:**
- Gemini 429 = **90 second cooldown** (RPM resets in ~60s), not 30–40 minutes like before
- Groq 429 = 55–70 second cooldown
- OpenRouter model temporarily down = that model gets a 5 minute timeout, next model tried immediately
- All cooldowns show a live countdown in Settings: `⏳ Rate-limited — clears in 4m32s`
- Provider status dots turn **yellow when rate-limited**, **red if dead**, **green when ready**
- Key pool always logged: `[Gemini] Key pool: 3 total, 3 ready, 0 on cooldown`

**OpenRouter fixes:**
- Models returning empty/null responses are now skipped and next model tried (was crashing the whole key)
- `openrouter/auto` added as first model — lets OpenRouter pick the best available free model automatically
- Updated free model list with currently active models

---

## 📝 Transcript Tab — Sub-tabs + AI Tweet Generator 3.0

The Transcript tab has been split into two sub-tabs:

### 📝 Transcript & Tweet
**Tweet Generator completely rewritten.** Hit Generate once and get **3 different tweet options** instantly:

- **Option 1 — Drama account style:** Bold punchy headline, uses "The tea:" and "The take:", pulls specific quotes directly from the transcript
- **Option 2 — Viral/meme energy:** Short, chaotic, screenshot-worthy phrasing
- **Option 3 — Thread opener:** 240–280 chars with a hook designed to drive replies and clicks

Each option is in its own tab, independently editable, with its own character counter. Copy This button copies whichever tab you're viewing.

**Smarter hashtags:**
- Reads names from your Context field and uses them as hashtags
- Never generates `#gaming` or `#gamingscandal` unless the clip is literally about gameplay
- Hashtags match what the specific tweet actually says

### 🔤 Burn Subtitles ⚠ Beta
Brand new sub-tab for burning captions directly onto video:

- **Self-contained** — transcribe right from the subtitle tab, no need to visit the Transcript tab first
- **Word-level timestamps** — uses Whisper's per-word timing for accurate sync
- **Pause detection** — subtitles go blank during silence gaps instead of running ahead
- **Karaoke mode** — each word highlights as it's spoken (customisable highlight color)
- Font picker, size, bold/italic, ALL CAPS
- Text color, outline color + thickness, background box with opacity
- 3×3 position grid (top/middle/bottom × left/center/right)
- **5 style presets:** Standard, Karaoke, Cinematic, Minimal, TikTok (3 words at a time)
- Live preview from a real frame extracted from your video
- Output folder picker

> ⚠ Burn Subtitles is in active beta. Timing and styling may not be perfect on all videos.

---

## ⬇️ Downloader — Single Queue

Single URL input removed. Now it's one clean area:
- One big **DOWNLOAD LINKS** text box — paste as many URLs as you want, one per line
- **⬇ Download All** button, Cancel, Clear, Auto-load checkbox
- Supports YouTube, Twitch, Kick, Twitter/X, TikTok and 1000+ more sites via yt-dlp

---

## 🔇 Censor — Multi-Video Queue

Rebuilt to match the Music Removal layout:
- Multi-file text area — paste paths or use **📂 Browse Multiple** to select many files at once
- **📋 Use Clip Finder Video** button to add whatever's loaded
- Processes all videos in order with per-video status
- One **🔇 CENSOR** button handles everything — old Add to Queue / Run Queue split is gone

---

## 🎵 Music Removal — Multi-Video Queue + Fix

- Same multi-file layout as Censor — text area, Browse Multiple, Use Clip Finder Video
- Fixed critical bug where the background thread was never started after a refactor — was stuck showing "starting X video(s)..." forever
- MOV/MKV/AVI files now correctly re-encode the video stream when merging (was producing 0kb output with `-c:v copy`)
- Each video shows `[1/3] Processing: filename.mp4...` in status
- Failed videos are logged and skipped — rest of queue continues

---

## 🖼 Thumbnail Finder ⚠ Beta

Complete overhaul using **DuckDuckGo image search** (zero setup, no API key needed):

- Searches the real web — actually finds Mizkif, Alinity, Asmongold, any streamer/celeb
- Uses the `ddgs` Python library which handles browser fingerprinting internally
- **Image Type selector:** Portrait/solo · Group photo · Stream screenshot · Any
  - Portrait mode appends `face photo headshot` to query + uses tall layout filter
  - Screenshot mode searches for stream/Twitch context specifically
- **Quality toggle:** HD (Large images only) or SD
- **Stock photos mode:** Toggle on to use Unsplash instead (needs free Unsplash key in Settings for stock photos)
- Beta notice shown in UI

---

## 💾 Save / Load Session

Two new buttons in the Clip Finder export bar:
- **Save Session** — exports all current clips (timestamps, titles, scores, filenames) to `AppData/Local/ClipFinder/clipfinder_session.json`
- **Load Session** — restores a previous session instantly with no re-transcribing or re-analysing needed
- Warns before loading if a different video is currently loaded

---

## ⚙️ Settings Improvements

- **Live rate-limit status** — provider dots update in real time during a run
- **Per-key transcript splitting** — Settings shows how many keys are active per provider
- **Clear Cooldowns button** — appears when keys are paused, lets you manually reset them
- Pixabay/Pexels keys removed (replaced by DDG)
- `ddgs` added to Update Modules list

---

## 🐛 Bug Fixes

- **`self.log()` 4-arg crash** — merge conflict left two message strings as separate arguments, caused crash at start of every AI run
- **`fonttools` not detected** — Python module is `fontTools` (capital T), was checking for `fonttools` and always showing as not installed
- **GPU detection showing `0s` duration** — was using ffprobe-style flags with the ffmpeg binary; fixed to parse `Duration:` from ffmpeg stderr
- **Gemini keys not rotating** — first 429 was triggering a 30–40 min cooldown on ALL keys; now only the specific key gets a 90s cooldown, Keys 2 and 3 remain available
- **OpenRouter `NoneType` crash** — free models sometimes return `choices = None`; now all `choices[0]` access is guarded, bad responses silently skipped
- **MKV/MOV export 0kb** — GPU encoder `h264_amf` can't stream-copy MKV/MOV containers into MP4; now detects these and re-encodes
- **Music Removal stuck forever** — `threading.Thread(target=_run).start()` line was missing after a refactor
- **Subtitle preview ffprobe error** — was trying to call `ffprobe.exe` which doesn't ship in the auto-downloaded ffmpeg bundle; now uses ffmpeg stderr parsing
- **Duplicate Download buttons** — both "Download Queue" and "Download All" were showing simultaneously; consolidated to one button
- **Censor queue listbox** — old `tk.Listbox` replaced with proper text area that shows full paths
- **Whisper GPU log `GPU=False`** — now explains WHY: `⚠ whisper.cpp not installed — go to Settings → Core Dependencies`

---

## 📦 New Dependencies (auto-installed)

- `ddgs` — DuckDuckGo image search (thumbnail finder)

---

*[@MarsScumbags](https://x.com/MarsScumbags) · [GitHub](https://github.com/thatspeedykid/clipfinder)*
