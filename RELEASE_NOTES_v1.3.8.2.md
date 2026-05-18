# ClipFinder v1.3.8.2

**Release date:** May 17, 2026

## What's New

### New Logo & Icon
- Redesigned app icon with new branding — sharper across all sizes (16px through 256px)
- ICO rebuilt with 9 embedded sizes to cover every Windows DPI scale (100% through 200%)
- Header logo now loads from a high-resolution PNG source for a crisp display at all resolutions
- Taskbar icon uses Win32 API directly (`WM_SETICON`) so Windows picks the correct frame size automatically — no more blurry upscaling

### Icon Improvements
- Title bar, taskbar, Explorer, and Alt+Tab all now show the correct size icon
- Auto-update delivers new logo files (`clipfinder_logo_512.png`, `clipfinder.ico`) to existing installs automatically

## Bug Fixes
- Fixed gap between header logo and "CLIP FINDER" text
- Header logo icon size increased for better visibility

## Upgrading

Existing users will receive this update automatically on next launch. The updater will download the new logo files alongside `clipfinder.py` so no reinstall is needed.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
