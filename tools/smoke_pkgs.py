"""CI smoke test for the pre-bundled packages - run it with the EMBEDDED python
(the interpreter end users actually get), not the runner's python:

    ClipFinder_dist\\python\\python.exe tools\\smoke_pkgs.py ClipFinder_dist [requirements.txt]

Fails the build (exit 1) instead of shipping an installer that only breaks on a user's machine:
  1. every package in requirements.txt is installed in pkgs\\ at a version its specifier accepts
  2. nothing that was deliberately dropped from the installer crept back in (size regression)
  3. the important modules import under the embedded interpreter
"""
import importlib
import importlib.metadata as md
import re
import sys
from pathlib import Path

dist = Path(sys.argv[1] if len(sys.argv) > 1 else 'ClipFinder_dist').resolve()
req_file = Path(sys.argv[2] if len(sys.argv) > 2 else 'requirements.txt').resolve()
pkgs = dist / 'pkgs'
sys.path.insert(0, str(pkgs))

# Optional in the app (installed on demand by the user / into its own env) - must NOT be bundled.
FORBIDDEN = {'torch', 'torchaudio', 'openai-whisper', 'demucs', 'mediapipe', 'numba', 'llvmlite',
             'bgutil-ytdlp-pot-provider', 'torch-directml'}

MODULES = ['_tkinter', 'ssl', 'sqlite3', 'ctypes',
           'numpy', 'scipy', 'PIL', 'imagehash', 'cv2', 'soundfile',
           'requests', 'yt_dlp', 'yt_dlp_ejs', 'curl_cffi',
           'google.genai', 'groq', 'openai',
           'faster_whisper', 'ctranslate2', 'onnxruntime', 'av',
           'fontTools', 'ddgs']

bad = []


def fail(msg):
    bad.append(msg)
    print(f'FAIL  {msg}')


print(f'python {sys.version.split()[0]}  pkgs={pkgs}')
if sys.version_info[:2] != (3, 12):
    fail(f'embedded python is {sys.version.split()[0]}, expected 3.12.x')
if not pkgs.is_dir() or not any(pkgs.iterdir()):
    fail(f'{pkgs} is missing or empty')

# 1) requirements.txt vs what is really installed in pkgs\
try:
    from packaging.requirements import Requirement          # installed in pkgs\ (huggingface_hub needs it)
    from packaging.utils import canonicalize_name
except Exception as exc:                                     # noqa: BLE001
    Requirement = None
    fail(f'cannot import packaging from pkgs: {exc!r}')

installed = {}
for d in md.distributions(path=[str(pkgs)]):
    name = d.metadata['Name']
    if name:
        installed[canonicalize_name(name) if Requirement else name.lower()] = d.version

if Requirement:
    wanted = []
    for line in req_file.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if line and not line.startswith('-'):
            wanted.append(Requirement(line))
    if not wanted:
        fail(f'no requirements found in {req_file}')
    for r in wanted:
        ver = installed.get(canonicalize_name(r.name))
        if ver is None:
            fail(f'{r.name}: not installed in pkgs')
        elif not r.specifier.contains(ver, prereleases=True):
            fail(f'{r.name}: installed {ver} does not satisfy "{r.specifier}"')
        else:
            print(f'ok    {r.name} {ver}')
    # extras must really have been pulled in ("yt-dlp[default,curl-cffi]")
    for extra_dist in ('yt-dlp-ejs', 'curl-cffi'):
        if canonicalize_name(extra_dist) not in installed:
            fail(f'{extra_dist}: missing (yt-dlp[default,curl-cffi] extras not installed)')

# 2) nothing that was dropped from the installer may come back
for n in sorted(FORBIDDEN & {re.sub(r'[-_.]+', '-', k).lower() for k in installed}):
    fail(f'{n} is bundled but must not be (optional/on-demand package)')

# 3) real imports
for name in MODULES:
    try:
        importlib.import_module(name)
        print(f'ok    import {name}')
    except Exception as exc:                                 # noqa: BLE001 - report everything
        fail(f'import {name}: {exc!r}')

if bad:
    print(f'\n{len(bad)} problem(s):')
    for b in bad:
        print(f'  - {b}')
    sys.exit(1)
print('\nsmoke test passed')
