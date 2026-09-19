# ClipFinder v1.4.0.0

**The revamp release.** Kick downloads work again, YouTube downloads are fixed for good, the update system was rebuilt so modules and the app itself actually update, Post Studio was rewritten, and about 150 audited bugs were fixed.

## What's New

### 📺 Channel browser — Kick, Twitch and YouTube, VODs *and* clips
The Kick tab moved out of Clip Finder into **Downloader → Browse channels**, and it now covers three platforms:
- **Kick** — VODs and Clips
- **Twitch** — VODs and Clips (top clips of the last week, widening automatically if the channel is quiet)
- **YouTube** — Streams, Videos and Shorts

Every entry has a thumbnail with a duration badge, views and date, plus **Load** (into Clip Finder), **Edit**, **Download** and **Queue** buttons. Paste a channel link or just a name; your last channel per platform is remembered.

### ⬇️ Downloader
- **Kick VODs fixed.** Kick moved to a new VOD id format and API, which broke every Kick download. ClipFinder now resolves the stream itself (Kick clips too).
- **YouTube fixed.** yt-dlp now needs a JavaScript runtime for YouTube. ClipFinder uses your Node.js 22+ (or downloads a portable Node 24 once, ~35 MB) and hands it to yt-dlp. The old client tricks and the bgutil plugin are gone.
- **Audio only now really gives an MP3** (an AAC setting used to clobber it).
- **Auto-transcribe** option next to auto-load (they are mutually exclusive): a finished download goes straight to the Transcript page.
- Cancel now stops the retry loop, partial files are cleaned up, the queue reports how many items really downloaded, and Twitch tries anonymous first (fixes the HTTP 401 from stale cookies).

### 🔄 Update Center (Settings) — the update system was rebuilt
- **Everything updates in-app**, also for people who don't use the installer: every module and dependency (yt-dlp, AI SDKs, faster-whisper, curl-cffi, OpenCV, …) plus **the app itself**.
- Updates are **downloaded and import-tested first, then swapped in at the next start** — a broken download can no longer break a working install. Failed swaps roll back automatically.
- Version rules per package (always latest / compatible range / leave alone), package groups that must move together, conflict detection with a one-click **Repair**.
- **App self-update** validates the new `clipfinder.py`, keeps a backup and can **roll back** with one click; a background check tells you when a new version is out.
- **Music Removal (Demucs) runs in its own isolated engine** (Settings → Update Center) with its own PyTorch. It can no longer collide with the app's packages — the source of the recurring Demucs problems.
- One ClipFinder at a time (single-instance lock) so updates never fight a running copy.

### 🚀 Post Studio — rewritten around your caption rules
Write TikTok, Instagram, YouTube Shorts and X posts from a transcript *or just a rough description*:
- Follows the full master prompt: finds the one moment people stop scrolling for, on-screen hook + caption per platform, YouTube title with a hashtag, X with **no hashtags and no em dashes**, factual-accuracy wording, SeeEx rules, creator tag rules.
- **Rules check** after every generation: auto-fixes what is mechanical (X hashtags/dashes, generic #viral/#fyp tags, SeeEx / Adrianah Lee / Rellik The Clown spelling, hashtag counts) and warns about the rest (criminal labels, "faked/lied", consent vs. assault, alleged claims stated as fact, missing SeeEx, Aishah Sofey tagging).
- **SeeEx mode** (Auto / Always / Not SeeEx), people-in-this-clip, angle override, saved standing rules, per-person handle memory.
- **Try again · Funnier · Shorten · More viral · free-text correction**, per-card regenerate, version history, editable results with per-field copy. **New clip** wipes everything so clips never bleed into each other.
- Pick a found clip straight from Clip Finder, or load a video and transcribe it.

### 🤖 AI providers refreshed
- Groq `llama-3.x` models were shut down on Aug 16 → now `gpt-oss-120b/20b` and Qwen3.8; Gemini 3.5 / 3.8 with correct thinking-token budgets; OpenRouter free-model list rebuilt against the live catalog.
- SDKs moved to google-genai 2.x, groq 1.x, openai 3.x. Rate limits and retired models fall through to the next model/key/provider automatically.

### 🎬 Other improvements
- **9:16 face tracking works again** (OpenCV YuNet; the old mediapipe tracker silently did nothing). No pip installs at export time.
- **Music Removal** rewritten around the isolated engine: real progress bar, working Cancel, honest "done / failed" summary, clear engine status.
- Faster launch: the ~10 second hang at startup is gone.
- Installer: version shown is always the real version (one source of truth), smaller installer; heavy optional packages install on demand.

## Bug Fixes (highlights of ~150)
Transcription (invalid whisper flag that forced slow CPU, stale cancel, wrong language), Auto Edit (silence detection, keyframe cuts, temp files, cancel), Censor (bleeping innocent words like "Scunthorpe", queue wipe, mux failures), Clip Finder (heatmap crash, placeholder text sent to the AI as instructions, Groq truncation, settings lost on close), export/queue/subtitle burning (BG box, karaoke colors, ffmpeg cancel), Editor/Studio/Thumbnails, key import/export (now PBKDF2-encrypted), config saved atomically with a backup, download-complete popup crash, and many more. See the CHANGELOG.

## Upgrading
- Existing installs update from inside the app (banner or Settings → Update Center). The first start after updating may take a moment while packages are refreshed.
- **Windows SmartScreen** may warn about a newly downloaded installer ("Windows protected your PC" → *More info* → *Run anyway*). The installer is not code-signed yet. Updating from inside the app does not trigger it.
- Music Removal asks once to install its engine (about 1–2 GB) the first time you use it.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
