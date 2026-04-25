# ✂ ClipFinder v1.3.5

> **Auto-Updater · YouTube 1080p · Download Quality Overhaul · Interview Fix · UI Polish**

---

## ⬇️ Install / Update

| | |
|---|---|
| **New install** | Run `ClipFinder-Setup.exe` below ↓ |
| **Existing users on v1.3.4** | Click **⬇ Download Now** in the orange banner — app updates itself automatically |

---

## ⚡ In-App Auto-Updater

ClipFinder now updates itself. No more downloading a new installer.

When a new version is available, the orange banner at the bottom shows **⬇ Download Now**. Click it and:
1. Progress popup appears
2. Downloads the new `clipfinder.py` directly from GitHub
3. Verifies it's valid Python before touching anything
4. Replaces itself silently
5. Relaunches automatically — splash runs if new packages are needed

"Open in Browser" button still available as fallback.

---

## 📺 YouTube 1080p Downloads — Finally Fixed

YouTube has required PO (Proof of Origin) tokens since mid-2024, which is why all previous download attempts returned 360p `format=18`. Fixed with two changes:

- **`yt-dlp` updated to `2026.3.17`** — includes YouTube extractor fixes
- **`bgutil-ytdlp-pot-provider` plugin** — auto-installed at first launch, handles PO token generation automatically. Hooks into yt-dlp silently.
- **Portable Node.js** — downloaded automatically to `AppData\Local\ClipFinder\node\` (no system install, no admin rights)

Downloads now consistently return `format=303+251` (1080p VP9 + Opus) or better.

---

## ⬇️ Download Quality Overhaul

Platform-specific download strategies:

| Platform | Strategy |
|---|---|
| **YouTube** | bgutil PO token plugin → `bestvideo+bestaudio` merge |
| **Twitch** | `chunked` quality format (source quality for VODs) |
| **TikTok** | `bytevc1` no-watermark stream |
| **Twitter/X** | Cookies required — clear error + 4-step guide if missing |
| **Everything else** | `web` client + best format fallback |

Each failed attempt now logs why it failed and what it's trying next.

---

## 🍪 Cookies — Browser Auto-Extract

Settings → Cookies now has a **browser dropdown** (Chrome / Firefox / Edge / Brave / Opera / Safari). Pick your browser and yt-dlp reads cookies directly from its database — no extension, no file export needed. Works for YouTube HD, Kick, Twitter/X.

`cookies.txt` file path still supported as fallback.

---

## 🎤 Interview Mode Fixed

- Clicking **Find Clips** in Interview mode now actually works — was silently crashing before launch due to missing `interview_names_box` reference
- Removed the redundant second names text box — just use the **Names:** field (top right) for both Normal and Interview modes
- AI now reads speaker names from the **video filename** automatically — e.g. `The Hollywood Fix - Aishah Sofey Talks Piper Rockelle` → AI uses "Aishah Sofey" and "Piper Rockelle" in clip titles without needing manual entry
- Interview prompt updated: if Names field is blank, AI infers names from the video title and transcript context

---

## 🖼 Thumbnail Finder — Real People Now Work

- Switched from Pixabay/Pexels (stock only) to **DuckDuckGo image search** via `ddgs` library
- Zero setup, no API key — finds actual streamer/celeb photos (Mizkif, Alinity, Asmongold, etc.)
- **Image Type selector:** 🧑 Portrait/solo · 👥 Group photo · 🖥 Stream screenshot · 🔀 Any
- Portrait mode adds headshot query bias + tall layout filter to avoid game screenshots
- Stock photos mode (toggle) uses Unsplash — optional free key in Settings
- Quality toggle: HD / SD

---

## ✂ Clip Finder UI

- **Clips default to unchecked** — nothing selected by default after AI finds clips. You manually pick what to export.
- **☑ Select All** and **☐ Deselect All** are now two separate orange buttons in the export bar (previously one confusing toggle)
- Removed **Transcribe Only** button from Clip Finder tab (still accessible via Transcript tab)

---

## 🐛 Bug Fixes

- **Gemini parse error** — was failing on JSON wrapped in `{"clips": [...]}` object or with preamble text before the array. Parser now handles all cases.
- **AI using "Mizkif" when not in video** — was hardcoded in example title in the AI prompt, causing AI to hallucinate the name. Removed.
- **Interview mode silent crash** — `_start()` called `self.interview_names_box.get()` which no longer existed after UI refactor. Now reads from `v_names` field.
- **bgutil package showing gray in Settings** — was checking wrong key (`bgutil_ytdlp_pot_provider` underscores vs `bgutil-ytdlp-pot-provider` dashes) so imp_map lookup never matched. Fixed.
- **YouTube cookiefile stripping** — every attempt was calling `_opts.pop('cookiefile', None)` for YouTube, actively removing cookies even when set. Fixed.
- **Pillow broken install** — now checks `PIL.Image` (not just `PIL`) so broken Pillow installs are caught and auto-reinstalled by prelaunch splash.
- **X/Twitter 403 error** — now shows clear 4-step fix guide instead of 50-line traceback.

---

## 📦 New Dependencies (auto-installed)

- `ddgs` — DuckDuckGo image search
- `bgutil-ytdlp-pot-provider` — YouTube PO token plugin
- Portable Node.js v20 — required by bgutil (downloaded to AppData, no system install)

---

*[@MarsScumbags](https://x.com/MarsScumbags) · [github.com/thatspeedykid/clipfinder](https://github.com/thatspeedykid/clipfinder)*
