# ClipFinder v1.4.0.1

A quick fix for v1.4.0.0.

## Fixed
- **Music Removal engine could not be installed** ("Installed but failed its self-test: No module named 'demucs'"). The installer's bundled Python ignores the `PYTHONPATH` variable, so the engine's own folder was never visible to it. The engine is now started with its folder added to the module path from inside Python. Verified with the bundled Python: the engine installs in about a minute and a real separation run produces the vocals and no-vocals tracks.
- The same problem in the Instagram fallback (gallery-dl) is fixed.

## Upgrading
Update from inside the app (banner or Settings → Update Center), then use **Install Music Removal engine** again.

---

*Built by [@MarsScumbags](https://x.com/MarsScumbags)*
