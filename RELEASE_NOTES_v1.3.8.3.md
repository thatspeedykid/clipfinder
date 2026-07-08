# ClipFinder v1.3.8.3

**Release date:** June 4, 2026

## Bug Fixes

### Kick Download Fixed
- Replaced broken curl_cffi dependency with plain `requests` for Kick API calls
- Kick clips and VODs now download correctly using session_token from cookies.txt
- Direct ffmpeg download from Kick CDN — faster and more reliable than yt-dlp for Kick
- Fixed 403 errors that appeared after module updates broke curl_cffi

### curl_cffi Stability
- Added dynamic MetaPathFinder to handle any broken curl_cffi submodule automatically
- Pinned `curl-cffi==0.7.4` — Update All Packages can no longer install a breaking version
- No more `No module named 'curl_cffi.const'` / `curl_cffi.aio` / `curl_cffi.utils` errors

### Post Studio Improvements
- Context/Angle field is now mandatory in AI prompts — posts stay on topic
- Transcript increased from 1000 to 6000 chars — no more missing content
- YT Shorts now generates title + description + hashtags (was title + hashtags only)
- Scoring calibrated — quality posts now consistently hit green (8-10)

## Upgrading

Existing users will receive this update automatically on next launch.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
