# Release tooling

The **git tag is the single source of truth** for the ClipFinder version. Everything that ships
must carry the same number, and the build fails loudly (it never silently ships a wrong version)
if anything disagrees.

## Releasing a version

```bat
:: 1. bump the version everywhere (clipfinder.py, ClipFinder.nsi, README badge) - strict, all-or-nothing
python tools/release_version.py set 1.4.0.0

:: 2. write the release notes (CI fails if the file is missing or empty) and the CHANGELOG entry
::    RELEASE_NOTES_v1.4.0.0.md

:: 3. verify locally (same check CI runs)
python tools/release_version.py check --tag v1.4.0.0

:: 4. commit, tag, push the tag
git add -A
git commit -m "release: v1.4.0.0"
git tag v1.4.0.0
git push origin <branch>
git push origin v1.4.0.0
```

Tags are `vX.Y.Z.W` (or `vX.Y.Z`, which is treated as `X.Y.Z.0`). Files always hold the 4-part form
because the Windows version resources need exactly four numbers.

To rehearse without publishing anything: GitHub -> Actions -> **Build & Release** -> *Run workflow*
(leave `dry_run` ticked). The full build runs and `ClipFinder-Setup.exe` is attached to the run as an
artifact for 3 days; no release is created.

## What CI enforces (`.github/workflows/build.yml`)

Early, before the ~10 minute build starts:

| Check | Fails when |
|---|---|
| tag format | the tag is not `vX.Y.Z` / `vX.Y.Z.W` |
| `release_version.py selftest` | the checker itself is broken (it is tested first, against temp copies of the real files) |
| `release_version.py check --tag <tag>` | `APP_VERSION` in `clipfinder.py`, `!define APP_VERSION` in `ClipFinder.nsi`, the README version badge and the tag are not all the same; or `ClipFinder.nsi` contains non-ASCII characters |
| release notes | `RELEASE_NOTES_<tag>.md` is missing or empty |
| `py_compile clipfinder.py` | the app does not compile |

After the build, read back from the real artifacts:

| Check | Fails when |
|---|---|
| installer EXE properties | `ClipFinder-Setup.exe` FileVersion / ProductVersion differ from the version |
| launcher EXE properties | `ClipFinder_dist\ClipFinder.exe` FileVersion / ProductVersion differ |
| shipped app | the `clipfinder.py` inside the installer has another `APP_VERSION`, differs from the repo file, or `clipfinder_core.py` is present |
| bundled packages | `tools/smoke_pkgs.py` (run with the *embedded* Python) finds a requirement missing or unimportable, or a dropped package (torch, demucs, ...) bundled again |
| installer size | outside 80-450 MB |

The installer's welcome/title text and Add/Remove Programs `DisplayVersion` come from the same
`APP_VERSION` define in `ClipFinder.nsi` that the checks above validate. Finally the release is created
from the tag with `ClipFinder-Setup.exe` and a `SHA256SUMS` asset; a missing file fails the step.
A moved or re-pushed tag cancels the older build of the same tag (workflow `concurrency`).

## Files

| File | Purpose |
|---|---|
| `release_version.py` | `get` / `check [--tag]` / `set X.Y.Z[.W]` / `selftest` - stdlib only, Python 3.12+ |
| `smoke_pkgs.py` | CI smoke test of `ClipFinder_dist\pkgs` with the embedded Python |

`requirements.txt` in the repo root is the exact package list bundled into the installer (one pip
transaction into `ClipFinder_dist\pkgs`); change it there. torch, openai-whisper and demucs are
deliberately **not** bundled - the app installs them on demand.

## Local build

```bat
py -3.12 --version                      :: must be 3.12.10 (the embedded Python is built from the same version)
build_installer.bat                     :: ClipFinder_dist\ with embedded Python, launcher, app files
py -3.12 -m pip install --target ClipFinder_dist\pkgs --only-binary=:all: -r requirements.txt
makensis ClipFinder.nsi                 :: -> ClipFinder-Setup.exe
```
