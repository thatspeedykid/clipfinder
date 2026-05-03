# ClipFinder v1.3.7 — Release Notes

**Released:** May 2026

---

## 🚀 Seamless Auto-Update for All Versions

The biggest infrastructure change in v1.3.7 — upgrading from any older version now works automatically.

**How it works:**
1. Auto-updater delivers the new `clipfinder.py` as always
2. On next launch, before the window even opens, ClipFinder checks for `clipfinder_core.py`
3. If missing or outdated → shows a mini splash, downloads it from GitHub, restarts
4. Default vision reference images (Stake, Roobet, Rainbet) download silently in background
5. App opens fully updated — no user action needed

Users on v1.3.6 and below get everything automatically on their next launch.

---

## ⚡ Smart Transcribe

New optional checkbox next to the mode buttons. When enabled, ClipFinder reads your instructions for time cutoffs and tells whisper.cpp to stop transcribing early.

**Example:** "ignore last hour" on a 109min video  
- Off: transcribes all 109min, then strips last hour from transcript  
- On: whisper.cpp stops at 49min — genuinely ~2x faster transcription

Off by default. Hover over it for a tooltip.

---

## 🎯 Vision Mode — Actually Works Now

Two major fixes to Vision Mode's gambling/content filtering:

**Pre-filter transcript:** Instead of telling the AI "don't include gambling clips" (which it ignored), Vision Mode now physically removes those transcript lines before the AI sees them. The AI can't suggest a clip it never read.

**Block merging:** Consecutive excluded timestamps are merged into continuous ranges. If gambling is detected at 35:00, 36:00, 45:30, 47:30, 49:00 — that becomes two clean blocks (34:00-37:00 and 44:30-50:00) with padding, not five isolated 90-second windows.

Log now shows exactly what got stripped:
```
🎯 Excluding 2 gambling block(s): 34:00-37:00, 44:30-50:00
🎯 Vision pre-filter: stripped 241 gambling lines — 948→707 transcript lines
```

---

## 📋 Instruction Filtering (All Modes)

Time-based instructions now actually filter the transcript in Normal mode too:

- `ignore last hour` → strips final hour from transcript before AI
- `ignore the last hour` → same
- `skip last 30 minutes` → strips final 30min
- `ignore first 30 minutes` → strips opening 30min

Combined: `don't show any gambling clips, ignore the last hour` → Vision strips gambling blocks AND instruction filter strips the last hour. AI gets a pre-cleaned focused transcript.

---

## 🎯 Vision Mode Reference Images

New section in Settings for teaching Vision Mode what to recognize.

**Default images bundled:** Stake, Roobet, Rainbet casino logos — installed automatically so "no gambling" works out of the box.

**Add your own:** Open Reference Images Folder → drop any screenshot → hit Scan & Label → Gemini Vision auto-identifies and renames it.

---

## Upgrade Notes

- **Auto-updater users:** Just accept the update — everything else is automatic
- **Fresh install:** NSIS installer now bundles `clipfinder_core.py` and `vision_refs/` with default images
- **No breaking changes** — all settings, keys, models carry over

---

*Full changelog: [CHANGELOG.md](CHANGELOG.md)*  
*Issues: [github.com/thatspeedykid/clipfinder/issues](https://github.com/thatspeedykid/clipfinder/issues)*
