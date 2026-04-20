"""
ClipFinder — AI Drama Clip Extractor
Run: python clipfinder.py  OR  ClipFinder.exe

When running as EXE: the app launches immediately.
Use Settings → Update Modules to install AI/transcription packages.
"""

APP_VERSION = "1.3.3"

import subprocess
import sys
import os

# ── App directory — where the app is installed (read-only in Program Files) ───
from pathlib import Path as _PathBase
if getattr(sys, 'frozen', False):
    APP_DIR = _PathBase(sys.executable).parent
else:
    APP_DIR = _PathBase(__file__).parent

# ── Fix Tcl/Tk paths for embedded Python ─────────────────────────────────────
# When launched from an embedded python.exe, TCL_LIBRARY and TK_LIBRARY must
# point to the tcl/tk folders inside our python/ directory
import os as _os_tcl
_py_dir = _PathBase(sys.executable).parent
for _tcl_dir in _py_dir.glob('tcl*'):
    if _tcl_dir.is_dir() and (_tcl_dir / 'init.tcl').exists():
        _os_tcl.environ.setdefault('TCL_LIBRARY', str(_tcl_dir))
        break
for _tk_dir in _py_dir.glob('tk*'):
    if _tk_dir.is_dir() and (_tk_dir / 'tk.tcl').exists():
        _os_tcl.environ.setdefault('TK_LIBRARY', str(_tk_dir))
        break

# ── User data directory — writable, never in Program Files ───────────────────
# Uses AppData/Local/ClipFinder so no admin rights needed for downloads/installs
import os as _os2
_appdata = _PathBase(_os2.environ.get('LOCALAPPDATA', _os2.path.expanduser('~')))
USER_DIR = _appdata / 'ClipFinder'
USER_DIR.mkdir(parents=True, exist_ok=True)

def _app_path(*parts):
    """Return writable user data path (AppData/Local/ClipFinder/...)."""
    p = USER_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _install_path(*parts):
    """Return read-only install path (Program Files/ClipFinder/...)."""
    return APP_DIR.joinpath(*parts)


# ── Dependency manifest ───────────────────────────────────────────────────────
# All packages the app may use.  Separated into:
#   REQUIRED_LIGHT  — tiny, fast to install, needed for the UI to function
#   REQUIRED_HEAVY  — large AI/ML packages; installed on-demand via Settings
REQUIRED_LIGHT = {
    'yt_dlp':    'yt-dlp',
    'PIL':       'Pillow',
    'requests':  'requests',
    'curl_cffi': 'curl-cffi',
}
REQUIRED_HEAVY = {
    'whisper':        'openai-whisper',
    'faster_whisper': 'faster-whisper',
    'groq':           'groq',
    'google.genai':   'google-genai',
    'openai':         'openai',
    'imagehash':      'imagehash',
    'cv2':            'opencv-python',
    'soundfile':      'soundfile',
    'numpy':          'numpy',
}
# Combined dict kept for backward-compat references elsewhere
REQUIRED = {**REQUIRED_LIGHT, **REQUIRED_HEAVY}


def _get_pip_executable():
    """Return Python interpreter path for pip. Handles all runtime modes."""
    import shutil as _sh, platform as _pl, glob as _gl, subprocess as _sp2

    _exe = _PathBase(sys.executable)

    # Mode 1: Running as python.exe directly (embedded or system Python)
    if _exe.name.lower() in ("python.exe", "python3.exe", "python", "python3"):
        return str(_exe)

    # Mode 2: Frozen EXE — must find real Python separately
    py = _sh.which("py")
    if py:
        try:
            r = _sp2.run([py, "-3.12", "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return py + " -3.12"
        except: pass

    for name in ("python3.12", "python3.12.exe"):
        found = _sh.which(name)
        if found: return found

    if _pl.system() == "Windows":
        import os as _os3
        _local = _os3.environ.get("LOCALAPPDATA", "")
        for pat in [
            r"C:\Python312\python.exe",
            r"C:\Program Files\Python312\python.exe",
            _local + r"\Programs\Python\Python312\python.exe",
        ]:
            if _PathBase(pat).exists(): return pat

    for name in ("python.exe", "python3.exe", "python", "python3"):
        found = _sh.which(name)
        if found and _PathBase(found).resolve() != _exe.resolve():
            return found

    return None


def _pip_cmd(packages, extra_args=None, target=None):
    """Build a pip install command targeting USER_DIR/pkgs."""
    pip_exe = _get_pip_executable()
    if pip_exe is None:
        return None
    parts = pip_exe.split() if ' ' in pip_exe else [pip_exe]
    tgt = target or PKGS_DIR
    cmd = parts + ['-m', 'pip', 'install',
                   '--target', str(tgt),
                   '--upgrade',
                   '--quiet',
                   '--no-warn-script-location'] + (extra_args or []) + packages
    return cmd


def _pip_cmd_safe(packages, extra_args=None):
    """Like _pip_cmd but skips packages whose .pyd files are locked (already loaded).
    Uses --no-deps and catches permission errors gracefully."""
    pip_exe = _get_pip_executable()
    if pip_exe is None:
        return None
    parts = pip_exe.split() if ' ' in pip_exe else [pip_exe]
    # Check if any of these packages have locked .pyd files
    _locked = set()
    for _pkg in packages:
        _mod = _pkg.replace('-','_').split('==')[0]
        for _pyd in PKGS_DIR.glob(f'{_mod}/**/*.pyd'):
            try:
                import os as _os3
                # Try opening exclusively — if locked, skip upgrade
                with open(_pyd, 'rb'): pass
            except (PermissionError, OSError):
                _locked.add(_pkg)
                break
    # For locked packages, use --ignore-installed to install alongside
    _safe_pkgs = [p for p in packages if p not in _locked]
    if not _safe_pkgs:
        return None  # all locked, nothing to do
    cmd = parts + ['-m', 'pip', 'install',
                   '--target', str(PKGS_DIR),
                   '--upgrade', '--quiet',
                   '--no-warn-script-location'] + (extra_args or []) + _safe_pkgs
    return cmd


# Packages installed by the app go here — survives across EXE relaunches
PKGS_DIR = USER_DIR / 'pkgs'
PKGS_DIR.mkdir(parents=True, exist_ok=True)

def _fresh_import(module_name):
    """Force a fresh import from PKGS_DIR, clearing any cached failure."""
    _ensure_pkgs_on_path()
    import importlib as _il
    # Clear the module and any parent packages from cache so they re-resolve
    parts = module_name.split('.')
    for i in range(len(parts), 0, -1):
        key = '.'.join(parts[:i])
        if key in sys.modules:
            del sys.modules[key]
    return _il.import_module(module_name)


def _ensure_pkgs_on_path():
    """Add package dirs to sys.path so installed packages are found."""
    # 1. PKGS_DIR (user-installed via Settings → Update Modules)
    PKGS_DIR.mkdir(exist_ok=True)
    pkg_str = str(PKGS_DIR)
    if pkg_str not in sys.path:
        sys.path.insert(0, pkg_str)
    # 2. Embedded Python site-packages (pre-bundled by setup_build.py)
    _pydir = _PathBase(sys.executable).parent
    for _sp_dir in [
        _pydir / 'Lib' / 'site-packages',
        _pydir / 'lib' / 'site-packages',
    ]:
        _sp_str = str(_sp_dir)
        if _sp_dir.exists() and _sp_str not in sys.path:
            sys.path.insert(1, _sp_str)
    # Version mismatch detection removed — packages installed by setup_build.py are always correct

_ensure_pkgs_on_path()  # run immediately at import time

def _run_pip_safe(packages):
    """Install packages to PKGS_DIR using Python 3.12 (matches EXE runtime)."""
    cmd = _pip_cmd(packages)
    if cmd is None:
        print('[CF] WARNING: Cannot find Python 3.12. Use Settings → Update Modules.')
        return
    PKGS_DIR.mkdir(exist_ok=True)
    print(f'[CF] pip: {" ".join(cmd[:3])} ... target={PKGS_DIR}')
    try:
        subprocess.check_call(cmd, timeout=300)
        _ensure_pkgs_on_path()
    except Exception as e:
        print(f'[CF] pip install warning: {e}')

def auto_install():
    """Install missing lightweight packages on first run.

    EXE mode  -> installs only REQUIRED_LIGHT via the real python.exe.
                 Heavy packages are deferred to Settings -> Update Modules.
                 NEVER calls sys.executable directly (that would re-launch the EXE).
    Script mode -> installs everything then restarts via os.execv.
    """
    _frozen = getattr(sys, 'frozen', False)
    target = REQUIRED_LIGHT if _frozen else REQUIRED

    missing = []
    for mod, pkg in target.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return

    print(f'[CF] Missing packages: {", ".join(missing)}')

    if _frozen:
        # EXE mode: use _run_pip_safe which finds the real python.exe
        _run_pip_safe(missing)
    else:
        # Script mode — install then continue (no restart to avoid loops)
        try:
            cmd = _pip_cmd(missing)
            if cmd:
                subprocess.check_call(cmd)
                _ensure_pkgs_on_path()  # reload path so new packages are found
        except Exception as e:
            print(f'[CF] pip install warning: {e}')

    # Try importing newly installed packages into current process
    import importlib
    for pkg in missing:
        mod_name = pkg.replace('-', '_').split('==')[0]
        try:
            importlib.import_module(mod_name)
        except Exception:
            pass


# Skip auto_install for embedded Python — packages pre-bundled in site-packages
_is_embedded = (_PathBase(sys.executable).parent / "Lib" / "site-packages").exists()
if not _is_embedded:
    auto_install()
_ensure_pkgs_on_path()  # always ensure paths are set
# Suppress HuggingFace warnings globally
import os as _hf_os
_hf_os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
_hf_os.environ.setdefault('HF_HUB_VERBOSITY', 'error')
_hf_os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')

# ── Suppress black console windows on Windows (EXE mode) ─────────────────────
# Every subprocess.run/call/Popen without creationflags spawns a visible cmd
# window briefly on Windows. Patch the defaults so all subprocess calls are
# silent — no black flash windows at startup or during operation.
if _hf_os.name == 'nt':
    import subprocess as _sp_patch
    _CREATE_NO_WINDOW = 0x08000000
    _sp_orig_run    = _sp_patch.run
    _sp_orig_call   = _sp_patch.check_call
    _sp_orig_popen  = _sp_patch.Popen

    def _silent_run(*args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = _CREATE_NO_WINDOW
        return _sp_orig_run(*args, **kwargs)

    def _silent_check_call(*args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = _CREATE_NO_WINDOW
        return _sp_orig_call(*args, **kwargs)

    class _SilentPopen(_sp_orig_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = _CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    _sp_patch.run         = _silent_run

    _sp_patch.check_call  = _silent_check_call
    _sp_patch.Popen       = _SilentPopen
    subprocess.run        = _silent_run
    subprocess.check_call = _silent_check_call
    subprocess.Popen      = _SilentPopen

# Pre-patch curl_cffi — install a meta path finder that stubs ANY missing
# curl_cffi submodule (aio, const, etc.) so broken installs still work
try:
    import sys as _sys_cffi, types as _types_cffi, importlib.abc as _iabc, importlib.machinery as _imach
    class _CurlCffiSubmoduleFinder(_iabc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith('curl_cffi.') and fullname not in _sys_cffi.modules:
                try:
                    # Try real import first
                    return None
                except Exception:
                    pass
            return None
        def find_module(self, fullname, path=None):
            if fullname.startswith('curl_cffi.'):
                return self
            return None
        def load_module(self, fullname):
            if fullname not in _sys_cffi.modules:
                _stub = _types_cffi.ModuleType(fullname)
                # Add common attributes that curl_cffi submodules export
                class _Stub: pass
                for _attr in ('AsyncCurl', 'Curl', 'CurlInfo', 'CurlOpt',
                              'CurlHttpVersion', 'CurlWsFlag', 'CURL_HTTP_VERSION_2'):
                    setattr(_stub, _attr, _Stub)
                _sys_cffi.modules[fullname] = _stub
            return _sys_cffi.modules[fullname]
    # Only add if not already there
    if not any(isinstance(f, _CurlCffiSubmoduleFinder) for f in _sys_cffi.meta_path):
        _sys_cffi.meta_path.append(_CurlCffiSubmoduleFinder())
except Exception: pass

def auto_install_gpu_whisper():
    """Detect GPU and install the right acceleration package for faster-whisper.
    Runs silently in background — does not block startup."""
    import platform as _pl
    if _pl.system() != 'Windows':
        return  # Linux/Mac have different paths

    # Check what's already installed
    try:
        import onnxruntime as _ort
        providers = _ort.get_available_providers()
        if 'DmlExecutionProvider' in providers:
            print('[CF] DirectML already available')
            return
        if 'CUDAExecutionProvider' in providers:
            print('[CF] CUDA onnxruntime already available')
            return
    except ImportError:
        pass  # onnxruntime not installed yet

    # Check for NVIDIA CUDA
    has_cuda = False
    try:
        import torch as _t
        has_cuda = _t.cuda.is_available()
    except ImportError:
        try:
            r = subprocess.run(['nvidia-smi'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            has_cuda = r.returncode == 0
        except Exception:
            pass

    if has_cuda:
        print('[CF] NVIDIA GPU detected — installing onnxruntime-gpu for Whisper...')
        try:
            subprocess.run([_get_pip_executable(), '-m', 'pip', 'install',
                                   'onnxruntime-gpu', '--quiet'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  check=True)
            print('[CF] onnxruntime-gpu installed')
        except Exception as e:
            print(f'[CF] onnxruntime-gpu install failed: {e}')
        return

    # Detect GPU via PowerShell (Win11 compatible), fallback to wmic
    has_gpu = False
    gpu_name = 'Unknown'
    gpu_lines = []
    try:
        import subprocess as _sp2, re as _re2
        r2 = _sp2.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'],
            stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=10, text=True)
        gpu_lines = [l.strip() for l in (r2.stdout or '').splitlines() if l.strip()]
    except Exception:
        pass

    if not gpu_lines:
        try:
            import subprocess as _sp2, re as _re2
            r2 = _sp2.run(['wmic','path','win32_VideoController','get','name'],
                          stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=10, text=True)
            gpu_lines = [l.strip() for l in (r2.stdout or '').splitlines()
                         if l.strip() and l.strip().lower() != 'name']
        except Exception:
            pass

    if gpu_lines:
        import re as _re2
        print(f'[CF] GPUs found: {gpu_lines}')
        for g in gpu_lines:
            if _re2.search(r'AMD|Radeon|RX [0-9]|RTX|GTX|NVIDIA|Arc A[0-9]', g, _re2.I):
                has_gpu = True; gpu_name = g; break
        if not has_gpu:
            for g in gpu_lines:
                if _re2.search(r'Intel|UHD|Iris', g, _re2.I):
                    has_gpu = True; gpu_name = g; break
    else:
        print('[CF] GPU detection failed — assuming GPU present')
        has_gpu = True

    if has_gpu:
        print(f'[CF] Detected GPU for DirectML: {gpu_name}')

    if has_gpu:
        # Check if torch-directml already installed
        try:
            import torch_directml as _tdml
            if _tdml.device_count() > 0:
                print('[CF] torch-directml already available')
                return
        except ImportError:
            pass

        print('[CF] AMD/Intel GPU detected — installing torch-directml for Whisper...')
        try:
            subprocess.run([_get_pip_executable(), '-m', 'pip', 'install',
                            'torch-directml', '--quiet'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True)
            print('[CF] torch-directml installed — AMD/Intel GPU Whisper enabled!')
        except Exception as e:
            # cache clear moved to after block
            print(f'[CF] torch-directml install failed: {e}')
            try:
                subprocess.run([_get_pip_executable(), '-m', 'pip', 'install',
                                'onnxruntime', '--quiet'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

def ensure_ffmpeg():
    """Auto-download ffmpeg if not found. Returns path."""
    import shutil as _sh, zipfile as _zf, tempfile as _tf, urllib.request as _ur
    # Check PATH first
    ff = _sh.which('ffmpeg')
    if ff:
        return ff
    # Check common locations including next to the script
    candidates = [
        _app_path('ffmpeg_bin') / 'ffmpeg.exe',
        _app_path('ffmpeg.exe'),
        Path('C:/ffmpeg/bin/ffmpeg.exe'),
        Path('C:/ffmpeg/ffmpeg.exe'),
        Path.home() / 'ffmpeg' / 'bin' / 'ffmpeg.exe',
        Path.home() / 'ffmpeg' / 'ffmpeg.exe',
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Auto-download
    print('ffmpeg not found — downloading automatically...')
    ff_dir = USER_DIR / 'ffmpeg_bin'
    ff_dir.mkdir(parents=True, exist_ok=True)
    ff_exe = ff_dir / 'ffmpeg.exe'
    import platform as _pl
    if _pl.system() != 'Windows':
        print('Please install ffmpeg: sudo apt install ffmpeg')
        return 'ffmpeg'
    url = ('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/'
           'ffmpeg-master-latest-win64-gpl.zip')
    zip_path = Path(_tf.gettempdir()) / 'ffmpeg_dl.zip'
    print('Downloading ffmpeg (~90MB)...')
    _ur.urlretrieve(url, zip_path)
    with _zf.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('/ffmpeg.exe'):
                with z.open(name) as s, open(ff_exe, 'wb') as d:
                    d.write(s.read())
                break
    zip_path.unlink(missing_ok=True)
    if ff_exe.exists():
        print(f'ffmpeg downloaded to {ff_exe}')
        return str(ff_exe)
    return 'ffmpeg'


# ── Now safe to import everything ─────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import re
import warnings
import traceback
from pathlib import Path

# ── Theme (matches ClipBait) ──────────────────────────────────────────────────
BG      = '#08080A'
BG2     = '#0F0F12'
BG3     = '#161619'
BG4     = '#1E1E22'
ACCENT  = '#FF6B1A'
ACCENT2 = '#FFB020'
FG      = '#F2EFE9'
FG2     = '#6B6862'
FG3     = '#9A948E'
BORDER  = '#28282C'
GREEN   = '#2ECC71'
RED     = '#E74C3C'
YELLOW  = '#F1C40F'

FONT_H2     = ('Segoe UI', 11, 'bold')
FONT_LABEL  = ('Segoe UI', 10)
FONT_SMALL  = ('Segoe UI', 9)
FONT_MONO   = ('Consolas', 10)
FONT_MONO_S = ('Consolas', 9)

# ── AI Providers ──────────────────────────────────────────────────────────────
PROVIDERS = {
    'Google Gemini (Free)': {
        'lib':    'gemini',
        'models': ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-2.5-flash'],
        'url':    'https://aistudio.google.com/apikey',
        'note':   'Free — no credit card needed',
    },
    'Groq (Free)': {
        'lib':    'groq',
        'models': [
            'llama-3.1-8b-instant',    # highest free limits, fast
            'llama3-8b-8192',          # very high limits
            'llama-3.3-70b-versatile', # smarter but lower daily limit
            'mixtral-8x7b-32768',      # good context window
        ],
        'url':    'https://console.groq.com',
        'note':   'Free — no credit card needed',
    },
    'OpenRouter (Free models)': {
        'lib':    'openrouter',
        'models': [
                        'qwen/qwen3.6-plus:free',
            'nvidia/nemotron-3-super-120b-a12b:free',
            'meta-llama/llama-3.3-70b-instruct:free',
            'meta-llama/llama-3.1-8b-instruct:free',
            'google/gemma-3-12b-it:free',
        ],
        'url':    'https://openrouter.ai/keys',
        'note':   '50+ free models — no credit card needed',
    },
}

AUTO_EDIT_PROMPT = """You are a professional video editor for a viral drama/streaming Twitter channel.
{context_block}
Given this timestamped transcript, select segments that together total approximately {target_sec} seconds ({target_min} minutes).

CRITICAL RULES — you MUST follow these:
- TOTAL combined duration must reach AT LEAST {target_sec} seconds — this is the most important rule
- Each individual segment MUST be at least {min_seg_sec} seconds long — never pick a tiny 5-10 second clip
- Prefer FEWER LONGER segments over many short ones — a 3-minute segment is better than six 30-second ones
- Each segment starts where a topic/point begins and ends when it naturally concludes
- Skip dead air, filler ("um", "uh", "like", "you know"), and boring transitions between topics
- Score each segment 1-10 based on: {score_desc}
- Select enough segments to fill the target duration — if you need 10 minutes, pick segments that add up to 10 minutes
- CRITICAL: Every segment MUST end on a completed sentence. Never cut mid-word or mid-sentence

Return ONLY a raw JSON array sorted by {order}:
[
  {{
    "start": "HH:MM:SS",
    "end":   "HH:MM:SS",
    "title": "Short label for this segment",
    "reason": "Why this is good content",
    "score": 9,
    "order": 1
  }}
]

TRANSCRIPT:
{transcript}
"""


AI_PROMPT = """You are an expert viral clip editor for a drama/streaming/gaming channel (@MarsScumbags style).
{context_block}
{names_block}
Find the 3-6 BEST moments to clip. Quality over quantity — 3 great clips beats 8 mediocre ones.

━━━ CLIP LENGTH — NON-NEGOTIABLE ━━━
MINIMUM: 1 minute 00 seconds (60 seconds) — NO EXCEPTIONS
MAXIMUM: 2 minutes 40 seconds (160 seconds)
IDEAL:   1:30 to 2:00 — enough room for full setup + escalation + payoff

If a juicy moment is only 20 seconds, DO NOT clip it alone.
Instead, include the 30-40 seconds BEFORE it (the lead-up/context) to hit minimum length.
If a moment runs over 2:40, find the natural END POINT before the 2:40 mark.
REJECT any clip under 60 seconds — do not output it.

━━━ SELF-CONTAINED RULE ━━━
Every clip must make sense to someone who has NEVER seen this stream.
- Start before the moment — include what caused it
- End AFTER the reaction/punchline/resolution lands fully
- Never cut mid-sentence, mid-thought, or before the crowd/streamer reacts
- Ask: "Would a random person watching this understand what happened?" — if no, extend the start

━━━ WHAT TO LOOK FOR ━━━
1. Hard reveals / confessions with reaction
2. Callouts / confrontations — include the accusation AND the response
3. Escalating rants — setup → build → punchline/explosion
4. Surprising admissions that contradict their image
5. Absurd escalating moments with a clear comedic payoff
6. Strong takes where someone gets pushed back on

━━━ SCORING (each /25) ━━━
- hook: Does the first 5 seconds grab immediately?
- engagement: Does tension build throughout? Does watching to the end feel rewarding?
- value: Real substance, not filler chatter
- shareability: Would people send this to their group chat?
- score (1-10): Only output clips scoring 7+. Be strict.

TITLE: News headline style — "Mizkif admits the prank went too far" not "Funny clip"

LENGTH CHECK: Before outputting, verify each clip is between 60-160 seconds.
Calculate: convert end and start to seconds, subtract. If under 60s, extend or drop it.

Return ONLY a raw JSON array — no markdown, no backticks, no explanation:
[
  {
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "title": "News headline — punchy, max 10 words",
    "summary": "The arc: what set it up, how it escalated, how it paid off",
    "reason": "What literally happens in plain terms",
    "score": 9,
    "hook": 22,
    "engagement": 24,
    "value": 18,
    "shareability": 23
  }
]

TRANSCRIPT:
{transcript}
"""

INTERVIEW_CLIP_PROMPT = """You are an expert clip editor for a drama/streaming Twitter channel.
{context_block}
This is an interview transcript. The interviewer asks questions and names people directly (e.g. "Hey Sophie, what do you think about...").

Interviewees in this interview: {names}

Your job:
1. Identify which person is speaking in each segment based on who was just addressed by the interviewer
2. Find the best 4-8 moments to clip — one clip per person per great moment
3. For each clip, note which person is the subject

CLIP LENGTH — NON-NEGOTIABLE:
- MINIMUM 60 seconds (1 full minute) — no exceptions, extend into lead-up if needed
- MAXIMUM 160 seconds (2 min 40 sec)
- IDEAL 90-120 seconds — question + full answer + reaction
- Never cut mid-sentence — end after the person fully completes their thought and any reaction
- If an answer is short, include more of the question/setup before it to reach 60s minimum

Score each clip 1-10 for viral/drama potential.

Return ONLY a raw JSON array sorted by score DESCENDING:
[
  {{
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "speaker": "Sophie",
    "title": "Punchy title max 8 words",
    "reason": "One sentence why this goes viral",
    "score": 9
  }}
]

TRANSCRIPT:
{transcript}
"""

TWEET_PROMPT = """You are a social media writer for @MarsScumbags, a streaming drama/clip channel on X/Twitter.
Read the transcript carefully. Identify WHO is involved, WHAT happened, and the most shocking/quotable moment.

== PEOPLE & CONTEXT ==
{context}

== TRANSCRIPT ==
{transcript}

== TONE ==
{tone}

== OUTPUT FORMAT ==
Write EXACTLY this — no preamble, no labels other than OPTION 1/2/3:

OPTION 1
[DRAMATIC DRAMA ACCOUNT STYLE — like a real tea/drama Twitter page]
Format it like this:
🚨 SHOCKING HEADLINE IN CAPS 🚨
One sentence setup explaining what happened and why it matters.

🚫 The tea: [pull an ACTUAL quote or specific detail from the transcript in quotes]

The take: [one punchy opinion sentence] [emoji]

#Name1 #Name2 #RelevantTag

OPTION 2
[VIRAL/MEME ENERGY — short, chaotic, makes people stop scrolling. Think "bro said what 💀" energy. Under 220 chars. No bullet points. Could be a reaction, a quote with reaction, or a spicy take. Something people screenshot and repost.]
[hashtags on same line or next line]

OPTION 3
[THREAD OPENER — 240-280 chars. Strong hook that makes people NEED to click or reply. Can end with a cliffhanger or ask a question to drive engagement.]
[hashtags]

== HASHTAG RULES — CRITICAL ==
- Use ACTUAL NAMES from the context as hashtags (#Mizkif #Alinity #xQc)
- Use platform only if relevant (#Kick #Twitch #YouTube)
- Use drama type if it fits (#Exposed #Drama #Beef #Leaked #Scandal)
- NEVER use #gaming #gamingscandal #gamer #streamer unless the clip is literally about gameplay
- Each option gets its OWN hashtags matching what THAT tweet says
- 3-5 hashtags max per option
- If context says "Mizkif reacting to MrBeast" use #Mizkif #MrBeast NOT #gaming

== RULES ==
- Option 1 MUST reference a specific quote or moment from the transcript — not vague
- Option 2 should feel like a real person tweeting, not a press release
- Each option must feel COMPLETELY different in vibe and structure
- Do NOT write "Option 1:" as a label — just write the content after the OPTION 1 header
"""


# Config lives next to the EXE/script so settings survive across launches
# This ensures _setup_done, API keys, folders etc persist properly
CONFIG_FILE = USER_DIR / 'clipfinder_config.json'


def _bind_mousewheel(widget, canvas):
    """Bind mousewheel to scroll a canvas. Call on any frame inside a scrollable canvas."""
    def _on_wheel(e):
        try:
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        except: pass
    widget.bind('<MouseWheel>', _on_wheel)
    widget.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))  # Linux
    widget.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

def _make_scrollbar(parent, canvas, orient='vertical'):
    """Create a custom canvas-drawn scrollbar. Returns None (wires directly to canvas)."""
    SB_W = 12
    frame = tk.Frame(parent, bg=BG2, width=SB_W)
    frame.pack(side='right' if orient == 'vertical' else 'bottom',
               fill='y' if orient == 'vertical' else 'x')
    frame.pack_propagate(False)
    cv = tk.Canvas(frame, bg=BG2, bd=0, highlightthickness=0)
    cv.pack(fill='both', expand=True)
    state = {'lo': 0.0, 'hi': 1.0, 'drag': 0}

    def _draw(*_):
        cv.delete('all')
        W = cv.winfo_width() or SB_W
        H = cv.winfo_height() or 200
        cv.create_rectangle(0, 0, W, H, fill=BG2, outline='')
        lo, hi = state['lo'], state['hi']
        if orient == 'vertical':
            y1 = int(lo * H) + 1; y2 = max(int(hi * H) - 1, y1 + 16)
            cv.create_rectangle(1, y1, W-1, y2, fill=ACCENT, outline='')
        else:
            x1 = int(lo * W) + 1; x2 = max(int(hi * W) - 1, x1 + 16)
            cv.create_rectangle(x1, 1, x2, H-1, fill=ACCENT, outline='')

    def _set(lo, hi):
        state['lo'] = float(lo); state['hi'] = float(hi); _draw()

    def _press(e): state['drag'] = e.y if orient == 'vertical' else e.x

    def _drag(e):
        pos = e.y if orient == 'vertical' else e.x
        dim = cv.winfo_height() if orient == 'vertical' else cv.winfo_width()
        dy = (pos - state['drag']) / max(dim, 1)
        state['drag'] = pos
        span = state['hi'] - state['lo']
        canvas.yview_moveto(max(0, min(1 - span, state['lo'] + dy))) if orient == 'vertical'             else canvas.xview_moveto(max(0, min(1 - span, state['lo'] + dy)))

    def _click(e):
        dim = cv.winfo_height() if orient == 'vertical' else cv.winfo_width()
        frac = (e.y if orient == 'vertical' else e.x) / max(dim, 1)
        span = state['hi'] - state['lo']
        canvas.yview_moveto(max(0, min(1 - span, frac - span / 2))) if orient == 'vertical'             else canvas.xview_moveto(max(0, min(1 - span, frac - span / 2)))

    cv.bind('<ButtonPress-1>', _press)
    cv.bind('<B1-Motion>', _drag)
    cv.bind('<Button-1>', _click)
    cv.bind('<Configure>', _draw)
    canvas.configure(yscrollcommand=_set) if orient == 'vertical' else canvas.configure(xscrollcommand=_set)
    return _set

def load_cfg():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}

def save_cfg(d):
    try:
        CONFIG_FILE.write_text(json.dumps(d, indent=2))
    except Exception:
        pass

def attach_rightclick(widget, root):
    """Attach a right-click context menu to any widget based on its type."""
    def show_menu(e):
        menu = tk.Menu(root, tearoff=0, bg='#1A1A1D', fg='#F0EDE8',
                       activebackground='#E8651A', activeforeground='#000',
                       font=('Segoe UI', 9), relief='flat', bd=1)
        wtype = type(widget).__name__

        if wtype in ('Entry',):
            menu.add_command(label='Cut',        command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label='Copy',       command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label='Paste',      command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label='Select All', command=lambda: widget.event_generate('<<SelectAll>>'))
            menu.add_separator()
            menu.add_command(label='Clear',      command=lambda: widget.delete(0, 'end'))
        elif wtype in ('Text', 'ScrolledText'):
            menu.add_command(label='Copy',       command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_separator()
            menu.add_command(label='Select All', command=lambda: (
                widget.tag_add('sel', '1.0', 'end')))
            # If editable
            if str(widget.cget('state')) != 'disabled':
                menu.add_separator()
                menu.add_command(label='Cut',   command=lambda: widget.event_generate('<<Cut>>'))
                menu.add_command(label='Paste', command=lambda: widget.event_generate('<<Paste>>'))
                menu.add_command(label='Clear', command=lambda: (
                    widget.config(state='normal'), widget.delete('1.0','end')))
        else:
            return  # no menu for labels, frames, buttons etc

        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    widget.bind('<Button-3>', show_menu)

def apply_rightclick_to_all(widget, root):
    """Recursively attach right-click menus to all Entry and Text widgets."""
    attach_rightclick(widget, root)
    for child in widget.winfo_children():
        apply_rightclick_to_all(child, root)

# ── Helpers ───────────────────────────────────────────────────────────────────
def ts(s):
    s = int(float(s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'

def ts_srt(s):
    """Convert seconds to SRT HH:MM:SS,mmm — CapCut/Premiere compatible."""
    s   = float(s)
    h   = int(s // 3600); s -= h * 3600
    m   = int(s // 60);   s -= m * 60
    sec = int(s)
    ms  = min(round((s - sec) * 1000), 999)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'


def detect_gpu_encoder(ff):
    """Detect best available GPU encoder. Returns (vcodec, acodec, extra_args).
    Priority: NVIDIA NVENC > AMD AMF > Intel QSV > CPU fallback."""
    try:
        r = subprocess.run([ff, '-encoders'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        enc_list = (r.stdout or b'').decode(errors='replace') + (r.stderr or b'').decode(errors='replace')

        # NVIDIA NVENC
        if 'h264_nvenc' in enc_list:
            # Quick test that NVENC actually works (card must be connected)
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: NVIDIA NVENC detected')
                return 'h264_nvenc', 'aac', ['-preset', 'p5', '-rc', 'vbr', '-cq', '18', '-b:v', '0', '-maxrate', '20M', '-profile:v', 'high', '-b:a', '192k']

        # AMD AMF (Windows)
        if 'h264_amf' in enc_list:
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_amf', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: AMD AMF detected (RX 6600 XT)')
                # usage=transcoding for quality, quality=speed for fast encode
                # rc=vbr_latency + qvbr_quality_level=23 = good quality fast
                return 'h264_amf', 'aac', ['-usage', 'transcoding', '-quality', 'quality', '-rc', 'vbr_peak', '-qvbr_quality_level', '18', '-profile:v', 'high', '-b:v', '8M', '-maxrate', '20M', '-b:a', '192k']

        # Intel QSV
        if 'h264_qsv' in enc_list:
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_qsv', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: Intel QSV detected')
                return 'h264_qsv', 'aac', ['-preset', 'medium', '-global_quality', '18', '-look_ahead', '1', '-b:a', '192k']

    except Exception as ex:
        print(f'[CF] GPU detection failed: {ex}')

    print('[CF] CPU: libx264 — high quality')
    return 'libx264', 'aac', [
        '-preset', 'slow', '-crf', '18', '-profile:v', 'high',
        '-movflags', '+faststart', '-b:a', '192k',
    ]

# Cache result so we only probe once per session
_GPU_ENCODER_CACHE = None
_GPU_ENCODER_RESET = False
def detect_encoder_name():
    try:
        v,_,_ = get_encoder(ensure_ffmpeg())
        return v
    except: return "cpu"

def get_encoder(ff):
    global _GPU_ENCODER_CACHE
    if _GPU_ENCODER_CACHE is None:
        _GPU_ENCODER_CACHE = detect_gpu_encoder(ff)
    return _GPU_ENCODER_CACHE

def find_ffmpeg():
    for p in [
        Path('C:/ffmpeg/bin/ffmpeg.exe'),
        Path('C:/ffmpeg/ffmpeg.exe'),
        _app_path('ffmpeg_bin') / 'ffmpeg.exe',
    ]:
        if p.exists():
            return str(p)
    import shutil
    ff = shutil.which('ffmpeg')
    return ff or 'ffmpeg'

# ── Main App ──────────────────────────────────────────────────────────────────
# Cache detected device so we only probe once per session
# Reset on launch so newly installed packages are detected
_WHISPER_DEVICE_CACHE = None

def _detect_whisper_device():
    """Detect best available compute device for whisper transcription.
    Returns (device, compute_type, label)"""
    global _WHISPER_DEVICE_CACHE
    if _WHISPER_DEVICE_CACHE:
        return _WHISPER_DEVICE_CACHE

    # ── 0. whisper.cpp + Vulkan (best for AMD/Intel on Windows) ──────────────
    if _find_whispercpp() and _find_whispercpp_model('base'):
        # Return cpu/int8 so faster-whisper fallback works correctly
        # The 'whispercpp' label is just for display
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'whisper.cpp Vulkan GPU ⚡')
        return _WHISPER_DEVICE_CACHE

    # ── 1. NVIDIA CUDA ────────────────────────────────────────────────────────
    try:
        import torch as _torch
        if _torch.cuda.is_available():
            name = _torch.cuda.get_device_name(0)
            _WHISPER_DEVICE_CACHE = ('cuda', 'float16', f'NVIDIA CUDA ({name})')
            return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # Test CUDA directly via faster-whisper
    try:
        _FW = _fresh_import('faster_whisper').WhisperModel
        _t = _FW('tiny', device='cuda', compute_type='float16',
                 download_root=str(_app_path('whisper_models')))
        del _t
        _WHISPER_DEVICE_CACHE = ('cuda', 'float16', 'NVIDIA CUDA')
        return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # ── 2. torch-directml (AMD/Intel on Windows) ──────────────────────────────
    try:
        import torch_directml as _dml
        if _dml.device_count() > 0:
            _WHISPER_DEVICE_CACHE = ('directml', 'float16', 'AMD/Intel DirectML GPU')
            return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # ── 3. CPU int8 via CTranslate2 — still 4x faster than openai-whisper ────
    # Check if faster-whisper is actually installed before claiming it
    try:
        import faster_whisper as _fw_check  # noqa
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'CPU int8 (faster-whisper)')
    except ImportError:
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'Not installed — use Settings → Update Modules')
    return _WHISPER_DEVICE_CACHE


_WCPP_INSTALL_LOCK = None  # module-level flag to prevent duplicate installs

def auto_install_whispercpp(model_size='base', status_cb=None):
    """Auto-download whisper-whisper-cli.exe (Vulkan) + ggml model for AMD/Intel GPU."""
    global _WCPP_INSTALL_LOCK
    import threading as _thr_lock
    if _WCPP_INSTALL_LOCK is not None:
        return  # already running or done
    _WCPP_INSTALL_LOCK = True
    global _WHISPER_DEVICE_CACHE
    import urllib.request as _ur, zipfile as _zf, tempfile as _tf
    import platform as _pl, shutil as _sh, json as _j

    def _log(msg):
        if not status_cb: print(f'[CF] {msg}')
        if status_cb: status_cb(msg)

    if _pl.system() != 'Windows':
        return

    install_dir = _app_path('whisper_cpp')
    models_dir  = install_dir / 'models'
    real_exe    = install_dir / 'whisper-whisper-cli.exe'
    model_path  = models_dir  / f'ggml-{model_size}.bin'

    install_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Download binary if needed ────────────────────────────────────
    if real_exe.exists():
        _size_mb = real_exe.stat().st_size // 1024 // 1024
        if _size_mb < 10:
            _log(f'Binary exists but only {_size_mb}MB — too small, deleting and re-downloading...')
            real_exe.unlink()
        else:
            _log(f'Binary already exists: {real_exe.name} ({_size_mb}MB)')
    if not real_exe.exists():
        _log('Downloading whisper-whisper-cli.exe (Vulkan)...')
        tmp_zip = Path(_tf.gettempdir()) / 'whispercpp.zip'
        asset_url = None

        # Fetch latest release and find the right asset URL directly
        try:
            req = _ur.Request(
                'https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest',
                headers={'User-Agent': 'ClipFinder/1.0'})
            with _ur.urlopen(req, timeout=20) as resp:
                release = _j.loads(resp.read())

            tag = release.get('tag_name', '')
            _log(f'Latest release: {tag}')
            all_assets = [(a['name'], a['browser_download_url'])
                          for a in release.get('assets', [])]
            _log(f'Available assets: {[n for n,_ in all_assets]}')

            # Priority order for Windows x64 Vulkan-capable builds
            # v1.7.x: whisper-*-bin-x64-release-vulkan.zip
            # v1.8.x: whisper-bin-x64.zip (has Vulkan support built in)
            PREFER = ['bin-x64', 'vulkan', 'win']  # terms that indicate good builds
            AVOID  = ['win32', 'blas', 'cublas', 'xcframework', '.jar']
            scored = []
            for name, url in all_assets:
                nl = name.lower()
                if not nl.endswith('.zip'): continue
                if any(a in nl for a in AVOID): continue
                score = sum(1 for p in PREFER if p in nl)
                if score > 0:
                    scored.append((score, name, url))
            scored.sort(reverse=True)
            if scored:
                _, best_name, asset_url = scored[0]
                _log(f'Selected: {best_name} (score={scored[0][0]})')
            # Last resort: any zip not explicitly bad
            if not asset_url:
                for name, url in all_assets:
                    nl = name.lower()
                    if nl.endswith('.zip') and not any(a in nl for a in AVOID):
                        asset_url = url
                        _log(f'Fallback asset: {name}')
                        break
        except Exception as e:
            _log(f'GitHub API failed: {e}')

        # Hardcoded fallbacks using known-good direct asset URLs
        if not asset_url:
            fallbacks = [
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.4/whisper-1.7.4-bin-x64-release.zip',
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.3/whisper-1.7.3-bin-x64-release.zip',
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.2/whisper-1.7.2-bin-x64-release.zip',
            ]
            for fb in fallbacks:
                try:
                    _log(f'Trying: {fb.split("/")[-1]}')
                    _ur.urlretrieve(fb, str(tmp_zip))
                    if tmp_zip.exists() and tmp_zip.stat().st_size > 100000:
                        asset_url = fb
                        _log('Fallback download succeeded')
                        break
                    else:
                        tmp_zip.unlink(missing_ok=True)
                except Exception as e:
                    _log(f'  Failed: {e}')
                    continue

        if not asset_url:
            _log('ERROR: Could not find a download URL. Check https://github.com/ggerganov/whisper.cpp/releases')
            return

        # Download if not already got from fallback loop
        if not tmp_zip.exists() or tmp_zip.stat().st_size < 100000:
            _log('Downloading zip...')
            try:
                def _dlprogress(count, block, total):
                    if total > 0 and count % 500 == 0:
                        pct = min(100, int(count * block / total * 100))
                        _log(f'Downloading... {pct}%')
                _ur.urlretrieve(asset_url, str(tmp_zip), reporthook=_dlprogress)
            except Exception as e:
                _log(f'Download failed: {e}')
                return

        # Extract
        _log('Extracting...')
        try:
            with _zf.ZipFile(str(tmp_zip), 'r') as z:
                exe_names = [n for n in z.namelist() if n.endswith('.exe')]
                _log(f'Executables in zip: {[Path(n).name for n in exe_names]}')
                all_names = z.namelist()
                _log(f'Zip contains: {[Path(n).name for n in all_names if not n.endswith("/")]}')
                for zname in all_names:
                    bn = Path(zname).name
                    if not bn or zname.endswith('/'): continue
                    if 'deprecation' in bn.lower(): continue
                    # Extract EVERYTHING — exes, dlls, models, config files
                    data = z.read(zname)
                    dest = install_dir / bn
                    if len(data) > 0:
                        dest.write_bytes(data)
                        if bn.endswith(('.exe','.dll')):
                            _log(f'Extracted: {bn} ({len(data)//1024}KB)')
            tmp_zip.unlink(missing_ok=True)
        except Exception as e:
            _log(f'Extraction failed: {e}')
            return

        # Find the real CLI binary — prefer whisper-cli.exe or main.exe
        # Explicitly avoid server, talk-llama, stream, command (wrong tools)
        AVOID_NAMES = ['talk-llama', 'server', 'stream', 'command', 'bench',
                       'quantize', 'lsp', 'wchess', 'vad', 'test']
        if not real_exe.exists():
            # First try exact names
            for try_name in ['whisper-cli.exe', 'main.exe']:
                candidate = install_dir / try_name
                if candidate.exists() and candidate.stat().st_size > 50_000:
                    _sh.copy2(str(candidate), str(real_exe))
                    _log(f'Linked {candidate.name} → {real_exe.name}')
                    break
        # Still not found? Pick smallest whisper*.exe that isn't a known wrong tool
        if not real_exe.exists():
            candidates = [
                p for p in install_dir.glob('whisper*.exe')
                if not any(a in p.name.lower() for a in AVOID_NAMES)
                and p.stat().st_size > 50_000
            ]
            if candidates:
                best = min(candidates, key=lambda p: p.stat().st_size)
                _sh.copy2(str(best), str(real_exe))
                _log(f'Linked {best.name} → {real_exe.name}')

        if not real_exe.exists():
            _log('ERROR: Binary not found after extraction')
            return

    _bsz = real_exe.stat().st_size
    _bsz_s = f'{_bsz//1024//1024}MB' if _bsz >= 1024*1024 else f'{_bsz//1024}KB'
    _log(f'Binary ready: {real_exe.name} ({_bsz_s})')
    _log(f'Files in whisper_cpp/: {[f.name for f in install_dir.glob("*") if f.is_file()]}')

    # ── Test run the binary to check for missing DLLs ─────────────────────────
    import subprocess as _sp_test
    test = _sp_test.run([str(real_exe), '--help'],
                       stdout=_sp_test.PIPE, stderr=_sp_test.PIPE, timeout=10)
    test_out = (test.stdout or b'').decode(errors='replace') + (test.stderr or b'').decode(errors='replace')
    if test.returncode == 3221225781 or test.returncode == -1073741819:
        _log('WARNING: Binary has DLL issues even with --help. Missing runtime DLLs.')
        _log(f'Test output: {test_out[:200]}')
    elif 'usage' in test_out.lower() or 'whisper' in test_out.lower() or test.returncode == 0:
        _log('Binary test OK — whisper.cpp ready to use GPU!')
    else:
        _log(f'Binary test rc={test.returncode}: {test_out[:200]}')

    # ── Copy Vulkan DLL next to binary so it can find it ─────────────────────
    vulkan_dll = install_dir / 'vulkan-1.dll'
    if not vulkan_dll.exists():
        _log('Looking for vulkan-1.dll...')
        # Search common AMD Adrenalin / system locations
        search_paths = [
            Path('C:/Windows/System32/vulkan-1.dll'),
            Path('C:/Windows/SysWOW64/vulkan-1.dll'),
        ]
        # AMD Adrenalin installs Vulkan in its own dir
        import glob as _glob
        for pattern in [
            'C:/Program Files/AMD/CNext/CNext/vulkan-1.dll',
            'C:/Program Files*/AMD*/vulkan-1.dll',
            'C:/Windows/System32/DriverStore/FileRepository/*/vulkan-1-*.dll',
        ]:
            for p in _glob.glob(pattern):
                search_paths.append(Path(p))

        found_vulkan = None
        for p in search_paths:
            if p.exists():
                found_vulkan = p
                break

        if found_vulkan:
            try:
                _sh.copy2(str(found_vulkan), str(vulkan_dll))
                _log(f'Copied {found_vulkan.name} from {found_vulkan.parent}')
            except Exception as e:
                _log(f'Could not copy vulkan DLL: {e}')
        else:
            _log('vulkan-1.dll not found in system — Vulkan GPU may not work')
            _log('Reinstall AMD Adrenalin drivers to fix this')

    # ── Step 2: Download ggml model ───────────────────────────────────────────
    if model_path.exists():
        _log(f'Model already exists: {model_path.name}')
    else:
        model_url = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                     f'ggml-{model_size}.bin')
        _sizes = {'tiny': 75, 'base': 142, 'small': 466, 'medium': 1500}
        _log(f'Downloading ggml-{model_size}.bin (~{_sizes.get(model_size, 142)}MB)...')
        try:
            def _reporthook(count, block, total):
                if total > 0 and count % 300 == 0:
                    pct = min(100, int(count * block / total * 100))
                    _log(f'Model: {pct}%')
            _ur.urlretrieve(model_url, str(model_path), reporthook=_reporthook)
            _log(f'Model ready: {model_path.name}')
        except Exception as e:
            _log(f'Model download failed: {e}')
            return

    _log('whisper.cpp GPU transcription ready! Restart or start a new transcription.')
    _WHISPER_DEVICE_CACHE = None

def _analyze_audio_energy(video_path, ffmpeg_path, num_peaks=15):
    """
    Analyze audio energy in a video to find loud/reaction moments.
    Returns list of peak timestamps sorted by energy (highest first).
    Uses ffmpeg volumedetect + astats to find spikes.
    """
    import subprocess as _sp, re as _re, json as _js
    try:
        # Get audio stats per 1-second window using silencedetect + volumedetect
        cmd = [ffmpeg_path, '-i', video_path,
               '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
               '-f', 'null', '-']
        r = _sp.run(cmd, capture_output=True, text=True, timeout=300)
        output = r.stderr + r.stdout

        # Parse RMS levels per frame
        rms_vals = []
        for m in _re.finditer(r'pts_time:([\d.]+).*?RMS_level=([\d.-]+)', output, _re.DOTALL):
            try:
                t = float(m.group(1))
                db = float(m.group(2))
                if db > -91:  # ignore silence
                    rms_vals.append((t, db))
            except: continue

        if not rms_vals:
            # Fallback: use silencedetect to find non-silent periods
            cmd2 = [ffmpeg_path, '-i', video_path,
                   '-af', 'silencedetect=noise=-30dB:d=0.5',
                   '-f', 'null', '-']
            r2 = _sp.run(cmd2, capture_output=True, text=True, timeout=300)
            loud_times = []
            for m in _re.finditer(r'silence_end: ([\d.]+)', r2.stderr):
                loud_times.append(float(m.group(1)))
            return sorted(loud_times[:num_peaks])

        # Sort by RMS level descending, get top peaks
        rms_vals.sort(key=lambda x: x[1], reverse=True)
        # Deduplicate — keep peaks at least 10s apart
        peaks = []
        for t, db in rms_vals:
            if all(abs(t - p) > 10 for p in peaks):
                peaks.append(t)
            if len(peaks) >= num_peaks:
                break
        return sorted(peaks)

    except Exception as e:
        print(f'[CF] Audio energy analysis failed: {e}')
        return []


def _analyze_scene_changes(video_path, ffmpeg_path, threshold=0.4):
    """
    Detect scene changes using ffmpeg scene filter.
    Returns list of timestamps where scene cuts happen.
    """
    import subprocess as _sp, re as _re
    try:
        cmd = [ffmpeg_path, '-i', video_path,
               '-vf', f'select=gt(scene\\,{threshold}),metadata=print:key=lavfi.scene_score',
               '-f', 'null', '-']
        r = _sp.run(cmd, capture_output=True, text=True, timeout=300)
        output = r.stderr + r.stdout
        times = []
        for m in _re.finditer(r'pts_time:([\d.]+)', output):
            try: times.append(float(m.group(1)))
            except: continue
        return sorted(set(times))
    except Exception as e:
        print(f'[CF] Scene change analysis failed: {e}')
        return []


def _find_whispercpp():
    """Find real whisper.cpp transcription binary.
    Validates the binary actually does transcription (not talk-llama or other tools)."""
    import shutil as _sh, subprocess as _sp3
    auto_dir = _app_path('whisper_cpp')

    def _is_real_whisper(exe_path):
        """Return True if this exe is actually whisper transcription, not talk-llama etc."""
        try:
            r = _sp3.run([str(exe_path), '--help'],
                        stdout=_sp3.PIPE, stderr=_sp3.PIPE, timeout=5)
            out = ((r.stdout or b'') + (r.stderr or b'')).decode(errors='replace').lower()
            # Real whisper outputs: --language, --model, --output-json etc
            # talk-llama outputs: --speak, --tts, to_speak.txt
            if 'to_speak' in out or 'talk-llama' in out or 'tts' in out:
                print(f'[CF] Rejecting {Path(exe_path).name} — appears to be talk-llama not whisper')
                return False
            if 'server' in Path(exe_path).name.lower() and ('port' in out or 'host' in out or '--port' in out):
                print(f'[CF] Rejecting {Path(exe_path).name} — appears to be HTTP server not CLI')
                return False
            if '--language' in out or '--model' in out or 'output-json' in out or '-oj' in out:
                return True
            # Fallback: if it's big enough and not obviously wrong, try it
            return Path(exe_path).stat().st_size > 50_000  # >50KB = real binary
        except Exception:
            return False

    if auto_dir.exists():
        # Check preferred names first before scanning all candidates
        for _pref in ['whisper-whisper-cli.exe', 'whisper-cli.exe', 'main.exe']:
            _p = auto_dir / _pref
            if _p.exists() and _p.stat().st_size > 50_000 and _is_real_whisper(_p):
                return str(_p)

        # Fall back to scanning all — sort by preference (avoid known-bad names)
        BAD = ['talk-llama', 'server', 'stream', 'command', 'bench',
               'quantize', 'lsp', 'wchess', 'vad', 'test']
        candidates = sorted(
            [p for p in auto_dir.glob('*.exe')
             if p.stat().st_size > 50_000
             and not any(b in p.name.lower() for b in BAD)],
            key=lambda x: x.stat().st_size  # smallest first — whisper-cli before talk-llama
        )
        for p in candidates:
            if _is_real_whisper(p):
                return str(p)
        # Log what was rejected
        all_big = [p for p in auto_dir.glob('*.exe') if p.stat().st_size > 50_000]
        if all_big:
            print(f'[CF] No valid whisper binary. All exes: {[(p.name, p.stat().st_size//1024) for p in all_big]}')
            print('[CF] Delete whisper_cpp/ folder to force re-download')

    for name in ['whisper-whisper-cli', 'whisper-cli']:
        found = _sh.which(name)
        if found and _is_real_whisper(found):
            return found
    return None

def _find_whispercpp_model(model_size):
    """Find ggml model — checks auto-install dir first."""
    model_map = {'tiny':'tiny','base':'base','small':'small','medium':'medium','large':'large-v3'}
    name = model_map.get(model_size, model_size)
    search_dirs = [
        _app_path('whisper_cpp') / 'models',  # auto-install
        _app_path('whisper.cpp') / 'models',
        Path('C:/whisper.cpp/models'),
        Path.home() / '.cache' / 'whisper',
    ]
    for d in search_dirs:
        for pattern in [f'ggml-{name}.bin', f'ggml-{name}-q5_0.bin', f'ggml-{name}-q8_0.bin']:
            p = d / pattern
            if p.exists(): return str(p)
    return None

def _do_transcribe(vid, model_size, initial_prompt=None, ffmpeg_path=None, progress_cb=None, use_word_timestamps=False):
    """Transcribe with best available backend:
    1. whisper.cpp + Vulkan (AMD/Intel/NVIDIA GPU on Windows — fastest)
    2. faster-whisper + CUDA (NVIDIA only)
    3. faster-whisper CPU int8 (always works, 4x faster than openai-whisper)
    4. openai-whisper CPU fallback
    """
    _ensure_pkgs_on_path()  # always check PKGS_DIR before importing whisper
    import os as _os, warnings as _wn
    _wn.filterwarnings('ignore')
    _os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
    _os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
    _os.environ.setdefault('HF_HUB_VERBOSITY', 'error')

    # Patch ffmpeg into PATH
    if ffmpeg_path and ffmpeg_path != 'ffmpeg':
        ff_dir = str(Path(ffmpeg_path).parent)
        _os.environ['PATH'] = ff_dir + _os.pathsep + _os.environ.get('PATH', '')

    # ── 1. whisper.cpp with Vulkan — AMD/Intel/NVIDIA GPU on Windows ─────────
    _wcpp = _find_whispercpp()
    _wmodel = _find_whispercpp_model(model_size) if _wcpp else None
    if _wcpp and _wmodel:
        try:
            import subprocess as _sp2, tempfile as _tf2, json as _j2, re as _re2
            print(f'[CF] whisper.cpp found: {_wcpp}')
            print(f'[CF] Whisper device: Vulkan GPU (whisper.cpp)')

            # Extract audio to wav first
            ff2 = ffmpeg_path or 'ffmpeg'
            tmp_wav = Path(_tf2.gettempdir()) / 'cf_wcpp_audio.wav'
            _sp2.run([ff2, '-y', '-i', vid, '-ar', '16000', '-ac', '1',
                      '-f', 'wav', str(tmp_wav)],
                     stdout=_sp2.PIPE, stderr=_sp2.PIPE)

            if tmp_wav.exists():
                # Output goes to same dir as wav file, named <stem>.json
                out_base = str(tmp_wav.with_suffix(''))  # no extension
                json_out = Path(out_base + '.json')

                # Build command — use -oj for JSON output (newer builds)
                # -t threads, no --gpu-device flag (auto-selects Vulkan)
                # Try -oj (newer builds) first, fall back to --output-json (older)
                cmd = [_wcpp,
                       '-m', _wmodel,
                       '-f', str(tmp_wav),
                       '-oj',                       # output JSON (newer flag)
                       '--output-file', out_base,
                       '-t', '4',
                       '-l', 'auto',
                ]
                if initial_prompt:
                    clean_prompt = initial_prompt[:200].replace('"', "'").strip()
                    cmd += ['--prompt', clean_prompt]

                print(f'[CF] whisper.cpp cmd: {" ".join(cmd)}')
                # Use Popen to stream output for live progress
                import re as _re_wcpp
                proc = _sp2.Popen(cmd, stdout=_sp2.PIPE, stderr=_sp2.PIPE)
                # Get video duration for percentage
                try:
                    import cv2 as _cv_dur
                    _cap_dur = _cv_dur.VideoCapture(vid)
                    _dur_wcpp = _cap_dur.get(_cv_dur.CAP_PROP_FRAME_COUNT) / max(_cap_dur.get(_cv_dur.CAP_PROP_FPS), 1)
                    _cap_dur.release()
                except: _dur_wcpp = 0
                stdout_lines = []
                stderr_lines = []
                # Read stderr (whisper.cpp writes progress there)
                import threading as _th_wcpp
                def _read_stderr():
                    for line in proc.stderr:
                        decoded = line.decode(errors='replace').strip()
                        stderr_lines.append(decoded)
                        # Parse timestamp: [MM:SS.mmm --> MM:SS.mmm]
                        _tm = _re_wcpp.search(r'\[(\d+):(\d+\.\d+)\s*-->', decoded)
                        if _tm and progress_cb and _dur_wcpp > 0:
                            mins, secs = int(_tm.group(1)), float(_tm.group(2))
                            cur = mins * 60 + secs
                            pct = min(99, int(cur / _dur_wcpp * 100))
                            dm, ds = divmod(int(cur), 60)
                            tm, ts = divmod(int(_dur_wcpp), 60)
                            progress_cb(pct, f'Transcribing (GPU)... {dm}:{ds:02d} / {tm}:{ts:02d}  ({pct}%)')
                def _read_stdout():
                    for line in proc.stdout:
                        stdout_lines.append(line.decode(errors='replace'))
                t1 = _th_wcpp.Thread(target=_read_stderr, daemon=True); t1.start()
                t2 = _th_wcpp.Thread(target=_read_stdout, daemon=True); t2.start()
                # Store proc so cancel can kill it
                _active_procs = getattr(_do_transcribe, '_active_procs', [])
                _active_procs.append(proc)
                _do_transcribe._active_procs = _active_procs
                proc.wait(timeout=3600)
                _do_transcribe._active_procs = [p for p in _active_procs if p != proc]
                t1.join(timeout=5); t2.join(timeout=5)
                stderr_txt = '\n'.join(stderr_lines)
                stdout_txt = '\n'.join(stdout_lines)
                if progress_cb: progress_cb(99, 'Finalising transcript...')
                class _FakeResult:
                    returncode = proc.returncode
                r = _FakeResult()

                # whisper.cpp sometimes writes <file>.wav.json instead of <file>.json
                if not json_out.exists():
                    alt = Path(str(tmp_wav) + '.json')
                    if alt.exists(): json_out = alt
                # Or it may print JSON to stdout
                if not json_out.exists() and stdout_txt.strip().startswith('{'):
                    json_out.write_text(stdout_txt, encoding='utf-8')

                if json_out.exists():
                    data = _j2.loads(json_out.read_text(encoding='utf-8'))
                    segments = []
                    for seg in data.get('transcription', []):
                        start_ms = seg.get('offsets', {}).get('from', 0)
                        end_ms   = seg.get('offsets', {}).get('to', 0)
                        text     = seg.get('text', '').strip()
                        sd = {
                            'start': start_ms / 1000.0,
                            'end':   end_ms   / 1000.0,
                            'text':  text,
                        }
                        if use_word_timestamps and seg.get('tokens'):
                            sd['words'] = [
                                {'word': t.get('text',''), 'start': t.get('offsets',{}).get('from',0)/1000,
                                 'end': t.get('offsets',{}).get('to',0)/1000}
                                for t in seg.get('tokens', []) if t.get('text','').strip()
                            ]
                        segments.append(sd)
                    try: tmp_wav.unlink()
                    except: pass
                    try: json_out.unlink()
                    except: pass
                    if progress_cb:
                        progress_cb(100, f'whisper.cpp done: {len(segments)} segments')
                    print(f'[CF] whisper.cpp done: {len(segments)} segments')
                    return {'segments': segments, 'language': 'en'}
                else:
                    rc = r.returncode
                    print(f'[CF] whisper.cpp failed (rc={rc})')
                    print(f'[CF]   stderr: {stderr_txt[-300:]}')
                    print(f'[CF]   stdout: {stdout_txt[:200]}')

                    # Build cmd without --no-prints for all retries
                    cmd_clean = [c for c in cmd if c != '--no-prints']

                    if rc == 3221225781 or rc == -1073741819:
                        print('[CF] STATUS_ACCESS_VIOLATION — missing Vulkan DLL')
                        _wcpp_dir = Path(_wcpp).parent
                        _vulkan_dst = _wcpp_dir / 'vulkan-1.dll'
                        if not _vulkan_dst.exists():
                            import glob as _gl2, shutil as _sh2
                            _vp_candidates = [
                                'C:/Windows/System32/vulkan-1.dll',
                                'C:/Program Files/AMD/CNext/CNext/vulkan-1.dll',
                                'C:/Program Files (x86)/AMD/CNext/CNext/vulkan-1.dll',
                            ] + list(_gl2.glob('C:/Windows/System32/DriverStore/FileRepository/*/vulkan-1-999-0-0-0.dll'))
                            for _vp in _vp_candidates:
                                if Path(_vp).exists():
                                    try:
                                        _sh2.copy2(_vp, str(_vulkan_dst))
                                        print(f'[CF] Copied vulkan-1.dll from {_vp}')
                                    except Exception as _ve:
                                        print(f'[CF] Copy failed: {_ve}')
                                    break
                        # Retry after DLL copy
                        if _vulkan_dst.exists():
                            print('[CF] Retrying with Vulkan DLL in place...')
                            r3 = _sp2.run(cmd_clean, stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=3600)
                            stderr3 = (r3.stderr or b'').decode(errors='replace')
                            stdout3 = (r3.stdout or b'').decode(errors='replace')
                            print(f'[CF] Vulkan retry rc={r3.returncode}')
                            if r3.returncode == 0 and json_out.exists():
                                # Success! Parse and return
                                _data3 = _j2.loads(json_out.read_text(encoding='utf-8'))
                                segments = []
                                for _seg in _data3.get('transcription', []):
                                    _s = _seg.get('offsets',{}).get('from',0)
                                    _e = _seg.get('offsets',{}).get('to',0)
                                    segments.append({'start':_s/1000.0,'end':_e/1000.0,
                                                    'text':_seg.get('text','').strip()})
                                print(f'[CF] whisper.cpp GPU success! {len(segments)} segments')
                                try: tmp_wav.unlink()
                                except: pass
                                try: json_out.unlink()
                                except: pass
                                return {'segments': segments, 'language': 'en'}
                            else:
                                print(f'[CF] Still failing after DLL copy (rc={r3.returncode})')
                                print(f'[CF] stderr: {stderr3[-300:]}')
                                dlls = list(_wcpp_dir.glob('*.dll'))
                                print(f'[CF] DLLs in whisper_cpp/: {[d.name for d in dlls]}')
                        else:
                            print('[CF] vulkan-1.dll not found on system — cannot auto-fix')

                    # Standard retry without --no-prints
                    # Retry with --output-json fallback (older builds)
                    if '-oj' in cmd:
                        print('[CF] Retrying without --no-prints flag...')
                        cmd_fallback = [c if c != '-oj' else '--output-json' for c in cmd_clean]
                        r2 = _sp2.run(cmd_fallback, stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=3600)
                        if json_out.exists() and json_out.stat().st_size > 10:
                            data = _j2.loads(json_out.read_text(encoding='utf-8'))
                            segments = []
                            for seg in data.get('transcription', []):
                                start_ms = seg.get('offsets',{}).get('from',0)
                                end_ms   = seg.get('offsets',{}).get('to',0)
                                segments.append({
                                    'start': start_ms/1000.0,
                                    'end':   end_ms/1000.0,
                                    'text':  seg.get('text','').strip()
                                })
                            print(f'[CF] whisper.cpp retry succeeded: {len(segments)} segments')
                            return {'segments': segments, 'language': 'en'}
                        print(f'[CF] Retry also failed: {(r2.stderr or b"").decode(errors="replace")[-200:]}')
        except Exception as _wcpp_err:
            print(f'[CF] whisper.cpp error: {_wcpp_err}, falling back...')
    elif _wcpp and not _wmodel:
        print(f'[CF] whisper.cpp: no ggml-{model_size}.bin — downloading now...')
        try:
            import urllib.request as _ur2, threading as _thr2
            _models_dir = _app_path('whisper_cpp', 'models')
            _models_dir.mkdir(parents=True, exist_ok=True)
            _model_dst  = _models_dir / f'ggml-{model_size}.bin'
            _model_url  = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                          f'ggml-{model_size}.bin')
            _sizes = {'tiny':75,'base':142,'small':466,'medium':1500,'large':3100}
            print(f'[CF] Downloading ggml-{model_size}.bin (~{_sizes.get(model_size,"?")}MB)...')
            if progress_cb: progress_cb(0, f'Downloading ggml-{model_size}.bin...')
            _last_model_pct = [-1]
            def _hook(c, b, t):
                if t > 0:
                    pct = int(c*b/t*100)
                    if pct >= _last_model_pct[0] + 10 or pct >= 99:
                        _last_model_pct[0] = pct
                        print(f'[CF] Model download: {pct}%')
                        if progress_cb: progress_cb(pct, f'Downloading ggml model: {pct}%')
            _ur2.urlretrieve(_model_url, str(_model_dst), reporthook=_hook)
            print(f'[CF] Downloaded: {_model_dst.name}')
            # Re-find model and retry
            _wmodel = str(_model_dst)
        except Exception as _mdl_err:
            print(f'[CF] Model download failed: {_mdl_err}')

    # ── 2. faster-whisper with CUDA/CPU ───────────────────────────────────────
    try:
        _FW = _fresh_import('faster_whisper').WhisperModel
        device, compute_type, device_label = _detect_whisper_device()
        print(f'[CF] Whisper device: {device_label}')

        if device == 'directml':
            # faster-whisper doesn't support DirectML — use openai-whisper + torch-directml
            raise RuntimeError('directml: route to openai-whisper+directml')

        fw_model = _FW(
            model_size,
            device=device,
            compute_type=compute_type,
            num_workers=2,
            cpu_threads=0,
            download_root=str(_app_path('whisper_models')),
        )

        # Get video duration for progress calculation
        try:
            _cv2t = _fresh_import('cv2')
            _cap = _cv2t.VideoCapture(vid)
            _dur = _cap.get(_cv2t.CAP_PROP_FRAME_COUNT) / max(_cap.get(_cv2t.CAP_PROP_FPS) or 30, 1)
            _cap.release()
        except Exception:
            _dur = 0

        segs_iter, info = fw_model.transcribe(
            vid,
            initial_prompt=initial_prompt or '',
            word_timestamps=use_word_timestamps,
            vad_filter=True,
            vad_parameters={
                'min_silence_duration_ms': 400,
                'speech_pad_ms': 200,
            },
            beam_size=5,
            best_of=5,
            temperature=0.0,
        )

        # Consume iterator and report progress
        segments = []
        for seg in segs_iter:
            # Check cancel flag (set by _cancel_task via _do_transcribe._cancelled)
            if getattr(_do_transcribe, '_cancelled', False):
                _do_transcribe._cancelled = False
                return {'segments': segments, 'language': getattr(info, 'language', 'en'), '_cancelled': True}
            sd = {'start': seg.start, 'end': seg.end, 'text': seg.text}
            if use_word_timestamps and seg.words:
                sd['words'] = [{'word': w.word, 'start': w.start, 'end': w.end} for w in seg.words]
            segments.append(sd)
            if progress_cb and _dur > 0:
                pct = min(99, int((seg.end / _dur) * 100))
                m, s = divmod(int(seg.end), 60)
                progress_cb(pct, f'Transcribing... {m}:{s:02d} / {int(_dur//60)}:{int(_dur%60):02d}  ({pct}%)')
            elif progress_cb:
                progress_cb(None, f'Transcribing... {len(segments)} segments found')

        print(f'[CF] Whisper done: {len(segments)} segments, lang={info.language}')
        return {'segments': segments, 'language': info.language}

    except Exception as fw_err:
        print(f'[CF] faster-whisper error: {fw_err}')
        print('[CF] Falling back to openai-whisper...')

    # ── Fallback: openai-whisper, with DirectML if available ────────────────
    try:
        import whisper as _w
    except ImportError:
        raise RuntimeError(
            'No transcription engine available.\n\n'
            'Go to Settings → Update Modules and install:\n'
            '  • faster-whisper  (recommended)\n'
            '  • openai-whisper  (fallback)\n\n'
            'The app will stay open while packages download.'
        )
    with _wn.catch_warnings():
        _wn.simplefilter('ignore')
        # Try to load on DirectML (AMD/Intel GPU via torch-directml)
        _device_str = 'cpu'
        try:
            import torch_directml as _dml2
            if _dml2.device_count() > 0:
                _device_str = _dml2.device(0)
                print(f'[CF] Whisper using DirectML GPU')
        except Exception:
            pass

        _ow_model = model_size if model_size not in ('auto', '') else 'base'
        model = _w.load_model(_ow_model, device=_device_str)

    if ffmpeg_path:
        try:
            import whisper.audio as _wa
            _wa.FFMPEG_PATH = ffmpeg_path
        except Exception: pass

    opts = {'verbose': False, 'word_timestamps': use_word_timestamps, 'fp16': False}
    if initial_prompt:
        opts['initial_prompt'] = initial_prompt
    with _wn.catch_warnings():
        _wn.simplefilter('ignore')
        result = model.transcribe(vid, **opts)
        raw_segs = result.get('segments', [])
        out_segs = []
        for seg in raw_segs:
            sd = {'start': seg['start'], 'end': seg['end'], 'text': seg['text'].strip()}
            if use_word_timestamps and seg.get('words'):
                sd['words'] = [{'word': w['word'], 'start': w['start'], 'end': w['end']}
                               for w in seg['words']]
            out_segs.append(sd)
        return {'segments': out_segs, 'language': result.get('language','en')}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ClipFinder 1.3.3 — AI Clip Extractor')
        self.geometry('1200x800')
        # Set window + taskbar icon
        try:
            # Look for clipfinder.ico next to the script or exe
            _ico_search = [
                _PathBase(__file__).parent / 'clipfinder.ico',
                _PathBase(sys.executable).parent / 'clipfinder.ico',
                USER_DIR.parent / 'clipfinder.ico',
            ]
            for _ico_path in _ico_search:
                if _ico_path.exists():
                    self.iconbitmap(str(_ico_path))
                    break
            else:
                # Fallback: use PIL to set icon from any found image
                from PIL import Image as _PI4, ImageTk as _PT4
                for _ico_path in _ico_search:
                    _png = _ico_path.with_suffix('.png')
                    if _png.exists():
                        _img = _PI4.open(str(_png))
                        self._win_icon = _PT4.PhotoImage(_img)
                        self.iconphoto(True, self._win_icon)
                        break
        except Exception:
            pass
        self.minsize(1000, 700)
        self.configure(bg=BG)

        self.cfg = load_cfg()

        self.v_video    = tk.StringVar()
        self.v_outdir   = tk.StringVar(value=self.cfg.get('outdir', ''))
        self.v_outdir.trace_add('write', lambda *_: self.cfg.update({'outdir': self.v_outdir.get()}) or save_cfg(self.cfg))
        self.v_key      = tk.StringVar()
        self.v_provider = tk.StringVar(value=self.cfg.get('provider', list(PROVIDERS.keys())[0]))
        # Per-provider key storage
        self._keys = {
            'Google Gemini (Free)':    self.cfg.get('key_gemini', ''),
            'Groq (Free)':             self.cfg.get('key_groq', ''),
            'OpenRouter (Free models)':self.cfg.get('key_openrouter', ''),
            '_brave_search':           self.cfg.get('key_brave_search', ''),
            '_unsplash':               self.cfg.get('key_unsplash', ''),
        }
        # StringVars for settings tab key editing
        self.v_keys = {
            'Google Gemini (Free)':     tk.StringVar(value=self._keys.get('Google Gemini (Free)','')),
            'Groq (Free)':              tk.StringVar(value=self._keys.get('Groq (Free)','')),
            'OpenRouter (Free models)': tk.StringVar(value=self._keys.get('OpenRouter (Free models)','')),
        }
        # Auto-update provider status when any key changes
        def _on_key_var_change(*_):
            if hasattr(self, '_prov_status_frame'):
                self._refresh_provider_status()
        for _v in self.v_keys.values():
            _v.trace_add('write', _on_key_var_change)
        self.v_key.set(self._keys.get(self.v_provider.get(), ''))
        # Auto-select best provider based on available keys (deferred so UI is ready)
        self.after(500, self._auto_select_provider)
        self.v_model    = tk.StringVar(value=self.cfg.get('model', ''))
        self.v_whisper  = tk.StringVar(value=self.cfg.get('whisper', 'auto'))
        self.v_status   = tk.StringVar(value='Ready.')

        self.clips      = []
        self.clip_vars  = []
        self.transcript = ''
        self.srt_result = None
        self.running    = False
        self._cancel_requested = False
        # Extra API keys per provider for round-robin rotation
        self._extra_keys = {
            'Google Gemini (Free)':    [k.strip() for k in self.cfg.get('key_gemini_extra','').split(',') if k.strip()],
            'Groq (Free)':             [k.strip() for k in self.cfg.get('key_groq_extra','').split(',') if k.strip()],
            'OpenRouter (Free models)':[k.strip() for k in self.cfg.get('key_openrouter_extra','').split(',') if k.strip()],
        }
        self._key_index = {}
        self._whisper_segments = []
        # Thumbnail finder state
        self._thumb_results  = []
        self._thumb_running  = False
        self._thumb_tk_refs  = []
        # Image Studio state
        self._studio_running   = False
        self._studio_dupes     = []   # list of dupe groups found
        self._studio_upscale_jobs = []
        # Censor tab state
        self._censor_running   = False
        self._censor_queue     = []   # bulk queue
        # Export queue
        self._export_queue = []  # list of (video_path, out_dir, clips)  # keep tk image refs alive
        self.ticker_on  = False

        # Downloader state
        self.v_dl_url      = tk.StringVar()
        self.v_dl_folder   = tk.StringVar(value=self.cfg.get('dl_folder', str(Path.home() / 'Downloads')))
        self.v_dl_quality  = tk.StringVar(value=self.cfg.get('dl_quality', 'best'))
        self.v_cookies     = tk.StringVar(value=self.cfg.get('cookies_file', ''))
        self.v_auto_load   = tk.BooleanVar(value=self.cfg.get('auto_load', True))
        self._last_dl_path = None
        self._dl_cancel_requested = False
        # Init censor words from config so clip-finder censor works before censor tab opens
        _saved_words = self.cfg.get('censor_words', None)
        self._censor_words = _saved_words if _saved_words else []  # populated by _build_censor_tab
        self._dl_q_btns    = {}
        # Auto-save downloader settings on change
        self.v_dl_folder.trace_add('write', self._dl_autosave)
        self.v_cookies.trace_add('write', self._dl_autosave)
        self.v_dl_quality.trace_add('write', self._dl_autosave)
        self.v_auto_load.trace_add('write', self._dl_autosave)

        # Apply scrollbar styling BEFORE any widgets are created
        self.option_add('*Scrollbar.background',        BG3)
        self.option_add('*Scrollbar.troughColor',       BG2)
        self.option_add('*Scrollbar.activeBackground',  BG3)
        self.option_add('*Scrollbar.highlightColor',    BG2)
        self.option_add('*Scrollbar.highlightBackground', BG2)
        self.option_add('*Scrollbar.relief',            'flat')
        self.option_add('*Scrollbar.borderWidth',       '0')
        self.option_add('*Scrollbar.width',             '7')
        self.option_add('*Scrollbar.elementBorderWidth','0')
        self.option_add('*Scrollbar.arrowColor',        BG3)
        self._build()
        self._refresh_provider()
        self.after(200, self._refresh_prov_btns)
        self.after(300, self._refresh_provider)
        # Apply right-click menus to all text inputs across the whole app
        self.after(200, lambda: apply_rightclick_to_all(self, self))
        self.after(300, self._fix_all_scrollbars)
        self.after(400, self._bind_global_mousewheel)
        self.after(800, self._check_first_run)

        def _on_close():
            try: self.destroy()
            except: pass
            import os as _osx; _osx._exit(0)
        self.protocol("WM_DELETE_WINDOW", _on_close)
        # Pre-check ffmpeg — FIND ONLY, never download at startup
        def _check_for_update():
            """Silently check GitHub for newer version on launch."""
            try:
                import urllib.request as _ur, json as _js2
                _api = 'https://api.github.com/repos/thatspeedykid/clipfinder/releases/latest'
                _req = _ur.Request(_api, headers={'User-Agent': 'ClipFinder'})
                with _ur.urlopen(_req, timeout=5) as _resp:
                    _data = _js2.loads(_resp.read())
                _latest = _data.get('tag_name','').lstrip('v')
                # Normalize both versions to comparable tuples
                # e.g. "1.2-beta" -> (1, 2, 0), "1.1" -> (1, 1, 0)
                def _ver_tuple(v):
                    import re as _re
                    nums = _re.findall(r'\d+', v)
                    t = tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))
                    is_pre = any(x in v.lower() for x in ('beta','rc','alpha','pre'))
                    return (t, 0 if is_pre else 1)
                _latest_t  = _ver_tuple(_latest)
                _current_t = _ver_tuple(APP_VERSION)
                if _latest and _latest_t > _current_t:
                    def _show_update():
                        # Floating update banner — always visible, over everything
                        _uw = tk.Toplevel(self)
                        _uw.overrideredirect(True)
                        _uw.attributes('-topmost', True)
                        _uw.configure(bg='#1e3a1e')
                        _bar_h = 36
                        def _pos_update(*_):
                            try:
                                x = self.winfo_x()
                                y = self.winfo_y()
                                w = self.winfo_width()
                                wh = self.winfo_height()
                                _uw.geometry(f'{w}x{_bar_h}+{x}+{y+wh-_bar_h-30}')
                            except: pass
                        tk.Label(_uw,
                                text=f'⬆  ClipFinder v{_latest} available  —  you have v{APP_VERSION}',
                                font=('Segoe UI',9,'bold'), fg='#00ff88', bg='#1e3a1e'
                                ).pack(side='left', padx=14)
                        tk.Button(_uw, text='⬇ Download Now', font=('Segoe UI',8,'bold'),
                                 bg=ACCENT, fg='#000', relief='flat', bd=0,
                                 cursor='hand2', padx=10, pady=6,
                                 command=lambda: __import__('webbrowser').open(
                                     'https://github.com/thatspeedykid/clipfinder/releases/latest')
                                 ).pack(side='left', padx=6)
                        tk.Button(_uw, text='✕', font=('Segoe UI',10,'bold'),
                                 fg='#00ff88', bg='#1e3a1e', relief='flat', bd=0,
                                 cursor='hand2', padx=12,
                                 command=_uw.destroy).pack(side='right', padx=8)
                        _pos_update()
                        self.bind('<Configure>', _pos_update)
                    self.after(2000, _show_update)
            except Exception:
                pass  # Silent fail — no internet or API down

        import threading as _thr2
        _thr2.Thread(target=_check_for_update, daemon=True).start()

        def _prefetch_ffmpeg():
            try:
                import shutil as _sh2
                # Only look for existing ffmpeg — do NOT call ensure_ffmpeg() which auto-downloads
                ff = _sh2.which('ffmpeg')
                if not ff:
                    for _c in [
                        _app_path('ffmpeg_bin') / 'ffmpeg.exe',
                        _app_path('ffmpeg.exe'),
                        Path('C:/ffmpeg/bin/ffmpeg.exe'),
                        Path('C:/ffmpeg/ffmpeg.exe'),
                    ]:
                        if _c.exists():
                            ff = str(_c)
                            break
                if ff:
                    import os as _os
                    _os.environ['PATH'] = str(Path(ff).parent) + _os.pathsep + _os.environ.get('PATH','')
                    vcodec, _, _ = get_encoder(ff)
                    enc_label = {
                        'h264_nvenc': 'NVIDIA NVENC',
                        'h264_amf':   'AMD AMF',
                        'h264_qsv':   'Intel QSV',
                        'libx264':    'CPU x264',
                    }.get(vcodec, vcodec)
                    def _update_ui(en=enc_label, vc=vcodec):
                        self.v_status.set(f'Ready · Encoder: {en}')
                        if hasattr(self, 'prog_lbl'):
                            self.prog_lbl.config(text='Ready')
                        if hasattr(self, '_gpu_badge'):
                            if vc == 'h264_amf':
                                self._gpu_badge.config(text='⚡ AMD GPU', bg='#E8651A', fg='#000')
                            elif vc == 'h264_nvenc':
                                self._gpu_badge.config(text='⚡ NVIDIA GPU', bg='#76b900', fg='#000')
                            elif vc == 'h264_qsv':
                                self._gpu_badge.config(text='⚡ Intel GPU', bg='#0071C5', fg='#fff')
                            else:
                                self._gpu_badge.config(text='CPU', bg='#2a2a2e', fg='#888')
                    self.after(0, _update_ui)
                else:
                    # ffmpeg not found — will be downloaded on first use, not at startup
                    self.after(0, lambda: self.v_status.set('Ready — ffmpeg not found (will download on first use)'))
            except Exception:
                self.after(0, lambda: self.v_status.set('Ready'))
        threading.Thread(target=_prefetch_ffmpeg, daemon=True).start()
        # Pre-build settings tab in background so it's instant when clicked
        def _prebuild_settings():
            import time as _t_pb
            _t_pb.sleep(1.5)  # let app fully render first
            self.after(0, lambda: _ensure_tab_built('settings'))
        threading.Thread(target=_prebuild_settings, daemon=True).start()
        # GPU whisper auto-install disabled — user installs via Settings → Update Modules
        # (auto-downloading at launch caused unwanted background downloads)
        # whisper.cpp auto-install disabled — user installs via Settings -> Update Modules
    def _build(self):
        self.configure(bg=BG)

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=48)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        # Orange left accent stripe
        tk.Frame(hdr, bg=ACCENT, width=4).pack(side='left', fill='y')
        # Logo + icon
        logo_f = tk.Frame(hdr, bg=BG2); logo_f.pack(side='left', padx=14)
        # App icon left of text
        try:
            from PIL import Image as _PI3, ImageTk as _PT3
            for _ip in [_PathBase(__file__).parent / 'clipfinder.ico',
                        _PathBase(sys.executable).parent / 'clipfinder.ico']:
                if _ip.exists():
                    self._hdr_icon = _PT3.PhotoImage(_PI3.open(str(_ip)).resize((22,22), _PI3.LANCZOS))
                    tk.Label(logo_f, image=self._hdr_icon, bg=BG2).pack(side='left', padx=(0,6))
                    break
        except Exception: pass
        tk.Label(logo_f, text='CLIP', font=('Segoe UI', 14, 'bold'),
                 fg=ACCENT, bg=BG2).pack(side='left')
        tk.Label(logo_f, text='FINDER', font=('Segoe UI', 14, 'bold'),
                 fg=FG, bg=BG2).pack(side='left')
        tk.Label(hdr, text='AI Drama Clip Extractor',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2).pack(side='left', padx=4)
        # Right side: GPU badge + channel tag
        _ms_lbl = tk.Label(hdr, text='@MarsScumbags', font=('Segoe UI', 8, 'bold'),
                 fg=ACCENT2, bg=BG2, cursor='hand2')
        _ms_lbl.pack(side='right', padx=(4,12))
        _ms_lbl.bind('<Button-1>', lambda e: __import__('webbrowser').open('https://x.com/MarsScumbags'))
        tk.Label(hdr, text=f'v{APP_VERSION}', font=('Segoe UI', 7),
                fg=FG3, bg=BG2).pack(side='right', padx=(0,2))
        self._gpu_badge = tk.Label(hdr, text='⚡ GPU', font=('Segoe UI', 7, 'bold'),
                 fg='#000', bg=ACCENT, padx=6, pady=1)
        self._gpu_badge.pack(side='right', padx=(0,6))
        tk.Frame(self, bg=ACCENT, height=2).pack(fill='x')  # orange line under header

        # ── Bottom status bar (packed BEFORE body so it always shows) ───────
        tk.Frame(self, bg=BORDER, height=1).pack(side='bottom', fill='x')
        bot = tk.Frame(self, bg=BG2, height=30)
        bot.pack(side='bottom', fill='x')
        bot.pack_propagate(False)

        # ── Main content ──────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(side='top', fill='both', expand=True)
        self._body = body  # store reference for update bar etc

        content = tk.Frame(body, bg=BG)
        content.pack(fill='both', expand=True)
        self._build_right(content)
        # Status text
        tk.Label(bot, textvariable=self.v_status, font=('Segoe UI', 8),
                 fg=FG2, bg=BG2, anchor='w').pack(side='left', fill='x',
                 expand=True, padx=10, pady=6)
        # Settings gear — bottom right
        tk.Button(bot, text='⚙', font=('Segoe UI', 11), bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=10, pady=2,
                  activebackground=BG3, activeforeground=FG,
                  command=lambda: self._switch_nb('settings')).pack(side='right')
        # Log toggle
        self._log_visible = tk.BooleanVar(value=False)
        tk.Button(bot, text='📋', font=('Segoe UI', 9), bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8,
                  activebackground=BG3,
                  command=self._toggle_log).pack(side='right')
        tk.Label(bot, text=f'ClipFinder {APP_VERSION}  ·  @MarsScumbags',
                font=('Segoe UI', 7), fg=FG3, bg=BG2).pack(side='right', padx=8)

    def _build_sidebar(self, p):
        def section(title):
            tk.Label(p, text=title, font=('Segoe UI', 8, 'bold'),
                     fg=ACCENT, bg=BG2, anchor='w', padx=12).pack(fill='x', pady=(10,2))

        def div():
            tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=12, pady=2)

        # Scrollable sidebar with custom scrollbar
        outer = tk.Frame(p, bg=BG2)
        outer.pack(fill='both', expand=True)
        _cv = tk.Canvas(outer, bg=BG2, bd=0, highlightthickness=0)
        _cv.pack(side='left', fill='both', expand=True)
        _make_scrollbar(outer, _cv)
        inner = tk.Frame(_cv, bg=BG2)
        inner.bind('<Configure>', lambda e: _cv.configure(scrollregion=_cv.bbox('all')))
        _cv.create_window((0, 0), window=inner, anchor='nw', tags='inner')
        def _on_cv_resize(e):
            _cv.itemconfig('inner', width=e.width)
        _cv.bind('<Configure>', _on_cv_resize)
        _cv.bind('<MouseWheel>', lambda e: _cv.yview_scroll(int(-1*(e.delta/120)), 'units'))
        p = inner  # build into scrollable inner frame

        def row(parent):
            f = tk.Frame(parent, bg=BG2, padx=10)
            f.pack(fill='x', pady=2)
            return f

        # Video file
        section('VIDEO FILE')
        vr = row(p)
        e1 = tk.Entry(vr, textvariable=self.v_video, font=FONT_SMALL,
                      bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4)
        e1.pack(side='left', fill='x', expand=True)
        tk.Button(vr, text='...', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=6,
                  command=self._pick_video).pack(side='right', padx=(4,0))

        div()

        # Output folder
        section('OUTPUT FOLDER')
        or_ = row(p)
        e2 = tk.Entry(or_, textvariable=self.v_outdir, font=FONT_SMALL,
                      bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4)
        e2.pack(side='left', fill='x', expand=True)
        tk.Button(or_, text='...', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=6,
                  command=self._pick_outdir).pack(side='right', padx=(4,0))

        div()

        # Video context
        section('VIDEO CONTEXT  (optional)')
        tk.Label(p, text='Who\'s in it, what\'s the drama, names, etc.',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2, padx=12
                 ).pack(anchor='w')
        ctx_wrap = tk.Frame(p, bg=BG3, padx=0)
        ctx_wrap.pack(fill='x', padx=12, pady=(3, 0))
        self.v_context = tk.Text(ctx_wrap, height=3, font=FONT_SMALL,
                                 bg=BG3, fg=FG, insertbackground=ACCENT,
                                 relief='flat', bd=6, wrap='word')
        self.v_context.pack(fill='x')
        self.v_context.insert('1.0', self.cfg.get('video_context', ''))
        self.v_context.bind('<FocusOut>', lambda e: (
            self.cfg.update({'video_context': self.v_context.get('1.0','end').strip()}),
            save_cfg(self.cfg)
        ))
        tk.Label(p, text='Used by AI for clip finding, auto edit, and transcription.',
                 font=('Segoe UI', 7), fg=FG2, bg=BG2, padx=12
                 ).pack(anchor='w', pady=(2, 0))

        div()

        # Provider
        section('AI PROVIDER')
        prov_frame = tk.Frame(p, bg=BG2, padx=12)
        prov_frame.pack(fill='x', pady=2)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=BG3, background=BG3,
                        foreground=FG, selectbackground=ACCENT, selectforeground='#000',
                        borderwidth=0, arrowcolor=FG2)
        style.map('TCombobox', fieldbackground=[('readonly', BG3)],
                  foreground=[('readonly', FG)], background=[('readonly', BG3)])
        # Dark scrollbars globally
        style.configure('Vertical.TScrollbar', background=BG3, troughcolor=BG2,
                        bordercolor=BG2, arrowcolor=FG2, relief='flat', borderwidth=0)
        style.configure('Horizontal.TScrollbar', background=BG3, troughcolor=BG2,
                        bordercolor=BG2, arrowcolor=FG2, relief='flat', borderwidth=0)
        style.map('Vertical.TScrollbar',
                  background=[('active', BORDER), ('pressed', ACCENT)])

        prov_cb = ttk.Combobox(prov_frame, textvariable=self.v_provider,
                               values=list(PROVIDERS.keys()), state='readonly', font=FONT_SMALL)
        prov_cb.pack(fill='x')
        prov_cb.bind('<<ComboboxSelected>>', lambda e: self._refresh_provider())
        self.lbl_note = tk.Label(p, text='', font=FONT_SMALL, fg=FG2, bg=BG2,
                                 anchor='w', padx=12, wraplength=290, justify='left')
        self.lbl_note.pack(fill='x')
        self.lbl_url = tk.Label(p, text='', font=FONT_SMALL, fg=ACCENT2, bg=BG2,
                                anchor='w', padx=12, cursor='hand2', wraplength=290)
        self.lbl_url.pack(fill='x')
        self.lbl_url.bind('<Button-1>', self._open_key_url)

        div()

        # API Key
        section('API KEY')
        kr = row(p)
        self.v_key.trace_add('write', self._on_key_changed)
        self.key_entry = tk.Entry(kr, textvariable=self.v_key, show='*',
                                   font=FONT_MONO_S, bg=BG3, fg=FG,
                                   insertbackground=ACCENT, relief='flat', bd=4)
        self.key_entry.pack(side='left', fill='x', expand=True)
        tk.Button(kr, text='show', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=4,
                  command=lambda: self.key_entry.config(
                      show='' if self.key_entry.cget('show') == '*' else '*')
                  ).pack(side='right', padx=(4,0))

        div()

        # AI Model
        section('AI MODEL')
        model_frame = tk.Frame(p, bg=BG2, padx=12)
        model_frame.pack(fill='x', pady=2)
        self.model_cb = ttk.Combobox(model_frame, textvariable=self.v_model,
                                      state='readonly', font=FONT_SMALL)
        self.model_cb.pack(fill='x')

        div()

        # Whisper
        section('WHISPER MODEL')
        wr = tk.Frame(p, bg=BG2, padx=12)
        wr.pack(fill='x', pady=2)
        for m in ['tiny', 'base', 'small', 'medium']:
            tk.Radiobutton(wr, text=m, variable=self.v_whisper, value=m,
                           font=FONT_SMALL, fg=FG, bg=BG2,
                           selectcolor=BG3, activebackground=BG2,
                           relief='flat', cursor='hand2').pack(side='left', padx=(0,6))
        tk.Label(p, text='tiny=fastest  medium=accurate',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2, padx=12).pack(anchor='w')

        div()

        div()

        # ── Interview Mode toggle ──────────────────────────────────────────────
        section('MODE')
        self.app_mode = tk.StringVar(value=self.cfg.get('app_mode', 'normal'))
        self.interview_mode = tk.BooleanVar(value=False)  # compat

        mode_row = tk.Frame(p, bg=BG2, padx=12)
        mode_row.pack(fill='x', pady=(0,4))
        self.mode_normal_btn = tk.Button(mode_row, text='🎬 Normal',
                                         font=FONT_SMALL, relief='flat', bd=0,
                                         cursor='hand2', padx=7, pady=5,
                                         command=lambda: self._set_mode('normal'))
        self.mode_normal_btn.pack(side='left', padx=(0,3))
        self.mode_interview_btn = tk.Button(mode_row, text='🎤 Interview',
                                            font=FONT_SMALL, relief='flat', bd=0,
                                            cursor='hand2', padx=7, pady=5,
                                            command=lambda: self._set_mode('interview'))
        self.mode_interview_btn.pack(side='left', padx=(0,3))
        self._refresh_mode_btns()

        # Interview frame
        self.interview_frame = tk.Frame(p, bg=BG2, padx=12)
        self.interview_frame.pack(fill='x')
        tk.Label(self.interview_frame, text='Interviewee names (one per line):',
                 font=FONT_SMALL, fg=FG2, bg=BG2).pack(anchor='w', pady=(4,2))
        tk.Label(self.interview_frame, text='e.g.  Sophie\nPiper\nAlinity',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2).pack(anchor='w')
        nw = tk.Frame(self.interview_frame, bg=BG3); nw.pack(fill='x', pady=(3,0))
        self.interview_names_box = tk.Text(nw, height=3, font=FONT_SMALL,
                                           bg=BG3, fg=FG, insertbackground=ACCENT,
                                           relief='flat', bd=6, wrap='word')
        self.interview_names_box.pack(fill='x')
        saved_names = self.cfg.get('interview_names', '')
        if saved_names:
            self.interview_names_box.insert('1.0', saved_names)
        tk.Label(self.interview_frame, text='AI identifies speakers by name.',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2).pack(anchor='w', pady=(2,0))

        # Buttons
        btn_frame = tk.Frame(p, bg=BG2, padx=12)
        btn_frame.pack(fill='x', pady=(8,4))
        self.go_btn = tk.Button(btn_frame, text='▶  FIND CLIPS',
                                font=('Segoe UI', 10, 'bold'),
                                bg=ACCENT, fg='#000', relief='flat',
                                cursor='hand2', pady=8, bd=0,
                                activebackground=ACCENT2, activeforeground='#000',
                                command=self._start)
        self.go_btn.pack(fill='x', pady=(0,4))
        self.trans_btn = tk.Button(btn_frame, text='📝  TRANSCRIBE ONLY',
                                   font=FONT_SMALL, bg=BG3, fg=FG,
                                   relief='flat', cursor='hand2', pady=6, bd=0,
                                   command=self._transcribe_only)
        self.trans_btn.pack(fill='x')

        # Log moved to bottom bar

    def _build_right(self, p):
        # ── Unified status bar ────────────────────────────────────────────────
        sb = tk.Frame(p, bg=BG2)
        sb.pack(fill='x')

        # Custom canvas progress bar — full visual control, no ttk theming issues
        _pb_h = 10
        pbar_wrap = tk.Frame(sb, bg=BG3, height=_pb_h)
        pbar_wrap.pack(fill='x')
        pbar_wrap.pack_propagate(False)
        _pb_cv = tk.Canvas(pbar_wrap, bg=BG3, height=_pb_h, bd=0,
                           highlightthickness=0)
        _pb_cv.pack(fill='both', expand=True)
        _pb_state = {'value': 0, 'mode': 'determinate', 'anim': 0}
        _pb_bar_id   = [None]
        _pb_glow_id  = [None]

        def _pb_draw(*_):
            _pb_cv.delete('all')
            w = _pb_cv.winfo_width() or 400
            h = _pb_h
            # Track
            _pb_cv.create_rectangle(0, 0, w, h, fill=BG3, outline='')
            if _pb_state['mode'] == 'indeterminate':
                # Animated sliding block
                pos = _pb_state['anim'] % (w + 120)
                x1 = pos - 100; x2 = pos
                x1 = max(0, x1); x2 = min(w, x2)
                if x2 > x1:
                    _pb_cv.create_rectangle(x1, 0, x2, h, fill=ACCENT, outline='')
                    # Glow edge
                    _pb_cv.create_rectangle(max(0,x2-4), 0, x2, h, fill=ACCENT2, outline='')
            else:
                pct = max(0, min(100, _pb_state['value']))
                if pct > 0:
                    bar_w = int(w * pct / 100)
                    # Main fill
                    _pb_cv.create_rectangle(0, 0, bar_w, h, fill=ACCENT, outline='')
                    # Bright leading edge
                    _pb_cv.create_rectangle(max(0, bar_w-4), 0, bar_w, h,
                                           fill=ACCENT2, outline='')
                    # Subtle segment lines every 25%
                    for pct_mark in [25, 50, 75]:
                        mx = int(w * pct_mark / 100)
                        if mx < bar_w:
                            _pb_cv.create_line(mx, 0, mx, h, fill=BG3, width=1)

        def _pb_animate():
            if _pb_state['mode'] == 'indeterminate':
                _pb_state['anim'] += 8
                _pb_draw()
            try:
                pbar_wrap.after(30, _pb_animate)
            except: pass

        _pb_cv.bind('<Configure>', _pb_draw)
        pbar_wrap.after(100, _pb_animate)

        # Compat shim — replaces ttk.Progressbar API used throughout the app
        class _PBar:
            def __getitem__(self, key):
                return _pb_state.get(key, 0)
            def __setitem__(self, key, val):
                _pb_state[key] = val
                if key == 'value': _pb_draw()
            def config(self, **kw):
                for k,v in kw.items():
                    _pb_state[k] = v
                if 'mode' in kw and kw['mode'] == 'determinate':
                    _pb_state['value'] = 0
                _pb_draw()
            def start(self, ms=50):
                _pb_state['mode'] = 'indeterminate'
                _pb_draw()
            def stop(self):
                _pb_state['mode'] = 'determinate'
                _pb_draw()

        self.progressbar = _PBar()

        # Detail row below bar
        sd = tk.Frame(sb, bg=BG2); sd.pack(fill='x', padx=10, pady=(3,4))

        self.status_step_lbl = tk.Label(sd, text='', font=('Segoe UI', 8,'bold'),
                                        fg=ACCENT, bg=BG2, anchor='w', width=9)
        self.status_step_lbl.pack(side='left')

        tk.Frame(sd, bg=BORDER, width=1).pack(side='left', fill='y', padx=(0,8))

        self.prog_lbl = tk.Label(sd, text='Ready — Encoder: detecting...',
                                 font=FONT_SMALL, fg=FG2, bg=BG2, anchor='w')
        self.prog_lbl.pack(side='left', fill='x', expand=True)

        self.status_pct_lbl = tk.Label(sd, text='', font=('Segoe UI', 8,'bold'),
                                       fg=ACCENT2, bg=BG2, width=5, anchor='e')
        self.status_pct_lbl.pack(side='right')

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Tab bar ───────────────────────────────────────────────────────────
        nb_bar = tk.Frame(p, bg=BG)
        nb_bar.pack(fill='x')
        self.nb_frames = {}
        self.nb_btns   = {}

        TABS = [
            ('clips',      '✂',  'Clip Finder'),
            ('transcript', '📝', 'Transcript'),
            ('downloader', '⬇',  'Downloader'),
            ('thumbs',     '🖼',  'Thumbnails'),
            ('studio',     '🔬', 'Studio'),
            ('censor',     '🔇', 'Censor'),
            ('music',      '🎵', 'Music Removal'),
        ]
        for key, icon, label in TABS:
            b = tk.Button(nb_bar, text=f'{icon}  {label}', font=('Segoe UI', 9),
                          relief='flat', bd=0, cursor='hand2',
                          padx=16, pady=8, bg=BG2, fg=FG2,
                          activebackground=BG3, activeforeground=FG,
                          command=lambda k=key: self._switch_nb(k))
            b.pack(side='left', fill='x', expand=True)
            self.nb_btns[key] = b

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        content = tk.Frame(p, bg=BG)
        content.pack(fill='both', expand=True)

        # Build clips tab immediately (shown on startup)
        clips_frame = tk.Frame(content, bg=BG)
        clips_frame.pack(fill='both', expand=True)
        self.nb_frames['clips'] = clips_frame
        self._build_clips_tab(clips_frame)

        # Lazy-build remaining tabs on first visit
        _lazy_builders = {
            'transcript': (self._build_trans_tab,),
            'downloader': (self._build_dl_tab,),
            'thumbs':     (self._build_thumb_tab,),
            'studio':     (self._build_studio_tab,),
            'censor':     (self._build_censor_tab,),
            'music':      (self._build_music_removal_tab,),
            'settings':   (self._build_settings_tab,),
        }
        self._tab_built = {'clips'}

        for key in _lazy_builders:
            f = tk.Frame(content, bg=BG)
            self.nb_frames[key] = f

        def _ensure_tab_built(key):
            if key not in self._tab_built:
                builders = _lazy_builders.get(key)
                if builders:
                    # Show loading indicator for slow tabs
                    if key == 'settings':
                        _lf = tk.Frame(self.nb_frames[key], bg=BG)
                        _lf.pack(fill='both', expand=True)
                        tk.Label(_lf, text='⚙ Loading settings...', 
                                font=('Segoe UI',11), fg=FG2, bg=BG).pack(expand=True)
                        self.nb_frames[key].update()
                        _lf.destroy()
                    builders[0](self.nb_frames[key])
                    self._tab_built.add(key)

        self._ensure_tab_built = _ensure_tab_built



        self._switch_nb('clips')
        # First-run welcome — only show if packages genuinely missing
        # _setup_done persists in config next to the EXE
        if not self.cfg.get('_setup_done', False):
            # Quick check: if faster_whisper or yt_dlp available, skip welcome
            _already_set_up = False
            try:
                import faster_whisper; _already_set_up = True
            except ImportError:
                _ensure_pkgs_on_path()
                try:
                    import faster_whisper; _already_set_up = True
                except ImportError:
                    pass
            if not _already_set_up:
                self.after(600, self._show_welcome_overlay)
            else:
                self.cfg['_setup_done'] = True
                save_cfg(self.cfg)

    def _show_welcome_overlay(self):
        """First-launch only overlay — points user to Settings to get started."""
        # Mark done immediately so it never shows again even if they close abruptly
        self.cfg['_setup_done'] = True
        save_cfg(self.cfg)

        ov = tk.Toplevel(self)
        ov.title('')
        ov.resizable(False, False)
        ov.configure(bg=BG)
        ov.grab_set()  # modal

        # Center over main window
        self.update_idletasks()
        mx = self.winfo_x() + self.winfo_width()  // 2
        my = self.winfo_y() + self.winfo_height() // 2
        W, H = 520, 420
        ov.geometry(f'{W}x{H}+{mx - W//2}+{my - H//2}')

        # Set same icon
        try:
            import base64 as _b64t, tempfile as _tft, os as _ost
            _d = _b64t.b64decode(_ICON_B64)
            _tmp = _tft.NamedTemporaryFile(suffix='.ico', delete=False)
            _tmp.write(_d); _tmp.close()
            ov.iconbitmap(_tmp.name)
            _ost.unlink(_tmp.name)
        except Exception:
            pass

        # ── Orange top bar ──────────────────────────────────────────────────────
        top = tk.Frame(ov, bg=ACCENT, height=5)
        top.pack(fill='x')

        inner = tk.Frame(ov, bg=BG, padx=32, pady=24)
        inner.pack(fill='both', expand=True)

        # Logo line
        logo_row = tk.Frame(inner, bg=BG); logo_row.pack(anchor='w', pady=(0, 4))
        tk.Label(logo_row, text='CLIP', font=('Segoe UI', 18, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(logo_row, text='FINDER', font=('Segoe UI', 18, 'bold'),
                 fg=FG, bg=BG).pack(side='left')
        tk.Label(logo_row, text='  v1.0 BETA', font=('Segoe UI', 9),
                 fg=FG2, bg=BG).pack(side='left', padx=(4,0))

        tk.Label(inner, text='Welcome! Before you start, complete these 3 quick steps:',
                 font=('Segoe UI', 10), fg=FG2, bg=BG).pack(anchor='w', pady=(0, 18))

        # ── Steps ───────────────────────────────────────────────────────────────
        steps = [
            ('1', ACCENT,  '🔑  Add your API keys',
             'Go to Settings → AI Provider API Keys\nAdd a free Gemini, Groq, or OpenRouter key to enable AI clip finding.'),
            ('2', ACCENT2, '⬇  Install AI packages',
             'Go to Settings → Update Modules\nClick  Install All AI Packages  — runs in background, app stays open.'),
            ('3', GREEN,   '🔧  Install core dependencies',
             'Go to Settings → Core Dependencies\nInstall ffmpeg and whisper.cpp for video processing & transcription.'),
        ]

        for num, color, title, desc in steps:
            row = tk.Frame(inner, bg=BG2, highlightbackground=BORDER,
                           highlightthickness=1)
            row.pack(fill='x', pady=4)
            # Color left stripe
            tk.Frame(row, bg=color, width=4).pack(side='left', fill='y')
            txt = tk.Frame(row, bg=BG2, padx=12, pady=8)
            txt.pack(side='left', fill='both', expand=True)
            tk.Label(txt, text=title, font=('Segoe UI', 9, 'bold'),
                     fg=FG, bg=BG2, anchor='w').pack(fill='x')
            tk.Label(txt, text=desc, font=('Segoe UI', 8),
                     fg=FG2, bg=BG2, anchor='w', justify='left').pack(fill='x')

        # ── Buttons ─────────────────────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=BG); btn_row.pack(fill='x', pady=(20, 0))

        def _go_settings():
            ov.destroy()
            self._switch_nb('settings')

        tk.Button(btn_row, text='⚙  Open Settings  →',
                  font=('Segoe UI', 10, 'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0,
                  cursor='hand2', padx=20, pady=8,
                  command=_go_settings).pack(side='left')

        tk.Button(btn_row, text='Skip for now',
                  font=('Segoe UI', 9),
                  bg=BG3, fg=FG2, relief='flat', bd=0,
                  cursor='hand2', padx=16, pady=8,
                  command=ov.destroy).pack(side='left', padx=(12, 0))

        tk.Label(btn_row, text='You can always reopen Settings via the ⚙ button',
                 font=('Segoe UI', 7), fg=FG3, bg=BG).pack(side='right')

        ov.protocol('WM_DELETE_WINDOW', ov.destroy)


    def _toggle_log(self):
        """Show/hide floating log overlay at bottom of window."""
        if hasattr(self, '_log_win') and self._log_win and self._log_win.winfo_exists():
            self._log_win.destroy()
            self._log_win = None
            return
        # Create overlay window attached to main window
        self._log_win = tk.Toplevel(self)
        self._log_win.transient(self)
        self._log_win.configure(bg=BG3)
        self._log_win.title('ClipFinder Log')
        self._log_win.resizable(True, False)
        # Position at bottom of main window
        def _reposition(*_):
            try:
                x = self.winfo_rootx()
                y = self.winfo_rooty()
                w = self.winfo_width()
                h = self.winfo_height()
                lh = 200
                # Full width flush with main window, sits just above status bar
                self._log_win.geometry(f'{w}x{lh}+{x}+{y+h-lh-30}')
            except: pass
        # Log text
        inner = tk.Frame(self._log_win, bg=BG3)
        inner.pack(fill='both', expand=True, padx=2, pady=2)
        self.log_box = tk.Text(inner, font=('Consolas',8),
                               bg=BG3, fg=FG3, relief='flat', bd=4,
                               wrap='word', state='disabled')
        self.log_box.pack(side='left', fill='both', expand=True)
        _make_scrollbar(inner, self.log_box)
        # Repopulate with buffered messages
        if hasattr(self, '_log_buffer') and self._log_buffer:
            self.log_box.config(state='normal')
            for msg, color in self._log_buffer[-200:]:
                if color:
                    tag = f'c{color}'
                    self.log_box.tag_configure(tag, foreground=color)
                    self.log_box.insert('end', msg+'\n', tag)
                else:
                    self.log_box.insert('end', msg+'\n')
            self.log_box.config(state='disabled')
            self.log_box.see('end')
        # Reposition and track main window moves
        _reposition()
        self.bind('<Configure>', _reposition)

    def _switch_nb(self, key):
        # Lazy-build tab on first visit
        if hasattr(self, '_ensure_tab_built'):
            self._ensure_tab_built(key)
        for k, f in self.nb_frames.items():
            f.pack_forget()
        self.nb_frames[key].pack(fill='both', expand=True)
        for k, b in self.nb_btns.items():
            if k == key:
                b.config(bg=ACCENT, fg='#000', font=('Segoe UI', 9, 'bold'))
            else:
                b.config(bg=BG2, fg=ACCENT2, font=('Segoe UI', 9))
        self.after(100, lambda: apply_rightclick_to_all(self.nb_frames[key], self))
        self.after(150, self._fix_all_scrollbars)
        # Auto-refresh dep status when opening settings
        if key == "settings" and hasattr(self, "_dep_refresh_fn"):
            self.after(200, self._dep_refresh_fn)

    def _build_clips_tab(self, p):

        def lbl(parent, text):
            return tk.Label(parent, text=text, font=FONT_SMALL, fg=FG2, bg=BG2)

        # ── Sub-tab bar: AI Clips | Auto Edit ─────────────────────────────────
        sub_bar = tk.Frame(p, bg=BG3)
        sub_bar.pack(fill='x')
        self._clips_sub_frames = {}
        self._clips_sub_btns = {}

        def _switch_sub(key):
            for k, f in self._clips_sub_frames.items():
                f.pack_forget()
            self._clips_sub_frames[key].pack(fill='both', expand=True)
            for k, b in self._clips_sub_btns.items():
                if k == key:
                    b.config(bg=ACCENT, fg='#000', font=('Segoe UI',8,'bold'))
                else:
                    b.config(bg=BG3, fg=ACCENT2, font=('Segoe UI',8))

        for sub_key, sub_lbl in [('ai_clips','✂  AI Clips'), ('auto_edit','⚡  Auto Edit')]:
            sb = tk.Button(sub_bar, text=sub_lbl, font=('Segoe UI',8),
                          relief='flat', bd=0, cursor='hand2',
                          padx=20, pady=6, bg=BG3, fg=FG2,
                          command=lambda k=sub_key: _switch_sub(k))
            sb.pack(side='left', fill='x', expand=True)
            self._clips_sub_btns[sub_key] = sb
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # AI Clips sub-frame (default)
        ai_clips_frame = tk.Frame(p, bg=BG)
        self._clips_sub_frames['ai_clips'] = ai_clips_frame

        # Auto Edit sub-frame
        ae_frame = tk.Frame(p, bg=BG)
        self._clips_sub_frames['auto_edit'] = ae_frame
        self._build_auto_edit_sub(ae_frame)

        # Show AI Clips by default
        _switch_sub('ai_clips')

        # All existing clips tab content goes into ai_clips_frame
        p = ai_clips_frame  # redirect remaining builds into sub-frame

        # ── Control panel ─────────────────────────────────────────────────────
        ctrl = tk.Frame(p, bg=BG2)
        ctrl.pack(fill='x')

        # ── Row 1: Video/URL + Output ──────────────────────────────────────────
        r1 = tk.Frame(ctrl, bg=BG2); r1.pack(fill='x', padx=10, pady=(7,2))
        lbl(r1, 'Video:').pack(side='left')
        vf = tk.Frame(r1, bg=BG3); vf.pack(side='left', fill='x', expand=True, padx=(4,4))
        self._video_entry = tk.Entry(vf, textvariable=self.v_video, font=FONT_SMALL, bg=BG3, fg=FG,
                 insertbackground=ACCENT, relief='flat', bd=4)
        self._video_entry.pack(side='left', fill='x', expand=True)
        # Placeholder hint
        def _on_video_focus_in(e):
            if self.v_video.get() == self._video_placeholder:
                self.v_video.set(''); self._video_entry.config(fg=FG)
        def _on_video_focus_out(e):
            if not self.v_video.get().strip():
                self.v_video.set(self._video_placeholder)
                self._video_entry.config(fg=FG2)
        self._video_placeholder = 'Paste URL (Kick/Twitch/YouTube/X) or click 📁 to browse...'
        self.v_video.set(self._video_placeholder)
        self._video_entry.config(fg=FG2)
        self._video_entry.bind('<FocusIn>', _on_video_focus_in)
        self._video_entry.bind('<FocusOut>', _on_video_focus_out)
        # Browse button
        tk.Button(vf, text='📁', font=FONT_SMALL, bg=BG2, fg=FG2, relief='flat', bd=0,
                  cursor='hand2', padx=5, command=self._pick_video).pack(side='right')
        # Download button — appears when URL is pasted
        self._dl_btn = tk.Button(vf, text='⬇  Download', font=('Segoe UI', 8, 'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=8,
                  command=self._download_and_load)
        self._dl_cancel_clip_btn = tk.Button(vf, text='✕', font=('Segoe UI', 8, 'bold'),
                  bg=RED, fg='#fff', relief='flat', bd=0, cursor='hand2', padx=8,
                  command=self._cancel_clip_download)
        # Show download button when URL detected; hide both when file loaded
        def _on_video_change(*_):
            val = self.v_video.get().strip()
            placeholder = getattr(self, '_video_placeholder', '')
            is_url = val.startswith('http') and not Path(val).exists() and val != placeholder
            is_downloading = getattr(self, '_clip_dl_running', False)
            if is_url and not is_downloading:
                self._dl_btn.pack(side='right', padx=(2,0))
                try: self._dl_cancel_clip_btn.pack_forget()
                except: pass
            elif not is_url:
                try: self._dl_btn.pack_forget()
                except: pass
                try: self._dl_cancel_clip_btn.pack_forget()
                except: pass
        self.v_video.trace_add('write', _on_video_change)
        lbl(r1, 'Output:').pack(side='left', padx=(4,0))
        of = tk.Frame(r1, bg=BG3); of.pack(side='left', fill='x', expand=True, padx=(4,0))
        tk.Entry(of, textvariable=self.v_outdir, font=FONT_SMALL, bg=BG3, fg=FG,
                 insertbackground=ACCENT, relief='flat', bd=4).pack(side='left', fill='x', expand=True)
        tk.Button(of, text='...', font=FONT_SMALL, bg=BG2, fg=FG2, relief='flat', bd=0,
                  cursor='hand2', padx=5, command=self._pick_outdir).pack(side='right')

        # ── Row 2: Context + Names ────────────────────────────────────────────
        r2 = tk.Frame(ctrl, bg=BG2); r2.pack(fill='x', padx=10, pady=2)
        lbl(r2, 'Context:').pack(side='left')
        cw = tk.Frame(r2, bg=BG3); cw.pack(side='left', fill='x', expand=True, padx=(4,8))
        self.v_context = tk.Text(cw, height=2, font=FONT_SMALL, bg=BG3, fg=FG,
                                 insertbackground=ACCENT, relief='flat', bd=4, wrap='word')
        self.v_context.pack(fill='x')
        self.v_context.insert('1.0', self.cfg.get('video_context',''))
        self.v_context.bind('<FocusOut>', lambda e: (
            self.cfg.update({'video_context': self.v_context.get('1.0','end').strip()}),
            save_cfg(self.cfg)))
        # Names field — helps AI identify who is who
        lbl(r2, 'Names:').pack(side='left')
        nw = tk.Frame(r2, bg=BG3); nw.pack(side='left', fill='x', expand=True, padx=(4,0))
        self.v_names = tk.Entry(nw, font=FONT_SMALL, bg=BG3, fg=FG,
                                insertbackground=ACCENT, relief='flat', bd=4)
        self.v_names.pack(fill='x')
        self.v_names.insert(0, self.cfg.get('video_names',''))
        _names_ph = 'Mizkif, xQc, HasanAbi...'
        if not self.cfg.get('video_names',''):
            self.v_names.insert(0, _names_ph)
            self.v_names.config(fg=FG2)
        def _names_in(e):
            if self.v_names.get() == _names_ph:
                self.v_names.delete(0,'end'); self.v_names.config(fg=FG)
        def _names_out(e):
            v = self.v_names.get().strip()
            if not v:
                self.v_names.insert(0, _names_ph); self.v_names.config(fg=FG2)
            self.cfg.update({'video_names': v}); save_cfg(self.cfg)
        self.v_names.bind('<FocusIn>', _names_in)
        self.v_names.bind('<FocusOut>', _names_out)

        # ttk style — only configure once globally
        if not getattr(App, '_ttk_styled', False):
            style = ttk.Style()
            try: style.theme_use('clam')
            except: pass
            for s,v in [('TCombobox',{'fieldbackground':BG3,'background':BG3,'foreground':FG,
                                       'selectbackground':ACCENT,'selectforeground':'#000',
                                       'borderwidth':0,'arrowcolor':FG2}),
                        ('Vertical.TScrollbar',{'background':BG3,'troughcolor':BG2,
                                                'bordercolor':BG2,'arrowcolor':FG2,
                                                'relief':'flat','borderwidth':0})]:
                style.configure(s, **v)
            style.map('TCombobox', fieldbackground=[('readonly',BG3)],
                      foreground=[('readonly',FG)], background=[('readonly',BG3)])
            App._ttk_styled = True
        style.map('Vertical.TScrollbar', background=[('active',BORDER),('pressed',ACCENT)])
        # Stub widgets needed by _refresh_provider / _refresh_prov_btns
        self._prov_btns = {}
        self._model_btns = {}
        self._model_btn_frame = tk.Frame(ctrl, bg=BG2)  # hidden frame
        self.v_key.trace_add('write', self._on_key_changed)
        self.key_entry = tk.Entry(ctrl, textvariable=self.v_key, show='*',
                                  font=FONT_MONO_S, bg=BG3, fg=FG,
                                  insertbackground=ACCENT, relief='flat', bd=4)
        # key_entry stays hidden (not packed)
        self.model_cb = type('FakeCB', (), {
            'config': lambda self, **kw: None,
            'pack':   lambda self, **kw: None,
        })()
        self.lbl_note = tk.Label(ctrl, text='', font=('Segoe UI', 7), fg=FG2, bg=BG2)
        self.lbl_url  = tk.Label(ctrl, text='', font=('Segoe UI', 7), fg=ACCENT2, bg=BG2,
                                 cursor='hand2')
        self.lbl_url.bind('<Button-1>', self._open_key_url)

        # ── Row 4: Whisper + Mode + Actions ───────────────────────────────────
        r4 = tk.Frame(ctrl, bg=BG2); r4.pack(fill='x', padx=10, pady=(2,7))

        # Whisper selector moved to Settings tab (auto-select by default)
        tk.Frame(r4, bg=BORDER, width=1).pack(side='left', fill='y', padx=10)
        lbl(r4, 'Mode:').pack(side='left')
        self.app_mode = tk.StringVar(value=self.cfg.get('app_mode','normal'))
        self.interview_mode = tk.BooleanVar(value=False)
        self.mode_normal_btn = tk.Button(r4, text='🎬 Normal', font=FONT_SMALL,
                                         relief='flat', bd=0, cursor='hand2', padx=7, pady=4,
                                         command=lambda: self._set_mode('normal'))
        self.mode_normal_btn.pack(side='left', padx=(4,2))
        self.mode_interview_btn = tk.Button(r4, text='🎤 Interview', font=FONT_SMALL,
                                            relief='flat', bd=0, cursor='hand2', padx=7, pady=4,
                                            command=lambda: self._set_mode('interview'))
        self.mode_interview_btn.pack(side='left', padx=(0,2))

        self._refresh_mode_btns()

        tk.Frame(r4, bg=BORDER, width=1).pack(side='left', fill='y', padx=10)

        # Action buttons on the right
        self.trans_btn = tk.Button(r4, text='📝 Transcribe Only', font=FONT_SMALL,
                                   bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                                   padx=10, pady=5, command=self._transcribe_only)
        self.trans_btn.pack(side='right', padx=(4,0))
        self.go_btn = tk.Button(r4, text='▶  FIND CLIPS',
                                font=('Segoe UI', 10,'bold'), bg=ACCENT, fg='#000',
                                relief='flat', bd=0, cursor='hand2', padx=16, pady=5,
                                activebackground=ACCENT2, command=self._start)
        self.go_btn.pack(side='right', padx=(0,4))
        self.cancel_btn = tk.Button(r4, text='✕ Cancel',
                                font=('Segoe UI', 9), bg=BG3, fg=FG2,
                                relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                                activebackground=RED, activeforeground='#fff',
                                command=self._cancel_task)
        # Hidden by default — shows when task is running
        # self.cancel_btn.pack() called in set_busy

        # ── Mode-specific panels ───────────────────────────────────────────────
        self.interview_frame = tk.Frame(ctrl, bg=BG2)
        self.interview_frame.pack(fill='x', padx=10)
        ir = tk.Frame(self.interview_frame, bg=BG2); ir.pack(fill='x', pady=(0,5))
        tk.Label(ir, text='📝 Names field above — add speaker names in the Names: box',
                font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left', padx=4)

        self.auto_frame = tk.Frame(ctrl, bg=BG2)
        self.auto_frame.pack(fill='x', padx=10)
        af = tk.Frame(self.auto_frame, bg=BG2); af.pack(fill='x', pady=(0,5))
        lbl(af, 'Length:').pack(side='left')
        self.auto_length_mode = tk.StringVar(value=self.cfg.get('auto_length_mode','short'))
        self.auto_short_btn = tk.Button(af, text='⚡ Short 1-2min', font=FONT_SMALL,
                                        relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                                        command=lambda: self._set_auto_length('short'))
        self.auto_short_btn.pack(side='left', padx=(4,3))
        self.auto_long_btn = tk.Button(af, text='📽 Long 10min', font=FONT_SMALL,
                                       relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                                       command=lambda: self._set_auto_length('long'))
        self.auto_long_btn.pack(side='left', padx=(0,8))
        self._refresh_auto_btns()
        self.auto_max_min = tk.StringVar(value=self.cfg.get('auto_max_min','2'))
        mrow2 = tk.Frame(af, bg=BG3); mrow2.pack(side='left')
        tk.Entry(mrow2, textvariable=self.auto_max_min, font=FONT_MONO_S, bg=BG3, fg=FG,
                 insertbackground=ACCENT, relief='flat', bd=4, width=4).pack(side='left')
        lbl(mrow2, 'min').pack(side='left', padx=4)
        tk.Frame(af, bg=BORDER, width=1).pack(side='left', fill='y', padx=8)
        lbl(af, 'Order:').pack(side='left')
        self.auto_order = tk.StringVar(value=self.cfg.get('auto_order','viral'))
        for val, txt in [('viral','⭐ Viral'),('pointed','🎯 Pointed'),('chrono','📅 Chrono')]:
            tk.Radiobutton(af, text=txt, variable=self.auto_order, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                           activebackground=BG2, relief='flat', cursor='hand2'
                           ).pack(side='left', padx=(4,0))
        tk.Frame(af, bg=BORDER, width=1).pack(side='left', fill='y', padx=8)
        lbl(af, 'Export:').pack(side='left')
        self.auto_export_final = tk.BooleanVar(value=True)
        self.auto_export_segs  = tk.BooleanVar(value=True)
        for var, txt in [(self.auto_export_final,'✂ Stitched'),(self.auto_export_segs,'📦 Segments')]:
            tk.Checkbutton(af, text=txt, variable=var, font=FONT_SMALL, fg=FG, bg=BG2,
                           selectcolor=BG3, activebackground=BG2, relief='flat',
                           cursor='hand2').pack(side='left', padx=(4,0))
        self._toggle_mode_frames()

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Clips header + export bar ─────────────────────────────────────────
        hdr = tk.Frame(p, bg=BG); hdr.pack(fill='x', padx=8, pady=(4,0))
        tk.Label(hdr, text='AI CLIP SUGGESTIONS', font=('Segoe UI', 9,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        # Select All / Deselect All toggle
        self._sel_all_state = tk.BooleanVar(value=False)
        def _toggle_select_all():
            new_state = not self._sel_all_state.get()
            self._sel_all_state.set(new_state)
            if new_state:
                self._select_all()
                _sel_btn.config(text='☐ Deselect All')
            else:
                for v in self.clip_vars: v.set(False)
                _sel_btn.config(text='☑ Select All')
        _sel_btn = tk.Button(hdr, text='☑ Select All', font=FONT_SMALL, bg=BG, fg=FG2,
                  relief='flat', bd=0, cursor='hand2',
                  command=_toggle_select_all)
        _sel_btn.pack(side='right')

        # Export action bar — LEFT: autocut + format toggles + censor | RIGHT: export button
        exp_bar = tk.Frame(p, bg=BG); exp_bar.pack(fill='x', padx=8, pady=(2,4))

        tk.Button(exp_bar, text='⚡ AUTO-CUT BEST 3', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                  command=self._autocut).pack(side='left', padx=(0,4))

        # 3-way export format: 16:9 / 9:16 / Both
        self.v_crop_mode = tk.StringVar(value='normal')
        _fmt_frame = tk.Frame(exp_bar, bg=BG3, bd=1, relief='flat')
        _fmt_frame.pack(side='left', padx=(0,6))
        self._fmt_btns = {}
        for _lbl, _val in [('16:9','normal'),('9:16','vertical'),('Both','both')]:
            _b = tk.Button(_fmt_frame, text=_lbl,
                           font=('Segoe UI', 7,'bold'),
                           bg=BG3, fg=FG2, relief='flat', bd=0,
                           padx=6, pady=3, cursor='hand2',
                           command=lambda v=_val: self._set_crop_mode(v))
            _b.pack(side='left')
            self._fmt_btns[_val] = _b
        self._set_crop_mode('normal')

        # Censor toggle (left side)
        tk.Frame(exp_bar, bg=BORDER, width=1).pack(side='left', fill='y', padx=6)
        self.censor_toggle = tk.BooleanVar(value=False)
        self.censor_toggle_btn = tk.Button(exp_bar, text='🔇 Censor OFF',
                                           font=FONT_SMALL, bg=BG3, fg=FG2,
                                           relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                                           command=self._toggle_clip_censor)
        self.censor_toggle_btn.pack(side='left', padx=(0,4))

        # Censor style radio buttons (hidden until ON)
        self.clip_censor_style = tk.StringVar(value=self.cfg.get('clip_censor_style','beep'))
        self._censor_style_frame = tk.Frame(exp_bar, bg=BG)
        self._censor_style_frame.pack(side='left')
        for val, lbl_t in [('beep','📢 Beep'),('silence','🔇 Silence'),('mp3','🎵 MP3')]:
            tk.Radiobutton(self._censor_style_frame, text=lbl_t,
                           variable=self.clip_censor_style, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                           activebackground=BG, relief='flat', cursor='hand2',
                           command=lambda: self._refresh_clip_censor_style()
                           ).pack(side='left', padx=(0,4))
        self._censor_style_frame.pack_forget()

        # EXPORT SELECTED — far RIGHT
        tk.Button(exp_bar, text='✂  EXPORT SELECTED', font=('Segoe UI', 9,'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=14, pady=5,
                  activebackground=ACCENT2,
                  command=self._export_or_censor).pack(side='right', padx=(6,0))


        # MP3 browse row — shown only when style=mp3 AND censor is on
        self._censor_mp3_row = tk.Frame(p, bg=BG2)
        mp3_inner = tk.Frame(self._censor_mp3_row, bg=BG2)
        mp3_inner.pack(fill='x', padx=8, pady=(0,3))
        tk.Label(mp3_inner, text='🎵 Custom sound file:', font=FONT_SMALL,
                fg=FG2, bg=BG2).pack(side='left')
        self._clip_mp3_var = tk.StringVar(value=self.cfg.get('censor_mp3',''))
        mp3_entry = tk.Entry(mp3_inner, textvariable=self._clip_mp3_var,
                            font=FONT_SMALL, bg=BG3, fg=FG,
                            insertbackground=ACCENT, relief='flat', bd=4, width=30)
        mp3_entry.pack(side='left', fill='x', expand=True, padx=(6,4))
        tk.Button(mp3_inner, text='📁 Browse', font=FONT_SMALL,
                 bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                 command=lambda: self._clip_mp3_var.set(
                     filedialog.askopenfilename(
                         title='Select MP3/audio file',
                         filetypes=[('Audio', '*.mp3 *.wav *.ogg *.m4a'), ('All', '*.*')]
                     ) or self._clip_mp3_var.get()
                 )).pack(side='left')
        self._clip_mp3_var.trace_add('write', lambda *_: (
            self.cfg.update({'censor_mp3': self._clip_mp3_var.get()}), save_cfg(self.cfg)))
        self._censor_mp3_row.pack_forget()  # hidden by default

        # Queue
        tk.Frame(exp_bar, bg=BORDER, width=1).pack(side='left', fill='y', padx=6)
        tk.Button(exp_bar, text='➕ Queue', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                  command=self._add_to_queue).pack(side='left', padx=(0,4))
        tk.Button(exp_bar, text='▶ Run Queue', font=FONT_SMALL,
                  bg=GREEN, fg='#000', relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                  command=self._run_export_queue).pack(side='left')

        # Permanent anchor for mp3 row — always packed, zero height
        self._mp3_row_anchor = tk.Frame(p, bg=BG, height=0)
        self._mp3_row_anchor.pack(fill='x')

        # Queue display strip
        self._queue_strip = tk.Frame(p, bg=BG3)
        self._queue_strip.pack(fill='x', padx=8, pady=(0,2))
        self.queue_lb = tk.Listbox(self._queue_strip, font=('Segoe UI', 7), bg=BG3, fg=FG2,
                                   selectbackground=ACCENT, selectforeground='#000',
                                   relief='flat', bd=4, height=2, activestyle='none')
        self.queue_lb.pack(fill='x')
        self._queue_strip.pack_forget()  # hidden until items added

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Clips canvas (grows with content) ─────────────────────────────────
        list_outer = tk.Frame(p, bg=BG3)
        list_outer.pack(fill='both', expand=True)
        # Clip canvas + visible scrollbar
        self.clip_canvas = tk.Canvas(list_outer, bg=BG3, bd=0, highlightthickness=0)
        self.clip_canvas.pack(side='left', fill='both', expand=True)
        _bind_mousewheel(self.clip_canvas, self.clip_canvas)

        # Scrollbar — drawn on a canvas so we fully control width/color on Windows
        _SB_W = 14
        _sb_cv = tk.Canvas(list_outer, bg=BG2, width=_SB_W, bd=0,
                            highlightthickness=0, cursor='arrow')
        _sb_cv.pack(side='right', fill='y')
        _sb_state = {'lo': 0.0, 'hi': 1.0, 'drag_y': None}

        def _sb_draw(*_):
            _sb_cv.delete('all')
            h = max(_sb_cv.winfo_height(), 10)
            lo, hi = _sb_state['lo'], _sb_state['hi']
            _sb_cv.create_rectangle(0, 0, _SB_W, h, fill=BG2, outline='')
            ty1 = int(lo * h) + 1
            ty2 = max(int(hi * h) - 1, ty1 + 16)
            _sb_cv.create_rectangle(2, ty1, _SB_W-2, ty2,
                                    fill=ACCENT, outline='', tags='thumb')

        def _yscroll_set(lo, hi):
            _sb_state['lo'] = float(lo)
            _sb_state['hi'] = float(hi)
            _sb_draw()

        def _sb_press(e):
            _sb_state['drag_y'] = e.y

        def _sb_drag(e):
            h = max(_sb_cv.winfo_height(), 10)
            dy = (e.y - (_sb_state['drag_y'] or e.y)) / h
            _sb_state['drag_y'] = e.y
            span = _sb_state['hi'] - _sb_state['lo']
            new_lo = max(0.0, min(1.0 - span, _sb_state['lo'] + dy))
            self.clip_canvas.yview_moveto(new_lo)

        def _sb_click(e):
            h = max(_sb_cv.winfo_height(), 10)
            frac = e.y / h
            span = _sb_state['hi'] - _sb_state['lo']
            self.clip_canvas.yview_moveto(max(0, min(1-span, frac - span/2)))

        _sb_cv.bind('<Button-1>', _sb_click)
        _sb_cv.bind('<ButtonPress-1>', _sb_press)
        _sb_cv.bind('<B1-Motion>', _sb_drag)
        _sb_cv.bind('<Configure>', _sb_draw)

        self.clip_canvas.configure(yscrollcommand=_yscroll_set)
        self.clip_canvas.bind('<MouseWheel>',
            lambda e: self.clip_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self.clip_frame = tk.Frame(self.clip_canvas, bg=BG3)
        self._clip_win_id = self.clip_canvas.create_window((0,0), window=self.clip_frame, anchor='nw')
        def _on_clip_frame_configure(e):
            self.clip_canvas.configure(scrollregion=self.clip_canvas.bbox('all'))
        def _on_clip_canvas_configure(e):
            # Make clip_frame fill canvas width so 3 cols stretch properly
            self.clip_canvas.itemconfig(self._clip_win_id, width=e.width)
        self.clip_frame.bind('<Configure>', _on_clip_frame_configure)
        self.clip_canvas.bind('<Configure>', _on_clip_canvas_configure)
        tk.Label(self.clip_frame, text='\n  Click ▶ FIND CLIPS to analyze your video.\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=30)


    def _build_auto_edit_sub(self, p):
        """Auto Edit sub-tab — removes silence from video using ffmpeg."""

        tk.Label(p, text='⚡  AUTO EDIT', font=('Segoe UI',11,'bold'),
                fg=ACCENT, bg=BG).pack(anchor='w', padx=20, pady=(14,2))
        tk.Label(p, text='Remove silence and dead air from any video in one pass.',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=20, pady=(0,10))

        # ── Video source ──────────────────────────────────────────────────────
        sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        sec.pack(fill='x', padx=16, pady=(0,8))
        inner = tk.Frame(sec, bg=BG2); inner.pack(fill='x', padx=12, pady=8)

        tk.Label(inner, text='Video:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_ae_video = tk.StringVar()
        ae_ef = tk.Frame(inner, bg=BG3); ae_ef.pack(side='left', fill='x', expand=True)
        tk.Entry(ae_ef, textvariable=self.v_ae_video, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(ae_ef, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_ae_video.set(
                     filedialog.askopenfilename(
                         filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')]
                     ) or self.v_ae_video.get())
                 ).pack(side='right')
        tk.Button(inner, text='Use Clip Finder video', font=FONT_SMALL,
                 bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8,
                 command=lambda: self.v_ae_video.set(self.v_video.get())
                 ).pack(side='left', padx=8)

        # ── Output ────────────────────────────────────────────────────────────
        out_row = tk.Frame(sec, bg=BG2); out_row.pack(fill='x', padx=12, pady=(0,8))
        tk.Label(out_row, text='Output:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_ae_out = tk.StringVar(value=self.cfg.get('outdir',''))
        ae_of = tk.Frame(out_row, bg=BG3); ae_of.pack(side='left', fill='x', expand=True)
        tk.Entry(ae_of, textvariable=self.v_ae_out, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(ae_of, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_ae_out.set(
                     filedialog.askdirectory(title='Output folder') or self.v_ae_out.get())
                 ).pack(side='right')

        # ── Settings ──────────────────────────────────────────────────────────
        set_sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        set_sec.pack(fill='x', padx=16, pady=(0,8))
        set_inner = tk.Frame(set_sec, bg=BG2); set_inner.pack(fill='x', padx=12, pady=10)

        tk.Label(set_inner, text='Silence removal:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_ae_mode = tk.StringVar(value='balanced')
        for val, lbl_txt, hint in [
            ('light',      'Light',      '-45dB — only long pauses'),
            ('balanced',   'Balanced',   '-35dB — recommended'),
            ('aggressive', 'Aggressive', '-25dB — tight cuts'),
        ]:
            f = tk.Frame(set_inner, bg=BG2); f.pack(side='left', padx=(12,0))
            tk.Radiobutton(f, text=lbl_txt, variable=self.v_ae_mode, value=val,
                          font=FONT_SMALL, fg=FG, bg=BG2,
                          selectcolor=BG3, activebackground=BG2,
                          cursor='hand2').pack(side='left')
            tk.Label(f, text=hint, font=('Segoe UI',7), fg=FG3, bg=BG2).pack(side='left', padx=(2,0))



        # ── Run button ────────────────────────────────────────────────────────
        btn_row = tk.Frame(p, bg=BG); btn_row.pack(fill='x', padx=16, pady=8)
        tk.Button(btn_row, text='⚡  RUN AUTO EDIT',
                 font=('Segoe UI',10,'bold'), bg=ACCENT, fg='#000',
                 relief='flat', bd=0, cursor='hand2', padx=20, pady=8,
                 command=self._run_auto_edit_sub).pack(side='left')
        tk.Label(btn_row, text='Removes silence in one ffmpeg pass — no glitches',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=12)

        # ── Status ────────────────────────────────────────────────────────────
        self.ae_status_lbl = tk.Label(p, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.ae_status_lbl.pack(fill='x', padx=20, pady=4)

    def _run_auto_edit_sub(self):
        """Run silence removal via ffmpeg silenceremove filter — one pass, no glitches."""
        vid = self.v_ae_video.get().strip()
        out = self.v_ae_out.get().strip()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No video', 'Select a video file first.'); return
        if not out:
            messagebox.showerror('No output', 'Select an output folder first.'); return

        ff = ensure_ffmpeg()
        if not ff:
            messagebox.showerror('ffmpeg missing', 'Install ffmpeg in Settings → Core Dependencies.'); return

        mode = self.v_ae_mode.get()
        db = {'light': '-45', 'balanced': '-35', 'aggressive': '-25'}.get(mode, '-35')


        Path(out).mkdir(parents=True, exist_ok=True)
        stem = Path(vid).stem
        out_path = str(Path(out) / f'{stem} - AutoEdit - ClipFinder.mp4')

        self.set_busy(True)
        self.ae_status_lbl.config(text='⏳ Processing...', fg=ACCENT2)
        self.log(f'⚡ Auto Edit: {stem} [{mode}]', ACCENT2)

        def _run():
            try:
                import subprocess as _sp, re as _re2, tempfile as _tmp2
                _ensure_pkgs_on_path()

                # Step 1: Transcribe to get word timestamps
                self.log('[Auto Edit] Transcribing for word-level cuts...', FG2)
                if getattr(self, '_cancel_requested', False): return
                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Transcribing...', fg=ACCENT2))
                self.set_progress('Auto Edit: transcribing...', pct=10)
                _wm = self.v_whisper.get() if hasattr(self,'v_whisper') else 'base'
                if _wm in ('auto',''):
                    _wm = 'base'
                try:
                    result = _do_transcribe(vid, _wm, ffmpeg_path=ff, use_word_timestamps=True)
                    segs = result.get('segments', [])
                    words = []
                    for seg in segs:
                        for w in seg.get('words', []):
                            words.append((w['start'], w['end']))
                    self.log(f'[Auto Edit] Got {len(words)} word timestamps', FG2)
                except Exception as _te:
                    self.log(f'[Auto Edit] Transcription failed: {_te} — using silence detection only', YELLOW)
                    words = []

                # Step 2: Build keep segments from word timestamps + silence gaps
                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Detecting silence...', fg=ACCENT2))
                self.set_progress('Auto Edit: detecting silence...', pct=35)
                _sil = _sp.run([ff,'-i',vid,'-af',f'silencedetect=noise={db}dB:d=0.3',
                                '-f','null','-'], capture_output=True, text=True, timeout=300)
                sil_starts = [float(m) for m in _re2.findall(r'silence_start: ([\d.]+)', _sil.stderr)]
                sil_ends   = [float(m) for m in _re2.findall(r'silence_end: ([\d.]+)', _sil.stderr)]
                self.log(f'[Auto Edit] Found {len(sil_starts)} silence gaps', FG2)

                # Get total duration
                _di = _sp.run([ff,'-i',vid], capture_output=True, text=True, timeout=30)
                _dm = _re2.search(r'Duration: (\d+):(\d+):([\d.]+)', _di.stderr)
                total = (int(_dm.group(1))*3600 + int(_dm.group(2))*60 + float(_dm.group(3))) if _dm else 0

                # Build keep list — snap cuts to word boundaries if we have them
                def _snap_to_word(t, wds, snap='end'):
                    """Snap timestamp to nearest word start or end boundary."""
                    if not wds:
                        return t
                    best, best_d = t, float('inf')
                    for ws, we in wds:
                        boundary = we if snap == 'end' else ws
                        d = abs(boundary - t)
                        if d < best_d:
                            best_d = d
                            best = boundary
                    # Only snap if within 0.5s — otherwise keep original
                    return best if best_d < 0.5 else t

                if sil_starts:
                    keeps = []
                    prev = 0.0
                    for ss, se in zip(sil_starts, sil_ends):
                        if ss > prev + 0.15:
                            # Snap cut-out point to nearest word end
                            # Snap cut-in point to nearest word start
                            snap_ss = _snap_to_word(ss, words, snap='end')
                            snap_se = _snap_to_word(se, words, snap='start')
                            keeps.append((prev, snap_ss))
                            prev = snap_se
                        else:
                            prev = se
                    if total > prev + 0.15:
                        keeps.append((prev, total))
                else:
                    keeps = [(0, total)] if total else []

                if words:
                    self.log(f'[Auto Edit] Word-boundary cuts applied ({len(words)} words)', FG2)

                if not keeps:
                    self.log('[Auto Edit] Nothing to cut', YELLOW)
                    self.after(0, lambda: self.ae_status_lbl.config(text='Nothing to cut', fg=YELLOW))
                    return

                removed = total - sum(e-s for s,e in keeps)
                self.log(f'[Auto Edit] Removing {removed:.1f}s silence, keeping {sum(e-s for s,e in keeps):.1f}s', FG2)

                # Step 3: Extract and concat segments
                self.after(0, lambda: self.ae_status_lbl.config(text=f'⏳ Cutting {len(keeps)} segments...', fg=ACCENT2))
                self.set_progress(f'Auto Edit: cutting {len(keeps)} segments...', pct=60)
                concat_f = str(Path(_tmp2.gettempdir()) / f'ae_concat_{Path(vid).stem}.txt')
                segs_out = []
                with open(concat_f, 'w') as cf:
                    for j, (ks, ke) in enumerate(keeps):
                        seg_p = str(Path(_tmp2.gettempdir()) / f'ae_s_{j}.mp4')
                        _sp.run([ff,'-y','-ss',str(ks),'-to',str(ke),'-i',vid,
                                 '-c','copy',seg_p],
                                stdout=_sp.PIPE, stderr=_sp.PIPE)
                        cf.write(f"file '{seg_p}'\n")
                        segs_out.append(seg_p)

                # Step 4: Concat with CRF encode to fix size + AV sync
                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Encoding final video...', fg=ACCENT2))
                self.set_progress('Auto Edit: encoding...', pct=80)
                # Use GPU encoder for quality + speed, fallback to x264 CRF 18
                _ae_vcodec, _ae_acodec, _ae_extra = get_encoder(ff)
                _sp.run([ff,'-y','-f','concat','-safe','0','-i',concat_f,
                         '-c:v',_ae_vcodec,'-c:a',_ae_acodec]+_ae_extra+[out_path],
                        stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=3600)

                # Cleanup
                for sf in segs_out:
                    try: Path(sf).unlink()
                    except: pass

                if Path(out_path).exists():
                    orig_mb = Path(vid).stat().st_size/1024/1024
                    new_mb  = Path(out_path).stat().st_size/1024/1024
                    self.log(f'✅ Auto Edit done: {orig_mb:.0f}MB → {new_mb:.0f}MB (removed {removed:.0f}s)', GREEN)
                    self.after(0, lambda: self.ae_status_lbl.config(
                        text=f'✅ {Path(out_path).name} — {orig_mb:.0f}MB → {new_mb:.0f}MB', fg=GREEN))
                else:
                    self.log('❌ Output file not created', RED)
                    self.after(0, lambda: self.ae_status_lbl.config(text='❌ Failed', fg=RED))

            except Exception as _e:
                import traceback as _tb
                self.log(f'Auto Edit error: {_tb.format_exc()}', RED)
                self.after(0, lambda: self.ae_status_lbl.config(text=f'❌ {_e}', fg=RED))
            finally:
                self.set_busy(False)

        threading.Thread(target=_run, daemon=True).start()

    def _build_trans_tab(self, p):

        # ── Sub-tab bar (top, matches AI Clips / Auto Edit style) ────────────
        sub_bar = tk.Frame(p, bg=BG3)
        sub_bar.pack(fill='x')
        self._trans_sub_frames = {}
        self._trans_sub_btns   = {}

        def _switch_trans_sub(key):
            for k, f in self._trans_sub_frames.items():
                f.pack_forget()
            self._trans_sub_frames[key].pack(fill='both', expand=True)
            for k, b in self._trans_sub_btns.items():
                b.config(bg=ACCENT if k == key else BG3,
                         fg='#000' if k == key else ACCENT2,
                         font=('Segoe UI',8,'bold') if k == key else ('Segoe UI',8))

        for _sk, _sl in [('transcript','📝  Transcript & Tweet'), ('subtitles','🔤  Burn Subtitles  ⚠ Beta')]:
            _sb = tk.Button(sub_bar, text=_sl, font=('Segoe UI',8),
                           relief='flat', bd=0, cursor='hand2',
                           padx=20, pady=6, bg=BG3, fg=FG2,
                           command=lambda k=_sk: _switch_trans_sub(k))
            _sb.pack(side='left', fill='x', expand=True)
            self._trans_sub_btns[_sk] = _sb
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # Sub-frames — both sit directly under p
        _trans_p = tk.Frame(p, bg=BG)
        _sub_p   = tk.Frame(p, bg=BG)
        self._trans_sub_frames['transcript'] = _trans_p
        self._trans_sub_frames['subtitles']  = _sub_p

        # Show transcript first
        _switch_trans_sub('transcript')
        p = _trans_p  # redirect so file picker + transcript/tweet content lands here

        # ── Top bar: standalone video input ──────────────────────────────────
        top = tk.Frame(p, bg=BG2)
        top.pack(fill='x', padx=0)
        tinp = tk.Frame(top, bg=BG2); tinp.pack(fill='x', padx=10, pady=6)
        tk.Label(tinp, text='Transcribe file:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_trans_file = tk.StringVar()
        tf = tk.Frame(tinp, bg=BG3); tf.pack(side='left', fill='x', expand=True, padx=(4,8))
        tk.Entry(tf, textvariable=self.v_trans_file, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(tf, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.v_trans_file.set(
                      filedialog.askopenfilename(
                          filetypes=[('Video/Audio','*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.webm'),
                                     ('All','*.*')]
                      ) or self.v_trans_file.get())
                  ).pack(side='right')
        tk.Button(tinp, text='📋 Use Clip Finder video', font=FONT_SMALL,
                  bg=BG2, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=lambda: self.v_trans_file.set(self.v_video.get())
                  ).pack(side='left', padx=(0,8))
        tk.Button(tinp, text='📝 TRANSCRIBE THIS FILE', font=('Segoe UI', 9,'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=14, pady=5,
                  activebackground=ACCENT2,
                  command=self._transcribe_standalone).pack(side='left')
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # Split pane: left = transcript, right = tweet generator
        pane = tk.Frame(p, bg=BG)
        pane.pack(fill='both', expand=True)

        # ── LEFT: transcript ──────────────────────────────────────────────────
        left = tk.Frame(pane, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(0, 6))

        hdr = tk.Frame(left, bg=BG)
        hdr.pack(fill='x', pady=(0, 6))
        tk.Label(hdr, text='FULL TRANSCRIPT', font=('Segoe UI', 9, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Button(hdr, text='Save .srt', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._save_srt).pack(side='right', padx=(4, 0))
        tk.Button(hdr, text='Save .txt', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._save_txt).pack(side='right', padx=4)
        tk.Button(hdr, text='Copy', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._copy_transcript).pack(side='right')
        tk.Button(hdr, text='📋 Log', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._toggle_log).pack(side='right', padx=4)

        trans_wrap = tk.Frame(left, bg=BG3)
        trans_wrap.pack(fill='both', expand=True)
        self.trans_box = tk.Text(trans_wrap, font=FONT_MONO_S, bg=BG3, fg=FG,
                                 insertbackground=ACCENT, relief='flat', bd=8,
                                 wrap='word', state='disabled')
        self.trans_box.pack(side='left', fill='both', expand=True)
        _make_scrollbar(trans_wrap, self.trans_box)
        self.wcount_lbl = tk.Label(left, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.wcount_lbl.pack(fill='x', pady=(4, 0))

        tk.Frame(pane, bg=BORDER, width=1).pack(side='left', fill='y')

        # ── RIGHT: tweet generator ────────────────────────────────────────────
        right = tk.Frame(pane, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        tk.Label(right, text='TWEET GENERATOR', font=('Segoe UI', 9, 'bold'),
                 fg=ACCENT, bg=BG).pack(anchor='w', pady=(0, 6))

        # Context input
        tk.Label(right, text='CONTEXT  (optional)', font=('Segoe UI', 8, 'bold'),
                 fg=FG2, bg=BG).pack(anchor='w')
        tk.Label(right, text="Who's in it, what's the drama, names, etc.",
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', pady=(1, 3))
        self.tweet_context = tk.Text(right, height=3, font=FONT_SMALL,
                                     bg=BG3, fg=FG, insertbackground=ACCENT,
                                     relief='flat', bd=6, wrap='word')
        self.tweet_context.pack(fill='x', pady=(0, 8))
        self.tweet_context.insert('1.0', self.cfg.get('tweet_context', self.cfg.get('video_context', '')))

        # Tone selector
        tk.Label(right, text='TONE', font=('Segoe UI', 8, 'bold'),
                 fg=FG2, bg=BG).pack(anchor='w')
        tone_row = tk.Frame(right, bg=BG)
        tone_row.pack(fill='x', pady=(3, 8))
        self.tweet_tone = tk.StringVar(value='drama')
        self._tweet_tone_btns = {}
        for tone, label in [('drama','🔥 Drama'),('tea','☕ Tea'),
                             ('breaking','📰 Breaking'),('hype','💥 Hype')]:
            b = tk.Button(tone_row, text=label, font=FONT_SMALL,
                          relief='flat', bd=0, cursor='hand2', padx=8, pady=5,
                          command=lambda t=tone: self._set_tweet_tone(t))
            b.pack(side='left', padx=(0, 3))
            self._tweet_tone_btns[tone] = b
        self._refresh_tweet_tones()

        tk.Frame(right, bg=BORDER, height=1).pack(fill='x', pady=6)

        # Generate button + spinner label
        gen_row = tk.Frame(right, bg=BG)
        gen_row.pack(fill='x', pady=(0, 6))
        self.tweet_gen_btn = tk.Button(gen_row, text='⚡  GENERATE TWEET',
                                       font=('Segoe UI', 9, 'bold'),
                                       bg=ACCENT, fg='#000', relief='flat', bd=0,
                                       cursor='hand2', pady=8,
                                       activebackground=ACCENT2,
                                       command=self._generate_tweet)
        self.tweet_gen_btn.pack(fill='x')
        self.tweet_gen_lbl = tk.Label(right, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self.tweet_gen_lbl.pack(anchor='w', pady=(2, 0))

        tk.Frame(right, bg=BORDER, height=1).pack(fill='x', pady=6)

        # 3-tab output area
        out_hdr = tk.Frame(right, bg=BG)
        out_hdr.pack(fill='x', pady=(0, 4))
        tk.Label(out_hdr, text='GENERATED TWEETS', font=('Segoe UI', 8, 'bold'),
                 fg=FG2, bg=BG).pack(side='left')
        tk.Button(out_hdr, text='Regenerate All', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._generate_tweet).pack(side='right', padx=4)

        # Tab bar for 3 options
        self._tweet_tab_idx = 0
        self.tweet_tabs_data = ['', '', '']  # store text for each tab
        tab_bar = tk.Frame(right, bg=BG2)
        tab_bar.pack(fill='x')
        self._tweet_tab_btns = []
        def _switch_tweet_tab(i):
            self._tweet_tab_idx = i
            for j, tb in enumerate(self._tweet_tab_btns):
                tb.config(bg=ACCENT if j == i else BG3,
                          fg='#000' if j == i else FG2)
            txt = self.tweet_tabs_data[i]
            self.tweet_out.config(state='normal')
            self.tweet_out.delete('1.0', 'end')
            self.tweet_out.insert('1.0', txt if txt else 'Hit ⚡ Generate Tweet to get options.')
            _update_char_count()
        for i, lbl in enumerate(['Option 1', 'Option 2', 'Option 3']):
            tb = tk.Button(tab_bar, text=lbl, font=FONT_SMALL,
                           bg=ACCENT if i == 0 else BG3,
                           fg='#000' if i == 0 else FG2,
                           relief='flat', bd=0, cursor='hand2', padx=14, pady=5,
                           command=lambda idx=i: _switch_tweet_tab(idx))
            tb.pack(side='left', padx=(0,2))
            self._tweet_tab_btns.append(tb)

        # Output text box (editable)
        tw = tk.Frame(right, bg=BG3)
        tw.pack(fill='both', expand=True)
        self.tweet_out = tk.Text(tw, font=FONT_MONO_S, bg=BG3, fg=FG,
                                 insertbackground=ACCENT, relief='flat', bd=8,
                                 wrap='word')
        _make_scrollbar(tw, self.tweet_out)
        self.tweet_out.pack(side='left', fill='both', expand=True)
        self.tweet_out.insert('1.0', 'Hit ⚡ Generate Tweet to get 3 different options.')

        # Char count + copy row
        bot_row = tk.Frame(right, bg=BG); bot_row.pack(fill='x', pady=(3,0))
        self.tweet_char_lbl = tk.Label(bot_row, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.tweet_char_lbl.pack(side='left')
        tk.Button(bot_row, text='Copy This', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=10, pady=2,
                  command=self._copy_tweet).pack(side='right')

        def _update_char_count(*_):
            txt = self.tweet_out.get('1.0', 'end').strip()
            chars = len(txt)
            self.tweet_char_lbl.config(
                text=f'{chars} chars',
                fg=GREEN if chars <= 280 else YELLOW if chars <= 500 else ACCENT)
        self.tweet_out.bind('<KeyRelease>', _update_char_count)
        self.tweet_out.bind('<Double-Button-1>', lambda e: (
            self.clipboard_clear(),
            self.clipboard_append(self.tweet_out.get('1.0','end').strip()),
            self.tweet_gen_lbl.config(text='Copied!', fg=GREEN)))

        # ── BURN SUBTITLES sub-tab content ────────────────────────────────────
        sub_body = tk.Frame(_sub_p, bg=BG); sub_body.pack(fill='both', expand=True, padx=20, pady=8)

        # Row 1: Video input with browse + transcribe button built-in
        io_row = tk.Frame(sub_body, bg=BG); io_row.pack(fill='x', pady=(0, 4))
        tk.Label(io_row, text='Video:', font=FONT_SMALL, fg=FG2, bg=BG, width=7, anchor='w').pack(side='left')
        self.v_sub_input = tk.StringVar()
        inp_f = tk.Frame(io_row, bg=BG3); inp_f.pack(side='left', fill='x', expand=True, padx=(0, 6))
        tk.Entry(inp_f, textvariable=self.v_sub_input, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4).pack(side='left', fill='x', expand=True)
        tk.Button(inp_f, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.v_sub_input.set(
                      filedialog.askopenfilename(filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')]
                      ) or self.v_sub_input.get())).pack(side='right')
        tk.Button(io_row, text='\U0001f4cb Use Clip Finder', font=FONT_SMALL,
                  bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=lambda: self.v_sub_input.set(self.v_video.get() or self.v_trans_file.get())).pack(side='left', padx=(0, 4))
        self.sub_trans_btn = tk.Button(io_row, text='\U0001f4dd Transcribe',
                  font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=3, command=self._sub_transcribe)
        self.sub_trans_btn.pack(side='left')
        self.sub_trans_lbl = tk.Label(io_row, text='Transcribe the video first', font=FONT_SMALL, fg=YELLOW, bg=BG)
        self.sub_trans_lbl.pack(side='left', padx=6)

        # Output folder
        out_row2 = tk.Frame(sub_body, bg=BG); out_row2.pack(fill='x', pady=(0, 8))
        tk.Label(out_row2, text='Save to:', font=FONT_SMALL, fg=FG2, bg=BG, width=7, anchor='w').pack(side='left')
        self.v_sub_outdir = tk.StringVar(value=self.cfg.get('sub_outdir', str(Path.home() / 'Downloads')))
        out_f2 = tk.Frame(out_row2, bg=BG3); out_f2.pack(side='left', fill='x', expand=True, padx=(0, 6))
        tk.Entry(out_f2, textvariable=self.v_sub_outdir, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4).pack(side='left', fill='x', expand=True)
        tk.Button(out_f2, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.v_sub_outdir.set(
                      filedialog.askdirectory() or self.v_sub_outdir.get())).pack(side='right')

        # Row 2: Style options
        style_row = tk.Frame(sub_body, bg=BG); style_row.pack(fill='x', pady=(0, 6))

        # Font family
        tk.Label(style_row, text='Font:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self.v_sub_font = tk.StringVar(value='Arial')
        font_opts = ['Arial', 'Impact', 'Helvetica', 'Roboto', 'Oswald',
                     'Anton', 'Bebas Neue', 'Comic Sans MS', 'Verdana', 'Tahoma']
        tk.OptionMenu(style_row, self.v_sub_font, *font_opts).configure(
            bg=BG3, fg=FG, font=FONT_SMALL, relief='flat', bd=0,
            activebackground=BG4, highlightthickness=0)
        om = tk.OptionMenu(style_row, self.v_sub_font, *font_opts)
        om.config(bg=BG3, fg=FG, font=FONT_SMALL, relief='flat', bd=0,
                  activebackground=BG4, highlightthickness=0, cursor='hand2')
        om.pack(side='left', padx=(4, 12))

        # Font size
        tk.Label(style_row, text='Size:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self.v_sub_size = tk.IntVar(value=48)
        tk.Spinbox(style_row, from_=16, to=120, textvariable=self.v_sub_size,
                   width=4, font=FONT_SMALL, bg=BG3, fg=FG, relief='flat',
                   buttonbackground=BG4, insertbackground=ACCENT).pack(side='left', padx=(4, 12))

        # Bold / Italic
        self.v_sub_bold   = tk.BooleanVar(value=True)
        self.v_sub_italic = tk.BooleanVar(value=False)
        tk.Checkbutton(style_row, text='Bold', variable=self.v_sub_bold,
                       font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2').pack(side='left', padx=(0, 6))
        tk.Checkbutton(style_row, text='Italic', variable=self.v_sub_italic,
                       font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2').pack(side='left', padx=(0, 12))
        # All caps
        self.v_sub_caps = tk.BooleanVar(value=False)
        tk.Checkbutton(style_row, text='ALL CAPS', variable=self.v_sub_caps,
                       font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2').pack(side='left')

        # Row 3: Colors
        color_row = tk.Frame(sub_body, bg=BG); color_row.pack(fill='x', pady=(0, 6))
        self.v_sub_color      = tk.StringVar(value='#FFFFFF')
        self.v_sub_outline    = tk.StringVar(value='#000000')
        self.v_sub_bg_col     = tk.StringVar(value='#000000')
        self.v_sub_highlight  = tk.StringVar(value='#FFE000')  # karaoke word color
        self.v_sub_bg_on      = tk.BooleanVar(value=True)
        self.v_sub_bg_opacity = tk.IntVar(value=60)
        self.v_sub_karaoke    = tk.BooleanVar(value=False)

        def _pick_color(var, btn):
            import tkinter.colorchooser as _cc
            c = _cc.askcolor(color=var.get(), title='Pick colour')[1]
            if c: var.set(c); btn.config(bg=c)

        # Text color
        tk.Label(color_row, text='Text:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        _tc_btn = tk.Button(color_row, bg='#FFFFFF', width=3, relief='flat', cursor='hand2',
                            command=lambda: _pick_color(self.v_sub_color, _tc_btn))
        _tc_btn.pack(side='left', padx=(4, 8))

        # Outline color
        tk.Label(color_row, text='Outline:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        _oc_btn = tk.Button(color_row, bg='#000000', width=3, relief='flat', cursor='hand2',
                            command=lambda: _pick_color(self.v_sub_outline, _oc_btn))
        _oc_btn.pack(side='left', padx=(4, 8))

        # Outline thickness
        tk.Label(color_row, text='Stroke:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self.v_sub_stroke = tk.IntVar(value=3)
        tk.Spinbox(color_row, from_=0, to=10, textvariable=self.v_sub_stroke,
                   width=3, font=FONT_SMALL, bg=BG3, fg=FG, relief='flat',
                   buttonbackground=BG4).pack(side='left', padx=(4, 8))

        # Karaoke highlight toggle + color
        tk.Checkbutton(color_row, text='Karaoke', variable=self.v_sub_karaoke,
                       font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2').pack(side='left')
        _hc_btn = tk.Button(color_row, bg='#FFE000', width=3, relief='flat', cursor='hand2',
                            command=lambda: _pick_color(self.v_sub_highlight, _hc_btn))
        _hc_btn.pack(side='left', padx=(4, 10))

        # Background box
        tk.Checkbutton(color_row, text='BG Box', variable=self.v_sub_bg_on,
                       font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2').pack(side='left')
        _bc_btn = tk.Button(color_row, bg='#000000', width=3, relief='flat', cursor='hand2',
                            command=lambda: _pick_color(self.v_sub_bg_col, _bc_btn))
        _bc_btn.pack(side='left', padx=(4, 4))
        tk.Label(color_row, text='Opacity:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        tk.Spinbox(color_row, from_=0, to=100, textvariable=self.v_sub_bg_opacity,
                   width=4, font=FONT_SMALL, bg=BG3, fg=FG, relief='flat',
                   buttonbackground=BG4).pack(side='left', padx=(4, 0))
        tk.Label(color_row, text='%', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')

        # Row 4: Position grid + style presets
        pos_preset_row = tk.Frame(sub_body, bg=BG); pos_preset_row.pack(fill='x', pady=(0, 6))

        # Position grid (3x3)
        tk.Label(pos_preset_row, text='Position:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=(0, 6))
        self.v_sub_position = tk.StringVar(value='bottom-center')
        _pos_grid = tk.Frame(pos_preset_row, bg=BG2)
        _pos_grid.pack(side='left', padx=(0, 16))
        _positions = [
            ('top-left',    '↖'), ('top-center',    '↑'), ('top-right',    '↗'),
            ('mid-left',    '←'), ('mid-center',    '·'), ('mid-right',    '→'),
            ('bottom-left', '↙'), ('bottom-center', '↓'), ('bottom-right', '↘'),
        ]
        _pos_btns = {}
        def _set_pos(pos):
            self.v_sub_position.set(pos)
            for p2, b2 in _pos_btns.items():
                b2.config(bg=ACCENT if p2 == pos else BG3, fg='#000' if p2 == pos else FG)
        for idx, (pos, sym) in enumerate(_positions):
            r, c = divmod(idx, 3)
            b = tk.Button(_pos_grid, text=sym, font=('Segoe UI', 8),
                          bg=ACCENT if pos == 'bottom-center' else BG3,
                          fg='#000' if pos == 'bottom-center' else FG,
                          relief='flat', bd=1, cursor='hand2', width=2, height=1,
                          command=lambda p=pos: _set_pos(p))
            b.grid(row=r, column=c, padx=1, pady=1)
            _pos_btns[pos] = b

        # Style presets
        tk.Label(pos_preset_row, text='Style:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=(0, 6))
        self.v_sub_style_preset = tk.StringVar(value='standard')
        _preset_btns = {}
        def _apply_preset(preset):
            self.v_sub_style_preset.set(preset)
            presets = {
                'standard':  {'bold': True, 'italic': False, 'caps': False, 'color': '#FFFFFF', 'outline': '#000000', 'stroke': 3, 'bg': True,  'bg_opacity': 0,  'size': 48},
                'karaoke':   {'bold': True, 'italic': False, 'caps': False, 'color': '#FFE000', 'outline': '#000000', 'stroke': 4, 'bg': False, 'bg_opacity': 0,  'size': 52},
                'cinematic': {'bold': False,'italic': False, 'caps': True,  'color': '#FFFFFF', 'outline': '#000000', 'stroke': 2, 'bg': True,  'bg_opacity': 70, 'size': 44},
                'minimal':   {'bold': False,'italic': False, 'caps': False, 'color': '#FFFFFF', 'outline': '#000000', 'stroke': 1, 'bg': False, 'bg_opacity': 0,  'size': 36},
                'tiktok':    {'bold': True, 'italic': False, 'caps': True,  'color': '#FFFFFF', 'outline': '#FF0050', 'stroke': 5, 'bg': False, 'bg_opacity': 0,  'size': 56, 'words': 3},
            }
            p = presets.get(preset, presets['standard'])
            self.v_sub_bold.set(p['bold']); self.v_sub_italic.set(p['italic'])
            self.v_sub_caps.set(p['caps']); self.v_sub_color.set(p['color'])
            self.v_sub_outline.set(p['outline']); self.v_sub_stroke.set(p['stroke'])
            self.v_sub_bg_on.set(p['bg']); self.v_sub_bg_opacity.set(p['bg_opacity'])
            self.v_sub_size.set(p['size'])
            if 'words' in p: self.v_sub_words.set(p['words'])
            _tc_btn.config(bg=p['color']); _oc_btn.config(bg=p['outline'])
            # Update button highlights
            for pr, pb in _preset_btns.items():
                pb.config(bg=ACCENT if pr == preset else BG3,
                          fg='#000' if pr == preset else FG)
            self._render_sub_preview()
        for preset, plbl in [('standard','Standard'),('karaoke','Karaoke'),
                              ('cinematic','Cinematic'),('minimal','Minimal'),('tiktok','TikTok')]:
            _pb = tk.Button(pos_preset_row, text=plbl, font=FONT_SMALL,
                      bg=ACCENT if preset == 'standard' else BG3,
                      fg='#000' if preset == 'standard' else FG,
                      relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                      command=lambda pr=preset: _apply_preset(pr))
            _pb.pack(side='left', padx=(0, 3))
            _preset_btns[preset] = _pb

        # Row 5: Words per line + Preview + Burn button
        action_row = tk.Frame(sub_body, bg=BG); action_row.pack(fill='x', pady=(4, 0))
        tk.Label(action_row, text='Words/line:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self.v_sub_words = tk.IntVar(value=6)
        tk.Spinbox(action_row, from_=1, to=20, textvariable=self.v_sub_words,
                   width=3, font=FONT_SMALL, bg=BG3, fg=FG, relief='flat',
                   buttonbackground=BG4).pack(side='left', padx=(4, 12))

        self.sub_preview_btn = tk.Button(action_row, text='👁  Preview Frame',
                  font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=5,
                  command=self._sub_preview_frame)
        self.sub_preview_btn.pack(side='left', padx=(0, 8))

        self.sub_burn_btn = tk.Button(action_row, text='🔤  BURN SUBTITLES',
                  font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000',
                  relief='flat', bd=0, cursor='hand2', padx=14, pady=6,
                  activebackground=ACCENT2,
                  command=self._burn_subtitles)
        self.sub_burn_btn.pack(side='left')

        self.sub_status_lbl = tk.Label(action_row, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self.sub_status_lbl.pack(side='left', padx=10)

        # Preview canvas (hidden until user clicks Preview)
        self._sub_preview_frame_widget = tk.Label(sub_body, bg=BG2, text='', cursor='hand2')
        tk.Label(sub_body, text='⚠  Burn Subtitles is in beta — timing and styling may not be perfect. Report issues to @MarsScumbags.',
                 font=('Segoe UI', 7), fg=YELLOW, bg=BG, wraplength=900, anchor='w', justify='left'
                 ).pack(fill='x', pady=(6, 0))
        tk.Label(sub_body, text='This feature is still in the works — more improvements coming in future updates.',
                 font=('Segoe UI', 7), fg=FG2, bg=BG, anchor='w'
                 ).pack(fill='x')

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _on_clips_canvas_resize(self, event):
        self.clip_canvas.itemconfig(self._clip_win_id, width=event.width)

    def _show_empty(self):
        for w in self.clip_frame.winfo_children():
            w.destroy()
        # Reset select all toggle
        if hasattr(self, '_sel_all_state'):
            self._sel_all_state.set(False)
        tk.Label(self.clip_frame,
                 text='\n  Click ▶ FIND CLIPS to analyze your video.\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=20, padx=10)

    def _on_key_changed(self, *_):
        if hasattr(self, '_keys'):
            self._keys[self.v_provider.get()] = self.v_key.get()



    def _refresh_model_btns(self):
        cur = self.v_model.get()
        for m, btn in getattr(self, '_model_btns', {}).items():
            try:
                btn.config(bg=ACCENT if m==cur else BG3,
                          fg='#000' if m==cur else FG2)
            except: pass

    def _refresh_prov_btns(self):
        cur = self.v_provider.get()
        for pname, btn in getattr(self, '_prov_btns', {}).items():
            btn.config(bg=ACCENT if pname==cur else BG3,
                       fg='#000' if pname==cur else FG2)

    def _refresh_provider(self, *_):
        self._refresh_prov_btns()
        prov = self.v_provider.get()
        data = PROVIDERS.get(prov, {})
        models = data.get('models', [])
        # Show/hide note labels based on whether they have content
        def _update_notes(note_txt, url_txt):
            try:
                _update_notes(note_txt, url_txt)
                # Pack inline in r3 only if there's text
                if note_txt:
                    self.lbl_note.pack(side='left', padx=(8,0))
                else:
                    self.lbl_note.pack_forget()
                if url_txt:
                    self.lbl_url.pack(side='left')
                else:
                    self.lbl_url.pack_forget()
            except: pass
        _update_notes(data.get('note', ''), '🔑 Get free key: ' + data.get('url', ''))
        self._key_url = data.get('url', '')
        # Rebuild model buttons
        try:
            saved = self.v_model.get()
            for w in self._model_btn_frame.winfo_children(): w.destroy()
            self._model_btns = {}
            for m in models:
                short = m.split("/")[-1].replace("gemini-","g-").replace("-flash","-f").replace("-pro","-p")[:16]
                b = tk.Button(self._model_btn_frame, text=short, font=FONT_SMALL,
                              relief="flat", bd=0, cursor="hand2", padx=6, pady=4,
                              bg=BG3, fg=FG2,
                              command=lambda mv=m: (self.v_model.set(mv), self._refresh_model_btns()))
                b.pack(side="left", padx=(0,2))
                self._model_btns[m] = b
            self.v_model.set(saved if saved in models else (models[0] if models else ""))
            self._refresh_model_btns()
        except Exception: pass
        # Restore saved key for this provider
        if hasattr(self, '_keys'):
            self.v_key.set(self._keys.get(prov, ''))

    def _open_key_url(self, *_):
        import webbrowser
        webbrowser.open(getattr(self, '_key_url', ''))

    def _pick_video(self):
        p = filedialog.askopenfilename(
            title='Select video',
            filetypes=[('Video', '*.mp4 *.mkv *.mov *.avi *.webm'), ('All', '*.*')])
        if p:
            self.v_video.set(p)
            if hasattr(self, '_video_entry'):
                self._video_entry.config(fg=FG)
            if not self.v_outdir.get():
                self.v_outdir.set(str(Path(p).parent))

    def _cancel_clip_download(self):
        """Cancel download triggered from the Clip Finder video field."""
        self._dl_cancel_requested = True
        self._clip_dl_running = False
        try:
            self._dl_cancel_clip_btn.pack_forget()
            self._dl_btn.pack(side='right', padx=(2,0))
        except: pass
        self.log('⛔ Download cancelled', YELLOW)
        self.set_progress('Cancelled', pct=0)

    def _download_and_load(self):
        """Download URL from video field using full pipeline then auto-load."""
        url = self.v_video.get().strip()
        if not url.startswith('http'):
            return
        # Pick download folder
        folder = self.v_outdir.get().strip() or self.cfg.get('dl_folder', '') or str(Path.home() / 'Downloads')
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.v_dl_url.set(url)
        self._dl_cancel_requested = False
        self._clip_dl_running = True
        self.log(f'⬇ Downloading: {url}', ACCENT2)
        self.set_progress('⬇ Starting download...', pct=0)
        # Swap to cancel button
        try:
            self._dl_btn.pack_forget()
            self._dl_cancel_clip_btn.pack(side='right', padx=(2,0))
        except: pass

        self._load_after_dl = True

        def _on_done():
            self._clip_dl_running = False
            try:
                self._dl_cancel_clip_btn.pack_forget()
                # Don't re-show download btn — URL replaced with file path
            except: pass

        import threading
        def _run_and_notify():
            self._dl_run(url, folder)
            self.after(0, _on_done)
        threading.Thread(target=_run_and_notify, daemon=True).start()

    def _pick_outdir(self):
        d = filedialog.askdirectory()
        if d:
            self.v_outdir.set(d)


    def _check_first_run(self):
        """Show setup prompt on first launch if packages not installed."""
        # Check if faster-whisper exists in pkgs/
        _ensure_pkgs_on_path()
        _has_pkgs = (any(PKGS_DIR.glob('faster_whisper*')) or
                     any(PKGS_DIR.glob('groq*')) or
                     any(PKGS_DIR.glob('google_genai*')))
        if _has_pkgs:
            return  # Already set up, nothing to do

        # First launch — show a friendly setup dialog
        if not messagebox.askyesno(
            'Welcome to ClipFinder! ⚡',
            'Hi! ClipFinder needs to download AI packages (~500MB) to work.\n\n'
            'This only happens once and runs in the background\n'
            'while the app stays open.\n\n'
            'Install now?',
            icon='info'
        ):
            return

        # Switch to settings and trigger install
        self._switch_nb('settings')
        self.after(300, self._trigger_install_all)

    def _trigger_install_all(self):
        """Programmatically click Install All AI Packages if available."""
        try:
            if hasattr(self, '_install_all_fn'):
                self._install_all_fn()
        except Exception:
            pass  # User can click manually

    def _bind_global_mousewheel(self):
        """Bind mousewheel to scroll whatever scrollable widget is under the cursor."""
        import tkinter as _tk

        def _find_scrollable(widget):
            """Walk up the widget tree to find a scrollable canvas or text widget."""
            w = widget
            for _ in range(12):  # max depth
                try:
                    cls = w.winfo_class()
                    if cls in ('Canvas', 'Text', 'Listbox'):
                        return w
                    w = w.nametowidget(w.winfo_parent())
                except: break
            return None

        def _on_mousewheel(event):
            # Find the widget under the cursor
            try:
                x, y = self.winfo_pointerxy()
                target = self.winfo_containing(x, y)
                if not target: return
                scrollable = _find_scrollable(target)
                if scrollable:
                    cls = scrollable.winfo_class()
                    delta = int(-1 * (event.delta / 120))
                    if cls == 'Canvas':
                        scrollable.yview_scroll(delta, 'units')
                    elif cls in ('Text', 'Listbox'):
                        scrollable.yview_scroll(delta, 'units')
            except: pass

        # Bind to the root window — catches ALL mousewheel events app-wide
        self.bind_all('<MouseWheel>', _on_mousewheel)
        # Linux scroll buttons
        self.bind_all('<Button-4>', lambda e: _on_mousewheel(type('E', (), {'delta': 120})()))
        self.bind_all('<Button-5>', lambda e: _on_mousewheel(type('E', (), {'delta': -120})()))

    def _fix_all_scrollbars(self):
        """Walk entire widget tree and force dark colors on every Scrollbar."""
        def _walk(widget):
            try:
                if isinstance(widget, tk.Scrollbar):
                    widget.config(
                        bg=BG2, troughcolor=BG2,
                        activebackground=BG3,
                        highlightbackground=BG2,
                        highlightcolor=BG2,
                        highlightthickness=0,
                        relief='flat', bd=0, width=5,
                        elementborderwidth=0
                    )
            except Exception:
                pass
            for child in widget.winfo_children():
                _walk(child)
        _walk(self)
        self.after(600, lambda: _walk(self))

    def _quit(self):
        # Flush current key for current provider
        if hasattr(self, '_keys'):
            self._keys[self.v_provider.get()] = self.v_key.get()
        # Merge everything into self.cfg so nothing gets lost
        self.cfg.update({
            'provider':          self.v_provider.get(),
            'model':             self.v_model.get(),
            'whisper':           self.v_whisper.get(),
            'tweet_context': self.tweet_context.get('1.0','end').strip() if hasattr(self,'tweet_context') else '',
            'outdir':            self.v_outdir.get().strip(),
            'key_gemini':        self._keys.get('Google Gemini (Free)', ''),
            'key_groq':          self._keys.get('Groq (Free)', ''),
            'key_openrouter':    self._keys.get('OpenRouter (Free models)', ''),
            'key_unsplash':      self._keys.get('_unsplash', ''),
            'key_brave_search':  self._keys.get('_brave_search', ''),
            'cookies_file':      self.v_cookies.get() if hasattr(self, 'v_cookies') else '',
            'dl_folder':         self.v_dl_folder.get() if hasattr(self, 'v_dl_folder') else '',
            'dl_quality':        self.v_dl_quality.get() if hasattr(self, 'v_dl_quality') else 'best',
            'auto_load':         self.v_auto_load.get() if hasattr(self, 'v_auto_load') else True,
            'thumb_outdir':      self.thumb_outdir_var.get() if hasattr(self, 'thumb_outdir_var') else '',
            'studio_scan_dir':   self.v_scan_folder.get() if hasattr(self, 'studio_scan_dir') else '',
            'studio_upscale_out': self.v_up_out.get() if hasattr(self, 'studio_upscale_out') else '',
            'interview_mode':    self.interview_mode.get() if hasattr(self, 'interview_mode') else False,
            'interview_names':   self.v_names.get().strip() if hasattr(self, 'v_names') else '',
            'app_mode':          self.app_mode.get() if hasattr(self, 'app_mode') else 'normal',
            'video_context':     self.v_context.get('1.0','end').strip() if hasattr(self, 'v_context') else '',
            'auto_length_mode':  self.auto_length_mode.get() if hasattr(self, 'auto_length_mode') else 'short',
            'auto_max_min':      self.auto_max_min.get() if hasattr(self, 'auto_max_min') else '2',
            'auto_order':        self.auto_order.get() if hasattr(self, 'auto_order') else 'viral',
            'censor_style':      self.censor_style.get() if hasattr(self, 'censor_style') else 'beep',
            'clip_censor_style': self.clip_censor_style.get() if hasattr(self, 'clip_censor_style') else 'beep',
            'censor_outdir':     self.censor_out_var.get() if hasattr(self, 'censor_out_var') else '',
            'censor_mp3':        self.censor_mp3_var.get() if hasattr(self, 'censor_mp3_var') else '',
            'censor_words':      self._censor_words if hasattr(self, '_censor_words') else [],
        })
        save_cfg(self.cfg)
        global _GPU_ENCODER_CACHE
        _GPU_ENCODER_CACHE = None
        self.destroy()

    def log(self, msg, color=None):
        print(f'[CF] {msg}')
        # Buffer all messages so log window can show history when opened
        if not hasattr(self, '_log_buffer'):
            self._log_buffer = []
        self._log_buffer.append((msg, color))
        if len(self._log_buffer) > 500:
            self._log_buffer = self._log_buffer[-500:]
        def _do():
            # Update status bar
            try: self.v_status.set(msg[:90])
            except: pass
            # Update log box if window is open
            try:
                if hasattr(self,'log_box') and self.log_box.winfo_exists():
                    self.log_box.config(state='normal')
                    if color:
                        tag = f't{abs(hash(msg))}'
                        self.log_box.tag_configure(tag, foreground=color)
                        self.log_box.insert('end', msg + '\n', tag)
                    else:
                        self.log_box.insert('end', msg + '\n')
                    self.log_box.see('end')
                    self.log_box.config(state='disabled')
            except: pass
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self.after(0, _do)

    def set_busy(self, busy):
        if busy:
            self._cancel_requested = False  # only reset when STARTING a new task
        state = 'disabled' if busy else 'normal'
        try: self.go_btn.config(state=state)
        except: pass
        try: self.trans_btn.config(state=state)
        except: pass
        try:
            if busy:
                self.cancel_btn.pack(side='right', padx=(0,4), before=self.go_btn)
                self.cancel_btn.config(bg=BG3, fg=FG2)
            else:
                self.cancel_btn.pack_forget()
        except: pass
        def _do():
            try:
                if busy:
                    self.progressbar.config(mode='indeterminate')
                    self.progressbar.start(10)
                else:
                    self.progressbar.stop()
                    self.progressbar.config(mode='determinate')
                    self.progressbar['value'] = 0
                    self.prog_lbl.config(text='Ready')
                    self.status_step_lbl.config(text='')
                    self.status_pct_lbl.config(text='')
            except: pass
        if threading.current_thread() is threading.main_thread(): _do()
        else: self.after(0, _do)

    def _cancel_task(self):
        """Cancel the currently running clip-finding task."""
        self._cancel_requested = True
        self.running = False
        # Signal faster-whisper iterator to stop
        _do_transcribe._cancelled = True
        # Kill any active whisper.cpp subprocess
        for _p in getattr(_do_transcribe, '_active_procs', []):
            try:
                _p.kill()
                self.log('⛔ Killed whisper process', YELLOW)
            except: pass
        _do_transcribe._active_procs = []
        self.log('⛔ Task cancelled', YELLOW)
        self.set_progress('Cancelled', pct=0)
        self.after(300, lambda: self.set_busy(False))

    def set_progress(self, msg, step=None, total=None, pct=None):
        """Update unified status bar from any thread.
        msg   = main status message e.g. 'Transcribing audio...'
        step  = current step number e.g. 2
        total = total steps e.g. 4
        pct   = percentage 0-100 (switches bar to determinate mode)
        """
        def _do():
            try:
                self.prog_lbl.config(text=msg)
                if step is not None and total is not None:
                    self.status_step_lbl.config(text=f'Step {step}/{total}')
                elif step is not None:
                    self.status_step_lbl.config(text=f'Step {step}')
                if pct is not None:
                    self.progressbar.stop()
                    self.progressbar.config(mode='determinate')
                    self.progressbar['value'] = max(0, min(100, pct))
                    self.status_pct_lbl.config(text=f'{int(pct)}%')
                else:
                    self.status_pct_lbl.config(text='')
            except: pass
        if threading.current_thread() is threading.main_thread(): _do()
        else: self.after(0, _do)

    # ── Validation ────────────────────────────────────────────────────────────
    def validate(self, need_ai=True, need_outdir=True):
        # Ensure pkgs/ is on path then check for whisper
        _ensure_pkgs_on_path()
        import importlib as _ilv
        _has_whisper = False
        # First try importing
        for _wmod in ('faster_whisper', 'whisper'):
            try:
                _ilv.import_module(_wmod)
                _has_whisper = True
                break
            except ImportError:
                pass
        # Also check by folder presence in PKGS_DIR (import may fail due to deps
        # but the package files are there and will work once deps load)
        if not _has_whisper:
            _has_whisper = (any(PKGS_DIR.glob('faster_whisper*')) or
                           any(PKGS_DIR.glob('whisper*')))
        if not _has_whisper:
            _msg = (
                'Whisper (transcription engine) is not installed.\n\n'
                'Go to:  ⚙ Settings  →  🔄 Update Modules\n'
                'Click "Install All AI Packages" or the ↑ Update button\n'
                'next to "faster-whisper".\n\n'
                'The app will stay open while packages install in the background.'
            )
            messagebox.showerror('Whisper Not Installed', _msg)
            self._switch_nb('settings')
            return False
        _vid_val = self.v_video.get().strip()
        _placeholder = getattr(self, "_video_placeholder", "")
        if not _vid_val or _vid_val == _placeholder:
            messagebox.showerror("No video", "Select a video file or paste a URL first.")
            return False
        if _vid_val.startswith("http"):
            if messagebox.askyesno("Download first?", f"Looks like a URL — download it first?\n\n{_vid_val[:80]}"):
                self._download_and_load()
            return False
        if not Path(_vid_val).exists():
            messagebox.showerror("Not found", f"File does not exist:\n{_vid_val}")
            return False
            messagebox.showerror('Not found', f'File does not exist:\n{self.v_video.get()}')
            return False
        if need_ai and not self.v_key.get().strip():
            messagebox.showerror('No API key', 'Enter your API key.')
            return False
        if need_outdir and not self.v_outdir.get().strip():
            messagebox.showerror('No output folder', 'Select an output folder.')
            return False
        return True

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _set_mode(self, mode):
        self.app_mode.set(mode)
        self.interview_mode.set(mode == 'interview')  # compat
        self._refresh_mode_btns()
        self._toggle_mode_frames()
        self.cfg['app_mode'] = mode
        save_cfg(self.cfg)

    def _set_auto_length(self, length):
        self.auto_length_mode.set(length)
        default = '2' if length == 'short' else '8'
        self.auto_max_min.set(default)
        self._refresh_auto_btns()
        self.cfg['auto_length_mode'] = length
        self.cfg['auto_max_min'] = default
        save_cfg(self.cfg)

    def _refresh_auto_btns(self):
        short = self.auto_length_mode.get() == 'short'
        self.auto_short_btn.config(bg=ACCENT if short else BG3, fg='#000' if short else FG)
        self.auto_long_btn.config( bg=ACCENT if not short else BG3, fg='#000' if not short else FG)

    def _refresh_mode_btns(self):
        m = self.app_mode.get()
        if hasattr(self, 'mode_normal_btn'):
            self.mode_normal_btn.config(
                bg=ACCENT if m=='normal' else BG3, fg='#000' if m=='normal' else FG)
        if hasattr(self, 'mode_interview_btn'):
            self.mode_interview_btn.config(
                bg=ACCENT if m=='interview' else BG3, fg='#000' if m=='interview' else FG)
        if hasattr(self, 'go_btn'):
            self.go_btn.config(text='▶  FIND CLIPS')

    def _toggle_mode_frames(self):
        m = self.app_mode.get()
        self.interview_frame.pack_forget()
        self.auto_frame.pack_forget()
        if m == 'interview':
            self.interview_frame.pack(fill='x', padx=0)
        elif m == 'auto':
            self.auto_frame.pack(fill='x', padx=0)

    def _toggle_interview_frame(self):
        self._toggle_mode_frames()


    def _transcribe_standalone(self):
        """Transcribe a file picked in the Transcript tab."""
        vid = self.v_trans_file.get().strip()
        if not vid:
            vid = self.v_video.get().strip()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No file', 'Select a video/audio file using the picker above, or load a video in Clip Finder first.')
            return
        # Set as main video and run transcription
        self.v_video.set(vid)
        self._transcribe_only()

    def _transcribe_only(self):
        if self.running: return
        if not self.validate(need_ai=False, need_outdir=False): return
        self.running = True
        self.set_busy(True)
        self.log('Starting transcription...')
        threading.Thread(target=self._run_transcribe, args=(False,), daemon=True).start()

    def _start(self):
        if self.running: return
        if not self.validate(need_ai=True): return
        mode = self.app_mode.get()
        if mode == 'interview':
            names = self.interview_names_box.get('1.0','end').strip()
            self.cfg['interview_names'] = names
            save_cfg(self.cfg)

        self.running = True
        self.set_busy(True)
        self._show_empty()
        self.log('Starting...')
        threading.Thread(target=self._run_transcribe, args=(True,), daemon=True).start()


    def _run_auto_edit_v2(self):
        """CapCut-style auto edit — silence removal + energy peaks + AI selection."""
        try:
            vid = self.v_video.get()
            if not vid or not Path(vid).exists():
                self.after(0, lambda: self.log('No video loaded', RED))
                return

            ff = ensure_ffmpeg()
            if not ff:
                self.after(0, lambda: self.log('ffmpeg required for Auto Edit', RED))
                return

            # Step 1: Get video duration
            import subprocess as _sp_ae, re as _re_ae, json as _js_ae
            self.set_progress('Auto Edit: analyzing video...', pct=5)
            if getattr(self, '_cancel_requested', False): return

            # Try ffmpeg stderr for duration (works on all file types)
            _dur_r = _sp_ae.run([ff, '-i', vid],
                                 capture_output=True, text=True, timeout=30)
            _dm = _re_ae.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur_r.stderr)
            if _dm:
                _h, _m, _s = _dm.groups()
                duration = int(_h)*3600 + int(_m)*60 + float(_s)
            else:
                # fallback to ffprobe
                _dur_r2 = _sp_ae.run([ff, '-v', 'error', '-show_entries', 'format=duration',
                                      '-of', 'default=noprint_wrappers=1:nokey=1', vid],
                                     capture_output=True, text=True, timeout=30)
                duration = float(_dur_r2.stdout.strip() or 300)
            self.log(f'[Auto Edit] Video: {duration:.0f}s ({duration/60:.1f}min)', FG2)

            # Step 2: Detect silence gaps — find non-silent segments
            self.set_progress('Auto Edit: detecting silence...', pct=15)
            _sil_r = _sp_ae.run([ff, '-i', vid, '-af',
                                  'silencedetect=noise=-35dB:d=0.8', '-f', 'null', '-'],
                                 capture_output=True, text=True, timeout=300)
            sil_output = _sil_r.stderr

            # Parse silence periods
            silence_starts = [float(m) for m in _re_ae.findall(r'silence_start: ([\d.]+)', sil_output)]
            silence_ends   = [float(m) for m in _re_ae.findall(r'silence_end: ([\d.]+)', sil_output)]
            self.log(f'[Auto Edit] Found {len(silence_starts)} silence gaps', FG2)

            # Step 3: Audio energy peaks
            self.set_progress('Auto Edit: finding reaction moments...', pct=30)
            if getattr(self, '_cancel_requested', False): return
            energy_peaks = _analyze_audio_energy(vid, ff, num_peaks=15)
            if energy_peaks:
                self.log(f'[Auto Edit] {len(energy_peaks)} energy peaks detected', FG2)

            # Step 4: Transcribe for AI context
            self.set_progress('Auto Edit: transcribing...', pct=40)
            if getattr(self, '_cancel_requested', False): return
            _ensure_pkgs_on_path()
            _wm = self.v_whisper.get()
            if _wm in ('auto', ''):
                _wm = 'base' if duration < 1800 else 'small'
            try:
                result = _do_transcribe(vid, _wm, ffmpeg_path=ff)
                transcript = result.get('text', '')
                _segs = result.get("segments", [])
                self.transcript = "\n".join(
                    "[" + ts(s["start"]) + " -> " + ts(s["end"]) + "] " + s["text"].strip()
                    for s in _segs)
                self.log(f'[Auto Edit] Transcribed: {len(transcript.split())} words', FG2)
            except Exception as te:
                transcript = ''
                self.log(f'[Auto Edit] Transcription skipped: {te}', YELLOW)

            # Step 5: Ask AI to pick the best clips using all the data
            self.set_progress('Auto Edit: AI selecting clips...', pct=60)
            self._current_energy_peaks = energy_peaks

            if transcript and getattr(self, 'transcript', ''):
                self.log('[Auto Edit] Sending to AI for clip selection...', FG2)
                # Trigger AI analysis — reuse existing pipeline
                # _run_transcribe with then_ai=True handles the full AI flow
                # We already have transcript set, so just run the AI part
                self.running = True
                try:
                    self._run_transcribe(then_ai=True)
                    return  # _run_transcribe handles busy/running cleanup
                except Exception as _ai_err:
                    self.log(f'[Auto Edit] AI error: {_ai_err}', YELLOW)
                    transcript = ''

            if not transcript:
                clips = []
                for i, peak in enumerate(energy_peaks[:6]):
                    start = max(0, peak - 30)
                    end   = min(duration, peak + 60)
                    clips.append({
                        'start': ts(start), 'end': ts(end),
                        'title': f'Energy Peak {i+1}',
                        'score': 8, 'reason': 'High audio energy moment'
                    })
                if clips:
                    def _display(c=clips):
                        self.clips = c
                        self._render_clips()
                        self.set_progress(f'Auto Edit: {len(c)} clips found!', pct=100)
                    self.after(0, _display)
                    self.log(f'[Auto Edit] ✅ {len(clips)} clips ready', GREEN)
                else:
                    self.log('[Auto Edit] No clips found', YELLOW)

        except Exception:
            import traceback as _tb
            self.after(0, lambda: self.log(f'Auto Edit error:\n{_tb.format_exc()}', RED))
        finally:
            self.running = False
            self.set_busy(False)

    def _run_transcribe(self, then_ai):
        try:
            vid = self.v_video.get()
            model_size = self.v_whisper.get()
            if model_size in ('auto', '', None):
                # Smart auto: pick model based on video duration + GPU
                try:
                    import subprocess as _ffp
                    _ff_dur = ensure_ffmpeg()
                    _dur_r = _ffp.run([_ff_dur, '-v', 'error', '-show_entries',
                                       'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', vid],
                                      capture_output=True, text=True, timeout=10)
                    _duration = float(_dur_r.stdout.strip() or 0)
                except Exception:
                    _duration = 0
                _has_gpu = getattr(self, '_gpu_type', 'CPU') not in ('CPU', '', None)
                if _duration < 300:          # under 5 min
                    model_size = 'tiny' if not _has_gpu else 'base'
                elif _duration < 1200:       # 5-20 min
                    model_size = 'base'
                elif _duration < 3600:       # 20-60 min
                    model_size = 'small'
                else:                        # 60+ min VOD
                    model_size = 'medium' if _has_gpu else 'small'
                self.log(f'[Auto] Video {_duration:.0f}s → whisper {model_size} (GPU={_has_gpu})', FG2)
            self.log(f'Transcribing: {Path(vid).name}  [{model_size}]')


            _ff = ensure_ffmpeg()
            _ctx_prompt = self.v_context.get('1.0','end').strip() if hasattr(self,'v_context') else ''

            # Real-time progress from transcription engine
            # Falls back to animated dots if no timestamps available
            self.ticker_on = True
            self._trans_got_real_progress = False

            def _progress_cb(pct, msg):
                self._trans_got_real_progress = True
                self.ticker_on = False  # stop dots once real progress starts
                if pct is not None:
                    self.after(0, lambda p=pct, m=msg:
                        self.set_progress(m, step=1, total=3, pct=p))
                else:
                    self.after(0, lambda m=msg:
                        self.set_progress(m, step=1, total=3))

            def tick():
                import time; d = 0; waited = 0
                while self.ticker_on:
                    d = (d % 5) + 1
                    # Only show dots if no real progress has come in yet
                    if not self._trans_got_real_progress:
                        dots = '.' * d
                        label = f'[{model_size}] Transcribing{dots}'
                        self.after(0, lambda lb=label: self.set_progress(lb, step=1, total=3))
                    time.sleep(0.8)
            threading.Thread(target=tick, daemon=True).start()

            result = _do_transcribe(vid, model_size,
                                    initial_prompt=_ctx_prompt or None,
                                    ffmpeg_path=_ff,
                                    progress_cb=_progress_cb)
            self.ticker_on = False
            self.srt_result = result

            segs_raw = result.get('segments', [])
            self._whisper_segments = segs_raw
            lines = []
            for seg in segs_raw:
                lines.append(f'[{ts(seg["start"])}] {seg["text"].strip()}')
            self.transcript = '\n'.join(lines)

            segs  = len(result.get('segments', []))
            words = len(self.transcript.split())

            def update_trans():
                self.trans_box.config(state='normal')
                self.trans_box.delete('1.0', 'end')
                self.trans_box.insert('1.0', self.transcript)
                self.trans_box.config(state='disabled')
                self.wcount_lbl.config(text=f'{segs} segments  ·  {words:,} words')
                # Only switch to transcript tab if this was a transcribe-only request
                if not then_ai:
                    self._switch_nb('transcript')
            self.after(0, update_trans)

            self.log(f'Transcription done: {segs} segments, {words:,} words', GREEN)

            if then_ai:
                if not getattr(self, '_cancel_requested', False):
                    self._run_ai()
                else:
                    self.log('⛔ Cancelled — skipping AI', YELLOW)
                    self.running = False
                    self.after(0, lambda: self.set_busy(False))
            else:
                self.running = False
                self.after(0, lambda: self.set_busy(False))

        except Exception as _run_err:
            self.ticker_on = False
            err_str = str(_run_err)
            err_tb  = traceback.format_exc()
            self.log(f'ERROR in transcription:\n{err_tb}', RED)
            self.running = False
            self.after(0, lambda: self.set_busy(False))
            if 'No transcription engine' in err_str or 'faster_whisper' in err_tb or 'No module named' in err_tb:
                def _show_whisper_dialog():
                    messagebox.showerror(
                        'Whisper Not Installed',
                        'No transcription engine found.\n\n'
                        'Go to:  ⚙ Settings  →  🔄 Update Modules\n'
                        'Click \"Install All AI Packages\" or update\n'
                        '\"faster-whisper\" individually.\n\n'
                        'Installation runs in the background — app stays open.'
                    )
                    self._switch_nb('settings')
                self.after(0, _show_whisper_dialog)

    # ── AI call helpers ───────────────────────────────────────────────────────

    def _call_with_key(self, prov_name, key, model, data):
        """Make a single API call with a specific key. Raises on failure."""
        lib = data['lib']
        if lib == 'gemini':
            from google import genai as _g
            client = _g.Client(api_key=key)
            all_models = data['models']
            try_models = [model] + [m for m in all_models if m != model]
            last_err = None
            for try_model in try_models:
                try:
                    resp = client.models.generate_content(
                        model=try_model, contents=self._current_prompt,
                        config={'temperature': 0.3, 'max_output_tokens': 4096})
                    return resp.text.strip()
                except Exception as _e:
                    if '429' in str(_e) or 'RESOURCE_EXHAUSTED' in str(_e):
                        last_err = _e; continue
                    raise
            raise last_err or Exception('Gemini quota exhausted')
        elif lib == 'groq':
            from groq import Groq as _G
            resp = _G(api_key=key).chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': self._current_prompt}],
                temperature=0.3, max_tokens=4096)
            return resp.choices[0].message.content.strip()
        elif lib == 'openrouter':
            from openai import OpenAI as _O
            _or = _O(base_url='https://openrouter.ai/api/v1', api_key=key)
            resp = _or.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': self._current_prompt}],
                temperature=0.3, max_tokens=8192)
            choice = resp.choices[0]
            raw = choice.message.content.strip()
            if choice.finish_reason == 'length' and len(raw) > 100:
                self.log('[OpenRouter] Truncated — retrying condensed', YELLOW)
                resp2 = _or.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': self._current_prompt[:len(self._current_prompt)//2] + '\n\n[Top 3 clips as JSON only]'}],
                    temperature=0.3, max_tokens=4096)
                raw = resp2.choices[0].message.content.strip()
            return raw
        raise ValueError(f'Unknown lib: {lib}')

    def _call_provider(self, prov_name, transcript_chunk):
        """Call a single provider, rotating through all configured keys. Returns clip list or raises."""
        data  = PROVIDERS[prov_name]
        lib   = data['lib']
        model = self.v_model.get() if self.v_provider.get() == prov_name else data['models'][0]

        # Key pool: primary + extras
        _primary = self._keys.get(prov_name, '').strip()
        _extras  = getattr(self, '_extra_keys', {}).get(prov_name, [])
        _key_pool = [k for k in [_primary] + list(_extras) if k]
        if not _key_pool:
            raise ValueError(f'No API key for {prov_name}')

        # Build prompt
        ctx_raw = self.v_context.get('1.0','end').strip() if hasattr(self,'v_context') else ''
        context_block = f'VIDEO CONTEXT: {ctx_raw}\n' if ctx_raw else ''
        _names_raw = ''
        if hasattr(self, 'v_names'):
            _nv = self.v_names.get().strip()
            _ph = 'Mizkif, xQc, HasanAbi...'
            if _nv and _nv != _ph:
                _names_raw = _nv
        names_block = (f'PEOPLE IN THIS VIDEO: {_names_raw}\nUse these names in titles and descriptions.\n') if _names_raw else ''
        _ep = getattr(self, '_current_energy_peaks', [])
        if _ep:
            context_block += f'AUDIO ENERGY PEAKS: {", ".join(f"{t:.0f}s" for t in _ep)}\n'
        import re as _re
        ts_matches = _re.findall(r'\[(\d{2}:\d{2}:\d{2})', transcript_chunk)
        section_note = f'SECTION: {ts_matches[0]} → {ts_matches[-1]}. Find clips within this range only.\n' if len(ts_matches) >= 2 else ''
        app_mode = self.app_mode.get() if hasattr(self,'app_mode') else 'normal'
        if app_mode == 'interview':
            _ph = 'Mizkif, xQc, HasanAbi...'
            names = self.v_names.get().strip() if hasattr(self,'v_names') else ''
            if names == _ph: names = ''
            names_list = ', '.join(n.strip() for n in names.splitlines() if n.strip()) or 'Unknown'
            prompt = INTERVIEW_CLIP_PROMPT.replace('{transcript}', transcript_chunk) \
                                          .replace('{names}', names_list) \
                                          .replace('{context_block}', context_block + section_note)
        else:
            prompt = AI_PROMPT.replace('{transcript}', transcript_chunk) \
                               .replace('{context_block}', context_block + section_note) \
                               .replace('{names_block}', names_block)

        # Try each key in pool — rotate on rate limit
        _last_err = None
        for _ki, key in enumerate(_key_pool):
            try:
                if lib == 'gemini':
                    from google import genai as _g
                    client = _g.Client(api_key=key)
                    all_models = data['models']
                    try_models = [model] + [m for m in all_models if m != model]
                    last_merr = None
                    raw = None
                    for try_model in try_models:
                        try:
                            resp = client.models.generate_content(
                                model=try_model, contents=prompt,
                                config={'temperature': 0.3, 'max_output_tokens': 4096})
                            raw = resp.text.strip()
                            last_merr = None
                            break
                        except Exception as _e:
                            if '429' in str(_e) or 'RESOURCE_EXHAUSTED' in str(_e):
                                last_merr = _e; continue
                            raise
                    if last_merr is not None:
                        raise last_merr

                elif lib == 'groq':
                    from groq import Groq as _G
                    _groq_prompt = prompt
                    # Groq has ~6000 token input limit on free — truncate if needed
                    if len(_groq_prompt) > 20000:
                        _groq_prompt = _groq_prompt[:20000] + '\n[Transcript truncated — find clips from the above]'
                        self.log('[Groq] Prompt truncated to fit token limit', FG2)
                    resp = _G(api_key=key).chat.completions.create(
                        model=model, messages=[{'role':'user','content':_groq_prompt}],
                        temperature=0.3, max_tokens=4096)
                    raw = resp.choices[0].message.content.strip()

                elif lib == 'openrouter':
                    from openai import OpenAI as _O
                    _or = _O(base_url='https://openrouter.ai/api/v1', api_key=key)
                    if not hasattr(self, '_dead_or_models'): self._dead_or_models = set()
                    _or_models = [m for m in data['models'] if m not in self._dead_or_models] or data['models']
                    _or_raw = None
                    for _orm in _or_models:
                        try:
                            _r = _or.chat.completions.create(
                                model=_orm, messages=[{'role':'user','content':prompt}],
                                temperature=0.3, max_tokens=8192)
                            _or_raw = _r.choices[0].message.content.strip()
                            if _r.choices[0].finish_reason == 'length' and _or_raw:
                                self.log('[OpenRouter] Truncated — retrying condensed', YELLOW)
                                _r2 = _or.chat.completions.create(
                                    model=_orm,
                                    messages=[{'role':'user','content':prompt[:len(prompt)//2]+'\n\n[Top 3 clips JSON only]'}],
                                    temperature=0.3, max_tokens=4096)
                                _or_raw = _r2.choices[0].message.content.strip()
                            break
                        except Exception as _orme:
                            _es = str(_orme).lower()
                            if '404' in _es or 'no endpoints' in _es:
                                self._dead_or_models.add(_orm)
                                self.log(f'[OpenRouter] {_orm} dead, trying next...', YELLOW)
                                continue
                            raise
                    if _or_raw is None: raise Exception('All OpenRouter models unavailable')
                    raw = _or_raw
                else:
                    raise ValueError(f'Unknown lib: {lib}')


                if _ki > 0:
                    self.log(f'[{prov_name}] Key {_ki+1} succeeded', GREEN)
                break  # success — exit key loop

            except Exception as _ke:
                _ks = str(_ke).lower()
                if any(x in _ks for x in ['429','rate','quota','resource_exhausted','too many']):
                    if _ki < len(_key_pool) - 1:
                        self.log(f'[{prov_name}] Key {_ki+1}/{len(_key_pool)} rate-limited → trying key {_ki+2}...', YELLOW)
                        _last_err = _ke
                        continue
                    else:
                        raise  # all keys exhausted
                raise  # non-rate-limit error

        # Parse JSON response
        clean = raw.strip()
        clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.MULTILINE)
        clean = re.sub(r'```\s*$', '', clean, flags=re.MULTILINE)
        clean = clean.strip()
        s, e = clean.find('['), clean.rfind(']')
        if s != -1 and e > s:
            clean = clean[s:e+1]
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass
        last_brace = clean.rfind('}')
        if last_brace != -1:
            trimmed = clean[:last_brace+1]
            if not trimmed.rstrip().endswith(']'):
                trimmed = trimmed + ']'
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError:
                pass
        objects = re.findall(r'\{[^{}]+\}', clean, re.DOTALL)
        if objects:
            try:
                return json.loads('[' + ','.join(objects) + ']')
            except json.JSONDecodeError:
                pass
        raise ValueError(f'Could not parse AI response: {raw[:200]}')

    def _run_ai(self):
        if getattr(self, '_cancel_requested', False):
            self.log('⛔ AI cancelled before start', YELLOW)
            self.running = False
            self.after(0, lambda: self.set_busy(False))
            return
        _ensure_pkgs_on_path()
        try:
            primary   = self.v_provider.get()
            all_provs = [primary] + [p for p in PROVIDERS if p != primary]
            keyed     = [p for p in all_provs if self._keys.get(p, '').strip()]

            if not keyed:
                raise ValueError('No API keys saved. Enter at least one key.')

            transcript = self.transcript
            lines      = transcript.splitlines()
            total_lines = len(lines)


            # ── Chunk size based on provider capability ───────────────────────
            # Gemini 2.0 Flash: 1M token context — can handle entire transcripts
            # Groq Llama 70B:   128k tokens — handles 4hr video in 2-3 chunks
            # OpenRouter free:  typically 4k-8k context — needs small chunks
            _prov_name = primary
            if 'gemini' in _prov_name.lower():
                CHARS_PER_CHUNK = 120000   # Gemini handles massive context
            elif 'groq' in _prov_name.lower():
                CHARS_PER_CHUNK = 48000    # Groq 128k context window
            else:
                CHARS_PER_CHUNK = 7500     # OpenRouter free — conservative
            full_text = transcript

            # Split into chunks by character count, respecting line boundaries
            chunks = []
            cur_lines = []
            cur_chars = 0
            for line in lines:
                cur_lines.append(line)
                cur_chars += len(line) + 1
                if cur_chars >= CHARS_PER_CHUNK:
                    chunks.append('\n'.join(cur_lines))
                    cur_lines = []
                    cur_chars = 0
            if cur_lines:
                chunks.append('\n'.join(cur_lines))

            n_chunks = len(chunks)
            self.log(
                f'Transcript: {total_lines} segments, {len(full_text):,} chars → '
                f'{n_chunks} chunk(s) at {CHARS_PER_CHUNK//1000}k chars/chunk '
                f'({_prov_name})', YELLOW)

            # ── Hybrid: audio energy peaks ────────────────────────────────────
            _energy_peaks = []
            try:
                _ff2 = ensure_ffmpeg()
                _vid_path = self.v_video.get()
                if _ff2 and _vid_path and Path(_vid_path).exists():
                    self.set_progress('Hybrid: analyzing audio energy peaks...', pct=28)
                    _energy_peaks = _analyze_audio_energy(_vid_path, _ff2, num_peaks=12)
                    if _energy_peaks:
                        self.log(f'[Hybrid] {len(_energy_peaks)} energy peaks: '
                                 + ', '.join(f'{t:.0f}s' for t in _energy_peaks[:8])
                                 + ('...' if len(_energy_peaks)>8 else ''), FG2)
            except Exception as _hye:
                self.log(f'[Hybrid] Energy analysis skipped: {_hye}', FG2)
            self.set_progress(f'Step 2/3 — AI analysis ({n_chunks} section(s))...',
                              step=2, total=3)
            self._current_energy_peaks = _energy_peaks  # available to _call_provider

            def _is_rate_err(e):
                s = str(e).lower()
                return any(x in s for x in ['429','503','rate','quota','resource_exhausted',
                                             'rate-limited','temporarily','upstream',
                                             'unavailable','overloaded','capacity'])

            # Track which providers are rate-limited globally
            _rl_provs = set()
            _rl_provs_lock = __import__('threading').Lock()

            def _mark_rl(prov):
                with _rl_provs_lock:
                    # Rotate to next key before marking as limited
                    _pool = [k for k in [self._keys.get(prov,'').strip()] + getattr(self,'_extra_keys',{}).get(prov,[]) if k]
                    if len(_pool) > 1:
                        _cur = getattr(self, '_key_index', {}).get(prov, 0)
                        _next = (_cur + 1) % len(_pool)
                        if not hasattr(self, '_key_index'): self._key_index = {}
                        self._key_index[prov] = _next
                        # Only mark RL if we've cycled through all keys
                        if _next != 0:
                            return  # still have keys to try, don't mark as RL yet
                    _rl_provs.add(prov)

            def _clear_rl(prov):
                with _rl_provs_lock:
                    _rl_provs.discard(prov)

            def _try_chunk(chunk, label, exclude=None, start_prov=None):
                exclude = exclude or set()
                # Start from assigned provider, skip any currently rate-limited
                _order = list(keyed)
                if start_prov and start_prov in _order:
                    idx = _order.index(start_prov)
                    _order = _order[idx:] + _order[:idx]
                # Try non-rate-limited providers first
                _dead = getattr(self, '_dead_models', set())
                _available = [p for p in _order if p not in _rl_provs and p not in exclude and p not in _dead]
                _fallback  = [p for p in _order if p in _rl_provs and p not in exclude and p not in _dead]
                for prov in _available + _fallback:
                    try:
                        self.log(f'[{label}] → {prov}...')
                        clips = self._call_provider(prov, chunk)
                        _clear_rl(prov)
                        self.log(f'[{label}] {prov} → {len(clips)} clips', GREEN)
                        return clips, prov
                    except Exception as ex:
                        s = str(ex).lower()
                        if _is_rate_err(ex):
                            _mark_rl(prov)
                            self.log(f'[{label}] {prov} rate-limited, trying next...', YELLOW)
                            continue
                        elif '404' in s or 'no endpoints' in s:
                            # Dead model — add to session dead list, never try again
                            if not hasattr(self, '_dead_models'):
                                self._dead_models = set()
                            self._dead_models.add(prov)
                            self.log(f'[{label}] {prov} model unavailable — skipping for session', YELLOW)
                            continue
                        elif '403' in s or 'access denied' in s or 'forbidden' in s:
                            self.log(f'[{label}] {prov} access denied, skipping...', YELLOW)
                            continue
                        self.log(f'[{label}] {prov} failed: {str(ex)[:80]}', RED)
                        continue
                return [], None

            # ── Multi-provider parallel processing ───────────────────────────
            # Strategy: always split transcript across ALL available providers
            # so every provider works simultaneously regardless of chunk count.
            # If more chunks than providers, providers cycle (each handles multiple).
            # If more providers than chunks, extra providers get adjacent sections
            # to cross-check and produce more clips.
            import concurrent.futures as _cf

            all_clips    = []
            seen_starts  = set()

            # Re-chunk using the SMALLEST per-provider limit so all providers
            # can handle their assigned chunks. Each provider gets chunks sized
            # to its own context window.
            def _chunks_for_prov(prov, text):
                if 'gemini' in prov.lower():
                    limit = 120000
                elif 'groq' in prov.lower():
                    limit = 48000
                else:
                    limit = 7500
                result, buf, buf_len = [], [], 0
                for line in text.splitlines():
                    buf.append(line)
                    buf_len += len(line) + 1
                    if buf_len >= limit:
                        result.append('\n'.join(buf))
                        buf, buf_len = [], 0
                if buf:
                    result.append('\n'.join(buf))
                return result

            # Assign chunks to providers — only split if transcript is long enough
            assignments = []
            _MIN_LINES_PER_SECTION = 20  # don't split tiny transcripts across 3 providers
            if len(keyed) == 1 or len(lines) < _MIN_LINES_PER_SECTION * 2:
                # Short transcript or single provider — just use first available provider
                _best_prov = keyed[0]
                for i, ch in enumerate(chunks):
                    assignments.append((ch, _best_prov, f'sec{i+1}/{n_chunks}'))
                if len(keyed) > 1 and len(lines) < _MIN_LINES_PER_SECTION * 2:
                    self.log(f'Short transcript ({len(lines)} lines) — using single provider to save quota', FG2)
            else:
                # Long transcript — split across providers to parallelize
                n_provs = min(len(keyed), max(1, len(lines) // _MIN_LINES_PER_SECTION))
                active_provs = keyed[:n_provs]
                section_size = max(1, len(lines) // n_provs)
                for pi, prov in enumerate(active_provs):
                    sec_start = pi * section_size
                    sec_end   = (pi + 1) * section_size if pi < n_provs - 1 else len(lines)
                    sec_lines = lines[sec_start:sec_end]
                    sec_text  = '\n'.join(sec_lines)
                    sub_chunks = _chunks_for_prov(prov, sec_text)
                    for si, sc in enumerate(sub_chunks):
                        lbl = f'{prov.split()[0]} sec{pi+1}'
                        if len(sub_chunks) > 1: lbl += f'.{si+1}'
                        assignments.append((sc, prov, lbl))

            total_tasks = len(assignments)
            self.log(
                f'Dispatching {total_tasks} task(s) across {len(keyed)} provider(s) in parallel',
                YELLOW)

            task_results  = [None] * total_tasks
            completed     = [0]
            import threading as _thr, time as _time
            _rl_lock      = _thr.Lock()
            _cooling_down = [False]  # shared flag — all threads wait when True

            def _task_worker(idx, chunk, prov, label):
                # Stagger start to avoid thundering herd on free APIs
                _time.sleep(idx * 0.8)

                # Check cancel before starting
                if getattr(self, '_cancel_requested', False):
                    return

                # Wait if global cooldown is active
                while _cooling_down[0]:
                    if getattr(self, '_cancel_requested', False):
                        return
                    _time.sleep(2)

                clips, used = _try_chunk(chunk, label, exclude=set(), start_prov=prov)

                # Retry loop — up to 3 times with increasing cooldown
                _retry = 0
                while not clips and _retry < 3:
                    # Check cancel before waiting
                    if getattr(self, '_cancel_requested', False):
                        return
                    _retry += 1
                    _wait = 30 * _retry  # 30s, 60s, 90s
                    with _rl_lock:
                        if not _cooling_down[0]:
                            _cooling_down[0] = True
                            self.log(f'[{label}] All providers rate-limited — waiting {_wait}s (attempt {_retry}/3)...', YELLOW)
                    # Sleep in small chunks so cancel works immediately
                    for _ in range(_wait):
                        if getattr(self, '_cancel_requested', False):
                            return
                        _time.sleep(1)
                    with _rl_lock:
                        _cooling_down[0] = False
                    if getattr(self, '_cancel_requested', False):
                        return
                    clips, used = _try_chunk(chunk, label, exclude=set(), start_prov=prov)

                if not clips:
                    self.log(f'[{label}] Giving up after 3 retries — skipping this section', YELLOW)

                task_results[idx] = clips or []
                completed[0] += 1
                pct = int(completed[0] / total_tasks * 100)
                self.after(0, lambda p=pct, l=label, n=completed[0]:
                    self.set_progress(
                        f'AI scanning {l} ({n}/{total_tasks} done)...',
                        step=2, total=3, pct=p))

            # Sequential — one task at a time, 5s gap between each
            import time as _t_seq
            for i, (ch, pv, lb) in enumerate(assignments):
                if getattr(self, '_cancel_requested', False):
                    self.log('⛔ AI cancelled', YELLOW)
                    break
                if i > 0:
                    # Check cancel during the 5s sleep too
                    for _ in range(5):
                        if getattr(self, '_cancel_requested', False):
                            break
                        _t_seq.sleep(1)
                if getattr(self, '_cancel_requested', False):
                    self.log('⛔ AI cancelled', YELLOW)
                    break
                _task_worker(i, ch, pv, lb)

            # Merge all results, deduplicate by start timestamp
            for result_list in task_results:
                for clip in (result_list or []):
                    k = clip.get('start','')
                    if k not in seen_starts:
                        seen_starts.add(k)
                        all_clips.append(clip)

            if not all_clips:
                if getattr(self, '_cancel_requested', False):
                    return
                raise Exception('All providers failed or rate-limited. Try again in a few minutes.')

            # Sort by score desc
            def _score_key(c):
                try: return -int(c.get('score', 5))
                except: return -5
            all_clips.sort(key=_score_key)

            # ── Verification pass: rewrite titles/descriptions from segment text ──
            # Extract only the transcript lines that fall within each clip's timestamps
            # so descriptions are guaranteed to match what's actually in the clip
            if all_clips and self.transcript:
                self.log('Verifying clip descriptions against transcript...', FG2)
                self.set_progress('Verifying clip accuracy...', step=3, total=3, pct=80)
                import re as _re_v

                def _ts_to_secs(t):
                    try:
                        parts = str(t).split(':')
                        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+float(parts[2])
                        if len(parts) == 2: return int(parts[0])*60+float(parts[1])
                        return float(t)
                    except: return 0.0

                def _extract_segment_text(start_t, end_t, transcript):
                    """Extract transcript lines that fall within clip timestamps."""
                    s = _ts_to_secs(start_t)
                    e = _ts_to_secs(end_t)
                    lines_out = []
                    for line in transcript.splitlines():
                        # Match [HH:MM:SS -> HH:MM:SS] format
                        m = _re_v.match(r'\[([\d:]+)\s*[-\u2192]\s*([\d:]+)\](.+)', line)
                        if m:
                            ls = _ts_to_secs(m.group(1))
                            le = _ts_to_secs(m.group(2))
                            # Include if overlaps with clip window
                            if ls < e and le > s:
                                lines_out.append(m.group(3).strip())
                    return ' '.join(lines_out)

                for clip in all_clips:
                    seg_text = _extract_segment_text(
                        clip.get('start','00:00:00'),
                        clip.get('end','00:01:00'),
                        self.transcript
                    )
                    if seg_text and len(seg_text) > 20:
                        clip['_verified_text'] = seg_text
                        # Rewrite description from actual segment text
                        clip['reason'] = seg_text[:200]

            self.clips = all_clips
            merged = all_clips  # for logging below

            if not self.clips:
                self.log('No clips found — all providers rate-limited. Try again in a minute.', RED)
            else:
                self.log(f'Done: {len(self.clips)} clip suggestions total!', GREEN)

            self.set_progress('Done!', step=3, total=3, pct=100)
            self.after(0, self._render_clips)
            self.after(0, lambda: self._switch_nb('clips'))

        except Exception:
            err = traceback.format_exc()
            self.log(f'ERROR in AI:\n{err}', RED)
        finally:
            self.running = False
            self.after(0, lambda: self.set_busy(False))

    # ── Clip rendering ────────────────────────────────────────────────────────
    def _grab_frame(self, vid, time_str):
        """Extract a frame from a video at given timestamp. Returns PIL Image or None."""
        try:
            import cv2 as _cv
            from PIL import Image as _I
            import numpy as _np
            cap = _cv.VideoCapture(vid)
            fps = cap.get(_cv.CAP_PROP_FPS) or 25
            p = time_str.split(':')
            secs = int(p[0])*3600 + int(p[1])*60 + float(p[2])
            # Go 1s into the clip so we don't hit a black frame
            secs = max(0, secs + 1)
            cap.set(_cv.CAP_PROP_POS_FRAMES, int(secs * fps))
            ret, frame = cap.read()
            cap.release()
            if not ret: return None
            rgb = _cv.cvtColor(frame, _cv.COLOR_BGR2RGB)
            img = _I.fromarray(rgb)
            img.thumbnail((160, 90), _I.LANCZOS)
            return img
        except Exception:
            return None

    def _render_clips(self):
        from PIL import ImageTk
        for w in self.clip_frame.winfo_children():
            w.destroy()
        self.clip_vars  = []
        self._clip_tk_imgs = []
        vid = self.v_video.get()

        # 2-column grid — wider cards, more readable
        COLS = 2
        for c in range(COLS):
            self.clip_frame.columnconfigure(c, weight=1, uniform='clipcol')

        for i, clip in enumerate(self.clips):
            var = tk.BooleanVar(value=True)
            self.clip_vars.append(var)
            row_idx = i // COLS
            col_idx = i %  COLS
            accent  = [ACCENT, ACCENT2, '#5A8F3C'][col_idx]

            card = tk.Frame(self.clip_frame, bg=BG3,
                            highlightbackground=BG4, highlightthickness=1)
            card.grid(row=row_idx, column=col_idx, sticky='nsew',
                      padx=4, pady=4)
            tk.Frame(card, bg=accent, width=3).pack(side='left', fill='y')

            # Thumbnail preview — click to open video player
            if vid and Path(vid).exists():
                thumb_img = self._grab_frame(vid, clip.get('start','00:00:00'))
                if thumb_img:
                    tk_img = ImageTk.PhotoImage(thumb_img)
                    self._clip_tk_imgs.append(tk_img)
                    thumb_frame = tk.Frame(card, bg=BG2, cursor='hand2')
                    thumb_frame.pack(side='left', padx=(6,0), pady=6)
                    thumb_lbl = tk.Label(thumb_frame, image=tk_img, bg=BG2, cursor='hand2')
                    thumb_lbl.pack()
                    # Play button overlay text
                    tk.Label(thumb_frame, text='▶ Preview', font=('Segoe UI', 7,'bold'),
                             fg=ACCENT, bg=BG2, cursor='hand2').pack()
                    # Click opens player
                    for w_bind in (thumb_frame, thumb_lbl):
                        w_bind.bind('<Button-1>', lambda e, c=clip, v=vid: self._open_clip_preview(v, c))

            inner = tk.Frame(card, bg=BG2)
            inner.pack(side='left', fill='x', expand=True, padx=10, pady=8)

            # Row 1: checkbox + number + speaker + title + score
            r1 = tk.Frame(inner, bg=BG2); r1.pack(fill='x')
            tk.Checkbutton(r1, variable=var, bg=BG2, activebackground=BG2,
                           selectcolor=BG3, fg=FG, relief='flat', cursor='hand2',
                           font=FONT_SMALL).pack(side='left')
            tk.Label(r1, text=f'#{i+1}', font=('Segoe UI', 9,'bold'),
                     fg=ACCENT, bg=BG2, width=3).pack(side='left')
            speaker = clip.get('speaker','')
            if speaker:
                tk.Label(r1, text=f'🎤 {speaker}',
                         font=('Segoe UI', 9,'bold'), fg=ACCENT2, bg=BG2
                         ).pack(side='left', padx=(0,4))
            tk.Label(r1, text=clip.get('title','Untitled'),
                     font=('Segoe UI', 10,'bold'), fg=FG, bg=BG2,
                     anchor='w').pack(side='left', padx=4)
            score = clip.get('score','?')
            try:
                s = int(score)
                sc = GREEN if s>=8 else YELLOW if s>=6 else FG3
            except Exception: sc = FG3
            score_frame = tk.Frame(r1, bg=BG2)
            score_frame.pack(side='right')
            tk.Label(score_frame, text=f'★{score}/10', font=('Segoe UI', 9,'bold'),
                     fg=sc, bg=BG2).pack(side='left')
            # Virality sub-scores (out of 25 like clips.gg)
            hook = clip.get('hook')
            eng  = clip.get('engagement')
            val  = clip.get('value')
            shar = clip.get('shareability')
            if any([hook, eng, val, shar]):
                sub_row = tk.Frame(inner, bg=BG2); sub_row.pack(fill='x', pady=(0,2))
                for _ico, _val, _col in [
                    ('🎣', hook, ACCENT2),
                    ('🔥', eng, YELLOW),
                    ('💡', val, '#8B5CF6'),
                    ('📤', shar, GREEN)]:
                    if _val:
                        tk.Label(sub_row, text=f'{_ico}{_val}/25',
                                 font=('Segoe UI', 7,'bold'), fg=_col, bg=BG2
                                 ).pack(side='left', padx=(0,6))
            # AI summary line
            summary = clip.get('summary','')
            if summary:
                tk.Label(inner, text=f'💬 {summary}',
                         font=('Segoe UI', 8,'italic'), fg=ACCENT2, bg=BG2,
                         anchor='w', wraplength=340, justify='left').pack(fill='x', pady=(2,0))
            # Sub-scores if available
            hook = clip.get('hook')
            eng  = clip.get('engagement')
            shar = clip.get('shareability')
            if hook or eng or shar:
                sub = tk.Frame(score_frame, bg=BG2); sub.pack(side='left', padx=(4,0))
                for lbl, val, color in [('🎣',hook,ACCENT2),('🔥',eng,YELLOW),('📤',shar,GREEN)]:
                    if val:
                        tk.Label(sub, text=f'{lbl}{val}', font=('Segoe UI', 7),
                                 fg=color, bg=BG2).pack(side='left', padx=1)

            # Row 2: editable start/end timestamps + duration
            r2 = tk.Frame(inner, bg=BG2); r2.pack(fill='x', pady=(4,2))
            tk.Label(r2, text='Start:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
            sv = tk.StringVar(value=clip.get('start','00:00:00'))
            ev = tk.StringVar(value=clip.get('end','00:01:00'))
            # Store vars back on clip for export
            clip['_sv'] = sv; clip['_ev'] = ev
            def _update_dur(sv=sv, ev=ev, r2=r2):
                try:
                    def _s(t):
                        p=t.split(':'); return int(p[0])*3600+int(p[1])*60+float(p[2])
                    dur = _s(ev.get()) - _s(sv.get())
                    if dur < 0: dur = 0
                    mins, secs = divmod(int(dur), 60)
                    for w2 in r2.winfo_children():
                        if getattr(w2,'_is_dur_lbl',False):
                            w2.config(text=f'{mins}m{secs:02d}s')
                except Exception: pass
            start_e = tk.Entry(r2, textvariable=sv, font=FONT_MONO_S,
                               bg=BG3, fg=YELLOW, insertbackground=YELLOW,
                               relief='flat', bd=4, width=10)
            start_e.pack(side='left', padx=(2,6))
            sv.trace_add('write', lambda *_,f=_update_dur: f())
            tk.Label(r2, text='End:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
            end_e = tk.Entry(r2, textvariable=ev, font=FONT_MONO_S,
                             bg=BG3, fg=YELLOW, insertbackground=YELLOW,
                             relief='flat', bd=4, width=10)
            end_e.pack(side='left', padx=(2,8))
            ev.trace_add('write', lambda *_,f=_update_dur: f())
            dur_lbl = tk.Label(r2, text='', font=FONT_SMALL, fg=FG2, bg=BG2)
            dur_lbl._is_dur_lbl = True
            dur_lbl.pack(side='left')
            _update_dur()

            # Row 3: reason + rename field
            reason = clip.get('reason','')
            if reason:
                tk.Label(inner, text=reason, font=FONT_SMALL, fg=FG2, bg=BG2,
                         anchor='w', wraplength=350, justify='left').pack(fill='x')
            # Rename field
            rn_row = tk.Frame(inner, bg=BG2); rn_row.pack(fill='x', pady=(3,0))
            tk.Label(rn_row, text='Filename:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
            name_var = tk.StringVar(value=re.sub(r'[\\/:*?"<>|]','',clip.get('title','clip'))[:40])
            clip['_name_var'] = name_var
            tk.Entry(rn_row, textvariable=name_var, font=FONT_SMALL,
                     bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                     ).pack(side='left', fill='x', expand=True, padx=(4,0))


    def _get_vertical_vf(self, vid, _ignored=None):
        """Get ffmpeg -vf filter for 9:16 crop, face-tracked if possible."""
        try:
            try:
                import mediapipe as _mp
            except ImportError:
                self.log('[9:16] Installing mediapipe...', FG2)
                import subprocess as _submp, sys as _sysmp
                _submp.run([_sysmp.executable, '-m', 'pip', 'install',
                           'mediapipe', '--quiet', '--no-deps',
                           '--break-system-packages'], capture_output=True)
                _submp.run([_sysmp.executable, '-m', 'pip', 'install',
                           'mediapipe', '--quiet',
                           '--break-system-packages'], capture_output=True)
                import mediapipe as _mp
            import cv2 as _cv
            # Sample frames to find average face X position
            cap = _cv.VideoCapture(vid)
            if not cap.isOpened():
                raise Exception("Cannot open video")
            total = int(cap.get(_cv.CAP_PROP_FRAME_COUNT)) or 1
            fps   = cap.get(_cv.CAP_PROP_FPS) or 30
            w     = int(cap.get(_cv.CAP_PROP_FRAME_WIDTH))
            h     = int(cap.get(_cv.CAP_PROP_FRAME_HEIGHT))
            # mediapipe 0.10+ changed API — try both
            try:
                face_det = _mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.5)
            except AttributeError:
                raise ImportError("mediapipe solutions API not available in this version")
            # Sample every ~5 seconds
            sample_frames = range(0, total, max(1, int(fps * 5)))
            x_positions = []
            for fi in list(sample_frames)[:30]:
                cap.set(_cv.CAP_PROP_POS_FRAMES, fi)
                ret, frame = cap.read()
                if not ret: continue
                rgb = _cv.cvtColor(frame, _cv.COLOR_BGR2RGB)
                res = face_det.process(rgb)
                if res.detections:
                    # Use the first/largest face center X
                    bb = res.detections[0].location_data.relative_bounding_box
                    cx = (bb.xmin + bb.width / 2) * w
                    x_positions.append(int(cx))
            cap.release()
            face_det.close()
            if x_positions:
                avg_x = int(sum(x_positions) / len(x_positions))
                crop_w = int(h * 9 / 16)
                # Clamp so crop stays in frame
                x_off = max(0, min(avg_x - crop_w // 2, w - crop_w))
                self.log(f'[9:16] Face-tracked crop: center at x={avg_x}, offset={x_off}', FG2)
                return ['-vf', f'crop={crop_w}:{h}:{x_off}:0,scale=1080:1920']
        except ImportError:
            self.log('[9:16] mediapipe not ready — using center crop', FG2)
        except Exception as ex:
            self.log(f'[9:16] Face track failed ({ex}) — center crop', FG2)
        # Fallback: center crop
        return ['-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']

    def _set_crop_mode(self, mode):
        self.v_crop_mode.set(mode)
        colors = {'normal': (ACCENT, '#000'), 'vertical': (ACCENT2, '#000'), 'both': (GREEN, '#000')}
        for _v, _b in self._fmt_btns.items():
            active = (_v == mode)
            _b.config(bg=colors[_v][0] if active else BG3,
                     fg=colors[_v][1] if active else FG2)

    def _select_all(self):
        for v in getattr(self, 'clip_vars', []):
            v.set(True)

    # ── Export ────────────────────────────────────────────────────────────────

    def _censor_selected_clips(self):
        """Export selected clips as censored versions."""
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Check at least one clip.')
            return
        style = self.clip_censor_style.get()
        mp3 = getattr(self, '_clip_mp3_var', tk.StringVar()).get() or self.cfg.get('censor_mp3','')
        out = self.v_outdir.get()
        vid = self.v_video.get()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No video', 'Select a video file first.')
            return
        self.set_busy(True)
        self.set_progress(f'Censoring {len(sel)} clips...', step=1, total=2)
        def _run():
            try:
                ff = ensure_ffmpeg()
                import tempfile as _tmp
                for i, clip in enumerate(sel):
                    self.set_progress(f'Censoring clip {i+1}/{len(sel)}...', step=1, total=2, pct=int(i/len(sel)*100))
                    start_t = clip['_sv'].get() if '_sv' in clip else clip.get('start','00:00:00')
                    end_t   = clip['_ev'].get() if '_ev' in clip else clip.get('end','00:01:00')
                    _ct = clip.get('title','clip')
                    title = re.sub(r'[\\/:*?"<>|\']', '', _ct).strip()[:45] or 'Clip'
                    # First export the clip
                    tmp_clip = str(Path(_tmp.gettempdir()) / f'cf_censor_clip_{i}.mp4')
                    _vcodec, _acodec, _extra = get_encoder(ff)
                    subprocess.run([ff,'-y','-ss',start_t,'-to',end_t,'-i',vid,
                                   '-c:v',_vcodec,'-c:a',_acodec]+_extra+[tmp_clip],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # Then censor it
                    _wm = self.v_whisper.get(); _wm = 'base' if _wm == 'auto' else _wm
                    result = _do_transcribe(tmp_clip, _wm,
                                           initial_prompt=self.v_context.get('1.0','end').strip() or None,
                                           ffmpeg_path=ff, use_word_timestamps=True)
                    segs = result.get('segments',[])
                    # Use censor tab words, fall back to CENSOR_WORD_LIST if empty
                    _cw = self._censor_words if self._censor_words else list(self.CENSOR_WORD_LIST)
                    words = [w.lower().strip() for w in _cw if w.strip()]
                    def _clip_word_match(w):
                        """Simple word match for clip censor."""
                        if len(w) < 2: return False
                        for b in words:
                            b = ''.join(c for c in b if c.isalpha())
                            if not b or len(b) < 3: continue
                            if w == b or w.startswith(b): return True
                            if len(b) <= 5 and b in w: return True
                        return False
                    hits = []
                    for seg in segs:
                        seg_words = seg.get('words', [])
                        if seg_words:
                            for wd in seg_words:
                                wt = ''.join(c for c in wd.get('word','').lower() if c.isalpha())
                                if _clip_word_match(wt):
                                    hits.append((max(0, wd['start']-0.05), wd['end']+0.1, wt))
                        else:
                            seg_text = seg.get('text','').lower()
                            seg_tokens = [''.join(c for c in t if c.isalpha()) for t in seg_text.split()]
                            seg_dur = seg['end'] - seg['start']
                            for ti, tok in enumerate(seg_tokens):
                                if _clip_word_match(tok):
                                    frac = ti / max(len(seg_tokens), 1)
                                    word_t = seg['start'] + frac * seg_dur
                                    hits.append((max(0, word_t-0.1), word_t+0.5, tok))
                    if hits:
                        _sf = _fresh_import('soundfile')
                        wav_in = str(Path(_tmp.gettempdir()) / f'cf_cen_wav_{i}.wav')
                        wav_out = str(Path(_tmp.gettempdir()) / f'cf_cen_out_{i}.wav')
                        subprocess.run([ff,'-y','-i',tmp_clip,'-vn','-ar','44100','-ac','2','-f','wav',wav_in],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        import numpy as _np
                        audio, sr = _sf.read(wav_in, dtype='float32')
                        beep = self._censor_make_beep(sr) if style=='beep' else None
                        if style=='mp3' and mp3 and Path(mp3).exists():
                            beep, bsr = _sf.read(mp3, dtype='float32')
                        for s_t, e_t, _ in hits:
                            s,e = int(s_t*sr), min(int(e_t*sr), len(audio))
                            if style=='silence': audio[s:e] = 0
                            elif beep is not None:
                                b = beep
                                if len(b) < e-s: b = _np.tile(b, ((e-s)//len(b)+1,1) if b.ndim==2 else (e-s)//len(b)+1)
                                audio[s:e] = b[:e-s]
                        _sf.write(wav_out, audio, sr)
                        _crop = getattr(self,'v_crop_mode',None)
                        _crop = _crop.get() if _crop else 'normal'
                        def _mux(inv, wav, outp, vertical=False):
                            if vertical:
                                _vf = self._get_vertical_vf(inv) or ['-vf','crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                                subprocess.run([ff,'-y','-i',inv,'-i',wav,'-map','0:v:0','-map','1:a:0']+_vf+
                                    ['-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-shortest',outp],
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            else:
                                subprocess.run([ff,'-y','-i',inv,'-i',wav,'-map','0:v:0','-map','1:a:0',
                                    '-c:v','copy','-c:a','aac','-b:a','192k','-shortest',outp],
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                        if _crop in ('normal','both'):
                            _mux(tmp_clip,wav_out,str(Path(out)/f'{title}_censored.mp4'))
                            self.log(f'[Censor] ✅ {title}_censored.mp4 ({len(hits)} words)',GREEN)
                        if _crop in ('vertical','both'):
                            _mux(tmp_clip,wav_out,str(Path(out)/f'{title}_censored_9x16.mp4'),vertical=True)
                            self.log(f'[Censor] ✅ {title}_censored_9x16.mp4',GREEN)
                    else:
                        _crop = getattr(self,'v_crop_mode',None)
                        _crop = _crop.get() if _crop else 'normal'
                        if _crop in ('normal','both'):
                            import shutil as _sh; _sh.copy2(tmp_clip,str(Path(out)/f'{title}.mp4'))
                            self.log(f'[Censor] Clean 16:9: {title}.mp4',GREEN)
                        if _crop in ('vertical','both'):
                            _vf = self._get_vertical_vf(tmp_clip) or ['-vf','crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                            subprocess.run([ff,'-y','-i',tmp_clip]+_vf+['-c:v','libx264','-preset','fast',
                                '-crf','18','-c:a','aac',str(Path(out)/f'{title}_9x16.mp4')],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            self.log(f'[Censor] Clean 9:16: {title}_9x16.mp4',GREEN)
                    try: Path(tmp_clip).unlink()
                    except: pass
                self.set_progress('Censor export done!', step=2, total=2, pct=100)
                self.after(0, lambda: messagebox.showinfo('Done', f'Censored {len(sel)} clips → {out}'))
            except Exception:
                self.log(f'Censor clips error:\n{__import__("traceback").format_exc()}', RED)
            finally:
                self.set_busy(False)
        threading.Thread(target=_run, daemon=True).start()


    def _toggle_clip_censor(self):
        """Toggle censor mode on/off for export."""
        self.censor_toggle.set(not self.censor_toggle.get())
        if self.censor_toggle.get():
            self.censor_toggle_btn.config(text='🔇 Censor ON', bg=ACCENT, fg='#000')
            self._censor_style_frame.pack(side='left')
        else:
            self.censor_toggle_btn.config(text='🔇 Censor OFF', bg=BG3, fg=FG2)
            self._censor_style_frame.pack_forget()
            try: self._censor_mp3_row.pack_forget()
            except: pass
        self._refresh_clip_censor_style()

    def _refresh_clip_censor_style(self):
        """Show/hide MP3 browse row based on selected censor style."""
        try:
            self._censor_mp3_row.pack_forget()
            if self.censor_toggle.get() and self.clip_censor_style.get() == 'mp3':
                # Use the permanent anchor frame (always packed, zero-height)
                self._censor_mp3_row.pack(fill='x', pady=(2,2),
                                          before=self._mp3_row_anchor)
        except Exception as _e:
            import traceback; print('[CF] mp3 row error:', traceback.format_exc())



    def _auto_edit_selected(self):
        """Auto Edit selected clips — removes silence, tightens pacing CapCut-style."""
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Select at least one clip first.')
            return
        ff = ensure_ffmpeg()
        if not ff:
            messagebox.showerror('ffmpeg missing', 'Install ffmpeg in Settings → Core Dependencies.')
            return
        out = self.v_outdir.get().strip()
        if not out:
            messagebox.showerror('No output folder', 'Set an output folder first.')
            return
        vid = self.v_video.get()
        self.set_busy(True)
        self.log(f'⚡ Auto Edit: processing {len(sel)} clip(s)...', ACCENT2)

        def _run():
            try:
                import subprocess as _sp, re as _re, tempfile as _tmp
                for i, clip in enumerate(sel):
                    self.set_progress(f'Auto Edit: clip {i+1}/{len(sel)}...', pct=int(i/len(sel)*100))
                    start_t = clip.get('_sv') and clip['_sv'].get() or clip.get('start','00:00:00')
                    end_t   = clip.get('_ev') and clip['_ev'].get() or clip.get('end','00:01:00')
                    _at = clip.get('title','clip')
                    title = re.sub(r'[\\/:*?"<>|]', '', _at).strip()[:45] or 'Clip'

                    # Step 1: Extract raw clip
                    raw = str(Path(_tmp.gettempdir()) / f'ae_raw_{i}.mp4')
                    _vcodec, _acodec, _extra = get_encoder(ff)
                    _sp.run([ff,'-y','-ss',start_t,'-to',end_t,'-i',vid,
                             '-c:v',_vcodec,'-c:a',_acodec]+_extra+[raw],
                            stdout=_sp.PIPE, stderr=_sp.PIPE)

                    # Step 2: Detect silence
                    _sil = _sp.run([ff,'-i',raw,'-af','silencedetect=noise=-35dB:d=0.3',
                                    '-f','null','-'], capture_output=True, text=True)
                    sil_starts = [float(m) for m in _re.findall(r'silence_start: ([\d.]+)', _sil.stderr)]
                    sil_ends   = [float(m) for m in _re.findall(r'silence_end: ([\d.]+)', _sil.stderr)]

                    if not sil_starts:
                        # No silence — just copy
                        import shutil as _sh
                        _sh.copy2(raw, str(Path(out) / f'{title} - ClipFinder - Part {i+1}.mp4'))
                        self.log(f'  Clip {i+1}: no silence detected, exported as-is', FG2)
                        continue

                    # Step 3: Build keep segments (non-silent parts)
                    keeps = []
                    prev = 0.0
                    for ss, se in zip(sil_starts, sil_ends):
                        if ss > prev + 0.1:
                            keeps.append((prev, ss))
                        prev = se
                    # Get duration
                    _dur = _sp.run([ff,'-i',raw], capture_output=True, text=True)
                    _dm = _re.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur.stderr)
                    if _dm:
                        h,m,s = _dm.groups()
                        total = int(h)*3600+int(m)*60+float(s)
                        if total > prev + 0.1:
                            keeps.append((prev, total))

                    if not keeps:
                        self.log(f'  Clip {i+1}: all silence, skipping', YELLOW)
                        continue

                    # Step 4: Concat non-silent segments
                    concat_list = str(Path(_tmp.gettempdir()) / f'ae_list_{i}.txt')
                    seg_files = []
                    with open(concat_list, 'w') as cf:
                        for j, (ks, ke) in enumerate(keeps):
                            seg = str(Path(_tmp.gettempdir()) / f'ae_seg_{i}_{j}.mp4')
                            _sp.run([ff,'-y','-ss',str(ks),'-to',str(ke),'-i',raw,
                                     '-c','copy',seg],
                                    stdout=_sp.PIPE, stderr=_sp.PIPE)
                            cf.write(f"file '{seg}'\n")
                            seg_files.append(seg)

                    out_path = str(Path(out) / f'{title} - ClipFinder - Part {i+1}.mp4')
                    _sp.run([ff,'-y','-f','concat','-safe','0','-i',concat_list,
                             '-c','copy', out_path],
                            stdout=_sp.PIPE, stderr=_sp.PIPE)

                    removed = sum(e-s for s,e in zip(sil_starts, sil_ends))
                    self.log(f'  ✅ Clip {i+1}: removed {removed:.1f}s silence → {out_path.split(chr(92))[-1]}', GREEN)

                    # Cleanup
                    for f2 in seg_files:
                        try: Path(f2).unlink()
                        except: pass
                    try: Path(raw).unlink()
                    except: pass

                self.set_progress(f'⚡ Auto Edit done! {len(sel)} clips processed', pct=100)
                self.after(0, lambda: messagebox.showinfo('Auto Edit Done',
                    f'Processed {len(sel)} clip(s)\nSaved to: {out}'))
            except Exception:
                import traceback as _tb
                self.log(f'Auto Edit error:\n{_tb.format_exc()}', RED)
            finally:
                self.set_busy(False)

        threading.Thread(target=_run, daemon=True).start()

    def _export_or_censor(self):
        """Export selected clips — with censoring if censor toggle is on."""
        if getattr(self, 'censor_toggle', None) and self.censor_toggle.get():
            self._censor_selected_clips()
        else:
            self._export_selected()

    def _export_selected(self):
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Check at least one clip.')
            return
        self.set_busy(True)
        threading.Thread(target=self._do_export, args=(sel,), daemon=True).start()

    def _autocut(self):
        if not self.clips:
            messagebox.showwarning('No clips', 'Run FIND CLIPS first.')
            return
        # Sort by score desc and take top 3 — not just first 3 chronologically
        def _score(c):
            try: return -int(c.get('score', 5))
            except: return -5
        best3 = sorted(self.clips, key=_score)[:3]
        self.set_busy(True)
        threading.Thread(target=self._do_export, args=(best3,), daemon=True).start()



    def _run_export_queue(self):
        if not hasattr(self, '_export_queue') or not self._export_queue:
            messagebox.showwarning('Empty Queue', 'Add clips to queue first.')
            return
        self.set_busy(True)
        jobs = list(self._export_queue)
        self._export_queue.clear()
        try: self.queue_lb.delete(0, 'end')
        except: pass
        threading.Thread(target=self._process_queue, args=(jobs,), daemon=True).start()

    def _add_to_queue(self):
        """Add currently selected clips to the export queue."""
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Select clips first.')
            return
        vid = self.v_video.get()
        out = self.v_outdir.get()
        if not vid or not out:
            messagebox.showwarning('Missing', 'Set video file and output folder first.')
            return
        # Deep copy clips with current editable values
        import copy
        clips_copy = []
        for clip in sel:
            c = dict(clip)
            c['start'] = clip['_sv'].get() if '_sv' in clip else clip.get('start','')
            c['end']   = clip['_ev'].get() if '_ev' in clip else clip.get('end','')
            c['_fname']= clip['_name_var'].get() if '_name_var' in clip else clip.get('title','clip')
            clips_copy.append(c)
        self._export_queue.append((vid, out, clips_copy))
        label = f'{Path(vid).name}  ({len(clips_copy)} clip{"s" if len(clips_copy)!=1 else ""})'
        if hasattr(self,'queue_listbox'): self.queue_listbox.insert('end', label)
        if hasattr(self,'queue_count_lbl'): self.queue_count_lbl.config(text=f'{len(self._export_queue)} video(s) queued')
        self.log(f'Added to queue: {label}', GREEN)

    def _clear_queue(self):
        self._export_queue.clear()
        if hasattr(self,'queue_listbox'): self.queue_listbox.delete(0, 'end')
        if hasattr(self,'queue_count_lbl'): self.queue_count_lbl.config(text='')
        self.log('Queue cleared.')

    def _run_queue(self):
        if not self._export_queue:
            messagebox.showwarning('Empty', 'Queue is empty. Add clips first.')
            return
        self.set_busy(True)
        threading.Thread(target=self._process_queue, daemon=True).start()

    def _process_queue(self, jobs=None):
        queue = jobs or self._export_queue or []
        total_ok = 0; total_clips = 0
        ff = find_ffmpeg()
        if not ff:
            self.log('Queue error: ffmpeg not found', RED)
            self.after(0, lambda: self.set_busy(False))
            return
        for qi, job in enumerate(queue):
            # job is a tuple (vid, out, clips) stored by _add_to_queue
            if isinstance(job, (tuple, list)) and len(job) == 3 and isinstance(job[2], list):
                vid, out, clips = job
            else:
                vid   = self.v_video.get()
                out   = self.v_outdir.get()
                clips = job if isinstance(job, list) else []
            if not vid or not Path(vid).exists():
                self.log(f'[Queue {qi+1}] Video not found: {vid}', RED)
                continue
            if not out:
                self.log(f'[Queue {qi+1}] No output folder set', RED)
                continue
            self.log(f'[Queue {qi+1}/{len(queue)}] {len(clips)} clips from: {Path(vid).name}')
            if getattr(self, '_cancel_requested', False): return
            self.set_progress(f'Queue {qi+1}/{len(queue)}: {Path(vid).name}', pct=int(qi/len(queue)*100))
            Path(out).mkdir(parents=True, exist_ok=True)
            for i, clip in enumerate(clips):
                start  = clip.get('start','00:00:00')
                end    = clip.get('end','00:01:00')
                _raw_title = clip.get('_fname', clip.get('title', 'clip'))
                fname_base = re.sub(r'[\\/:*?"<>|]', '', _raw_title).strip()[:45] or 'Clip'
                fname  = f'{fname_base} - ClipFinder - Part {i+1}.mp4'
                dest   = str(Path(out)/fname)
                self.log(f'  Cutting [{start} → {end}]: {fname}')
                if getattr(self, '_cancel_requested', False): return
                self.set_progress(f'Queue: cutting {fname[:40]}...', pct=int((qi*len(clips)+i+1)/(len(queue)*len(clips))*100))
                _vcodec, _acodec, _extra = get_encoder(ff)
                r = subprocess.run([ff,'-y','-ss',start,'-to',end,'-i',vid,
                                   '-c:v',_vcodec,'-c:a',_acodec]+_extra+[dest],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if r.returncode == 0:
                    total_ok += 1
                    self.log(f'  ✅ {fname}', GREEN)
                else:
                    self.log(f'  ❌ Export failed for {fname}', RED)
                total_clips += 1
        self.log(f'Queue done: {total_ok}/{total_clips} clips exported.', GREEN)
        self.set_progress(f'✅ Queue done: {total_ok}/{total_clips} clips exported', pct=100)
        self.after(0, lambda: self.set_busy(False))
        self.after(0, self._clear_queue)
        self.after(0, lambda: messagebox.showinfo('Queue Done',
            f'Exported {total_ok}/{total_clips} clips from {len(queue)} video(s).'))


    def _open_clip_preview(self, vid, clip):
        """Open clip in system default player — fast, no crash."""
        import subprocess as _sp_prev, tempfile as _tmp_prev
        ff = ensure_ffmpeg()
        start = clip.get('start', '00:00:00')
        end   = clip.get('end',   '00:01:00')
        title = re.sub(r'[\\/:*?"<>|]', '', clip.get('title', 'preview'))[:40]

        # Cut the clip to a temp file and open with system player
        tmp = Path(_tmp_prev.gettempdir()) / f'cf_preview_{title[:20]}.mp4'
        self.log(f'Cutting preview: {start} → {end}', FG2)
        self.set_progress('Cutting preview...', pct=50)

        def _cut_and_open():
            try:
                r = subprocess.run(
                    [ff, '-y', '-ss', start, '-to', end, '-i', vid,
                     '-c', 'copy', str(tmp)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if r.returncode == 0 and tmp.exists():
                    import os as _os
                    _os.startfile(str(tmp))  # Windows default player
                    self.after(0, lambda: self.set_progress('▶ Preview opened', pct=100))
                else:
                    self.after(0, lambda: self.log('Preview cut failed', RED))
            except Exception as ex:
                self.after(0, lambda e=ex: self.log(f'Preview error: {e}', RED))

        import threading
        threading.Thread(target=_cut_and_open, daemon=True).start()


    def _snap_to_segment(self, timestamp_str, snap='end'):
        """Snap timestamp to a clean sentence boundary.
        Uses multiple signals: punctuation, pause gaps, segment length.
        END: finds next clean sentence end within 10s of target.
        START: finds cleanest entry point at or near target."""
        if not self._whisper_segments:
            return timestamp_str
        try:
            parts = timestamp_str.split(':')
            t = int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
        except Exception:
            return timestamp_str

        segs = self._whisper_segments
        if not segs:
            return timestamp_str

        import re as _snap_re

        def _sentence_score(txt):
            """Score 0-3: how likely this segment text ends a complete thought."""
            t2 = txt.strip()
            if not t2: return 0
            # Hard sentence endings
            if _snap_re.search(r'[.!?]["\']?$', t2): return 3
            # Trailing off / ellipsis
            if t2.endswith('...'): return 2
            # Long segment = probably a complete thought
            if len(t2) > 80: return 2
            # Ends mid-word or with filler = bad cut point
            if _snap_re.search(r'\b(um|uh|like|and|but|so|because|that|if|the|a|an|in|on|at|to)$', t2, _snap_re.I):
                return 0
            return 1

        if snap == 'end':
            # Find first segment whose end >= target time
            target_idx = len(segs) - 1
            for i, seg in enumerate(segs):
                if seg['end'] >= t:
                    target_idx = i
                    break

            # Score current segment
            cur_score = _sentence_score(segs[target_idx]['text'])
            if cur_score >= 3:
                return ts(min(segs[target_idx]['end'] + 0.3, segs[-1]['end']))

            # Look ahead up to 10s or 6 segments for cleaner end
            LENIENCY = 10.0
            best_end   = segs[target_idx]['end']
            best_score = cur_score

            for j in range(target_idx + 1, min(target_idx + 7, len(segs))):
                seg = segs[j]
                if seg['end'] > t + LENIENCY:
                    break
                s = _sentence_score(seg['text'])
                # Bonus if there's a natural pause after this segment
                if j + 1 < len(segs):
                    gap = segs[j+1]['start'] - seg['end']
                    if gap > 0.5:
                        s = max(s, 2)
                if s > best_score:
                    best_score = s
                    best_end   = seg['end']
                if s >= 3:
                    break

            return ts(min(best_end + 0.3, segs[-1]['end']))

        else:  # snap == 'start'
            # Find closest segment start to target
            best_idx  = 0
            best_dist = float('inf')
            for i, seg in enumerate(segs):
                d = abs(seg['start'] - t)
                if d < best_dist:
                    best_dist = d
                    best_idx  = i

            # Prefer a segment that starts after a gap or sentence end
            for i in range(best_idx, max(0, best_idx - 5), -1):
                if segs[i]['start'] > t + 2.0:
                    continue
                if i > 0:
                    gap        = segs[i]['start'] - segs[i-1]['end']
                    prev_score = _sentence_score(segs[i-1]['text'])
                    if gap > 0.3 and prev_score >= 2:
                        return ts(segs[i]['start'])

            return ts(max(0.0, segs[best_idx]['start'] - 0.1))

    def _do_export(self, clips):
        vid = self.v_video.get()
        out = self.v_outdir.get()
        base = Path(vid).stem
        ff = find_ffmpeg()
        ok = 0
        def _to_sec(t):
            try:
                p = t.split(':')
                return int(p[0])*3600 + int(p[1])*60 + float(p[2])
            except Exception: return 0

        for i, clip in enumerate(clips):
            # Use editable timestamps if user trimmed them
            raw_start = clip['_sv'].get() if '_sv' in clip else clip.get('start','00:00:00')
            raw_end   = clip['_ev'].get() if '_ev' in clip else clip.get('end','00:01:00')
            if self._whisper_segments:
                start = self._snap_to_segment(raw_start, snap='start')
                end   = self._snap_to_segment(raw_end,   snap='end')
            else:
                start, end = raw_start, raw_end

            # Enforce minimum 60s (1 min) matching AI prompt rules
            dur = _to_sec(end) - _to_sec(start)
            if dur < 60:
                end = ts(_to_sec(start) + 60)
                end = self._snap_to_segment(end, snap='end')
                self.log(f'Clip extended from {dur:.0f}s to 60s minimum')

            # Use custom filename if provided, else AI title
            if '_name_var' in clip and clip['_name_var'].get().strip():
                title = re.sub(r'[\\/:*?"<>|]', '', clip['_name_var'].get().strip())[:50]
            else:
                title = re.sub(r'[\\/:*?"<>|]', '', clip.get('title','clip'))[:40]

            fname = f'{title} - ClipFinder - Part {i+1}.mp4'
            dest  = str(Path(out) / fname)
            self.log(f'Cutting [{start} → {end}]: {fname}')
            if getattr(self, '_cancel_requested', False): return
            self.set_progress(f'✂ Exporting {i+1}/{len(clips)}: {title[:40]}...', pct=int(i/len(clips)*100))
            _vcodec, _acodec, _extra = get_encoder(ff)
            # Add hwaccel input decoding for GPU encoders
            _hw_args = []
            if _vcodec == 'h264_amf':
                _hw_args = ['-hwaccel', 'auto']
            elif _vcodec == 'h264_nvenc':
                _hw_args = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
            elif _vcodec == 'h264_qsv':
                _hw_args = ['-hwaccel', 'qsv']
            _crop_mode = getattr(self, 'v_crop_mode', None)
            _crop_mode = _crop_mode.get() if _crop_mode else 'normal'
            _base_cmd = [ff, '-y'] + _hw_args + ['-ss', start, '-to', end, '-i', vid]

            def _run_fmt(out_path, vertical=False, _st=start, _en=end):
                # Build fresh command — vertical skips hwaccel (causes issues with vf filters)
                if vertical:
                    _cmd_base = [ff, '-y', '-ss', _st, '-to', _en, '-i', vid]
                    _vff = self._get_vertical_vf(vid)
                    if not _vff:
                        _vff = ['-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                    _cmd = _cmd_base + ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18'] + _vff + ['-c:a', 'aac', '-b:a', '192k', out_path]
                else:
                    _cmd = _base_cmd + ['-c:v', _vcodec] + ['-c:a', _acodec] + _extra + [out_path]
                _r = subprocess.run(_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if _r.returncode != 0:
                    _err = _r.stderr.decode(errors='replace')[-300:] if _r.stderr else ''
                    self.log(f'[Export] {"9:16" if vertical else "16:9"} failed: {_err[-120:]}', RED)
                    if vertical:
                        # Retry with simple center crop
                        _cmd_base2 = [ff, '-y', '-ss', _st, '-to', _en, '-i', vid]
                        _fallback = _cmd_base2 + ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                                                   '-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920',
                                                   '-c:a', 'aac', '-b:a', '192k', out_path]
                        _r = subprocess.run(_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return _r.returncode == 0

            dest_v = str(Path(out) / f'{title} - ClipFinder - Part {i+1} 9x16.mp4')
            if _crop_mode == 'normal':
                if _run_fmt(dest): ok += 1; self.log(f'Saved: {fname}', GREEN)
                else: self.log(f'Failed: {fname}', RED)
            elif _crop_mode == 'vertical':
                if _run_fmt(dest_v, vertical=True): ok += 1; self.log(f'Saved (9:16): {Path(dest_v).name}', GREEN)
                else: self.log(f'Failed (9:16): {fname}', RED)
            elif _crop_mode == 'both':
                ok_n = _run_fmt(dest)
                ok_v = _run_fmt(dest_v, vertical=True)
                if ok_n or ok_v: ok += 1
                if ok_n: self.log(f'Saved 16:9: {fname}', GREEN)
                if ok_v: self.log(f'Saved 9:16: {Path(dest_v).name}', GREEN)
                if not ok_n and not ok_v: self.log(f'Both failed: {fname}', RED)

        self.log(f'Done: {ok}/{len(clips)} clips saved to {out}', GREEN)
        self.set_progress(f'✅ Done: {ok}/{len(clips)} clips exported', pct=100)
        self.after(0, lambda: self.set_busy(False))
        self.after(0, lambda: messagebox.showinfo('Done', f'{ok}/{len(clips)} clips saved to:\n{out}'))

    # ── Transcript actions ────────────────────────────────────────────────────

    def _set_tweet_tone(self, tone):
        self.tweet_tone.set(tone)
        self._refresh_tweet_tones()

    def _refresh_tweet_tones(self):
        tone_styles = {
            'drama':    ('🔥 Drama',   ACCENT),
            'tea':      ('☕ Tea',     '#8B5CF6'),
            'breaking': ('📰 Breaking','#3B82F6'),
            'hype':     ('💥 Hype',    '#EF4444'),
        }
        cur = self.tweet_tone.get()
        for t, b in self._tweet_tone_btns.items():
            active = (t == cur)
            color = tone_styles[t][1]
            b.config(bg=color if active else BG3,
                     fg='#fff' if active else FG3)

    def _generate_tweet(self):
        if not self.transcript.strip():
            messagebox.showwarning('No transcript', 'Transcribe a video first.')
            return
        # Save context
        ctx = self.tweet_context.get('1.0', 'end').strip()
        self.cfg['tweet_context'] = ctx
        save_cfg(self.cfg)

        self.tweet_gen_btn.config(state='disabled', text='⏳  Generating...')
        groq_key = self._keys.get('Groq (Free)','')
        prov_hint = 'Groq' if groq_key else 'AI'
        self.tweet_gen_lbl.config(text=f'Calling {prov_hint}...')
        threading.Thread(target=self._run_tweet_gen, daemon=True).start()

    def _run_tweet_gen(self):
        try:
            # Tweet gen: prefer Groq (fastest, best at short punchy text)
            # Reload keys from config in case settings tab hasn't been opened
            for _pk, _cfg_k in [('Groq (Free)', 'key_groq'),
                                  ('Google Gemini (Free)', 'key_gemini'),
                                  ('OpenRouter (Free models)', 'key_openrouter')]:
                if not self._keys.get(_pk, '').strip():
                    _v = self.cfg.get(_cfg_k, '').strip()
                    if _v: self._keys[_pk] = _v
            keyed = [p for p in PROVIDERS if self._keys.get(p, '').strip()]
            if not keyed:
                raise ValueError('No API key saved. Go to ⚙ Settings and enter a key.')
            groq_prov = 'Groq (Free)'
            if groq_prov in keyed:
                prov = groq_prov  # always prefer Groq for tweets
            elif self.v_provider.get() in keyed:
                prov = self.v_provider.get()
            else:
                prov = keyed[0]
            data  = PROVIDERS[prov]
            lib   = data['lib']
            key   = self._keys.get(prov, '').strip()
            model = self.v_model.get() if self.v_provider.get() == prov else data['models'][0]

            ctx   = self.tweet_context.get('1.0', 'end').strip() if hasattr(self, 'tweet_context') else ''
            tone  = self.tweet_tone.get()

            tone_notes = {
                'drama':    'Sharp and dry like a real Twitter drama account. Punchy sentences, deadpan observations.',
                'tea':      'Gossip columnist energy. Knowing tone. "Allegedly." "Sources say." Reading between lines.',
                'breaking': 'Straight-faced news anchor covering streaming drama like geopolitics. Completely serious.',
                'hype':     'Maximum chaos energy. Hyperbole cranked to 11. Treat everything like a world event.',
            }

            # Use first 6000 chars of transcript for tweet gen
            prompt = TWEET_PROMPT.replace('{context}', ctx or 'No additional context provided.')
            prompt = prompt.replace('{transcript}', self.transcript[:6000])
            prompt += f'\n\nTone style: {tone_notes.get(tone, "")}'

            # Try all models in the selected provider, then fall back to others
            raw = None
            # Try order: selected prov first, then Groq, then rest
            _rest = [p for p in keyed if p != prov]
            _groq = [p for p in _rest if 'Groq' in p]
            _others = [p for p in _rest if 'Groq' not in p]
            providers_to_try = [prov] + _groq + _others

            for try_prov in providers_to_try:
                try_data  = PROVIDERS[try_prov]
                try_lib   = try_data['lib']
                try_key   = self._keys.get(try_prov, '').strip()
                try_models = ([model] + [m for m in try_data['models'] if m != model]
                              if try_prov == prov else try_data['models'])

                for try_model in try_models:
                    try:
                        if try_lib == 'gemini':
                            from google import genai as _g
                            client = _g.Client(api_key=try_key)
                            resp = client.models.generate_content(
                                model=try_model, contents=prompt,
                                config={'temperature': 0.85, 'max_output_tokens': 2000})
                            raw = resp.text.strip()

                        elif try_lib == 'groq':
                            from groq import Groq as _G
                            resp = _G(api_key=try_key).chat.completions.create(
                                model=try_model,
                                messages=[{'role': 'user', 'content': prompt}],
                                temperature=0.85, max_tokens=2000)
                            raw = resp.choices[0].message.content.strip()

                        elif try_lib == 'openrouter':
                            from openai import OpenAI as _O
                            resp = _O(base_url='https://openrouter.ai/api/v1', api_key=try_key
                                      ).chat.completions.create(
                                model=try_model,
                                messages=[{'role': 'user', 'content': prompt}],
                                temperature=0.85, max_tokens=2000)
                            raw = resp.choices[0].message.content.strip()

                        prov = try_prov  # update for display in status
                        model = try_model
                        break  # success

                    except Exception as _e:
                        err_str = str(_e)
                        if any(x in err_str for x in ['404', '429', 'RESOURCE_EXHAUSTED',
                                                        'quota', 'decommission', 'No endpoints']):
                            continue  # try next model
                        raise  # unexpected error, surface it

                if raw is not None:
                    break  # got a result, stop trying providers

            if raw is None:
                raise ValueError('All providers and models failed. Check your API keys.')

            # Parse 3 options from the raw response
            import re as _re_tw
            _parts = _re_tw.split(r'OPTION\s*[123]\s*\n', raw)
            _parts = [p.strip() for p in _parts if p.strip()]
            # Pad to 3 in case AI didn't produce all 3
            while len(_parts) < 3:
                _parts.append('')
            _opt1, _opt2, _opt3 = _parts[0], _parts[1], _parts[2]

            def _update():
                self.tweet_tabs_data = [_opt1, _opt2, _opt3]
                # Show option 1 by default, reset tab selection
                for j, tb in enumerate(self._tweet_tab_btns):
                    tb.config(bg=ACCENT if j == 0 else BG3,
                              fg='#000' if j == 0 else FG2)
                self._tweet_tab_idx = 0
                self.tweet_out.config(state='normal')
                self.tweet_out.delete('1.0', 'end')
                self.tweet_out.insert('1.0', _opt1 or raw)
                chars = len(self.tweet_out.get('1.0','end').strip())
                self.tweet_char_lbl.config(
                    text=f'{chars} chars',
                    fg=GREEN if chars <= 280 else YELLOW if chars <= 500 else ACCENT)
                self.tweet_gen_btn.config(state='normal', text='⚡  GENERATE TWEET')
                self.tweet_gen_lbl.config(text=f'Done via {prov} — 3 options generated')
            self.after(0, _update)

        except Exception:
            err = traceback.format_exc()
            def _err():
                self.tweet_gen_btn.config(state='normal', text='⚡  GENERATE TWEET')
                self.tweet_gen_lbl.config(text='Error — check log', fg=RED)
                self.log(f'Tweet gen error:\n{err}', RED)
            self.after(0, _err)

    def _copy_tweet(self):
        t = self.tweet_out.get('1.0', 'end').strip()
        if t:
            self.clipboard_clear()
            self.clipboard_append(t)
            self.tweet_gen_lbl.config(text='Copied to clipboard!', fg=GREEN)

    # ── Subtitle burn-in ──────────────────────────────────────────────────────
    def _get_sub_settings(self):
        """Return current subtitle style settings as a dict."""
        return {
            'font':       self.v_sub_font.get(),
            'size':       self.v_sub_size.get(),
            'bold':       self.v_sub_bold.get(),
            'italic':     self.v_sub_italic.get(),
            'caps':       self.v_sub_caps.get(),
            'color':      self.v_sub_color.get(),
            'outline':    self.v_sub_outline.get(),
            'stroke':     self.v_sub_stroke.get(),
            'bg_on':      self.v_sub_bg_on.get(),
            'bg_color':   self.v_sub_bg_col.get(),
            'bg_opacity': self.v_sub_bg_opacity.get(),
            'position':   self.v_sub_position.get(),
            'words':      self.v_sub_words.get(),
            'karaoke':    getattr(self, 'v_sub_karaoke', None) and self.v_sub_karaoke.get(),
            'highlight':  getattr(self, 'v_sub_highlight', None) and self.v_sub_highlight.get() or '#FFE000',
        }

    def _hex_to_ass_color(self, hex_col, alpha=0):
        """Convert #RRGGBB to ASS &HAABBGGRR format."""
        h = hex_col.lstrip('#')
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f'&H{alpha:02X}{b:02X}{g:02X}{r:02X}'

    def _transcript_to_ass(self, s):
        """Convert whisper segments to ASS with pause detection and karaoke word highlight."""
        import re as _re

        segs = getattr(self, '_whisper_segments', [])
        if not segs:
            srt = getattr(self, 'srt_result', {})
            segs = srt.get('segments', []) if srt else []
        if not segs:
            _ts_re = _re.compile(r'^\[(\d+[\d:.]+)\]\s*(.*)')
            parsed = []
            for line in self.transcript.split('\n'):
                m = _ts_re.match(line.strip())
                if m:
                    _p = m.group(1).split(':')
                    t = int(_p[0])*60+float(_p[1]) if len(_p)==2 else int(_p[0])*3600+int(_p[1])*60+float(_p[2])
                    parsed.append({'start': t, 'end': None, 'text': m.group(2)})
            for i, sg in enumerate(parsed):
                sg['end'] = parsed[i+1]['start'] if i+1<len(parsed) else sg['start']+3.0
            segs = parsed

        words_per = s['words']
        caps      = s['caps']
        karaoke   = s.get('karaoke', False)
        hi_color  = s.get('highlight', '#FFE000')
        PAUSE_GAP = 0.4  # seconds of silence = end subtitle group

        pos_map = {
            'top-left':     (r'\an7',60,50),   'top-center':    (r'\an8',960,50),   'top-right':    (r'\an9',1860,50),
            'mid-left':     (r'\an4',60,540),  'mid-center':    (r'\an5',960,540),  'mid-right':    (r'\an6',1860,540),
            'bottom-left':  (r'\an1',60,1000), 'bottom-center': (r'\an2',960,1000), 'bottom-right': (r'\an3',1860,1000),
        }
        an_tag = pos_map.get(s['position'], (r'\an2', 960, 1000))[0]

        tc = self._hex_to_ass_color(s['color'])
        hc = self._hex_to_ass_color(hi_color)
        oc = self._hex_to_ass_color(s['outline'])
        bg_alpha = max(0, 255 - int(s['bg_opacity'] / 100 * 255)) if s['bg_on'] else 255
        bc = self._hex_to_ass_color(s['bg_color'], alpha=bg_alpha)

        def _ts(t):
            h=int(t//3600); m=int((t%3600)//60); sc=t%60
            return f'{h}:{m:02d}:{sc:05.2f}'

        ass = (
            '[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
            'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, '
            'Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            f'Style: Default,{s["font"]},{s["size"]},{tc},{hc},{oc},{bc},'
            f'{"1" if s["bold"] else "0"},{"1" if s["italic"] else "0"},0,0,100,100,0,0,1,'
            f'{s["stroke"]},0,2,60,60,80,1\n\n'
            '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
        )

        # Flatten all segments into word list with real timestamps
        all_words = []
        for seg in segs:
            raw = _re.sub(r'^\[[\d:.\s>-]+\]\s*', '', seg.get('text','')).strip()
            if not raw: continue
            word_data = seg.get('words', [])
            if word_data and all('start' in w and 'end' in w for w in word_data):
                for w in word_data:
                    wt = w.get('word','').strip()
                    if wt:
                        all_words.append({
                            'word':  wt.upper() if caps else wt,
                            'start': float(w['start']),
                            'end':   float(w['end']),
                        })
            else:
                seg_s = float(seg.get('start', 0))
                seg_e = float(seg.get('end', seg_s + 3.0))
                wl = raw.upper().split() if caps else raw.split()
                if wl:
                    wd = (seg_e - seg_s) / len(wl)
                    for i, w in enumerate(wl):
                        all_words.append({'word': w, 'start': seg_s+i*wd, 'end': seg_s+(i+1)*wd})

        if not all_words:
            return ass

        # Group words into chunks, breaking at pause gaps
        groups = []
        i = 0
        while i < len(all_words):
            grp = [all_words[i]]
            i += 1
            while i < len(all_words) and len(grp) < words_per:
                gap = all_words[i]['start'] - all_words[i-1]['end']
                if gap > PAUSE_GAP:
                    break
                grp.append(all_words[i])
                i += 1
            groups.append(grp)

        for grp in groups:
            cs = grp[0]['start']
            ce = grp[-1]['end']
            if ce <= cs: ce = cs + 0.3
            if karaoke:
                line = f'{{{an_tag}}}'
                for w in grp:
                    dur_cs = max(1, int((w['end'] - w['start']) * 100))
                    line += f'{{\\kf{dur_cs}}}{w["word"]} '
                ass += f'Dialogue: 0,{_ts(cs)},{_ts(ce)},Default,,0,0,0,,{line.rstrip()}\n'
            else:
                line = ' '.join(w['word'] for w in grp)
                ass += f'Dialogue: 0,{_ts(cs)},{_ts(ce)},Default,,0,0,0,,{{{an_tag}}}{line}\n'
        return ass

    def _sub_transcribe(self):
        """Transcribe the video selected in the subtitle tab — no need to visit Transcript tab."""
        inp = self.v_sub_input.get().strip()
        if not inp or not Path(inp).exists():
            messagebox.showwarning('No video', 'Select a video file first.')
            return
        self.sub_trans_btn.config(state='disabled', text='⏳ Transcribing...')
        self.sub_trans_lbl.config(text='Transcribing...', fg=FG2)
        def _run():
            try:
                _ensure_pkgs_on_path()
                ff = ensure_ffmpeg()
                _wm = self.v_whisper.get()
                if not _wm or _wm == 'auto':
                    _wm = 'base'
                result = _do_transcribe(inp, _wm, ffmpeg_path=ff, use_word_timestamps=True)
                segs_raw = result.get('segments', [])
                self._whisper_segments = segs_raw
                self.srt_result = result
                self.transcript = '\n'.join(
                    f'[{s["start"]:.2f}] {s["text"].strip()}' for s in segs_raw)
                n = len(segs_raw)
                def _done():
                    self.sub_trans_btn.config(state='normal', text='📝 Transcribe')
                    self.sub_trans_lbl.config(text=f'✅ {n} segments ready', fg=GREEN)
                self.after(0, _done)
            except Exception as _ex:
                import traceback as _tb
                _e = _tb.format_exc()
                def _err():
                    self.sub_trans_btn.config(state='normal', text='📝 Transcribe')
                    self.sub_trans_lbl.config(text=f'❌ {_ex}', fg=RED)
                    self.log(f'Subtitle transcription error:\n{_e}', RED)
                self.after(0, _err)
        import threading; threading.Thread(target=_run, daemon=True).start()

    def _sub_preview_frame(self):
        """Take a screenshot of the app window overlaid with subtitle style sample."""
        inp = self.v_sub_input.get().strip()
        if not inp or not Path(inp).exists():
            messagebox.showwarning('No video', 'Select a video file first.')
            return
        s = self._get_sub_settings()
        self.sub_status_lbl.config(text='Grabbing preview...', fg=FG2)
        def _run():
            try:
                import subprocess as _sp, tempfile as _tf, os as _os, base64 as _b64
                from PIL import Image, ImageDraw, ImageFont
                import io as _io

                _ff = ensure_ffmpeg()
                if not _ff:
                    self.after(0, lambda: self.sub_status_lbl.config(text='ffmpeg not found', fg=RED))
                    return

                # Get duration using ffmpeg stderr (ffprobe may not be in bundle)
                import re as _re_dur
                _dur_r = _sp.run([_ff, '-i', inp], capture_output=True, text=True, errors='replace')
                _dm = _re_dur.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur_r.stderr)
                try:
                    _h, _m, _s2 = _dm.groups()
                    mid = (int(_h)*3600 + int(_m)*60 + float(_s2)) / 2
                except:
                    mid = 5.0

                tf_png = _tf.mktemp(suffix='.png')
                _sp.run([_ff, '-ss', str(mid), '-i', inp,
                         '-vframes', '1', '-q:v', '2', '-vf', 'scale=640:360',
                         tf_png, '-y'], capture_output=True)

                if not Path(tf_png).exists():
                    self.after(0, lambda: self.sub_status_lbl.config(
                        text='Could not extract frame from video', fg=RED))
                    return

                img = Image.open(tf_png).convert('RGB')
                draw = ImageDraw.Draw(img, 'RGBA')

                sample = 'This is how your subtitles look'
                if s['caps']: sample = sample.upper()

                # Load font from Windows fonts folder
                font_size = max(14, s['size'] // 3)
                fnt = None
                _wf = r'C:\Windows\Fonts'
                _name = s['font'].replace(' ', '')
                for _fn in [
                    _os.path.join(_wf, s['font'] + '.ttf'),
                    _os.path.join(_wf, s['font'] + 'bd.ttf'),
                    _os.path.join(_wf, _name + '.ttf'),
                    _os.path.join(_wf, _name + 'bd.ttf'),
                    _os.path.join(_wf, 'arial.ttf'),
                    _os.path.join(_wf, 'calibri.ttf'),
                ]:
                    try: fnt = ImageFont.truetype(_fn, size=font_size); break
                    except: pass
                if fnt is None: fnt = ImageFont.load_default()

                # Position map for 640x360
                pos_map = {
                    'top-left':     (30,  25),  'top-center':    (320, 25),  'top-right':    (610, 25),
                    'mid-left':     (30,  180), 'mid-center':    (320, 180), 'mid-right':    (610, 180),
                    'bottom-left':  (30,  330), 'bottom-center': (320, 330), 'bottom-right': (610, 330),
                }
                tx, ty = pos_map.get(s['position'], (320, 330))

                def _hc(h):
                    hx = h.lstrip('#')
                    return tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))

                tc2 = _hc(s['color'])
                oc2 = _hc(s['outline'])

                try: bbox = draw.textbbox((tx, ty), sample, font=fnt, anchor='ms')
                except: bbox = (tx-120, ty-font_size-4, tx+120, ty+4)

                if s['bg_on']:
                    pad = 6
                    bc2 = _hc(s['bg_color'])
                    alpha = int(s['bg_opacity'] / 100 * 255)
                    draw.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad],
                                   fill=(*bc2, alpha))

                stroke = min(s['stroke'], 3)
                if stroke > 0:
                    for dx in range(-stroke, stroke+1):
                        for dy in range(-stroke, stroke+1):
                            if dx or dy:
                                try: draw.text((tx+dx, ty+dy), sample, font=fnt, fill=(*oc2, 255), anchor='ms')
                                except: draw.text((tx+dx, ty+dy), sample, font=fnt, fill=(*oc2, 255))
                try: draw.text((tx, ty), sample, font=fnt, fill=(*tc2, 255), anchor='ms')
                except: draw.text((tx, ty), sample, font=fnt, fill=(*tc2, 255))

                buf = _io.BytesIO()
                img.save(buf, format='PNG')
                img_b64 = _b64.b64encode(buf.getvalue()).decode('ascii')
                _os.unlink(tf_png)

                def _show():
                    import tkinter as _tk3
                    photo = _tk3.PhotoImage(data=img_b64)
                    self._sub_preview_frame_widget.config(image=photo, text='')
                    self._sub_preview_frame_widget._photo = photo
                    self._sub_preview_frame_widget.pack(fill='x', pady=(8, 4))
                    self.sub_status_lbl.config(text='Preview ↑ — click Burn to apply', fg=GREEN)
                self.after(0, _show)

            except Exception as _ex:
                import traceback as _tb2
                _err2 = _tb2.format_exc()
                self.after(0, lambda e=str(_ex), tb=_err2: (
                    self.sub_status_lbl.config(text=f'Preview error: {e}', fg=RED),
                    self.log(f'Preview error:\n{tb}', RED)))
        import threading; threading.Thread(target=_run, daemon=True).start()

    def _render_sub_preview(self):
        """Regenerate preview if one is already showing."""
        if self._sub_preview_frame_widget.winfo_ismapped():
            self._sub_preview_frame()

    def _burn_subtitles(self):
        """Burn subtitles into video using ffmpeg ASS filter."""
        inp = self.v_sub_input.get().strip()
        if not inp or not Path(inp).exists():
            messagebox.showwarning('No input', 'Select a video file first.')
            return
        # Auto-transcribe if no segments yet
        if not getattr(self, '_whisper_segments', []):
            self.sub_status_lbl.config(text='No transcript — transcribing first...', fg=YELLOW)
            self.sub_burn_btn.config(state='disabled', text='⏳ Transcribing...')
            def _then_burn():
                if getattr(self, '_whisper_segments', []):
                    self._burn_subtitles()
                else:
                    self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES')
                    self.sub_status_lbl.config(text='❌ Transcription failed', fg=RED)
            def _run_trans():
                try:
                    _ensure_pkgs_on_path()
                    ff = ensure_ffmpeg()
                    _wm = self.v_whisper.get()
                    if not _wm or _wm == 'auto': _wm = 'base'
                    result = _do_transcribe(inp, _wm, ffmpeg_path=ff, use_word_timestamps=True)
                    segs_raw = result.get('segments', [])
                    self._whisper_segments = segs_raw
                    self.srt_result = result
                    self.transcript = '\n'.join(
                        f'[{s["start"]:.2f}] {s["text"].strip()}' for s in segs_raw)
                    self.after(0, lambda: (
                        self.sub_trans_lbl.config(text=f'✅ {len(segs_raw)} segments', fg=GREEN),
                        _then_burn()
                    ))
                except Exception as _ex:
                    self.after(0, lambda e=str(_ex): (
                        self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES'),
                        self.sub_status_lbl.config(text=f'❌ Transcription failed: {e}', fg=RED)
                    ))
            import threading; threading.Thread(target=_run_trans, daemon=True).start()
            return
        outdir = self.v_sub_outdir.get().strip()
        Path(outdir).mkdir(parents=True, exist_ok=True)
        stem = Path(inp).stem
        outfile = str(Path(outdir) / f'{stem} - Subtitled - ClipFinder.mp4')
        s = self._get_sub_settings()
        self.sub_burn_btn.config(state='disabled', text='⏳ Burning...')
        self.sub_status_lbl.config(text='Starting...', fg=FG2)
        self.cfg['sub_outdir'] = outdir
        save_cfg(self.cfg)

        def _run():
            try:
                import subprocess as _sp, tempfile as _tf, os as _os, re as _re_sub
                _ff = ensure_ffmpeg()
                if not _ff:
                    self.after(0, lambda: (
                        self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES'),
                        self.sub_status_lbl.config(text='❌ ffmpeg not found', fg=RED)))
                    return

                # Write ASS file
                ass_content = self._transcript_to_ass(s)
                tf_ass = _tf.mktemp(suffix='.ass')
                with open(tf_ass, 'w', encoding='utf-8') as _f:
                    _f.write(ass_content)

                # Get video duration for progress %
                _dur_r = _sp.run([_ff, '-i', inp], capture_output=True, text=True)
                _dm = _re_sub.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur_r.stderr)
                _total_s = 1.0
                if _dm:
                    _h, _m, _s2 = _dm.groups()
                    _total_s = int(_h)*3600 + int(_m)*60 + float(_s2)

                # Pick encoder
                _enc = getattr(self, '_encoder', '')
                if 'amf' in _enc: _vcodec = ['h264_amf']
                elif 'nvenc' in _enc: _vcodec = ['h264_nvenc']
                elif 'qsv' in _enc: _vcodec = ['h264_qsv']
                else: _vcodec = ['libx264', '-crf', '18', '-preset', 'fast']

                ass_escaped = tf_ass.replace('\\', '/').replace(':', '\\:')
                cmd = [_ff, '-i', inp,
                       '-vf', f"ass='{ass_escaped}'",
                       '-c:v'] + _vcodec + ['-c:a', 'copy', outfile, '-y']

                self.after(0, lambda: self.set_progress('🔤 Burning subtitles...', pct=1))
                proc = _sp.Popen(cmd, stderr=_sp.PIPE, text=True,
                                 encoding='utf-8', errors='replace')
                for line in proc.stderr:
                    if 'time=' in line:
                        try:
                            _t = line.split('time=')[1].split()[0]
                            _parts = _t.split(':')
                            _cur = int(_parts[0])*3600 + int(_parts[1])*60 + float(_parts[2])
                            _pct = min(99, int(_cur / _total_s * 100))
                            self.after(0, lambda p=_pct, t=_t: (
                                self.set_progress(f'🔤 Burning subtitles... {t}', pct=p),
                                self.sub_status_lbl.config(text=f'Burning... {t}', fg=FG2)
                            ))
                        except: pass
                proc.wait()
                _os.unlink(tf_ass)

                if proc.returncode == 0:
                    def _done():
                        self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES')
                        self.sub_status_lbl.config(text=f'✅ Saved: {Path(outfile).name}', fg=GREEN)
                        self.set_progress(f'✅ Subtitles burned: {Path(outfile).name}', pct=100)
                        self.log(f'✅ Subtitles burned: {outfile}', GREEN)
                    self.after(0, _done)
                else:
                    raise RuntimeError(f'ffmpeg returned code {proc.returncode}')
            except Exception as _ex:
                import traceback as _tb
                _err = _tb.format_exc()
                def _err_ui():
                    self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES')
                    self.sub_status_lbl.config(text='❌ Error — check log', fg=RED)
                    self.set_progress('❌ Subtitle burn failed', pct=0)
                    self.log(f'Subtitle burn error:\n{_err}', RED)
                self.after(0, _err_ui)
        import threading; threading.Thread(target=_run, daemon=True).start()

    def _copy_transcript(self):
        t = self.trans_box.get('1.0', 'end').strip()
        if t:
            self.clipboard_clear()
            self.clipboard_append(t)
            self.log('Copied to clipboard.', GREEN)

    def _save_txt(self):
        if not self.transcript:
            messagebox.showwarning('No transcript', 'Transcribe first.')
            return
        p = filedialog.asksaveasfilename(defaultextension='.txt',
            filetypes=[('Text', '*.txt')],
            initialfile=Path(self.v_video.get()).stem + '_transcript.txt')
        if p:
            Path(p).write_text(self.transcript, encoding='utf-8')
            self.log(f'Saved: {Path(p).name}', GREEN)

    def _save_srt(self):
        if not self.srt_result:
            messagebox.showwarning('No transcript', 'Transcribe first.')
            return
        p = filedialog.asksaveasfilename(defaultextension='.srt',
            filetypes=[('SRT', '*.srt')],
            initialfile=Path(self.v_video.get()).stem + '.srt')
        if not p: return
        lines = []
        for i, seg in enumerate(self.srt_result.get('segments', []), 1):
            start_ts = ts_srt(seg["start"])
            end_ts   = ts_srt(seg["end"])
            text     = seg['text'].strip()
            lines += [str(i), f'{start_ts} --> {end_ts}', text, '']
        # Write with CRLF line endings — required by CapCut, Premiere, DaVinci
        content = '\r\n'.join(lines)
        Path(p).write_bytes(content.encode('utf-8'))
        self.log(f'SRT saved: {Path(p).name} ({len(self.srt_result.get("segments",[]))} entries)', GREEN)


    # ═══════════════════════════════════════════════════════════════════════════
    # DOWNLOADER TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_dl_tab(self, p):
        def sec(t):
            tk.Label(p, text=t, font=('Segoe UI', 9, 'bold'),
                     fg=ACCENT, bg=BG, anchor='w').pack(anchor='w', padx=20, pady=(14,0))
        def div():
            tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=20, pady=8)

        # Header
        hdr = tk.Frame(p, bg=BG); hdr.pack(fill='x', padx=20, pady=(16,0))
        tk.Label(hdr, text='VIDEO DOWNLOADER', font=('Segoe UI', 11, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(hdr, text='  YouTube · Twitch · Twitter/X · Kick',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=8)
        div()

        # Batch queue box
        q_hdr = tk.Frame(p, bg=BG); q_hdr.pack(fill='x', padx=20, pady=(0,4))
        tk.Label(q_hdr, text='📋  BATCH QUEUE', font=('Segoe UI',9,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(q_hdr, text='  paste one URL per line — downloads in order',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self._dl_queue_status = tk.Label(q_hdr, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self._dl_queue_status.pack(side='right')
        q_frame = tk.Frame(p, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        q_frame.pack(fill='x', padx=20, pady=(0,4))
        self._dl_queue_box = tk.Text(q_frame, height=6, font=FONT_MONO_S,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat',
                 bd=6, wrap='none')
        self._dl_queue_box.pack(side='left', fill='both', expand=True)
        _qs = tk.Scrollbar(q_frame, command=self._dl_queue_box.yview)
        _qs.pack(side='right', fill='y')
        self._dl_queue_box.config(yscrollcommand=_qs.set)
        q_btn_row = tk.Frame(p, bg=BG); q_btn_row.pack(fill='x', padx=20, pady=(0,4))
        self._dl_queue_btn = tk.Button(q_btn_row, text='⬇  Download Queue',
                  font=('Segoe UI',9,'bold'), bg=ACCENT2, fg='#000',
                  relief='flat', bd=0, cursor='hand2', padx=14, pady=6,
                  command=self._dl_start_queue)
        self._dl_queue_btn.pack(side='left')
        tk.Button(q_btn_row, text='✕ Clear', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=10, pady=6,
                  command=lambda: self._dl_queue_box.delete('1.0', 'end')
                  ).pack(side='left', padx=6)
        div()

        # URL
        sec('URL')
        ur = tk.Frame(p, bg=BG); ur.pack(fill='x', padx=20, pady=(4,0))
        url_e = tk.Entry(ur, textvariable=self.v_dl_url, font=FONT_MONO_S,
                         bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=6)
        url_e.pack(side='left', fill='x', expand=True)
        self._dl_go_btn = tk.Button(ur, text='⬇  Download', font=FONT_SMALL,
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=6, activebackground=ACCENT2,
                  command=self._dl_start)
        self._dl_go_btn.pack(side='right', padx=(8,0))
        self._dl_cancel_btn = tk.Button(ur, text='✕ Cancel', font=FONT_SMALL,
                  bg=RED, fg='#fff', relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=6,
                  command=self._dl_cancel)
        # shown/hidden by _dl_set_busy
        tk.Label(p, text='YouTube · Twitch · Twitter/X · Kick · TikTok and more',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=20, pady=(3,0))

        # Auto-load checkbox
        al_row = tk.Frame(p, bg=BG); al_row.pack(fill='x', padx=20, pady=(6,0))
        tk.Checkbutton(al_row, text='Auto-load into Clip Finder after download',
                       variable=self.v_auto_load, font=FONT_SMALL, fg=FG2, bg=BG,
                       selectcolor=BG3, activebackground=BG, relief='flat',
                       cursor='hand2').pack(side='left')
        div()

        # Save folder
        sec('SAVE TO')
        fr = tk.Frame(p, bg=BG); fr.pack(fill='x', padx=20, pady=(4,0))
        tk.Entry(fr, textvariable=self.v_dl_folder, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=6
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(fr, text='...', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=6,
                  command=self._dl_pick_folder).pack(side='right', padx=(6,0))
        div()

        # VOD Mode toggle
        sec('MODE')
        vod_row = tk.Frame(p, bg=BG); vod_row.pack(fill='x', padx=20, pady=(4,0))
        self.v_vod_mode = tk.BooleanVar(value=self.cfg.get('vod_mode', False))
        def _toggle_vod(*_):
            self.cfg['vod_mode'] = self.v_vod_mode.get()
            save_cfg(self.cfg)
            _vod_lbl.config(
                text='📼  VOD Mode ON — saves to vod/ folder, 8x parallel download',
                fg=GREEN) if self.v_vod_mode.get() else _vod_lbl.config(
                text='📼  VOD Mode OFF — auto-detects Twitch/Kick VODs',
                fg=FG2)
        tk.Checkbutton(vod_row, text='📼  VOD Mode', variable=self.v_vod_mode,
                      font=('Segoe UI',9,'bold'), fg=FG, bg=BG,
                      activebackground=BG, selectcolor=BG3,
                      command=_toggle_vod, cursor='hand2').pack(side='left')
        _vod_lbl = tk.Label(vod_row,
            text='📼  VOD Mode OFF — auto-detects Twitch/Kick VODs',
            font=FONT_SMALL, fg=FG2, bg=BG)
        _vod_lbl.pack(side='left', padx=8)
        if self.v_vod_mode.get(): _toggle_vod()
        div()

        # Quality
        sec('QUALITY')
        q_row = tk.Frame(p, bg=BG); q_row.pack(fill='x', padx=20, pady=(6,0))
        for val, label in [('best','🏆 Best'),('1080','1080p'),('720','720p'),
                            ('480','480p'),('audio','🎵 Audio only')]:
            b = tk.Button(q_row, text=label, font=FONT_SMALL,
                          relief='flat', cursor='hand2', padx=10, pady=6, bd=0,
                          command=lambda v=val: self._set_dl_quality(v))
            b.pack(side='left', padx=3)
            self._dl_q_btns[val] = b
        self._refresh_dl_quality()
        div()

        # Cookies — now in Settings tab
        div()
        cr = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        cr.pack(fill='x', padx=16, pady=(0,4))
        ci = tk.Frame(cr, bg=BG2); ci.pack(fill='x', padx=12, pady=8)
        tk.Label(ci, text='🍪  Cookies for Kick/Twitter/X',
                 font=('Segoe UI',9,'bold'), fg=FG, bg=BG2).pack(side='left')
        tk.Button(ci, text='⚙  Manage in Settings',
                 font=FONT_SMALL, bg=BG3, fg=ACCENT2, relief='flat', bd=0,
                 cursor='hand2', padx=10, pady=3,
                 command=lambda: self._switch_nb('settings')).pack(side='right')
        self._dl_cookie_lbl = tk.Label(ci, text='', font=('Segoe UI',8), bg=BG2)
        self._dl_cookie_lbl.pack(anchor='w', pady=(4,0))
        def _refresh_cookie_status(*_):
            cpath = self.v_cookies.get().strip()
            if cpath and Path(cpath).exists():
                self._dl_cookie_lbl.config(text=f'✅  {cpath}', fg=GREEN)
            elif cpath:
                self._dl_cookie_lbl.config(text=f'⚠️  File not found: {cpath}', fg=YELLOW)
            else:
                self._dl_cookie_lbl.config(text='⚠️  No cookies set — add in ⚙ Settings', fg=YELLOW)
        self.v_cookies.trace_add('write', _refresh_cookie_status)
        _refresh_cookie_status()
        div()

        # Log
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=20, pady=8)
        tk.Label(p, text='📋  Download progress shows in the LOG panel on the left sidebar.',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=20, pady=(0,4))

        tk.Button(p, text='📂  Open Download Folder', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', pady=7,
                  command=lambda: os.startfile(self.v_dl_folder.get())
                  if Path(self.v_dl_folder.get()).exists() else None
                  ).pack(fill='x', padx=20, pady=(8,14))

    def _set_dl_quality(self, val):
        self.v_dl_quality.set(val)
        self._refresh_dl_quality()

    def _refresh_dl_quality(self):
        cur = self.v_dl_quality.get()
        for val, b in self._dl_q_btns.items():
            b.config(bg=ACCENT if val == cur else BG3,
                     fg='#000' if val == cur else FG3)

    def _dl_pick_folder(self):
        d = filedialog.askdirectory(title='Save downloads to...')
        if d:
            self.v_dl_folder.set(d)
            self._dl_autosave()

    def _dl_pick_cookies(self):
        p = filedialog.askopenfilename(title='Select cookies.txt',
            filetypes=[('Cookies', '*.txt'), ('All', '*.*')])
        if p:
            self.v_cookies.set(p)
            self._dl_autosave()

    def _dl_log_write(self, text, color=None):
        self.log(text, color)

    def _dl_cancel(self):
        """Cancel current download and stop queue if running."""
        self._dl_cancel_requested = True
        self._dl_queue_cancel = True  # stop queue loop too
        self._dl_log_write('⛔ Download cancelled', YELLOW)
        self._dl_set_busy(False)
        self.set_progress('', pct=0)

    def _dl_set_busy(self, busy):
        """Toggle Download ↔ Cancel button in downloader tab."""
        # Don't reset cancel_requested during a queue run — queue manages its own state
        if not getattr(self, '_in_queue', False):
            self._dl_cancel_requested = not busy
        try:
            if busy:
                self._dl_go_btn.pack_forget()
                self._dl_cancel_btn.pack(side='right', padx=(8,0))
            else:
                self._dl_cancel_btn.pack_forget()
                self._dl_go_btn.pack(side='right', padx=(8,0))
        except: pass

    def _dl_start_queue(self):
        """Download all URLs from the queue box in order."""
        try:
            raw = self._dl_queue_box.get('1.0', 'end').strip()
        except: raw = ''
        urls = [u.strip() for u in raw.splitlines() if u.strip().startswith('http')]
        if not urls:
            messagebox.showerror('Empty Queue', 'Paste at least one URL in the queue box.')
            return
        self._dl_queue_btn.config(state='disabled', text='⬇ Downloading...')
        self._dl_queue_cancel = False  # queue-level cancel flag
        def _run_queue():
            for i, url in enumerate(urls):
                if self._dl_queue_cancel:
                    self._dl_log_write('⛔ Queue cancelled', YELLOW)
                    break
                self.after(0, lambda u=url, n=i+1, t=len(urls): (
                    self._dl_queue_status.config(text=f'({n}/{t}) downloading...'),
                    self.v_dl_url.set(u),
                ))
                self._dl_cancel_requested = False
                self._in_queue = True  # flag: suppress per-item done popup
                folder = self.v_dl_folder.get().strip()
                Path(folder).mkdir(parents=True, exist_ok=True)
                self._dl_log_write(f'\n[Queue {i+1}/{len(urls)}] {url}', ACCENT2)
                self._dl_log_write(f'Starting download...', FG2)
                self._dl_log_write(f'URL: {url}', FG2)
                try:
                    self._dl_run(url, folder)
                except Exception as _qe:
                    self._dl_log_write(f'❌ Queue item {i+1} failed: {_qe}', RED)
                self._in_queue = True  # keep flag set until loop ends
                import time; time.sleep(0.5)
            self._in_queue = False
            self.after(0, lambda: (
                self._dl_queue_btn.config(state='normal', text='⬇  Download Queue'),
                self._dl_queue_status.config(
                    text=f'✅ {len(urls)} done' if not self._dl_queue_cancel else '⛔ Cancelled'),
                self.set_progress('', pct=0),
            ))
        import threading
        threading.Thread(target=_run_queue, daemon=True).start()

    def _dl_start(self):
        url = self.v_dl_url.get().strip()
        if not url:
            messagebox.showerror('Missing URL', 'Paste a video URL first.')
            return
        folder = self.v_dl_folder.get().strip()
        Path(folder).mkdir(parents=True, exist_ok=True)
        # Clear the main log for a fresh download
        try:
            self.log_box.config(state='normal')
            self.log_box.delete('1.0', 'end')
            self.log_box.config(state='disabled')
        except Exception:
            pass
        self._dl_cancel_requested = False
        self._dl_set_busy(True)
        self._dl_log_write(f'Starting download...', FG2)
        self._dl_log_write(f'URL: {url}', FG2)
        threading.Thread(target=self._dl_run, args=(url, folder), daemon=True).start()

    def _dl_run(self, url, folder):
        try:
            import yt_dlp, shutil as _sh, re as _re, urllib.request as _ur, json as _json

            # ── VOD detection — manual toggle OR auto-detect ──────────────
            _manual_vod = getattr(self, 'v_vod_mode', None)
            _manual_vod = _manual_vod.get() if _manual_vod else False
            _is_vod_url = _manual_vod or any(p in url.lower() for p in [
                'twitch.tv/videos/', 'kick.com/video/',
            ])
            # For YouTube/generic we detect after getting info
            _vod_folder = str(Path(folder) / 'vod')
            _clip_folder = folder

            quality = self.v_dl_quality.get()
            if quality == 'audio':
                fmt = 'bestaudio/best'
                pp  = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
            elif quality == 'best':
                # Best video + best audio regardless of codec, merge to mp4
                # vp9/av1 + opus is fine — ffmpeg will remux/transcode to mp4
                fmt = ('bestvideo+bestaudio'
                       '/bestvideo[ext=mp4]+bestaudio[ext=m4a]'
                       '/best[ext=mp4]'
                       '/best')
                pp  = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'},
                       {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
            else:
                # Specific resolution — prefer vp9 (higher quality per bitrate than h264)
                fmt = (f'bestvideo[height<={quality}]+bestaudio'
                       f'/bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]'
                       f'/best[height<={quality}][ext=mp4]'
                       f'/best[height<={quality}]'
                       f'/best')
                pp  = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'},
                       {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]

            ff = find_ffmpeg()
            ffmpeg_loc = str(Path(ff).parent) if ff and ff != 'ffmpeg' else None
            if not ffmpeg_loc and _sh.which('ffmpeg'):
                ffmpeg_loc = str(Path(_sh.which('ffmpeg')).parent)

            # VOD mode: use vod subfolder + max concurrent fragments for speed
            _out_folder = _vod_folder if _is_vod_url else _clip_folder
            Path(_out_folder).mkdir(parents=True, exist_ok=True)
            if _is_vod_url:
                self._dl_log_write('📼  VOD detected — saving to vod/ folder', ACCENT2)
                self._dl_log_write('⚡  Concurrent fragment download enabled', FG2)

            ydl_opts = {
                'format': fmt,
                'outtmpl': str(Path(_out_folder) / '%(uploader)s - %(title)s - ClipFinder.%(ext)s'),
                'postprocessors': pp,
                'merge_output_format': 'mp4',
                'postprocessor_args': {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']},
                'quiet': False,
                'no_warnings': False,
                'noplaylist': True,
                'playlist_items': '1',
                'progress_hooks': [self._dl_progress_hook],
                'concurrent_fragment_downloads': 8,  # parallel fragments = much faster for VODs
                # YouTube n-challenge workarounds
                # Use ios client — doesn't need JS runtime for n-challenge
                # ios works with cookies and doesn't require po_token
                'extractor_args': {'youtube': {
                    'player_client': ['ios', 'web'],
                    'skip': ['translated_subs', 'hls', 'dash'],
                }},
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
            }
            if ffmpeg_loc:
                ydl_opts['ffmpeg_location'] = ffmpeg_loc

            # Kick.com — curl_cffi Chrome impersonation to bypass Cloudflare
            if 'kick.com' in url.lower():
                video_url = None
                clip_match = _re.search(r'clips/(clip_[A-Za-z0-9]+)', url)
                vod_match  = _re.search(r'/videos/([a-f0-9-]{36})', url)
                try:
                    from curl_cffi import requests as _cffi
                    _hdrs = {'Referer': 'https://kick.com/', 'Accept': 'application/json',
                             'Accept-Language': 'en-US,en;q=0.9'}
                    _kick_title    = None
                    _kick_streamer = None
                    if clip_match:
                        clip_id = clip_match.group(1)
                        self._dl_log_write('🔧  Kick clip — Chrome impersonation...', FG2)
                        _resp = _cffi.get(f'https://kick.com/api/v2/clips/{clip_id}',
                                          impersonate='chrome120', headers=_hdrs, timeout=15)
                        if _resp.status_code == 200:
                            cd = _resp.json()
                            video_url = (cd.get('clip_url') or cd.get('video_url') or
                                        (cd.get('clip') or {}).get('video_url'))
                            _kick_streamer = (cd.get('channel', {}).get('slug') or
                                             cd.get('broadcaster', {}).get('username') or
                                             cd.get('streamer', {}).get('username'))
                            _kick_title = (cd.get('title') or cd.get('clip_title') or
                                          (cd.get('clip') or {}).get('title'))
                    elif vod_match:
                        vod_id = vod_match.group(1)
                        self._dl_log_write('🔧  Kick VOD — Chrome impersonation...', FG2)
                        for ep in [f'v1/video/{vod_id}', f'v2/videos/{vod_id}']:
                            _resp = _cffi.get(f'https://kick.com/api/{ep}',
                                              impersonate='chrome120', headers=_hdrs, timeout=15)
                            if _resp.status_code == 200:
                                vd = _resp.json()
                                video_url = (vd.get('source') or vd.get('playback_url') or
                                            vd.get('hls_url') or vd.get('video_url') or
                                            (vd.get('livestream') or {}).get('source'))
                                _kick_streamer = (vd.get('channel', {}).get('slug') or
                                                 vd.get('user', {}).get('username'))
                                _kick_title = vd.get('session_title') or vd.get('title')
                                if video_url: break
                except Exception as ke:
                    self._dl_log_write(f'⚠️  curl_cffi: {ke}', YELLOW)
                if video_url:
                    self._dl_log_write('✅  Got Kick URL', FG2)
                    url = video_url
                    ydl_opts['format'] = 'best'
                    # Override outtmpl with clean Kick name
                    if _kick_streamer or _kick_title:
                        import re as _re_k
                        _ks = _re_k.sub(r'[\/:*?"<>|]', '', _kick_streamer or 'Kick').strip()
                        _kt = _re_k.sub(r'[\/:*?"<>|]', '', _kick_title or 'clip').strip()[:60]
                        ydl_opts['outtmpl'] = str(Path(_out_folder) / f'{_ks} - {_kt} - ClipFinder.%(ext)s')
                        self._dl_log_write(f'📁  Name: {_ks} - {_kt} - ClipFinder', FG2)
                else:
                    self._dl_log_write('⚠️  Kick API failed — trying yt-dlp...', YELLOW)
                ydl_opts['http_headers'] = {
                    'Referer': 'https://kick.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                }

            # Cookies — only apply for platforms that need them
            # YouTube works WITHOUT cookies and cookies break client selection
            cookies = self.v_cookies.get().strip()
            is_youtube = any(x in url.lower() for x in ['youtube.com', 'youtu.be'])
            is_twitter = any(x in url.lower() for x in ['twitter.com', 'x.com', 't.co'])
            needs_cookies = not is_youtube  # YouTube breaks with cookies+n-challenge

            if cookies and Path(cookies).exists() and needs_cookies:
                ydl_opts['cookiefile'] = cookies
                self._dl_log_write('🍪  Using cookies.txt', FG2)
            elif cookies and Path(cookies).exists() and is_youtube:
                self._dl_log_write('ℹ️  YouTube: skipping cookies (not needed, causes issues)', FG2)
            elif is_twitter:
                self._dl_log_write('⚠️  No cookies.txt — X/Twitter may fail', YELLOW)

            # Try with web+mweb first, fall back to default if it fails
            def _try_dl(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info = None
            last_err = None
            # For YouTube without cookies, ios/android work great
            # For other sites, use web client
            if is_youtube:
                client_attempts = [
                    (['ios'],              fmt),
                    (['ios', 'web'],       'best'),
                    (['android'],          'best'),
                    (['android_vr'],       'best'),
                    (None,                 'best[ext=mp4]/best'),
                ]
            else:
                client_attempts = [
                    (['web'],              fmt),
                    (None,                 'best[ext=mp4]/best'),
                ]
            for _clients, _fmt in client_attempts:
                try:
                    _opts = dict(ydl_opts)
                    _opts['format'] = _fmt
                    # Remove cookies for YouTube — they break ios/android clients
                    if is_youtube:
                        _opts.pop('cookiefile', None)
                    if _clients:
                        _opts['extractor_args'] = {'youtube': {
                            'player_client': _clients,
                            'skip': ['translated_subs'],
                        }}
                    else:
                        _opts.pop('extractor_args', None)
                    client_str = '+'.join(_clients) if _clients else 'default'
                    self._dl_log_write(f'Trying {client_str}...', FG2)
                    info = _try_dl(_opts)
                    if info:
                        break
                except Exception as _ex:
                    last_err = _ex
                    continue
            if not info:
                raise last_err or Exception('All download attempts failed')

            title    = info.get('title', 'video') or 'video'
            uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id', '')
            # Fix NA uploader — extract from URL path
            if not uploader or uploader.strip().upper() == 'NA':
                import re as _re_url
                _url_match = _re_url.search(r'(?:twitch\\.tv|kick\\.com|youtube\\.com/c?|x\\.com)/([^/?&#]+)', url)
                uploader = _url_match.group(1) if _url_match else ''
            # Fix generic titles like "master", "index", "playlist"
            if title.lower() in ('master', 'index', 'playlist', 'na', 'video', ''):
                title = info.get('description', '')[:60] or info.get('webpage_url_basename','') or title
            # Rename downloaded file if uploader was NA
            if uploader and uploader.upper() != 'NA':
                import re as _re_fn, glob as _gl
                _safe_up = _re_fn.sub(r'[\/:*?"<>|]', '', uploader).strip()
                _safe_ti = _re_fn.sub(r'[\/:*?"<>|]', '', title).strip()[:60]
                _new_name = f'{_safe_up} - {_safe_ti} - ClipFinder.mp4' if _safe_ti else f'{_safe_up} - ClipFinder.mp4'
                # Find and rename the downloaded file
                try:
                    _dl_files = sorted(Path(_out_folder).glob('*NA*ClipFinder*'), key=lambda x: x.stat().st_mtime, reverse=True)
                    if _dl_files:
                        _new_path = Path(_out_folder) / _new_name
                        _dl_files[0].rename(_new_path)
                        self._dl_log_write(f'✏️  Renamed: {_new_name}', FG2)
                except Exception as _re: pass
            self._dl_log_write('', FG2)
            self._dl_log_write(f'✅  Done: {title}', GREEN)
            self._dl_log_write(f'📁  Saved to: {folder}', FG2)

            # Find downloaded file
            downloaded = None
            try:
                rds = info.get('requested_downloads', [])
                if rds and rds[0].get('filepath'):
                    downloaded = rds[0]['filepath']
                    # Handle merge — final file may have .mp4 extension
                    if not Path(downloaded).exists():
                        mp4 = str(Path(downloaded).with_suffix('.mp4'))
                        if Path(mp4).exists():
                            downloaded = mp4
                if not downloaded:
                    video_exts = {'.mp4','.mkv','.webm','.mov','.avi','.mp3'}
                    for f in sorted(Path(folder).glob('*'),
                                    key=lambda x: x.stat().st_mtime, reverse=True):
                        if f.suffix.lower() in video_exts:
                            downloaded = str(f); break
            except Exception:
                pass

            if downloaded:
                self._last_dl_path = downloaded
                # Auto-load if triggered from clip finder URL field
                _load_clip = getattr(self, '_load_after_dl', False)
                self._load_after_dl = False
                def _finish(p=downloaded, lc=_load_clip):
                    self.set_progress(f'✅  Done: {Path(p).name}', pct=100)
                    self.set_busy(False)
                    if lc:
                        self.v_video.set(p)
                        if hasattr(self, '_video_entry'):
                            self._video_entry.config(fg=FG)
                        if not self.v_outdir.get():
                            self.v_outdir.set(str(Path(p).parent))
                        self._switch_nb('clips')
                        self.log(f'✅ Loaded: {Path(p).name} — hit ▶ FIND CLIPS', GREEN)
                    elif self.v_auto_load.get():
                        self._dl_log_write('📎  Loading into Clip Finder...', ACCENT2)
                        self._dl_auto_load()
                    else:
                        self._dl_done_popup(p)
                self.after(0, _finish)

        except Exception as e:
            if 'cancelled by user' in str(e).lower():
                self._dl_log_write('⛔ Download cancelled.', YELLOW)
            else:
                self._dl_log_write(f'❌  Error: {e}', RED)
                import traceback as _tb
                self._dl_log_write(_tb.format_exc(), RED)
        finally:
            self.after(0, lambda: self._dl_set_busy(False))

    def _dl_progress_hook(self, d):
        import re as _re_dl
        def _clean(s):
            """Strip ANSI escape codes."""
            return _re_dl.sub(r'\033\[[0-9;]*m|\x1b\[[0-9;]*m', '', str(s or '')).strip()

        if d.get('status') == 'downloading':
            # Use raw bytes for reliable percentage (avoids ANSI-polluted strings)
            _dl  = d.get('downloaded_bytes') or 0
            _tot = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            pct_raw = (_dl / _tot * 100) if _tot > 0 else 0
            speed_raw = d.get('speed') or 0
            speed_s = (f'{speed_raw/1024:.0f}KB/s' if speed_raw < 1024*1024
                       else f'{speed_raw/1024/1024:.1f}MB/s') if speed_raw else '---'
            eta_raw = d.get('eta')
            if eta_raw:
                eta_s = f'{int(eta_raw)//60}:{int(eta_raw)%60:02d}'
            elif _tot > 0 and speed_raw > 0:
                _secs = int((_tot - _dl) / speed_raw)
                eta_s = f'{_secs//60}:{_secs%60:02d}'
            else:
                eta_s = '---'

            # Update top progress bar on every hook call
            self.after(0, lambda p=pct_raw, sp=speed_s, e=eta_s:
                self.set_progress(f'⬇  {sp}  ETA {e}', pct=int(p)))

            # Log only every 5%
            _last = getattr(self, '_last_dl_log_pct', -10)
            if pct_raw - _last >= 5 or pct_raw >= 99:
                self._last_dl_log_pct = pct_raw
                fname = Path(d.get('filename', '')).name[:70]
                self.after(0, lambda p=pct_raw, sp=speed_s, e=eta_s, f=fname:
                    self._dl_log_write(f'⬇  {p:5.1f}%  {sp}  ETA {e}  —  {f}', FG))

        elif d.get('status') == 'finished':
            self._last_dl_log_pct = -10
            self.after(0, lambda: self.set_progress('⚙️ Merging...', pct=100))
            self._dl_log_write('⚙️  Processing...', ACCENT2)
        if getattr(self, '_dl_cancel_requested', False):
            raise Exception('Download cancelled by user')


    def _dl_auto_load(self):
        if not self._last_dl_path: return
        self.v_video.set(self._last_dl_path)
        if not self.v_outdir.get():
            self.v_outdir.set(str(Path(self._last_dl_path).parent))
        self._switch_nb('clips')
        self.log(f'✅  Loaded into Clip Finder: {Path(self._last_dl_path).name}', GREEN)
        self.log('Hit ▶ FIND CLIPS to analyze, or 📝 TRANSCRIBE ONLY for a quick tweet.', FG2)

    def _dl_autosave(self, *_):
        # Merge into self.cfg so nothing else gets lost
        self.cfg.update({
            'dl_folder':    self.v_dl_folder.get(),
            'cookies_file': self.v_cookies.get(),
            'dl_quality':   self.v_dl_quality.get(),
            'auto_load':    self.v_auto_load.get(),
        })
        save_cfg(self.cfg)

    def _dl_done_popup(self, filepath):
        # Skip popup when downloading as part of a queue
        if getattr(self, '_in_queue', False):
            self._dl_log_write(f'✅  Saved: {Path(filepath).name}', GREEN)
            return
        dlg.title('Download Complete')
        dlg.configure(bg=BG2)
        dlg.resizable(False, False)
        dlg.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()//2 - 180
        y = self.winfo_y() + self.winfo_height()//2 - 80
        dlg.geometry(f'360x160+{x}+{y}')
        tk.Label(dlg, text='✅  Download Complete', font=('Segoe UI', 11,'bold'),
                 fg=GREEN, bg=BG2).pack(pady=(18,4))
        tk.Label(dlg, text=Path(filepath).name, font=FONT_SMALL, fg=FG2, bg=BG2).pack()
        br = tk.Frame(dlg, bg=BG2); br.pack(pady=18)
        tk.Button(br, text='📂  Open Folder', font=FONT_SMALL, bg=BG3, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=5,
                  command=lambda: (os.startfile(str(Path(filepath).parent)), dlg.destroy())
                  ).pack(side='left', padx=4)
        tk.Button(br, text='▶  Play', font=FONT_SMALL, bg=BG3, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=5,
                  command=lambda: (os.startfile(filepath), dlg.destroy())
                  ).pack(side='left', padx=4)
        tk.Button(br, text='✂  Load in Clip Finder', font=FONT_SMALL,
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=8, pady=5,
                  command=lambda: (self._dl_auto_load(), dlg.destroy())
                  ).pack(side='left', padx=4)

    # ═══════════════════════════════════════════════════════════════════════════
    # END DOWNLOADER TAB
    # ═══════════════════════════════════════════════════════════════════════════


    # ═══════════════════════════════════════════════════════════════════════════
    # THUMBNAIL FINDER TAB  — web image search
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_thumb_tab(self, p):
        # Left = scrollable controls panel, Right = image results
        left_outer = tk.Frame(p, bg=BG, width=300)
        left_outer.pack(side='left', fill='y')
        left_outer.pack_propagate(False)

        # Scrollable left panel
        lcv = tk.Canvas(left_outer, bg=BG, bd=0, highlightthickness=0)
        _make_scrollbar(left_outer, lcv)
        left = tk.Frame(lcv, bg=BG)
        left.bind('<Configure>', lambda e: lcv.configure(scrollregion=lcv.bbox('all')))
        lcv.create_window((0,0), window=left, anchor='nw', tags='linner')
        lcv.bind('<Configure>', lambda e: lcv.itemconfig('linner', width=e.width))
        lcv.bind('<MouseWheel>', lambda e: lcv.yview_scroll(int(-1*(e.delta/120)),'units'))
        lcv.pack(side='left', fill='both', expand=True)

        tk.Frame(p, bg=BORDER, width=1).pack(side='left', fill='y', padx=6)
        right = tk.Frame(p, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        PAD = {'padx': 14}

        def lbl(t, pady=None, **kw):
            pk = {'anchor': 'w', **PAD}
            if pady is not None: pk['pady'] = pady
            tk.Label(left, text=t, bg=BG, **kw).pack(**pk)
        def div():
            tk.Frame(left, bg=BORDER, height=1).pack(fill='x', padx=14, pady=5)
        def sec(t):
            tk.Label(left, text=t, font=('Segoe UI', 9, 'bold'),
                     fg=ACCENT, bg=BG).pack(anchor='w', pady=(8,2), **PAD)

        lbl('THUMBNAIL FINDER', font=('Segoe UI', 11, 'bold'), fg=ACCENT, pady=(12,2))
        lbl('Search the web for HD images of\nany streamer or person',
            font=FONT_SMALL, fg=FG2, justify='left')
        div()

        # Search box
        sec('SEARCH')
        se = tk.Frame(left, bg=BG3, **PAD); se.pack(fill='x', pady=(2,0), padx=14)
        self.thumb_query_var = tk.StringVar()
        te = tk.Entry(se, textvariable=self.thumb_query_var, font=FONT_MONO_S,
                      bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=6)
        te.pack(fill='x', ipady=3)
        te.bind('<Return>', lambda e: self._thumb_start())
        lbl('e.g.  Mizkif  Alinity  Pokimane drama',
            font=FONT_SMALL, fg=FG2, pady=(2,0))
        div()

        # Unsplash key now in Settings tab
        self.thumb_unsplash_var = tk.StringVar(value=self._keys.get('_unsplash',''))
        _unsplash_status = '✅ Unsplash key set' if self._keys.get('_unsplash','').strip() else '⚠️ No Unsplash key — add in ⚙ Settings for better results'
        _uc = ACCENT2 if '⚠' in _unsplash_status else GREEN
        ur_row = tk.Frame(left, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        ur_row.pack(fill='x', padx=14, pady=(0,4))
        tk.Label(ur_row, text=_unsplash_status, font=('Segoe UI',8), fg=_uc, bg=BG2).pack(side='left', padx=8, pady=6)
        tk.Button(ur_row, text='⚙ Settings', font=('Segoe UI',8), bg=BG2, fg=ACCENT2,
                 relief='flat', bd=0, cursor='hand2', padx=8,
                 command=lambda: self._switch_nb('settings')).pack(side='right', padx=6)
        div()

        # Count
        sec('HOW MANY')
        cr = tk.Frame(left, bg=BG); cr.pack(anchor='w', **PAD)
        self.thumb_count_var = tk.IntVar(value=5)
        for n in [3, 5, 8, 10]:
            tk.Radiobutton(cr, text=str(n), variable=self.thumb_count_var, value=n,
                           font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                           activebackground=BG, relief='flat', cursor='hand2'
                           ).pack(side='left', padx=(0,10))
        div()

        # Prefer
        sec('PREFER')
        self.thumb_pref_var = tk.StringVar(value='reaction')
        for val, lbl_text in [('reaction','😮 Reactions / expressions'),
                               ('hd','📸 Highest resolution'),
                               ('drama','🔥 Drama / intense moments')]:
            tk.Radiobutton(left, text=lbl_text, variable=self.thumb_pref_var, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                           activebackground=BG, relief='flat', cursor='hand2'
                           ).pack(anchor='w', padx=14)
        div()

        # Save to
        sec('SAVE FOLDER')
        sf = tk.Frame(left, bg=BG3); sf.pack(fill='x', padx=14, pady=(2,0))
        self.thumb_outdir_var = tk.StringVar(
            value=self.cfg.get('thumb_outdir', str(Path.home() / 'Downloads')))
        tk.Entry(sf, textvariable=self.thumb_outdir_var, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=6
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(sf, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=6,
                  command=self._thumb_pick_outdir).pack(side='right')
        div()

        # Buttons
        self.thumb_go_btn = tk.Button(left, text='🔍  FIND THUMBNAILS',
                                      font=('Segoe UI', 10, 'bold'),
                                      bg=ACCENT, fg='#000', relief='flat', bd=0,
                                      cursor='hand2', pady=10, activebackground=ACCENT2,
                                      command=self._thumb_start)
        self.thumb_go_btn.pack(fill='x', padx=14, pady=(4,4))
        tk.Button(left, text='💾  SAVE ALL HD', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', pady=6,
                  command=self._thumb_save_all).pack(fill='x', padx=14)

        self.thumb_status_lbl = tk.Label(left, text='', font=FONT_SMALL,
                                         fg=FG2, bg=BG, wraplength=265, justify='left')
        self.thumb_status_lbl.pack(anchor='w', padx=14, pady=(8,14))

        # ── Right: results grid ───────────────────────────────────────────────
        rh = tk.Frame(right, bg=BG); rh.pack(fill='x', pady=(10,6), padx=6)
        tk.Label(rh, text='TOP RESULTS', font=('Segoe UI', 9,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        self.thumb_result_count = tk.Label(rh, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self.thumb_result_count.pack(side='left', padx=8)

        gw = tk.Frame(right, bg=BG3); gw.pack(fill='both', expand=True, padx=6)
        gcv = tk.Canvas(gw, bg=BG3, bd=0, highlightthickness=0)
        _make_scrollbar(gw, gcv)
        self.thumb_grid = tk.Frame(gcv, bg=BG3)
        self.thumb_grid.bind('<Configure>',
            lambda e: gcv.configure(scrollregion=gcv.bbox('all')))
        gcv.create_window((0,0), window=self.thumb_grid, anchor='nw', tags='inner')
        gcv.bind('<Configure>', lambda e: gcv.itemconfig('inner', width=e.width))
        gcv.bind('<MouseWheel>', lambda e: gcv.yview_scroll(int(-1*(e.delta/120)),'units'))
        gcv.pack(side='left', fill='both', expand=True)
        self._thumb_show_empty()

    def _thumb_show_empty(self):
        for w in self.thumb_grid.winfo_children():
            w.destroy()
        tk.Label(self.thumb_grid,
                 text='\n  Type a streamer name and click\n  🔍 FIND THUMBNAILS\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=40)

    def _thumb_pick_outdir(self):
        d = filedialog.askdirectory()
        if d:
            self.thumb_outdir_var.set(d)
            self.cfg['thumb_outdir'] = d
            save_cfg(self.cfg)

    def _thumb_set_status(self, msg, color=None):
        def _do():
            try:
                self.thumb_status_lbl.config(text=msg, fg=color or FG2)
            except Exception:
                pass
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self.after(0, _do)

    def _thumb_start(self):
        if self._thumb_running:
            return
        q = self.thumb_query_var.get().strip()
        if not q:
            messagebox.showerror('No search', 'Enter a name or search term.')
            return
        self._thumb_running = True
        self._thumb_results = []
        self._thumb_tk_refs = []
        self.thumb_go_btn.config(state='disabled', text='⏳  Searching...')
        self._thumb_show_empty()
        self._thumb_set_status('Searching...')
        threading.Thread(target=self._thumb_run, daemon=True).start()

    def _thumb_run(self):
        try:
            from PIL import Image
            import requests as _req
            import urllib3; urllib3.disable_warnings()
            import warnings as _warn; _warn.filterwarnings('ignore', category=DeprecationWarning)
            import io, json as _json, re as _re

            query = self.thumb_query_var.get().strip()
            count = self.thumb_count_var.get()
            pref  = self.thumb_pref_var.get()

            pref_suffix = {
                'reaction': 'reaction expression',
                'hd':       'HD',
                'drama':    'drama intense',
            }.get(pref, '')
            full_query = f'{query} {pref_suffix} streamer'

            self._thumb_set_status(f'Searching: "{full_query}"...')
            self.log(f'[Thumbnails] Searching: {full_query}')

            sess = _req.Session()
            sess.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            })

            image_urls = self._thumb_search(sess, full_query, max_results=80)

            if not image_urls:
                raise ValueError('No images found.\n\nTip: Add a free Unsplash API key in the Thumbnails tab for guaranteed results.\nSign up free at unsplash.com/developers')

            self.log(f'[Thumbnails] Got {len(image_urls)} URLs, downloading...')

            scored = []
            ok = 0
            for idx, (img_url, known_w, known_h) in enumerate(image_urls):
                try:
                    self._thumb_set_status(
                        f'Checking image {idx+1}/{len(image_urls)} '
                        f'({ok} good so far)...')
                    resp = sess.get(img_url, timeout=7, verify=False,
                                    stream=True)
                    if resp.status_code != 200:
                        continue
                    data = resp.content
                    if len(data) < 2000:
                        continue
                    img = Image.open(io.BytesIO(data)).convert('RGB')
                    w, h = img.size

                    score = 0.0
                    # 1. Resolution
                    score += min((w * h) / (1920 * 1080), 1.0) * 4.0
                    # 2. Aspect ratio (16:9 ideal)
                    ratio = w / max(h, 1)
                    score += max(0.0, 2.0 - abs(ratio - 1.777) * 2)
                    # 3. Colorfulness
                    import colorsys
                    pixels = list(img.resize((40, 40)).convert("RGB").getdata())
                    sat = sum(colorsys.rgb_to_hsv(px[0]/255,px[1]/255,px[2]/255)[1]
                              for px in pixels) / max(len(pixels),1)
                    score += min(sat * 4, 2.0)
                    # 4. Brightness balance
                    bright = sum(img.convert('L').resize((40,40)).tobytes()) / 1600
                    if 55 < bright < 215:
                        score += 1.0
                    # 5. HD bonus
                    if w >= 1280 and h >= 720:  score += 1.5
                    if w >= 1920 and h >= 1080: score += 1.0

                    scored.append((score, img, img_url, w, h))
                    ok += 1
                except Exception:
                    continue

            self.log(f'[Thumbnails] Loaded {len(scored)} images successfully')
            if not scored:
                raise ValueError('Could not load any images. Try a different search term.')

            scored.sort(key=lambda x: -x[0])
            results = []
            for rank, (score, img, url, w, h) in enumerate(scored[:count]):
                display = img.copy()
                display.thumbnail((400, 230), Image.LANCZOS)
                results.append({
                    'rank': rank+1, 'score': round(score,1),
                    'img': img, 'display': display,
                    'url': url, 'width': w, 'height': h,
                })

            self._thumb_results = results
            self._thumb_set_status(f'Done! Top {len(results)} found.', GREEN)
            self.log(f'[Thumbnails] Done — {len(results)} images ready', GREEN)
            self.after(0, self._thumb_render)

        except Exception:
            err = traceback.format_exc()
            self.log(f'[Thumbnails] Error:\n{err}', RED)
            self._thumb_set_status('Error — check log.', RED)
        finally:
            self._thumb_running = False
            self.after(0, lambda: self.thumb_go_btn.config(
                state='normal', text='🔍  FIND THUMBNAILS'))

    def _thumb_search(self, sess, query, max_results=40):
        import urllib.parse as _up, json as _js, re as _re

        # ── 1. Unsplash API (free 50/hr, best quality) ───────────────────────
        # Try _keys first, then fall back to cfg directly (in case settings tab not opened)
        unsplash_key = (self._keys.get('_unsplash','') or 
                        self.cfg.get('key_unsplash','')).strip()
        if unsplash_key:
            try:
                self.log('[Thumbnails] Trying Unsplash API...')
                # Use original query term only (strip pref suffixes — Unsplash is photos not streamers)
                raw_q = self.thumb_query_var.get().strip()
                r = sess.get('https://api.unsplash.com/search/photos',
                    params={'query': raw_q, 'per_page': max_results,
                            'order_by': 'relevant', 'orientation': 'landscape',
                            'content_filter': 'low'},
                    headers={'Authorization': f'Client-ID {unsplash_key}',
                             'Accept-Version': 'v1'},
                    timeout=10, verify=False)
                self.log(f'[Thumbnails] Unsplash status: {r.status_code}')
                if r.status_code == 200:
                    items = r.json().get('results', [])
                    self.log(f'[Thumbnails] Unsplash results: {len(items)}')
                    results = []
                    for item in items:
                        urls = item.get('urls', {})
                        url  = urls.get('full') or urls.get('regular','')
                        w    = item.get('width', 1920)
                        h    = item.get('height', 1080)
                        if url: results.append((url, w, h))
                    if results: return results[:max_results]
            except Exception as ex:
                self.log(f'[Thumbnails] Unsplash error: {ex}', YELLOW)

        # ── 2. DuckDuckGo (proper session with cookies) ───────────────────────
        try:
            self.log('[Thumbnails] Trying DuckDuckGo...')
            # Warm up session with a real browser visit first
            sess.get('https://duckduckgo.com/', timeout=8, verify=False)
            import time as _t; _t.sleep(0.3)
            r1 = sess.get('https://duckduckgo.com/',
                params={'q': query, 'iax': 'images', 'ia': 'images'},
                timeout=10, verify=False)
            self.log(f'[Thumbnails] DDG html: {r1.status_code}, {len(r1.text)}ch')
            vqd = _re.search(r'vqd=([0-9-]+)', r1.text)
            if not vqd:
                # Try alternate token location
                vqd = _re.search(r'"vqd":"([^"]+)"', r1.text)
            self.log(f'[Thumbnails] DDG vqd: {vqd.group(1) if vqd else "NOT FOUND"}')
            if vqd:
                import time as _t2; _t2.sleep(0.5)
                r2 = sess.get('https://duckduckgo.com/i.js',
                    params={'q': query, 'o': 'json', 'vqd': vqd.group(1),
                            'f': ',,,,,', 'p': '1', 'l': 'wt-wt'},
                    headers={
                        'Referer': 'https://duckduckgo.com/',
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Sec-Fetch-Dest': 'empty',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'same-origin',
                    },
                    timeout=10, verify=False)
                self.log(f'[Thumbnails] DDG api: {r2.status_code}')
                if r2.status_code == 200:
                    items = r2.json().get('results', [])
                    self.log(f'[Thumbnails] DDG results: {len(items)}')
                    results = [(i['image'], i.get('width',1280), i.get('height',720))
                               for i in items if i.get('image')]
                    if results: return results[:max_results]
        except Exception as ex:
            self.log(f'[Thumbnails] DDG error: {ex}', YELLOW)

        # ── 3. Bing (with warmed session) ─────────────────────────────────────
        try:
            self.log('[Thumbnails] Trying Bing...')
            sess.get('https://www.bing.com/', timeout=8, verify=False)
            import time as _t; _t.sleep(0.4)
            r = sess.get('https://www.bing.com/images/search',
                params={'q': query, 'qft': '+filterui:imagesize-large', 'FORM':'IRFLTR'},
                headers={'Referer': 'https://www.bing.com/',
                         'Accept': 'text/html,application/xhtml+xml'},
                timeout=12, verify=False)
            self.log(f'[Thumbnails] Bing: {r.status_code}, {len(r.text)}ch')
            results = []
            # Pattern 1: murl JSON field
            for m in _re.finditer(r'"murl":"(https?://[^"]+)"', r.text):
                url = m.group(1)
                if not any(x in url for x in ['bing.com','microsoft.com','msn.com','th.bing']):
                    results.append((url, 1280, 720))
            # Pattern 2: iurl field (image url)
            for m in _re.finditer(r'"iurl":"(https?://[^"]+)"', r.text):
                url = m.group(1)
                if not any(x in url for x in ['bing.com','microsoft.com','msn.com','th.bing']):
                    results.append((url, 1280, 720))
            # Pattern 3: data-src on img tags
            for m in _re.finditer(r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', r.text):
                url = m.group(1)
                if 'bing' not in url:
                    results.append((url, 1280, 720))
            # Deduplicate
            seen = set(); deduped = []
            for item in results:
                if item[0] not in seen:
                    seen.add(item[0]); deduped.append(item)
            results = deduped
            self.log(f'[Thumbnails] Bing urls found: {len(results)}')
            if results: return results[:max_results]
        except Exception as ex:
            self.log(f'[Thumbnails] Bing error: {ex}', YELLOW)

        # ── 4. Pixabay (scrape) ───────────────────────────────────────────────
        try:
            self.log('[Thumbnails] Trying Pixabay...')
            r = sess.get(f'https://pixabay.com/images/search/{_up.quote(query)}/',
                timeout=12, verify=False)
            self.log(f'[Thumbnails] Pixabay: {r.status_code}, {len(r.text)}ch')
            results = []
            for m in _re.finditer(r'"largeImageURL":"(https?://[^"]+)"', r.text):
                results.append((m.group(1), 1920, 1080))
            for m in _re.finditer(r'"webformatURL":"(https?://[^"]+)"', r.text):
                results.append((m.group(1), 1280, 720))
            self.log(f'[Thumbnails] Pixabay urls: {len(results)}')
            if results: return list(dict.fromkeys(results))[:max_results]
        except Exception as ex:
            self.log(f'[Thumbnails] Pixabay error: {ex}', YELLOW)


        # Try Google Images as last resort
        try:
            self.log('[Thumbnails] Trying Google Images...')
            import urllib.parse as _up2, re as _re2
            _gq = _up2.quote_plus(query)
            _gh = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            _gr = sess.get(f'https://www.google.com/search?q={_gq}&tbm=isch&num=10',
                          headers=_gh, timeout=10, verify=False)
            _gurls = _re2.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', _gr.text)
            _gurls = [u for u in _gurls if len(u) < 300 and 'gstatic' not in u][:max_results]
            self.log(f'[Thumbnails] Google Images: {len(_gurls)} urls')
            for _gu in _gurls:
                try:
                    _ir = sess.get(_gu, timeout=8, verify=False)
                    if _ir.status_code == 200 and len(_ir.content) > 5000:
                        results.append((_gu, 1280, 720))
                        if len(results) >= max_results: break
                except: continue
            if results: return list(dict.fromkeys(results))[:max_results]
        except Exception as _ge:
            self.log(f'[Thumbnails] Google Images error: {_ge}')

        self.log('[Thumbnails] ALL BACKENDS FAILED. Add a free Unsplash key for best results.', RED)
        return []

    def _thumb_render(self):
        from PIL import ImageTk
        for w in self.thumb_grid.winfo_children():
            w.destroy()
        self._thumb_tk_refs = []

        count = len(self._thumb_results)
        self.after(0, lambda: self.thumb_result_count.config(
            text=f'{count} result{"s" if count!=1 else ""} found'))

        for r in self._thumb_results:
            tk_img = ImageTk.PhotoImage(r['display'])
            self._thumb_tk_refs.append(tk_img)  # prevent GC

            card = tk.Frame(self.thumb_grid, bg=BG2,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill='x', padx=6, pady=5)

            # Image
            img_lbl = tk.Label(card, image=tk_img, bg=BG2, cursor='hand2')
            img_lbl.pack(side='left', padx=(8, 10), pady=8)
            img_lbl.bind('<Button-1>',
                lambda e, ri=r: self._thumb_preview(ri))
            # Right-click context menu on image
            def _make_ctx(ri=r):
                m = tk.Menu(self, tearoff=0, bg=BG3, fg=FG,
                            activebackground=ACCENT, activeforeground='#000',
                            font=FONT_SMALL, relief='flat', bd=1)
                m.add_command(label='🔍  Preview full size',
                              command=lambda: self._thumb_preview(ri))
                m.add_command(label='💾  Save HD PNG',
                              command=lambda: self._thumb_save_one(ri))
                m.add_command(label='🌐  Open image URL in browser',
                              command=lambda: __import__('webbrowser').open(ri['url']))
                m.add_separator()
                m.add_command(label='📋  Copy image URL',
                              command=lambda: (self.clipboard_clear(),
                                              self.clipboard_append(ri['url'])))
                return m
            _ctx = _make_ctx()
            img_lbl.bind('<Button-3>',
                lambda e, m=_ctx: m.tk_popup(e.x_root, e.y_root))

            # Info
            info = tk.Frame(card, bg=BG2)
            info.pack(side='left', fill='both', expand=True, pady=8)

            top_row = tk.Frame(info, bg=BG2); top_row.pack(anchor='w')
            rank_col = ACCENT if r['rank'] == 1 else ACCENT2 if r['rank'] <= 3 else FG3
            tk.Label(top_row, text=f'#{r["rank"]}',
                     font=('Segoe UI', 14, 'bold'), fg=rank_col, bg=BG2
                     ).pack(side='left', padx=(0, 8))
            sc = GREEN if r['score'] >= 7 else YELLOW if r['score'] >= 4 else FG3
            tk.Label(top_row, text=f'Score {r["score"]}',
                     font=('Segoe UI', 9, 'bold'), fg=sc, bg=BG2).pack(side='left')

            tk.Label(info, text=f'{r["width"]} × {r["height"]}  px',
                     font=FONT_SMALL, fg=FG2, bg=BG2).pack(anchor='w', pady=(4, 0))

            # Truncated URL
            short_url = r['url'][:70] + '...' if len(r['url']) > 70 else r['url']
            tk.Label(info, text=short_url, font=('Courier New', 7),
                     fg=FG2, bg=BG2, wraplength=380, justify='left').pack(anchor='w')

            btn_row = tk.Frame(info, bg=BG2); btn_row.pack(anchor='w', pady=(8, 0))
            tk.Button(btn_row, text='💾  Save HD',
                      font=FONT_SMALL, bg=ACCENT, fg='#000',
                      relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                      activebackground=ACCENT2,
                      command=lambda ri=r: self._thumb_save_one(ri)
                      ).pack(side='left', padx=(0, 6))
            tk.Button(btn_row, text='🔍  Preview',
                      font=FONT_SMALL, bg=BG3, fg=FG,
                      relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                      command=lambda ri=r: self._thumb_preview(ri)
                      ).pack(side='left', padx=(0, 6))
            tk.Button(btn_row, text='🌐  Open URL',
                      font=FONT_SMALL, bg=BG3, fg=FG,
                      relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                      command=lambda ri=r: __import__('webbrowser').open(ri['url'])
                      ).pack(side='left')

    def _thumb_save_one(self, r):
        out = self.thumb_outdir_var.get().strip() or str(Path.home() / 'Downloads')
        Path(out).mkdir(parents=True, exist_ok=True)
        q   = re.sub(r'[\\/:*?"<>|]', '', self.thumb_query_var.get())[:30]
        fname = f'thumb_{q}_#{r["rank"]}_{r["width"]}x{r["height"]}.png'
        path  = str(Path(out) / fname)
        r['img'].save(path, 'PNG')
        self._thumb_set_status(f'Saved: {fname}', GREEN)
        self.log(f'[Thumbnails] Saved: {fname}', GREEN)

    def _thumb_save_all(self):
        if not self._thumb_results:
            messagebox.showwarning('No results', 'Search for thumbnails first.')
            return
        out = self.thumb_outdir_var.get().strip() or str(Path.home() / 'Downloads')
        Path(out).mkdir(parents=True, exist_ok=True)
        q = re.sub(r'[\\/:*?"<>|]', '', self.thumb_query_var.get())[:30]
        for r in self._thumb_results:
            fname = f'thumb_{q}_#{r["rank"]}_{r["width"]}x{r["height"]}.png'
            r['img'].save(str(Path(out) / fname), 'PNG')
        msg = f'Saved {len(self._thumb_results)} images to:\n{out}'
        self._thumb_set_status(f'Saved {len(self._thumb_results)} images!', GREEN)
        self.log(f'[Thumbnails] Saved all to {out}', GREEN)
        messagebox.showinfo('Saved!', msg)
        try: os.startfile(out)
        except: pass

    def _thumb_preview(self, r):
        win = tk.Toplevel(self)
        win.title(f'Preview #{r["rank"]} — {r["width"]}×{r["height"]}')
        win.configure(bg=BG)
        win.grab_set()
        from PIL import ImageTk
        preview = r['img'].copy()
        preview.thumbnail((1280, 720), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(preview)
        lbl = tk.Label(win, image=tk_img, bg=BG)
        lbl.image = tk_img
        lbl.pack(padx=10, pady=10)
        info_row = tk.Frame(win, bg=BG); info_row.pack(pady=(0, 6))
        tk.Label(info_row, text=f'Original: {r["width"]}×{r["height"]}px',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=8)
        tk.Button(info_row, text='💾 Save HD', font=FONT_SMALL,
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=4, command=lambda: self._thumb_save_one(r)
                  ).pack(side='left', padx=4)
        tk.Button(info_row, text='Close', font=FONT_SMALL, bg=BG3, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                  command=win.destroy).pack(side='left', padx=4)

    # ═══════════════════════════════════════════════════════════════════════════
    # END THUMBNAIL FINDER TAB
    # ═══════════════════════════════════════════════════════════════════════════


    # ═══════════════════════════════════════════════════════════════════════════
    # IMAGE STUDIO TAB — Duplicate Finder + AI Upscaler
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_studio_tab(self, p):
        # ── Top half: two panels side by side ────────────────────────────────
        top = tk.Frame(p, bg=BG)
        top.pack(fill='x', padx=0, pady=0)

        # ── LEFT: Duplicate Finder ────────────────────────────────────────────
        dup = tk.Frame(top, bg=BG2)
        dup.pack(side='left', fill='both', expand=True, padx=(8,0), pady=8)

        tk.Label(dup, text='🔍  DUPLICATE FINDER', font=('Segoe UI', 9,'bold'),
                 fg=ACCENT, bg=BG2).pack(anchor='w', padx=8)
        tk.Label(dup, text='Scan folder for duplicate/similar images and move to /duplicates',
                 font=FONT_SMALL, fg=FG2, bg=BG2).pack(anchor='w', padx=8)

        # Folder row
        sf_row = tk.Frame(dup, bg=BG2); sf_row.pack(fill='x', padx=8, pady=(6,2))
        tk.Label(sf_row, text='Folder:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_scan_folder = tk.StringVar(value=self.cfg.get('scan_folder',''))
        sf_wrap = tk.Frame(sf_row, bg=BG3); sf_wrap.pack(side='left', fill='x', expand=True, padx=(4,0))
        tk.Entry(sf_wrap, textvariable=self.v_scan_folder, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(sf_wrap, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.v_scan_folder.set(
                      filedialog.askdirectory() or self.v_scan_folder.get())
                  ).pack(side='right')

        # Sensitivity row
        sens_row = tk.Frame(dup, bg=BG2); sens_row.pack(fill='x', padx=8, pady=(2,6))
        tk.Label(sens_row, text='Sensitivity:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_dup_sens = tk.StringVar(value='similar')
        for val, lbl in [('exact','Exact only'),('similar','Similar'),('very','Very similar')]:
            tk.Radiobutton(sens_row, text=lbl, variable=self.v_dup_sens, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                           activebackground=BG2, relief='flat', cursor='hand2'
                           ).pack(side='left', padx=(6,0))

        btn_row = tk.Frame(dup, bg=BG2); btn_row.pack(fill='x', padx=8, pady=(0,8))
        self.dup_btn = tk.Button(btn_row, text='🔎  FIND DUPLICATES',
                                 font=('Segoe UI', 9,'bold'), bg=ACCENT, fg='#000',
                                 relief='flat', bd=0, cursor='hand2', padx=14, pady=6,
                                 activebackground=ACCENT2, command=self._studio_find_dupes)
        self.dup_btn.pack(side='left', padx=(0,8))
        tk.Button(btn_row, text='📦 MOVE DUPES TO /duplicates',
                  font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=6,
                  command=self._studio_move_dupes).pack(side='left')

        # ── DIVIDER ───────────────────────────────────────────────────────────
        tk.Frame(top, bg=BORDER, width=1).pack(side='left', fill='y', padx=8)

        # ── RIGHT: AI Upscaler ────────────────────────────────────────────────
        up = tk.Frame(top, bg=BG2)
        up.pack(side='left', fill='both', expand=True, padx=(0,8), pady=8)

        tk.Label(up, text='🔬  AI UPSCALER', font=('Segoe UI', 9,'bold'),
                 fg=ACCENT, bg=BG2).pack(anchor='w', padx=8)
        tk.Label(up, text='Real-ESRGAN · runs locally · no internet after first install',
                 font=FONT_SMALL, fg=FG2, bg=BG2).pack(anchor='w', padx=8)

        # File slots row + scale/output/button side by side
        up_body = tk.Frame(up, bg=BG2); up_body.pack(fill='x', padx=8, pady=(6,0))

        # Slots (left of up_body)
        slots_area = tk.Frame(up_body, bg=BG2)
        slots_area.pack(side='left', fill='x', expand=True)

        slot_hdr = tk.Frame(slots_area, bg=BG2); slot_hdr.pack(fill='x', pady=(0,4))
        tk.Label(slot_hdr, text='Input images (up to 5):', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        tk.Button(slot_hdr, text='📂 Load from folder', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._studio_load_folder).pack(side='left', padx=(8,4))
        tk.Button(slot_hdr, text='🗑 Clear', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._studio_clear_slots).pack(side='left')

        self._up_slots = []
        for i in range(5):
            sr = tk.Frame(slots_area, bg=BG2); sr.pack(fill='x', pady=1)
            tk.Label(sr, text=str(i+1), font=FONT_SMALL, fg=FG2, bg=BG2, width=2).pack(side='left')
            sv = tk.StringVar()
            self._up_slots.append(sv)
            tk.Entry(sr, textvariable=sv, font=FONT_SMALL, bg=BG3, fg=FG,
                     insertbackground=ACCENT, relief='flat', bd=3).pack(side='left', fill='x', expand=True)
            tk.Button(sr, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                      relief='flat', bd=0, cursor='hand2', padx=4,
                      command=lambda s=sv: s.set(
                          filedialog.askopenfilename(
                              filetypes=[('Image','*.png *.jpg *.jpeg *.webp *.bmp'),('All','*.*')]
                          ) or s.get())
                      ).pack(side='right')

        # Right side: scale + output + button
        up_ctrl = tk.Frame(up_body, bg=BG2, padx=12)
        up_ctrl.pack(side='right', fill='y')

        tk.Label(up_ctrl, text='SCALE', font=('Segoe UI', 8,'bold'), fg=ACCENT, bg=BG2).pack(anchor='w')
        self.v_up_scale = tk.IntVar(value=2)
        sf = tk.Frame(up_ctrl, bg=BG2); sf.pack(anchor='w')
        for s in [2, 3, 4]:
            tk.Radiobutton(sf, text=f'{s}×', variable=self.v_up_scale, value=s,
                           font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                           activebackground=BG2, relief='flat', cursor='hand2'
                           ).pack(side='left', padx=(0,4))

        tk.Label(up_ctrl, text='OUTPUT FOLDER', font=('Segoe UI', 8,'bold'),
                 fg=ACCENT, bg=BG2).pack(anchor='w', pady=(8,2))
        self.v_up_out = tk.StringVar(value=self.cfg.get('up_out', str(Path.home()/'Downloads')))
        out_row = tk.Frame(up_ctrl, bg=BG3); out_row.pack(fill='x')
        tk.Entry(out_row, textvariable=self.v_up_out, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4, width=22
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(out_row, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.v_up_out.set(
                      filedialog.askdirectory() or self.v_up_out.get())
                  ).pack(side='right')

        self.up_btn = tk.Button(up_ctrl, text='🔬  UPSCALE',
                                font=('Segoe UI', 9,'bold'), bg=ACCENT, fg='#000',
                                relief='flat', bd=0, cursor='hand2', padx=12, pady=8,
                                activebackground=ACCENT2, command=self._studio_upscale)
        self.up_btn.pack(fill='x', pady=(10,0))

        # ── Results (full width below) ────────────────────────────────────────
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=8)

        rh = tk.Frame(p, bg=BG); rh.pack(fill='x', padx=8, pady=(4,2))
        tk.Label(rh, text='RESULTS', font=('Segoe UI', 8,'bold'), fg=ACCENT, bg=BG).pack(side='left')
        self.studio_result_lbl = tk.Label(rh, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self.studio_result_lbl.pack(side='left', padx=8)
        tk.Button(rh, text='🗑 Clear', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=self._studio_clear_results).pack(side='right')

        rw = tk.Frame(p, bg=BG3); rw.pack(fill='both', expand=True, padx=8, pady=(0,8))
        rcv = tk.Canvas(rw, bg=BG3, bd=0, highlightthickness=0)
        rcv.pack(side='left', fill='both', expand=True)
        _make_scrollbar(rw, rcv)
        
        
        self.studio_results_frame = tk.Frame(rcv, bg=BG3)
        self.studio_results_frame.bind('<Configure>',
            lambda e: rcv.configure(scrollregion=rcv.bbox('all')))
        rcv.create_window((0,0), window=self.studio_results_frame, anchor='nw', tags='sr')
        rcv.bind('<Configure>', lambda e: rcv.itemconfig('sr', width=e.width))
        rcv.bind('<MouseWheel>', lambda e: rcv.yview_scroll(int(-1*(e.delta/120)),'units'))
        tk.Label(self.studio_results_frame,
                 text='\n  Find duplicates or upscale images to see results here.\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=30)


    def _studio_show_empty(self, msg=''):
        for w in self.studio_results_frame.winfo_children(): w.destroy()
        tk.Label(self.studio_results_frame, text=f'\n  {msg}\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=30, padx=10)

    def _studio_clear_results(self):
        self._studio_dupes = []
        self._studio_show_empty('Cleared.')
        self.studio_result_lbl.config(text='')

    def _studio_set_status(self, msg, color=None):
        def _do():
            try:
                if hasattr(self,'studio_status_lbl'): self.studio_status_lbl.config(text=msg, fg=color or FG2)
            except: pass
        if threading.current_thread() is threading.main_thread(): _do()
        else: self.after(0, _do)

    def _studio_set_busy(self, busy):
        state = 'disabled' if busy else 'normal'
        for b in [getattr(self,x,None) for x in ("studio_dupe_btn","studio_move_btn","studio_upscale_btn") if hasattr(self,x)]:
            try: b.config(state=state)
            except: pass

    # ── Duplicate Finder ──────────────────────────────────────────────────────

    def _studio_load_folder(self):
        """Load up to 5 images from a folder into the upscaler slots."""
        folder = filedialog.askdirectory(title='Select folder with images')
        if not folder: return
        exts = {'.png','.jpg','.jpeg','.webp','.bmp','.tiff'}
        files = sorted([f for f in Path(folder).iterdir()
                        if f.suffix.lower() in exts])[:5]
        for i, sv in enumerate(self._up_slots):
            sv.set(str(files[i]) if i < len(files) else '')

    def _studio_clear_slots(self):
        for sv in self._up_slots:
            sv.set('')

    def _studio_find_dupes(self):
        if self._studio_running: return
        folder = self.v_scan_folder.get().strip()
        if not folder or not Path(folder).exists():
            messagebox.showerror('No folder', 'Select a folder to scan.')
            return
        self._studio_running = True
        self._studio_set_busy(True)
        self._studio_set_status('Scanning...')
        self._studio_show_empty('Scanning...')
        threading.Thread(target=self._studio_run_dupes, args=(folder,), daemon=True).start()

    def _studio_run_dupes(self, folder):
        try:
            try:
                _ih = _fresh_import('imagehash')
            except ImportError:
                raise ImportError('imagehash not installed. Go to Settings → Update Modules to install it.')
            from PIL import Image as _Img

            sens = self.v_dup_sens.get()
            threshold = {'exact': 0, 'similar': 8, 'very': 15}.get(sens, 8)
            img_exts  = {'.jpg','.jpeg','.png','.bmp','.webp','.gif','.tiff'}

            self.log(f'[Studio] Scanning {folder} for duplicates...')
            self._studio_set_status('Collecting images...')

            paths = [p for p in Path(folder).rglob('*') if p.suffix.lower() in img_exts]
            self.log(f'[Studio] Found {len(paths)} images')

            if not paths:
                self._studio_set_status('No images found in folder.')
                return

            # Hash all images
            hashes = {}
            for i, path in enumerate(paths):
                self._studio_set_status(f'Hashing {i+1}/{len(paths)}: {path.name}')
                try:
                    img  = _Img.open(path)
                    h    = _ih.phash(img)
                    hashes[path] = h
                except Exception:
                    continue

            # Group by similarity
            self._studio_set_status('Comparing hashes...')
            groups = []
            visited = set()
            path_list = list(hashes.keys())

            for i, p1 in enumerate(path_list):
                if p1 in visited: continue
                group = [p1]
                visited.add(p1)
                for p2 in path_list[i+1:]:
                    if p2 in visited: continue
                    diff = hashes[p1] - hashes[p2]
                    if diff <= threshold:
                        group.append(p2)
                        visited.add(p2)
                if len(group) > 1:
                    # Sort by file size desc — keep the biggest (best quality)
                    group.sort(key=lambda p: p.stat().st_size, reverse=True)
                    groups.append(group)

            self._studio_dupes = groups
            total_dupes = sum(len(g)-1 for g in groups)
            self.log(f'[Studio] Found {len(groups)} duplicate groups, {total_dupes} files to remove', GREEN)
            self._studio_set_status(f'Done! {len(groups)} groups, {total_dupes} duplicates found.', GREEN)
            self.after(0, lambda: self._studio_render_dupes(groups))

        except Exception:
            err = traceback.format_exc()
            self.log(f'[Studio] Dupe error:\n{err}', RED)
            self._studio_set_status('Error — check log.', RED)
        finally:
            self._studio_running = False
            self.after(0, lambda: self._studio_set_busy(False))

    def _studio_render_dupes(self, groups):
        from PIL import Image as _Img, ImageTk as _ITk
        for w in self.studio_results_frame.winfo_children(): w.destroy()
        if not groups:
            self._studio_show_empty('No duplicates found!')
            self.studio_result_lbl.config(text='No duplicates found')
            return

        total_dupes = sum(len(g)-1 for g in groups)
        self.studio_result_lbl.config(text=f'{len(groups)} groups · {total_dupes} duplicates')

        # Keep tk image refs alive
        if not hasattr(self, '_studio_tk_imgs'):
            self._studio_tk_imgs = []
        self._studio_tk_imgs.clear()

        for gi, group in enumerate(groups):
            card = tk.Frame(self.studio_results_frame, bg=BG2,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill='x', padx=6, pady=4)

            # Header row
            hdr = tk.Frame(card, bg=BG2); hdr.pack(fill='x', padx=8, pady=(6,4))
            tk.Label(hdr, text=f'Group #{gi+1}',
                     font=('Segoe UI', 9,'bold'), fg=ACCENT, bg=BG2).pack(side='left')
            tk.Label(hdr, text=f'  {len(group)} files  ({len(group)-1} duplicate{"s" if len(group)>2 else ""})',
                     font=FONT_SMALL, fg=YELLOW, bg=BG2).pack(side='left')
            # Open folder button
            first_path = group[0]
            tk.Button(hdr, text='📂', font=FONT_SMALL, bg=BG2, fg=FG2,
                      relief='flat', bd=0, cursor='hand2',
                      command=lambda p=first_path: os.startfile(str(p.parent))
                      ).pack(side='right', padx=4)

            # Thumbnail strip
            thumb_row = tk.Frame(card, bg=BG2); thumb_row.pack(fill='x', padx=8, pady=(0,6))
            for fi, fpath in enumerate(group):
                col = tk.Frame(thumb_row, bg=BG3 if fi==0 else BG2, padx=4, pady=4)
                col.pack(side='left', padx=(0,6))

                # Thumbnail
                try:
                    img = _Img.open(fpath)
                    img.thumbnail((100, 70), _Img.LANCZOS)
                    tk_img = _ITk.PhotoImage(img)
                    self._studio_tk_imgs.append(tk_img)
                    lbl_img = tk.Label(col, image=tk_img, bg=col.cget('bg'), cursor='hand2')
                    lbl_img.pack()
                    lbl_img.bind('<Button-1>', lambda e, p=fpath: os.startfile(str(p)))
                except Exception:
                    tk.Label(col, text='?', font=FONT_SMALL, fg=FG2,
                             bg=col.cget('bg'), width=10, height=4).pack()

                badge = '✅ KEEP' if fi==0 else '🗑 DUPE'
                badge_col = GREEN if fi==0 else RED
                tk.Label(col, text=badge, font=('Segoe UI', 7,'bold'),
                         fg=badge_col, bg=col.cget('bg')).pack()
                try:
                    size_kb = fpath.stat().st_size // 1024
                    size_str = f'{size_kb:,} KB'
                except: size_str = '?'
                tk.Label(col, text=fpath.name[:18]+'..' if len(fpath.name)>18 else fpath.name,
                         font=('Segoe UI', 7), fg=FG if fi==0 else FG2,
                         bg=col.cget('bg'), wraplength=100).pack()
                tk.Label(col, text=size_str, font=('Segoe UI', 7),
                         fg=FG2, bg=col.cget('bg')).pack()

    def _studio_move_dupes(self):
        if not self._studio_dupes:
            messagebox.showwarning('No results', 'Run FIND DUPLICATES first.')
            return
        folder = self.v_scan_folder.get().strip()
        dupes_dir = Path(folder) / 'duplicates'
        dupes_dir.mkdir(exist_ok=True)
        moved = 0
        for group in self._studio_dupes:
            for fpath in group[1:]:  # skip first (keep the best)
                try:
                    dest = dupes_dir / fpath.name
                    # Handle name collisions
                    if dest.exists():
                        dest = dupes_dir / f'{fpath.stem}_{fpath.stat().st_size}{fpath.suffix}'
                    fpath.rename(dest)
                    moved += 1
                except Exception as ex:
                    self.log(f'[Studio] Could not move {fpath.name}: {ex}', RED)
        self.log(f'[Studio] Moved {moved} duplicates to {dupes_dir}', GREEN)
        self._studio_set_status(f'Moved {moved} duplicates to /duplicates folder!', GREEN)
        # Update result label but keep cards visible
        self.studio_result_lbl.config(text=f'✅ Moved {moved} dupes → /duplicates')
        self._studio_dupes = []
        ans = messagebox.askyesno('Done!',
            f'Moved {moved} duplicate files to:\n{dupes_dir}\n\nOpen the duplicates folder?')
        if ans:
            try: os.startfile(str(dupes_dir))
            except: pass

    def _studio_load_from_folder(self):
        """Pick a folder and auto-fill the 5 upscale slots with first 5 images found."""
        folder = filedialog.askdirectory(title='Select folder with images')
        if not folder: return
        img_exts = {'.jpg','.jpeg','.png','.bmp','.webp','.tiff'}
        imgs = [str(p) for p in sorted(Path(folder).iterdir())
                if p.suffix.lower() in img_exts][:5]
        for i, var in enumerate(self._up_slots):
            var.set(imgs[i] if i < len(imgs) else '')
        self._studio_set_status(f'Loaded {len(imgs)} images from folder.')

    # ── Upscaler ──────────────────────────────────────────────────────────────
    def _studio_upscale(self):
        if self._studio_running: return
        files = [v.get().strip() for v in self._up_slots if v.get().strip()]
        if not files:
            messagebox.showerror('No files', 'Add at least one image to upscale.')
            return
        missing = [f for f in files if not Path(f).exists()]
        if missing:
            messagebox.showerror('Not found', f'File not found:\n{missing[0]}')
            return
        out_dir = self.v_up_out.get().strip()
        if not out_dir:
            messagebox.showerror('No output', 'Select an output folder.')
            return
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        scale = self.v_up_scale.get()
        self._studio_running = True
        self._studio_set_busy(True)
        self._studio_set_status(f'Starting upscale (×{scale}) for {len(files)} image(s)...')
        self._studio_show_empty(f'Upscaling {len(files)} image(s) at ×{scale}...\nThis may take a minute per image on CPU.')
        threading.Thread(target=self._studio_run_upscale,
                         args=(files, scale, out_dir), daemon=True).start()

    def _studio_run_upscale(self, files, scale, out_dir):
        try:
            import urllib.request as _ur
            import warnings as _w; _w.filterwarnings('ignore')

            # ── Ensure opencv-contrib installed (has dnn_superres) ────────────
            self._studio_set_status('Checking dependencies...')
            self.log('[Studio] Checking opencv-contrib-python...')
            try:
                _cv2 = _fresh_import('cv2')
                _cv2.dnn_superres.DnnSuperResImpl_create()
            except Exception:
                self.log('[Studio] Installing opencv-contrib-python (one time)...', YELLOW)
                self._studio_set_status('Installing opencv-contrib (one time ~50MB)...')
                subprocess.check_call([_get_pip_executable(), '-m', 'pip', 'install',
                                       'opencv-contrib-python', '--upgrade'])
                _cv2 = _fresh_import('cv2')
            _cv2 = _fresh_import('cv2')
            from PIL import Image as _Img
            import numpy as _np
            self.log('[Studio] Dependencies OK', GREEN)

            # ── Download SR model if needed ───────────────────────────────────
            model_dir = _app_path('sr_models')
            model_dir.mkdir(exist_ok=True)

            # Try EDSR first (best quality), then FSRCNN (faster)
            candidates = [
                (f'EDSR_x{scale}.pb', 'EDSR', scale,
                 f'https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x{scale}.pb'),
                (f'FSRCNN_x{scale}.pb', 'FSRCNN', scale,
                 f'https://github.com/nicehuster/cnn-facial-landmark/raw/master/FSRCNN_x{scale}.pb'),
                (f'ESPCN_x{scale}.pb', 'ESPCN', scale,
                 f'https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x{scale}.pb'),
            ]
            model_path = None; model_name_used = None
            for fname, mname, mscale, url in candidates:
                dest = model_dir / fname
                if not dest.exists():
                    self.log(f'[Studio] Downloading {fname}...')
                    self._studio_set_status(f'Downloading {fname} (one time)...')
                    try:
                        _ur.urlretrieve(url, str(dest))
                    except Exception as ex:
                        self.log(f'[Studio] Download failed: {ex}', YELLOW)
                        if dest.exists(): dest.unlink()
                        continue
                if dest.exists() and dest.stat().st_size > 5000:
                    model_path = str(dest); model_name_used = mname; break

            if not model_path:
                raise RuntimeError('Could not download any SR model. Check internet connection.')

            # ── Load model ────────────────────────────────────────────────────
            self._studio_set_status(f'Loading {model_name_used} x{scale} model...')
            self.log(f'[Studio] Model: {model_name_used} x{scale}')
            sr = _cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(model_path)
            sr.setModel(model_name_used.lower(), scale)

            # ── Upscale each file ─────────────────────────────────────────────
            results_info = []
            for i, fpath in enumerate(files):
                self._studio_set_status(f'Upscaling {i+1}/{len(files)}: {Path(fpath).name}...')
                self.log(f'[Studio] Processing: {Path(fpath).name}')
                try:
                    img = _cv2.imread(fpath)
                    if img is None:
                        pil = _Img.open(fpath).convert('RGB')
                        img = _np.array(pil)[:, :, ::-1]
                    h_in, w_in = img.shape[:2]
                    output = sr.upsample(img)
                    h_out, w_out = output.shape[:2]
                    out_name = f'{Path(fpath).stem}_x{scale}_{model_name_used}.png'
                    out_path = str(Path(out_dir) / out_name)
                    _cv2.imwrite(out_path, output)
                    self.log(f'[Studio] Saved: {out_name} ({w_in}x{h_in}→{w_out}x{h_out})', GREEN)
                    results_info.append({'name': out_name, 'path': out_path,
                                         'in_w': w_in, 'in_h': h_in,
                                         'out_w': w_out, 'out_h': h_out, 'ok': True})
                except Exception as ex:
                    self.log(f'[Studio] Failed {Path(fpath).name}: {ex}', RED)
                    results_info.append({'name': Path(fpath).name, 'ok': False, 'error': str(ex)})

            ok = sum(1 for r in results_info if r['ok'])
            self._studio_set_status(f'Done! {ok}/{len(files)} upscaled.', GREEN)
            self.log(f'[Studio] Complete: {ok}/{len(files)}', GREEN)
            self.after(0, lambda: self._studio_render_upscale_results(results_info, out_dir))

        except Exception:
            err = traceback.format_exc()
            self.log(f'[Studio] Upscale error:\n{err}', RED)
            self._studio_set_status('Error — check log.', RED)
        finally:
            self._studio_running = False
            self.after(0, lambda: self._studio_set_busy(False))

    def _studio_render_upscale_results(self, results, out_dir):
        for w in self.studio_results_frame.winfo_children(): w.destroy()
        ok = sum(1 for r in results if r['ok'])
        self.studio_result_lbl.config(text=f'{ok}/{len(results)} upscaled successfully')

        for r in results:
            card = tk.Frame(self.studio_results_frame, bg=BG2,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill='x', padx=6, pady=4)
            inner = tk.Frame(card, bg=BG2); inner.pack(fill='x', padx=10, pady=8)
            top   = tk.Frame(inner, bg=BG2); top.pack(fill='x')
            if r['ok']:
                tk.Label(top, text='✅', font=('Segoe UI', 12), fg=GREEN, bg=BG2).pack(side='left', padx=(0,6))
                tk.Label(top, text=r['name'], font=('Segoe UI', 9,'bold'), fg=FG, bg=BG2).pack(side='left')
                tk.Label(inner, text=f'{r["in_w"]}×{r["in_h"]}  →  {r["out_w"]}×{r["out_h"]}',
                         font=FONT_SMALL, fg=FG2, bg=BG2).pack(anchor='w', pady=(2,4))
                btn_r = tk.Frame(inner, bg=BG2); btn_r.pack(anchor='w')
                tk.Button(btn_r, text='📂 Open folder', font=FONT_SMALL, bg=BG3, fg=FG,
                          relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                          command=lambda d=out_dir: os.startfile(d)
                          ).pack(side='left', padx=(0,6))
                tk.Button(btn_r, text='🖼 Open image', font=FONT_SMALL, bg=BG3, fg=FG,
                          relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                          command=lambda p=r['path']: os.startfile(p)
                          ).pack(side='left')
            else:
                tk.Label(top, text='❌', font=('Segoe UI', 12), fg=RED, bg=BG2).pack(side='left', padx=(0,6))
                tk.Label(top, text=r['name'], font=('Segoe UI', 9,'bold'), fg=FG2, bg=BG2).pack(side='left')
                tk.Label(inner, text=r.get('error','Unknown error'),
                         font=FONT_SMALL, fg=RED, bg=BG2, wraplength=450, justify='left').pack(anchor='w')

        tk.Button(self.studio_results_frame, text=f'📂  Open Output Folder',
                  font=FONT_SMALL, bg=ACCENT, fg='#000', relief='flat', bd=0,
                  cursor='hand2', pady=6, activebackground=ACCENT2,
                  command=lambda: os.startfile(out_dir)
                  ).pack(fill='x', padx=6, pady=(6,8))

    # ═══════════════════════════════════════════════════════════════════════════
    # END IMAGE STUDIO TAB
    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # AUTO EDIT ENGINE
    # ═══════════════════════════════════════════════════════════════════════════

    def _run_auto_edit(self):
        try:
            vid = self.v_video.get()
            out = self.v_outdir.get()
            ff  = ensure_ffmpeg()

            # ── Step 1: Transcribe ────────────────────────────────────────────
            whisper_model = self.v_whisper.get()
            if whisper_model in ('auto', ''):
                whisper_model = 'base'
            self.set_progress(f'Transcribing [{whisper_model}]...', step=1, total=4)
            self.log(f'Auto Edit: transcribing [{whisper_model}]...')

            _ctx_ae = self.v_context.get('1.0','end').strip() if hasattr(self,'v_context') else ''
            if _ctx_ae:
                self.log('Using context as Whisper initial prompt')

            self.ticker_on = True
            def ae_tick():
                import time; d = 0
                while self.ticker_on:
                    d = (d%5)+1
                    self.after(0, lambda x=d: self.v_status.set(
                        f'Transcribing [{whisper_model}]'+'.'*x))
                    time.sleep(1)
            threading.Thread(target=ae_tick, daemon=True).start()

            def _ae_progress_cb(pct, msg):
                self.after(0, lambda p=pct, m=msg:
                    self.set_progress(m, step=1, total=4, pct=p))
                self.after(0, lambda m=msg: self.v_status.set(m))

            result = _do_transcribe(vid, whisper_model,
                                    initial_prompt=_ctx_ae or None,
                                    ffmpeg_path=ff,
                                    progress_cb=_ae_progress_cb)
            self.ticker_on = False
            self._whisper_segments = result.get('segments', [])
            segs_raw = self._whisper_segments
            transcript_lines = [f'[{ts(seg["start"])}] {seg["text"].strip()}' for seg in segs_raw]
            self.transcript = '\n'.join(transcript_lines)
            self.srt_result  = result
            self.log(f'Transcription done: {len(segs_raw)} segments', GREEN)

            # ── Step 2: AI selects segments ───────────────────────────────────
            self.set_progress('Auto Edit 2/4 — AI selecting segments...')
            try:
                target_min = float(self.auto_max_min.get())
            except Exception:
                target_min = 0  # 0 = auto-scale

            # Auto-scale formula based on video duration
            _cv2tmp = _fresh_import('cv2')
            cap_tmp = _cv2tmp.VideoCapture(vid)
            vid_dur_sec = cap_tmp.get(_cv2tmp.CAP_PROP_FRAME_COUNT) / max(cap_tmp.get(_cv2tmp.CAP_PROP_FPS) or 30, 1)
            cap_tmp.release()
            vid_dur_min = vid_dur_sec / 60
            self.log(f'Auto Edit: video duration ~{vid_dur_min:.1f} min')

            if target_min <= 0:
                # Auto-scale: derive target from video length
                if vid_dur_min >= 50:
                    target_min = 15.0
                elif vid_dur_min >= 30:
                    target_min = 10.0
                elif vid_dur_min >= 20:
                    target_min = 7.0
                elif vid_dur_min >= 10:
                    target_min = 4.0
                elif vid_dur_min >= 3:
                    target_min = 1.5
                else:
                    target_min = max(vid_dur_min * 0.4, 0.5)
                self.log(f'Auto-scaled target: {target_min:.1f} min from {vid_dur_min:.1f} min video')
            else:
                # User-specified target — warn if too large
                if target_min >= vid_dur_min:
                    target_min = vid_dur_min * 0.5
                    self.log(f'Target capped to {target_min:.1f} min (50% of video)', YELLOW)

            target_sec = int(target_min * 60)
            self.log(f'Target: {target_min:.1f} min ({target_sec}s)')
            _order_mode = self.auto_order.get()
            if _order_mode == 'viral':
                order_str  = 'score descending — highest viral/drama potential first'
                score_desc = 'viral potential: callouts, confessions, arguments, shocking moments'
            elif _order_mode == 'pointed':
                order_str  = 'score descending — most relevant/explanatory segments first'
                score_desc = 'clarity and relevance: how well the segment explains the core topic, delivers the key argument, or summarizes what the video is about'
            else:
                order_str  = 'start time ascending — chronological order'
                score_desc = 'overall quality and importance'
            # min segment = 10% of target or 45s, whichever is larger
            min_seg_sec = max(45, int(target_sec * 0.10))
            _ctx_raw = self.v_context.get('1.0','end').strip() if hasattr(self,'v_context') else ''
            _ctx_block = f'VIDEO CONTEXT: {_ctx_raw}\n' if _ctx_raw else ''
            # Free models have small context windows — truncate smartly
            # Keep first 60% and last 40% so we capture both start and end of video
            tr = self.transcript
            # Provider-aware context limit for auto edit
            _ae_prov = self.v_provider.get()
            if 'gemini' in _ae_prov.lower():
                max_chars = 500000  # Gemini 1M token context
            elif 'groq' in _ae_prov.lower():
                max_chars = 80000   # Groq 128k context
            else:
                max_chars = 8000    # OpenRouter free

            if len(tr) > max_chars:
                # Keep first 40%, middle 20%, last 40% to represent full video
                a = int(max_chars * 0.40)
                b = int(max_chars * 0.20)
                c = max_chars - a - b
                mid_start = len(tr)//2 - b//2
                tr = (tr[:a]
                      + f'\n[...{len(tr)//1000}k chars omitted for context limit...]\n'
                      + tr[mid_start:mid_start+b]
                      + '\n[...]\n'
                      + tr[-c:])
                self.log(f'Transcript truncated: {len(tr):,} chars for {_ae_prov}', YELLOW)
            else:
                self.log(f'Full transcript: {len(tr):,} chars for {_ae_prov}')
            prompt = AUTO_EDIT_PROMPT.replace('{transcript}', tr)\
                                     .replace('{target_sec}', str(target_sec))\
                                     .replace('{target_min}', f'{target_min:.1f}')\
                                     .replace('{min_seg_sec}', str(min_seg_sec))\
                                     .replace('{score_desc}', score_desc)\
                                     .replace('{order}', order_str)\
                                     .replace('{context_block}', _ctx_block)
            self.log(f'Prompt length: {len(prompt)} chars')

            self.log(f'Auto Edit: asking AI to select segments for {target_min}min edit...')
            def _is_rate(e):
                s = str(e).lower()
                return any(x in s for x in ['429','503','rate','quota','resource_exhausted',
                                             'temporarily','unavailable','overloaded','capacity'])

            def _is_access_denied(e):
                s = str(e).lower()
                return any(x in s for x in ['403','access denied','forbidden','unauthorized'])

            segments = []
            keyed_provs = [p for p in [self.v_provider.get()] +
                           list(PROVIDERS.keys()) if self._keys.get(p,'').strip()]
            self.log(f'Trying {len(keyed_provs)} provider(s)...')
            for prov in keyed_provs:
                try:
                    self.log(f'Sending to {prov}...')
                    segments = self._call_provider_prompt(prov, prompt)
                    if segments:
                        self.log(f'AI segments: {len(segments)} selected by {prov}', GREEN)
                        break
                    else:
                        self.log(f'{prov} returned empty, trying next...', YELLOW)
                except Exception as ex:
                    err_str = str(ex)
                    if _is_rate(ex):
                        self.log(f'{prov} rate-limited, trying next...', YELLOW)
                    elif '403' in err_str:
                        self.log(f'{prov} 403 access denied — check key or disable VPN', YELLOW)
                    elif '400' in err_str:
                        self.log(f'{prov} 400 bad request — prompt too long, trying next...', YELLOW)
                    elif '401' in err_str:
                        self.log(f'{prov} 401 unauthorized — API key invalid', YELLOW)
                    else:
                        self.log(f'{prov} failed: {err_str[:120]}', RED)
                    continue

            if not segments:
                raise ValueError(
                    f'No provider returned segments.\n'
                    f'Tried: {", ".join(keyed_provs)}\n'
                    f'If Groq shows 403: disable VPN or check Groq dashboard.\n'
                    f'If OpenRouter shows 400: video may be too long for free model context.')

            # ── Step 3: Validate + enforce target duration ────────────────────
            self.set_progress('Validating segments...', step=3, total=4)
            def _s2sec(t):
                try:
                    p=t.split(':'); return int(p[0])*3600+int(p[1])*60+float(p[2])
                except: return 0

            # Sort by order pref
            if self.auto_order.get() == 'viral':
                try: segments.sort(key=lambda c: -int(c.get('score',5)))
                except: pass
            else:
                try: segments.sort(key=lambda c: _s2sec(c.get('start','0:0:0')))
                except: pass

            # Trim segment list to fit inside target_sec
            kept = []
            total = 0.0
            min_seg = max(30, int(target_sec * 0.08))  # min 30s per segment
            for seg in segments:
                start_s = _s2sec(seg.get('start','0:0:0'))
                end_s   = _s2sec(seg.get('end','0:0:0'))
                dur = end_s - start_s
                if dur < 10: continue  # skip bogus
                # Extend if too short
                if dur < min_seg:
                    end_s = start_s + min_seg
                    seg['end'] = ts(end_s)
                    seg['end'] = self._snap_to_segment(seg['end'], snap='end')
                    dur = _s2sec(seg['end']) - start_s
                # Snap boundaries
                seg['start'] = self._snap_to_segment(seg['start'], snap='start')
                seg['end']   = self._snap_to_segment(seg['end'],   snap='end')
                # Extend end to nearest complete sentence within 3s
                end_sec = _s2sec(seg['end'])
                for wseg in self._whisper_segments:
                    if 0 < wseg['end'] - end_sec < 3.0:
                        seg['end'] = ts(wseg['end'] + 0.25)
                        break
                dur = _s2sec(seg['end']) - _s2sec(seg['start'])
                # Keep adding until we hit target (allow 10% over)
                if total < target_sec:
                    kept.append(seg)
                    total += dur
            if not kept:
                kept = segments  # fallback — use all

            total_min = total / 60
            self.log(f'Auto Edit: {len(kept)} segments, ~{total_min:.1f}min total', GREEN)

            # ── Step 4: Export ────────────────────────────────────────────────
            self.set_progress('Exporting clips...', step=4, total=4)
            base   = Path(vid).stem
            Path(out).mkdir(parents=True, exist_ok=True)
            seg_files = []  # for concat

            # Determine if we need individual files (either to keep or for concat)
            need_segs = self.auto_export_segs.get() or self.auto_export_final.get()
            tmp_seg_files = []  # temp files created just for concat (deleted after)

            if need_segs:
                self.log('Exporting segments...')
                for i, seg in enumerate(kept):
                    title = re.sub(r'[\\/:*?"<>|\']','',seg.get('title','segment'))[:30]
                    fname = f'{title} - ClipFinder - Part {i+1:02d}.mp4'
                    dest  = str(Path(out)/fname)
                    _vcodec, _acodec, _extra = get_encoder(ff)
                    _hw_args = []
                    if _vcodec == 'h264_amf':   _hw_args = ['-hwaccel','auto']
                    elif _vcodec == 'h264_nvenc': _hw_args = ['-hwaccel','cuda','-hwaccel_output_format','cuda']
                    elif _vcodec == 'h264_qsv':  _hw_args = ['-hwaccel','qsv']
                    # Use edited timestamps if user changed them in the UI
                    exp_start = seg['_sv'].get() if '_sv' in seg else seg['start']
                    exp_end   = seg['_ev'].get() if '_ev' in seg else seg['end']
                    exp_title = seg['_name_var'].get() if '_name_var' in seg else title
                    if exp_title != title:
                        _st = re.sub(r'[\\/:*?"<>|\']', '', exp_title)[:30]
                        fname = f'{_st} - ClipFinder - Part {i+1:02d}.mp4'
                        dest  = str(Path(out)/fname)
                    r = subprocess.run(
                        [ff,'-y']+_hw_args+['-ss',exp_start,'-to',exp_end,'-i',vid,
                         '-c:v',_vcodec,'-c:a',_acodec]+_extra+[dest],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if r.returncode == 0:
                        seg_files.append(dest)
                        if self.auto_export_segs.get():
                            self.log(f'  ✅ {fname}', GREEN)
                        else:
                            tmp_seg_files.append(dest)  # mark for cleanup
                    else:
                        self.log(f'  ❌ {fname}: {(r.stderr or b'').decode(errors='replace')[-80:]}', RED)

            # Export stitched final edit
            if self.auto_export_final.get() and seg_files:
                self.log('Stitching final edit...')
                # Write ffmpeg concat list — use output folder to avoid temp path issues
                concat_list_path = Path(out) / 'cf_concat_list.txt'
                concat_lines = []
                for sf in seg_files:
                    # ffmpeg concat format: backslashes must be forward, 
                    # single quotes escaped as \' inside the quoted path
                    safe = str(sf).replace('\\', '/')
                    # For paths with apostrophes, use double-quote format instead
                    if "'" in safe:
                        concat_lines.append(f'file "{safe}"')
                    else:
                        concat_lines.append(f"file '{safe}'")
                concat_list_path.write_text('\n'.join(concat_lines), encoding='utf-8')
                # Log first line so we can verify format
                self.log(f'Concat list sample: {concat_lines[0] if concat_lines else "empty"}')
                self.log(f'Concat list: {concat_list_path} ({len(concat_lines)} files)')

                final_name = f'{base}_auto_FINAL_{total_min:.1f}min.mp4'
                final_dest = str(Path(out) / final_name)
                _vcodec, _acodec, _extra = get_encoder(ff)
                _hw_args = ['-hwaccel','auto'] if _vcodec == 'h264_amf' else []
                r = subprocess.run(
                    [ff,'-y']+_hw_args+['-f','concat','-safe','0',
                     '-i', str(concat_list_path),
                     '-c:v',_vcodec,'-c:a',_acodec]+_extra+[final_dest],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if r.returncode == 0:
                    self.log(f'✅ Final edit: {final_name}', GREEN)
                else:
                    self.log(f'❌ Concat failed: {(r.stderr or b'').decode(errors='replace')[-200:]}', RED)
                try: concat_list_path.unlink()
                except: pass
                # Remove temp segment files if user only wanted the final edit
                for tmp_f in tmp_seg_files:
                    try: Path(tmp_f).unlink()
                    except: pass

            # Attach StringVars so clip cards render properly
            for seg in kept:
                if '_sv' not in seg:
                    seg['_sv'] = tk.StringVar(value=seg.get('start','00:00:00'))
                if '_ev' not in seg:
                    seg['_ev'] = tk.StringVar(value=seg.get('end','00:01:00'))
                if '_name_var' not in seg:
                    safe = re.sub(r'[\\/:*?"<>|\']','',seg.get('title','segment'))[:40]
                    seg['_name_var'] = tk.StringVar(value=safe)

            exported_count = len(seg_files)
            self.clips = kept
            self.set_progress(f'Auto Edit done! {exported_count} clips exported')
            self.log(f'Auto Edit complete! {exported_count} clips saved to {out}', GREEN)
            self.after(0, self._render_clips)
            self.after(0, lambda: self._switch_nb('clips'))
            self.after(0, lambda: messagebox.showinfo('Auto Edit Done',
                f'{exported_count} clips exported\n'
                f'Total: ~{total_min:.1f} min\n'
                f'Saved to: {out}'))

        except Exception:
            err = traceback.format_exc()
            self.log(f'Auto Edit error:\n{err}', RED)
        finally:
            self.running = False
            self.ticker_on = False
            self.after(0, lambda: self.set_busy(False))

    def _call_provider_prompt(self, prov_name, prompt):
        """Call a provider with a raw prompt instead of the transcript template."""
        import json as _j
        raw = self._call_provider_raw(prov_name, prompt)
        # Parse JSON from response
        raw = raw.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'): raw = raw[4:]
        raw = raw.strip().strip('`').strip()
        try:
            data = _j.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            import re as _r
            m = _r.search(r'\[.*\]', raw, _r.DOTALL)
            if m:
                try: return _j.loads(m.group(0))
                except: pass
        return []

    def _call_provider_raw(self, prov_name, prompt):
        """Send a raw prompt to a provider and return text response."""
        key = self._keys.get(prov_name, '').strip()
        if not key:
            raise ValueError(f'No key for {prov_name}')
        # Clean prompt — remove any null bytes or control chars that cause 400s
        prompt = prompt.replace('\x00', '').replace('\r', ' ')
        # Truncate if too long (OpenRouter free models have small context windows)
        if len(prompt) > 12000:
            # Keep the instructions and truncate the transcript portion
            mid = prompt.find('TRANSCRIPT:')
            if mid != -1:
                header = prompt[:mid + 12]
                transcript_part = prompt[mid + 12:]
                max_transcript = 12000 - len(header) - 200
                transcript_part = transcript_part[:max_transcript] + '\n[... transcript truncated ...]'
                prompt = header + transcript_part

        if prov_name == 'Google Gemini (Free)':
            import google.genai as _gg
            client = _gg.Client(api_key=key)
            models = PROVIDERS[prov_name]['models']
            for model in models:
                try:
                    resp = client.models.generate_content(model=model, contents=prompt)
                    return resp.text
                except Exception as ex:
                    if any(x in str(ex).lower() for x in ['429','quota','resource_exhausted']):
                        raise
                    continue

        elif prov_name == 'Groq (Free)':
            from groq import Groq as _G
            client = _G(api_key=key)
            model = PROVIDERS[prov_name]['models'][0]
            resp = client.chat.completions.create(
                model=model,
                messages=[{'role':'user','content':prompt}],
                max_tokens=4096, temperature=0.3)
            return resp.choices[0].message.content

        elif prov_name == 'OpenRouter (Free models)':
            import requests as _r
            model = self.v_model.get() or PROVIDERS[prov_name]['models'][0]
            resp  = _r.post('https://openrouter.ai/api/v1/chat/completions',
                            headers={'Authorization': f'Bearer {key}',
                                     'Content-Type': 'application/json'},
                            json={'model': model,
                                  'messages': [{'role':'user','content':prompt}],
                                  'max_tokens': 4096},
                            timeout=60)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']

        raise ValueError(f'Unknown provider: {prov_name}')

    # ═══════════════════════════════════════════════════════════════════════════
    # END AUTO EDIT ENGINE
    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # CENSOR TAB
    # ═══════════════════════════════════════════════════════════════════════════

    # Default banned word list (YouTube/TikTok policy)
    CENSOR_WORD_LIST = [
        'retarded', 'retard', 'faggot', 'fag', 'nigger', 'nigga', 'chink',
        'spic', 'kike', 'tranny', 'cunt', 'bitch', 'fuck', 'shit', 'ass',
        'dick', 'cock', 'pussy', 'bastard', 'whore', 'slut', 'piss',
        'motherfucker', 'asshole', 'bullshit', 'goddamn', 'jackass',
        'dumbass', 'dipshit', 'shithead', 'fucked', 'fucking', 'fucker',
    ]


    def _build_settings_tab(self, p):
        """Settings tab — API keys, cookies, preferences all in one place."""
        scroll_canvas = tk.Canvas(p, bg=BG, highlightthickness=0)
        _make_scrollbar(p, scroll_canvas)  # packs itself internally
        scroll_canvas.pack(fill='both', expand=True)
        inner = tk.Frame(scroll_canvas, bg=BG)
        win_id = scroll_canvas.create_window((0,0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: (
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all')),
            scroll_canvas.itemconfig(win_id, width=scroll_canvas.winfo_width())
        ))
        scroll_canvas.bind('<Configure>', lambda e:
            scroll_canvas.itemconfig(win_id, width=e.width))
        # Mousewheel scrolling
        _bind_mousewheel(scroll_canvas, scroll_canvas)
        inner.bind('<MouseWheel>', lambda e: scroll_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        def section(title, subtitle=""):
            f = tk.Frame(inner, bg=BG3, highlightbackground=BG4, highlightthickness=1)
            f.pack(fill='x', padx=14, pady=(10,0))
            hd = tk.Frame(f, bg=BG4); hd.pack(fill='x')
            tk.Frame(hd, bg=ACCENT, width=3).pack(side='left', fill='y')
            hd_inner = tk.Frame(hd, bg=BG4); hd_inner.pack(side='left', padx=10, pady=7)
            tk.Label(hd_inner, text=title, font=('Segoe UI', 10, 'bold'), fg=FG, bg=BG4).pack(anchor='w')
            if subtitle:
                tk.Label(hd_inner, text=subtitle, font=('Segoe UI', 8), fg=FG2, bg=BG4).pack(anchor='w')
            body = tk.Frame(f, bg=BG3); body.pack(fill='x', padx=12, pady=8)
            return body


        def row(parent, label, var, show_btn=False, hint=''):
            r = tk.Frame(parent, bg=BG3); r.pack(fill='x', pady=3)
            tk.Label(r, text=label, font=FONT_SMALL, fg=FG2, bg=BG3, width=22, anchor='w').pack(side='left')
            ef = tk.Frame(r, bg=BG4); ef.pack(side='left', fill='x', expand=True)
            e = tk.Entry(ef, textvariable=var, font=FONT_SMALL, bg=BG4, fg=FG,
                        insertbackground=ACCENT, relief='flat', bd=4,
                        show='•' if show_btn else '')
            e.pack(side='left', fill='x', expand=True)
            if show_btn:
                vis = tk.BooleanVar(value=False)
                def _toggle(e=e, v=vis):
                    v.set(not v.get())
                    e.config(show='' if v.get() else '•')
                tk.Button(ef, text='👁', font=FONT_SMALL, bg=BG3, fg=FG2,
                         relief='flat', bd=0, cursor='hand2',
                         command=_toggle).pack(side='right', padx=2)
            if hint:
                tk.Label(r, text=hint, font=('Segoe UI', 7), fg=FG3, bg=BG2).pack(side='left', padx=6)
            return e

        # ── API Keys ──
        # Build section header manually so we can add Export/Import buttons to it
        _s1_outer = tk.Frame(inner, bg=BG3, highlightbackground=BG4, highlightthickness=1)
        _s1_outer.pack(fill='x', padx=14, pady=(10,0))
        _s1_hd = tk.Frame(_s1_outer, bg=BG4); _s1_hd.pack(fill='x')
        tk.Frame(_s1_hd, bg=ACCENT, width=3).pack(side='left', fill='y')
        _s1_hd_inner = tk.Frame(_s1_hd, bg=BG4); _s1_hd_inner.pack(side='left', padx=10, pady=7, fill='x', expand=True)
        tk.Label(_s1_hd_inner, text='🔑  AI Provider API Keys', font=('Segoe UI', 10, 'bold'), fg=FG, bg=BG4).pack(anchor='w')
        tk.Label(_s1_hd_inner, text='Keys are saved locally — never sent anywhere except the AI provider you choose',
                 font=('Segoe UI', 8), fg=FG2, bg=BG4).pack(anchor='w')
        # Export / Import buttons in the header — right side
        _s1_btn_frame = tk.Frame(_s1_hd, bg=BG4)
        _s1_btn_frame.pack(side='right', padx=10, pady=7)
        _export_btn = tk.Button(_s1_btn_frame, text='📤  Export All Keys', font=('Segoe UI', 8),
                 bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=4)
        _export_btn.pack(side='left', padx=(0,6))
        _import_btn = tk.Button(_s1_btn_frame, text='📥  Import All Keys', font=('Segoe UI', 8),
                 bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=4)
        _import_btn.pack(side='left')
        s1 = tk.Frame(_s1_outer, bg=BG3); s1.pack(fill='x', padx=12, pady=8)

        # All 4 providers use identical layout — order: Gemini, Unsplash, Groq, OpenRouter
        _all_providers = [
            ('Google Gemini (Free)',     'Gemini',      'Free · best for long videos',        'https://aistudio.google.com/app/apikey'),
            ('_unsplash',               'Unsplash',    'Free · 50 req/hr · thumbnail search', 'https://unsplash.com/oauth/applications'),
            ('Groq (Free)',             'Groq',        'Free · fastest inference',             'https://console.groq.com/keys'),
            ('OpenRouter (Free models)','OpenRouter',  'Free models available',                'https://openrouter.ai/keys'),
        ]

        # Ensure Unsplash var exists
        if not hasattr(self, 'v_unsplash_key'):
            self.v_unsplash_key = tk.StringVar(value=self._keys.get('_unsplash',''))

        _provider_entries = {}
        _extra_key_vars = {}  # pkey -> list of StringVars for extra keys
        _extra_key_frames = {}  # pkey -> frame containing extra rows

        def _make_eye_toggle(entry):
            def _t(): entry.config(show='' if entry.cget('show')=='•' else '•')
            return _t

        # Fixed column widths so ALL rows (primary + extra) align perfectly
        # Using character units on Labels directly — immune to canvas sizing issues
        _COL_NAME  = 14   # chars for left name column
        _COL_RIGHT = 32   # chars for right hint column

        for pkey, display, hint, url in _all_providers:
            if pkey == '_unsplash':
                _var = self.v_unsplash_key
            else:
                _var = self.v_keys.get(pkey, tk.StringVar())
            _has = bool(_var.get().strip())

            # ── Primary key row ───────────────────────────────────────────────
            pr = tk.Frame(s1, bg=BG3); pr.pack(fill='x', pady=3)

            # LEFT: single label, character width — no frame needed
            tk.Label(pr, text=f'{"●" if _has else "○"} {display}',
                     font=('Segoe UI',9,'bold'),
                     fg=GREEN if _has else FG3, bg=BG3,
                     width=_COL_NAME, anchor='w').pack(side='left', padx=(4,0))

            # RIGHT: hint + Get key — packed before entry so they claim space first
            tk.Button(pr, text='Get key →', font=('Segoe UI',7),
                     bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=6,
                     command=lambda u=url: __import__('webbrowser').open(u)).pack(side='right', padx=(0,6))
            tk.Label(pr, text=hint, font=('Segoe UI',7), fg=FG2, bg=BG3,
                     width=_COL_RIGHT, anchor='e').pack(side='right')

            # RIGHT: + button (fixed, before entry)
            _plus_holder = tk.Frame(pr, bg=BG3, width=28)
            _plus_holder.pack(side='right'); _plus_holder.pack_propagate(False)
            _plus_btn = tk.Button(_plus_holder, text='＋', font=('Segoe UI',9,'bold'),
                                 bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2')
            _plus_btn.pack(expand=True)

            # MIDDLE: entry expands to fill
            ef = tk.Frame(pr, bg=BG4)
            ef.pack(side='left', fill='x', expand=True, padx=6)
            e = tk.Entry(ef, textvariable=_var, font=('Consolas',9),
                        bg=BG4, fg=FG, insertbackground=ACCENT, relief='flat', bd=4, show='•')
            e.pack(side='left', fill='x', expand=True)
            tk.Button(ef, text='👁', font=('Segoe UI',8), bg=BG4, fg=FG2,
                     relief='flat', bd=0, cursor='hand2', padx=4,
                     command=_make_eye_toggle(e)).pack(side='right')
            _provider_entries[pkey] = _var

            # ── Extra key rows container ──────────────────────────────────────
            _extra_key_vars[pkey] = []
            _extra_key_frames[pkey] = tk.Frame(s1, bg=BG3)
            _extra_key_frames[pkey].pack(fill='x')
            _cfg_extra_k = {
                'Google Gemini (Free)':'key_gemini_extra',
                'Groq (Free)':'key_groq_extra',
                'OpenRouter (Free models)':'key_openrouter_extra',
                '_unsplash':'key_unsplash_extra'
            }.get(pkey, '')
            _existing_extras = [k.strip() for k in self.cfg.get(_cfg_extra_k,'').split(',') if k.strip()]

            def _add_extra_row(pk=pkey, val=''):
                _ev = tk.StringVar(value=val)
                _extra_key_vars[pk].append(_ev)
                _kidx = len(_extra_key_vars[pk])

                # Same parent as primary rows
                _erow = tk.Frame(s1, bg=BG3)
                _erow.pack(fill='x', pady=1)

                # LEFT: character-width label — matches primary row exactly
                tk.Label(_erow, text=f'  ↳ Key {_kidx+1}',
                        font=('Segoe UI',8), fg=ACCENT2, bg=BG3,
                        width=_COL_NAME, anchor='w').pack(side='left', padx=(4,0))

                # RIGHT: spacer + ✕ button — packed before entry same as primary
                tk.Button(_erow, text='✕', font=('Segoe UI',9,'bold'),
                         bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=6,
                         command=lambda r=_erow, v=_ev, pk2=pk: (
                             r.destroy(), _extra_key_vars[pk2].remove(v)
                         )).pack(side='right', padx=(0,6))
                # Blank spacer same width as hint column keeps entry aligned with primary
                tk.Label(_erow, text='', bg=BG3,
                         width=_COL_RIGHT).pack(side='right')

                # MIDDLE: orange-bordered entry — same padx=6 as primary
                _eef = tk.Frame(_erow, bg=ACCENT, padx=1, pady=1)
                _eef.pack(side='left', fill='x', expand=True, padx=6)
                _einn = tk.Frame(_eef, bg=BG4); _einn.pack(fill='both', expand=True)
                _ee = tk.Entry(_einn, textvariable=_ev, font=('Consolas',9),
                              bg=BG4, fg=FG, insertbackground=ACCENT, relief='flat', bd=4, show='•')
                _ee.pack(side='left', fill='x', expand=True)
                tk.Button(_einn, text='👁', font=('Segoe UI',8), bg=BG4, fg=FG2,
                         relief='flat', bd=0, cursor='hand2', padx=4,
                         command=_make_eye_toggle(_ee)).pack(side='right')

            for _ev_val in _existing_extras:
                _add_extra_row(pkey, _ev_val)
            _plus_btn.config(command=lambda pk=pkey: _add_extra_row(pk))

        def _save_keys():
            for pkey, var in _provider_entries.items():
                val = var.get().strip()
                if pkey == '_unsplash':
                    self._keys['_unsplash'] = val
                    self.cfg['key_unsplash'] = val
                    if hasattr(self, 'thumb_unsplash_var'):
                        self.thumb_unsplash_var.set(val)
                else:
                    self._keys[pkey] = val
            # Save extra keys
            _cfg_map = {
                'Google Gemini (Free)': ('key_gemini', 'key_gemini_extra'),
                'Groq (Free)':          ('key_groq',   'key_groq_extra'),
                'OpenRouter (Free models)': ('key_openrouter', 'key_openrouter_extra'),
            }
            for pkey, (cfg_k, cfg_extra_k) in _cfg_map.items():
                self.cfg[cfg_k] = self._keys.get(pkey, '')
                extras = [v.get().strip() for v in _extra_key_vars.get(pkey, []) if v.get().strip()]
                self.cfg[cfg_extra_k] = ','.join(extras)
                if hasattr(self, '_extra_keys'):
                    self._extra_keys[pkey] = extras
            save_cfg(self.cfg)
            self._auto_select_provider()
            self.log(f'✅ API keys saved', GREEN)

        def _export_keys():
            import json as _j, base64 as _b64, hashlib as _hs
            from tkinter import simpledialog as _sd, filedialog as _fd
            _save_keys()
            _bundle = {'v': 1, 'keys': {
                'key_gemini':           self._keys.get('Google Gemini (Free)', ''),
                'key_gemini_extra':     self.cfg.get('key_gemini_extra', ''),
                'key_groq':             self._keys.get('Groq (Free)', ''),
                'key_groq_extra':       self.cfg.get('key_groq_extra', ''),
                'key_openrouter':       self._keys.get('OpenRouter (Free models)', ''),
                'key_openrouter_extra': self.cfg.get('key_openrouter_extra', ''),
                'key_unsplash':         self._keys.get('_unsplash', ''),
            }}
            pw = _sd.askstring('Export Keys', 'Set a password to encrypt your keys:', show='*', parent=self)
            if not pw: return
            dest = _fd.asksaveasfilename(title='Save encrypted key bundle',
                defaultextension='.cfkeys', initialfile='clipfinder_keys.cfkeys',
                filetypes=[('ClipFinder Keys', '*.cfkeys'), ('All', '*.*')])
            if not dest: return
            try:
                _key = _hs.sha256(pw.encode()).digest()
                _data = _j.dumps(_bundle).encode()
                _cipher = bytearray()
                _ks = _key
                for i, b in enumerate(_data):
                    if i % 32 == 0 and i > 0: _ks = _hs.sha256(_ks).digest()
                    _cipher.append(b ^ _ks[i % 32])
                with open(dest, 'wb') as _f:
                    _f.write(_b64.b64encode(b'CFKEYS1:' + bytes(_cipher)))
                messagebox.showinfo('Exported', f'Keys saved to:\n{dest}\n\nKeep this file and your password safe!')
                self.log(f'✅ Keys exported to {dest}', GREEN)
            except Exception as ex:
                messagebox.showerror('Export failed', str(ex))

        def _import_keys():
            import json as _j, base64 as _b64, hashlib as _hs
            from tkinter import simpledialog as _sd, filedialog as _fd
            src = _fd.askopenfilename(title='Select encrypted key bundle',
                filetypes=[('ClipFinder Keys', '*.cfkeys'), ('All', '*.*')])
            if not src: return
            pw = _sd.askstring('Import Keys', 'Enter the password for this key bundle:', show='*', parent=self)
            if not pw: return
            try:
                with open(src, 'rb') as _f: _raw = _b64.b64decode(_f.read())
                _magic = b'CFKEYS1:'
                if not _raw.startswith(_magic):
                    messagebox.showerror('Import failed', 'Not a valid ClipFinder key bundle.'); return
                _cipher = _raw[len(_magic):]
                _key = _hs.sha256(pw.encode()).digest()
                _plain = bytearray()
                _ks = _key
                for i, b in enumerate(_cipher):
                    if i % 32 == 0 and i > 0: _ks = _hs.sha256(_ks).digest()
                    _plain.append(b ^ _ks[i % 32])
                _bundle = _j.loads(_plain.decode())
                if _bundle.get('v') != 1:
                    messagebox.showerror('Import failed', 'Unknown bundle version.'); return
                _kd = _bundle.get('keys', {})
                self._keys['Google Gemini (Free)']     = _kd.get('key_gemini', '')
                self._keys['Groq (Free)']              = _kd.get('key_groq', '')
                self._keys['OpenRouter (Free models)'] = _kd.get('key_openrouter', '')
                self._keys['_unsplash']                = _kd.get('key_unsplash', '')
                self.cfg.update({k: _kd.get(k, '') for k in [
                    'key_gemini','key_gemini_extra','key_groq','key_groq_extra',
                    'key_openrouter','key_openrouter_extra','key_unsplash']})
                save_cfg(self.cfg)
                for _pk, _ck in [('Google Gemini (Free)','key_gemini'),
                                  ('Groq (Free)','key_groq'),
                                  ('OpenRouter (Free models)','key_openrouter')]:
                    if _pk in self.v_keys: self.v_keys[_pk].set(_kd.get(_ck, ''))
                if hasattr(self, 'v_unsplash_key'): self.v_unsplash_key.set(_kd.get('key_unsplash',''))
                self._auto_select_provider()
                messagebox.showinfo('Imported', 'All keys imported!\nExtra keys (Key 2, Key 3) reload on next Settings open.')
                self.log('✅ Keys imported successfully', GREEN)
            except (ValueError, KeyError):
                messagebox.showerror('Import failed', 'Wrong password or corrupted file.')
            except Exception as ex:
                messagebox.showerror('Import failed', str(ex))

        # Wire export/import to the header buttons created earlier
        _export_btn.config(command=_export_keys)
        _import_btn.config(command=_import_keys)

        # Save & Apply button
        btn_row = tk.Frame(s1, bg=BG3); btn_row.pack(fill='x', pady=(10,0))
        tk.Button(btn_row, text='💾  Save & Apply', font=('Segoe UI', 9, 'bold'),
                 bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=14, pady=5,
                 command=_save_keys).pack(side='left')
        tk.Label(btn_row, text='Keys auto-apply on save — no restart needed',
                font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left', padx=10)

        # ── Smart Provider Status ──
        s2 = section('🤖  AI Provider Status')
        self._prov_status_frame = s2
        _leg = tk.Frame(s2, bg=BG2); _leg.pack(anchor='w', pady=(0,6))
        for _lt, _lc in [('● Ready', GREEN), ('  ● Rate-limited', YELLOW), ('  ○ No key', FG3)]:
            tk.Label(_leg, text=_lt, font=('Segoe UI',8), fg=_lc, bg=BG2).pack(side='left')
        # Defer to background — provider status check imports packages (slow)
        self.after(50, self._refresh_provider_status)

        # ── Whisper / Transcription ──
        s3 = section('🎙️  Transcription Settings')
        wr = tk.Frame(s3, bg=BG3); wr.pack(fill='x', pady=3)
        tk.Label(wr, text='Whisper Model:', font=FONT_SMALL, fg=FG2, bg=BG3, width=18, anchor='w').pack(side='left')
        self._whisper_btns = {}
        for size, desc in [('auto','Auto ✓'), ('tiny','Fastest'), ('base','Balanced'), ('small','Better'), ('medium','Best')]:
            active = (self.v_whisper.get() == size) or (size == 'auto' and self.v_whisper.get() not in ['tiny','base','small','medium'])
            def _set_whisper(s=size):
                self.v_whisper.set(s)
                self.cfg.update({'whisper': s}); save_cfg(self.cfg)
                for sz, btn in self._whisper_btns.items():
                    btn.config(bg=ACCENT if sz == s else BG4, fg='#000' if sz == s else FG2)
            b = tk.Button(wr, text=f'{size} ({desc})' if size != 'auto' else '✦ Auto',
                         font=FONT_SMALL, bg=ACCENT if active else BG4, fg='#000' if active else FG2,
                         relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                         command=_set_whisper)
            b.pack(side='left', padx=(0,4))
            self._whisper_btns[size] = b
        tk.Label(wr, text='Auto picks best model for your hardware', font=('Segoe UI',7), fg=FG2, bg=BG3).pack(side='left', padx=8)

        # ── Cookies ──
        s4 = section('🍪  Cookies (for Kick/Twitter/X downloads)')
        tk.Label(s4, text='Required for downloading from Kick clips and X/Twitter. Get via Get cookies.txt LOCALLY Chrome extension.',
                font=FONT_SMALL, fg=FG2, bg=BG2, wraplength=600, justify='left').pack(anchor='w', pady=(0,6))
        cr = tk.Frame(s4, bg=BG2); cr.pack(fill='x', pady=3)
        tk.Label(cr, text='cookies.txt path:', font=FONT_SMALL, fg=FG2, bg=BG2, width=22, anchor='w').pack(side='left')
        cf = tk.Frame(cr, bg=BG3); cf.pack(side='left', fill='x', expand=True)
        tk.Entry(cf, textvariable=self.v_cookies, font=FONT_SMALL, bg=BG3, fg=FG,
                insertbackground=ACCENT, relief='flat', bd=4).pack(side='left', fill='x', expand=True)
        tk.Button(cf, text='...', font=FONT_SMALL, bg=BG2, fg=FG2, relief='flat', bd=0,
                 cursor='hand2', padx=5, command=self._dl_pick_cookies).pack(side='right')

        tk.Button(s4, text='🌐  Get cookies.txt extension (Chrome)',
                 font=FONT_SMALL, bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                 command=lambda: __import__('webbrowser').open(
                     'https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc'
                 )).pack(anchor='w', pady=(6,0))

        # ── Output Folders ──
        s5 = section('📁  Default Output Folders')

        def _folder_row(parent, label, var):
            fr = tk.Frame(parent, bg=BG3); fr.pack(fill='x', pady=3)
            tk.Label(fr, text=label, font=FONT_SMALL, fg=FG2, bg=BG3, width=22, anchor='w').pack(side='left')
            ef = tk.Frame(fr, bg=BG4); ef.pack(side='left', fill='x', expand=True)
            tk.Entry(ef, textvariable=var, font=FONT_SMALL, bg=BG4, fg=FG,
                    insertbackground=ACCENT, relief='flat', bd=4).pack(side='left', fill='x', expand=True)
            def _browse(v=var):
                from tkinter import filedialog as _fd
                d = _fd.askdirectory(title='Select folder', initialdir=v.get() or str(Path.home()))
                if d: v.set(d); save_cfg(self.cfg)
            tk.Button(ef, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2, relief='flat', bd=0,
                     cursor='hand2', padx=6, command=_browse).pack(side='right')

        _folder_row(s5, 'Clips output folder:', self.v_outdir)
        _folder_row(s5, 'Download folder:', self.v_dl_folder)

        # ── Update Modules ──
        s6 = section('🔄  Update Modules',
                     'Keep yt-dlp, whisper, ffmpeg and all AI packages up to date')
        tk.Label(s6, text='Updates run in the background — app stays open. Check log for progress.',
                font=('Segoe UI', 8), fg=FG2, bg=BG3, wraplength=700).pack(anchor='w', pady=(0,4))

        # ── First-run / EXE notice ──────────────────────────────────────────
        _is_frozen = getattr(sys, 'frozen', False)
        def _check_heavy_installed():
            """Return True if faster-whisper is installed (in PKGS_DIR or system)."""
            _ensure_pkgs_on_path()
            import importlib as _ilh2
            try:
                _ilh2.import_module('faster_whisper'); return True
            except ImportError:
                pass
            # Check folder presence in PKGS_DIR
            try:
                return any(PKGS_DIR.glob('faster_whisper*')) or any(PKGS_DIR.glob('faster-whisper*'))
            except: return False

        # ── "Install All AI Packages" — always visible (works first-run AND re-install) ──
        # Check quickly — just look for pkgs dir existence, don't scan imports
        _heavy_installed = bool(list(PKGS_DIR.glob('faster_whisper*'))[:1]) if PKGS_DIR.exists() else False
        _notice_bg = '#1a1200' if not _heavy_installed else BG3
        _notice_border = ACCENT2 if not _heavy_installed else BORDER
        notice = tk.Frame(s6, bg=_notice_bg, highlightbackground=_notice_border, highlightthickness=1)
        if not _heavy_installed:
            notice.pack(fill='x', pady=(0, 8))
        ni = tk.Frame(notice, bg=_notice_bg); ni.pack(fill='x', padx=10, pady=8)

        if not _heavy_installed:
            tk.Label(ni, text='⚡  First-time setup — install AI packages below',
                    font=('Segoe UI', 9, 'bold'), fg=ACCENT2, bg=_notice_bg).pack(anchor='w')
            tk.Label(ni, text='Packages install to the app folder and persist across launches.',
                    font=('Segoe UI', 8), fg=FG2, bg=_notice_bg).pack(anchor='w', pady=(2,4))
        else:
            pass  # Hide the notice entirely when all installed

        # Per-package install progress bar (canvas-based)
        _inst_prog_frame = tk.Frame(ni, bg=_notice_bg)
        _inst_prog_canvas = tk.Canvas(_inst_prog_frame, bg=BG4, height=8, bd=0, highlightthickness=0)
        _inst_prog_canvas.pack(fill='x')
        _inst_prog_lbl = tk.Label(_inst_prog_frame, text='', font=('Segoe UI', 7), fg=FG2, bg=_notice_bg, anchor='w')
        _inst_prog_lbl.pack(fill='x')
        _inst_prog_frame.pack_forget()  # hidden until install starts

        def _draw_inst_progress(pct, msg=''):
            _inst_prog_canvas.delete('all')
            w = _inst_prog_canvas.winfo_width() or 400
            h = 8
            _inst_prog_canvas.create_rectangle(0, 0, w, h, fill=BG4, outline='')
            bar_w = max(0, int(w * pct / 100))
            if bar_w > 0:
                _inst_prog_canvas.create_rectangle(0, 0, bar_w, h, fill=ACCENT2, outline='')
                _inst_prog_canvas.create_rectangle(max(0, bar_w-3), 0, bar_w, h, fill=FG, outline='')
            _inst_prog_lbl.config(text=msg)

        _INSTALL_HEAVY_PKGS = [
            # Pure Python AI providers first
            'google-genai', 'groq', 'openai', 'yt-dlp', 'requests', 'curl-cffi',
            # Numeric base MUST come before imagehash/soundfile/whisper
            'numpy', 'scipy',
            # Audio + image (depend on numpy)
            'Pillow', 'soundfile', 'imagehash',
            # Whisper engines
            'faster-whisper', 'openai-whisper',
            # Video processing
            'opencv-python',
            # Optional face tracking
            'mediapipe',
            # Music removal
            'torch', 'torchaudio', 'demucs',
        ]

        def _install_all_heavy():
            _install_btn.config(text='⟳ Installing... (check log)', state='disabled', bg=BG4, fg=FG2)
            _inst_prog_frame.pack(fill='x', pady=(4, 0))
            _draw_inst_progress(0, 'Starting install...')
            self.set_busy(True)
            self.set_progress('Installing AI packages...', pct=2)

            def _do_heavy():
                import subprocess as _sp
                n = len(_INSTALL_HEAVY_PKGS)
                self.log('🔄 Installing all AI/transcription packages...', ACCENT2)
                self.log('This may take 5-15 minutes depending on connection speed.', FG2)
                ok_count = 0
                for i, pkg in enumerate(_INSTALL_HEAVY_PKGS):
                    pct_before = max(2, int(i / n * 95))
                    self.after(0, lambda p=pkg, pct=pct_before: (
                        _draw_inst_progress(pct, f'Installing {p}... ({pct}%)'),
                        self.set_progress(f'⬇ Installing {p}...', pct=pct)
                    ))
                    self.log(f'  → {pkg}...', FG2)
                    _nodeps = pkg in {'faster-whisper', 'openai-whisper'}
                    _cmd = _pip_cmd([pkg], ['--no-deps'] if _nodeps else [])
                    if _cmd is None:
                        self.after(0, lambda: self.log('❌ Cannot find Python — check Settings', RED))
                        break
                    r = _sp.run(_cmd, capture_output=True, text=True, timeout=300)
                    if r.returncode != 0 and _nodeps:
                        r = _sp.run(_pip_cmd([pkg]), capture_output=True, text=True, timeout=300)
                    if r.returncode != 0 and b'Access is denied' in (r.stderr or b'').encode():
                        self.after(0, lambda p=pkg: self.log(
                            f'⚠ {p} is locked (in use). Restart ClipFinder to complete install.', YELLOW))
                        r = type('R', (), {'returncode': 0})()  # treat as ok, will work after restart
                    _ok = r.returncode == 0
                    if _ok:
                        ok_count += 1
                    if not _ok:
                        _err_tail = (r.stderr or '')[-150:].strip()
                        self.after(0, lambda p=pkg, e=_err_tail: self.log(f'  ❌ {p}: {e}', RED))
                    else:
                        self.after(0, lambda p=pkg: self.log(f'  ✅ {p}', GREEN))

                def _finish():
                    _draw_inst_progress(100, f'Done! {ok_count}/{n} packages installed.')
                    _draw_inst_progress(100, f'{ok_count}/{n} packages installed.')
                    if ok_count >= n - 2:
                        _install_btn.config(text=f'✅ All installed ({ok_count}/{n}) — restart to activate',
                                           bg='#1a3a1a', fg=GREEN, state='normal')
                        self.cfg['_setup_done'] = True
                        save_cfg(self.cfg)
                        self.log(f'✅ {ok_count}/{n} packages installed! Restart ClipFinder to activate.', GREEN)
                    else:
                        _install_btn.config(text=f'⚠ {ok_count}/{n} installed — click to retry',
                                           bg='#3a2000', fg=ACCENT2, state='normal')
                        self.log(f'⚠ {ok_count}/{n} packages installed. Click again to retry.', YELLOW)
                    self.set_busy(False)
                    self.set_progress(f'✅ {ok_count}/{n} packages installed', pct=100)
                    try: _refresh_dep_display()
                    except Exception: pass
                self.after(0, _finish)
            import threading; threading.Thread(target=_do_heavy, daemon=True).start()

        self._install_all_fn = _install_all_heavy  # store ref for first-run auto-trigger
        _btn_text = '⬇  Install All AI Packages' if not _heavy_installed else '🔄  Reinstall All AI Packages'
        _btn_bg   = ACCENT2 if not _heavy_installed else BG4
        _btn_fg   = '#000' if not _heavy_installed else FG
        _install_btn = tk.Button(ni, text=_btn_text,
            font=('Segoe UI', 9, 'bold'), bg=_btn_bg, fg=_btn_fg,
            relief='flat', bd=0, cursor='hand2', padx=16, pady=6,
            command=_install_all_heavy)
        _install_btn.pack(anchor='w')

        tk.Label(s6, text='Use individual ↑ Update buttons below or "Update All" to refresh packages.',
                font=('Segoe UI', 8), fg=FG2, bg=BG3, wraplength=700).pack(anchor='w', pady=(4,4))

        mods = [
            # ── AI / Transcription ──────────────────────────────────────────
            ('faster-whisper', 'faster-whisper',            'GPU transcription engine  ← install first'),
            ('openai-whisper', 'openai-whisper',            'Fallback transcription engine'),
            ('google-genai',   'google-genai',              'Gemini AI provider'),
            ('groq',           'groq',                      'Groq AI provider'),
            ('openai',         'openai',                    'OpenRouter/OpenAI provider'),
            # ── Video / Download ────────────────────────────────────────────
            ('yt-dlp',         'yt-dlp',                   'Video downloader — update for new sites/fixes'),
            ('curl-cffi',      'curl-cffi',                 'Kick/Cloudflare bypass'),
            # ── Image / Video Processing ────────────────────────────────────
            ('Pillow',         'Pillow',                    'Image processing'),
            ('opencv-python',  'opencv-python',             'Video frame analysis + face tracking'),
            ('imagehash',      'imagehash',                 'Duplicate image detection'),
            ('mediapipe',      'mediapipe --no-deps',       'Face detection for 9:16 vertical crop'),
            # ── Audio / Core ────────────────────────────────────────────────
            ('soundfile',      'soundfile',                 'Audio read/write — required for Censor tab'),
            ('numpy',          'numpy',                     'Numeric processing — required for audio/video'),
            ('requests',       'requests',                  'HTTP requests — required for downloads'),
            # ── Music Removal ────────────────────────────────────────────────
            ('demucs',         'demucs',                    'AI music removal — required for Music Removal tab'),
            ('torch',          'torch',                     'PyTorch — required by Demucs'),
            ('torchaudio',     'torchaudio',                'Audio processing — required by Demucs'),
            # ── Subtitle Burn-in ────────────────────────────────────────────
            ('fonttools',      'fonttools',                 'Font enumeration — required for Burn Subtitles'),
        ]

        # Packages that need --no-deps to avoid DLL permission conflicts
        _NODEPS_PKGS = {'faster-whisper', 'openai-whisper'}

        _UPDATE_FLAG = USER_DIR / 'pending_update.flag'

        def _request_update_on_reboot(pkg='all'):
            try:
                existing = set(_UPDATE_FLAG.read_text().splitlines()) if _UPDATE_FLAG.exists() else set()
                existing.add(pkg)
                _UPDATE_FLAG.write_text('\n'.join(sorted(existing)))
            except: pass

        def _update_pkg(pkg_name, btn):
            _request_update_on_reboot(pkg_name)
            btn.config(text='⏳ On reboot', bg='#2a2000', fg=ACCENT2, state='normal')
            self.log(f'📋 {pkg_name} queued — restart ClipFinder to install', ACCENT2)
            messagebox.showinfo('Queued', f'{pkg_name} will install on next launch.\nRestart ClipFinder now to apply.')

        def _update_all():
            _request_update_on_reboot('all')
            self.log('📋 All packages queued — restart ClipFinder to install', ACCENT2)
            messagebox.showinfo('Queued', 'All packages will install on next launch.\nRestart ClipFinder now to apply.')

        # Grid of packages

        _dot_updates = []  # deferred package status checks

        def _pkg_installed_check(pkg_name):
            import importlib as _il
            _imp_map = {
                'faster-whisper': 'faster_whisper', 'openai-whisper': 'whisper',
                'google-genai': 'google.genai', 'opencv-python': 'cv2',
                'yt-dlp': 'yt_dlp', 'curl-cffi': 'curl_cffi',
                'mediapipe': 'mediapipe', 'demucs': 'demucs',
                'imagehash': 'imagehash', 'soundfile': 'soundfile',
                'Pillow': 'PIL', 'numpy': 'numpy', 'requests': 'requests',
                'groq': 'groq', 'openai': 'openai',
                'torch': 'torch', 'torchaudio': 'torchaudio',
                'fonttools': 'fontTools',
            }
            mod = _imp_map.get(pkg_name, pkg_name.replace('-','_').lower())
            try:
                m = _il.import_module(mod)
                if mod == 'pydantic_core': _il.import_module('pydantic_core.core_schema')
                if mod in ('torch','torchaudio'): _ = m.__version__
                return True
            except: return False

        for i, (pkg, pkg_pip, desc) in enumerate(mods):
            mr = tk.Frame(s6, bg=BG3); mr.pack(fill='x', pady=2)
            # Show placeholder dot — update async after UI draws
            _dot_lbl = tk.Label(mr, text='…',
                    font=('Segoe UI', 9), fg=FG3, bg=BG3)
            _dot_lbl.pack(side='left', padx=(8,2))
            _name_lbl = tk.Label(mr, text=pkg, font=('Consolas', 8, 'bold'),
                    fg=FG2, bg=BG3, width=18, anchor='w')
            _name_lbl.pack(side='left', padx=(0,8))
            def _update_dot(p=pkg, dl=_dot_lbl, nl=_name_lbl):
                ok = _pkg_installed_check(p)
                dl.config(text='✅' if ok else '○', fg=GREEN if ok else FG3)
                nl.config(fg=FG if ok else FG2)
            _dot_updates.append(_update_dot)
            tk.Label(mr, text=desc, font=('Segoe UI', 8), fg=FG2, bg=BG3).pack(side='left')
            upd_btn = tk.Button(mr, text='↑ Update', font=('Segoe UI', 8),
                               bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=10, pady=2)
            upd_btn.config(command=lambda p=pkg_pip, b=upd_btn: _update_pkg(p, b))
            upd_btn.pack(side='right')

        # Run package status checks in background after UI is drawn
        def _run_dot_updates():
            for fn in _dot_updates:
                try: self.after(0, fn)
                except: pass
        threading.Thread(target=_run_dot_updates, daemon=True).start()

        upd_all_row = tk.Frame(s6, bg=BG3); upd_all_row.pack(fill='x', pady=(10,0))
        tk.Button(upd_all_row, text='🔄  Update All Packages', font=('Segoe UI', 9, 'bold'),
                 bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=14, pady=5,
                 command=_update_all).pack(side='left')
        tk.Label(upd_all_row, text='Recommended when you see download or AI errors',
                font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left', padx=10)

        # ── Core Dependencies ──
        s7 = section('🔧  Core Dependencies',
                     'ClipFinder manages these automatically — reinstall if something breaks')

        def _check_dep_status():
            """Check which deps are installed and update the UI."""
            import shutil as _sh
            _ensure_pkgs_on_path()  # make sure PKGS_DIR packages are importable
            statuses = {}
            # ffmpeg — check all known locations
            # When frozen, sys.executable is the EXE itself — its parent IS APP_DIR
            # ffmpeg_bin lives next to the EXE
            _exe_dir = _PathBase(sys.executable).parent if getattr(sys, 'frozen', False) else APP_DIR
            _ffmpeg_candidates = [
                APP_DIR / 'ffmpeg_bin' / 'ffmpeg.exe',    # script mode
                APP_DIR / 'ffmpeg.exe',
                _exe_dir / 'ffmpeg_bin' / 'ffmpeg.exe',   # EXE mode
                _exe_dir / 'ffmpeg.exe',
                _PathBase('C:/ffmpeg/bin/ffmpeg.exe'),
                _PathBase('C:/ffmpeg/ffmpeg.exe'),
                _PathBase.home() / 'ffmpeg' / 'bin' / 'ffmpeg.exe',
            ]
            ff = _sh.which('ffmpeg')
            if not ff:
                for _cand in _ffmpeg_candidates:
                    if _cand.exists():
                        ff = str(_cand)
                        break
            statuses['ffmpeg'] = ff
            # whisper.cpp
            wcpp = _find_whispercpp()
            statuses['whisper.cpp'] = wcpp
            # whisper models — check both whisper.cpp ggml format AND faster-whisper HF cache
            for sz in ['tiny', 'base', 'small', 'medium']:
                m = _find_whispercpp_model(sz)
                if not m:
                    # Also check faster-whisper huggingface cache
                    fw_cache = _app_path('whisper_models')
                    for sub in fw_cache.glob(f'models--Systran--faster-whisper-{sz}*'):
                        if sub.is_dir(): m = str(sub); break
                    if not m:
                        # Check HF default cache
                        import os as _os2
                        hf_cache = Path(_os2.environ.get('HF_HOME', Path.home() / '.cache' / 'huggingface'))
                        for sub in (hf_cache / 'hub').glob(f'models--Systran--faster-whisper-{sz}*'):
                            if sub.is_dir(): m = str(sub); break
                statuses[f'ggml-{sz}'] = m
            # Python packages
            _ensure_pkgs_on_path()  # make sure pkgs dir is on path
            for pkg in ['faster_whisper', 'yt_dlp', 'cv2', 'curl_cffi', 'soundfile', 'imagehash']:
                try:
                    __import__(pkg)
                    statuses[pkg] = True
                except ImportError:
                    # Check PKGS_DIR by multiple name variants
                    _variants = [pkg, pkg.replace('_','-'), pkg.replace('-','_'), pkg.lower()]
                    statuses[pkg] = any(
                        any(PKGS_DIR.glob(f'{v}*')) for v in _variants
                    )
            return statuses

        # Status display frame
        dep_status_frame = tk.Frame(s7, bg=BG3)
        dep_status_frame.pack(fill='x', pady=(0, 8))

        def _refresh_dep_display():
            for w in dep_status_frame.winfo_children(): w.destroy()
            try:
                statuses = _check_dep_status()
            except Exception as e:
                tk.Label(dep_status_frame, text=f'Status check failed: {e}',
                        font=FONT_SMALL, fg=RED, bg=BG3).pack(anchor='w')
                return
            dep_display = [
                ('ffmpeg',        'ffmpeg',         'Video processing — required for everything'),
                ('whisper.cpp',   'whisper.cpp',    'GPU transcription (AMD/Intel via Vulkan)'),
                ('ggml-tiny',     'ggml-tiny',      'Whisper tiny model (~75MB)'),
                ('ggml-base',     'ggml-base',      'Whisper base model (~145MB) ← recommended'),
                ('ggml-small',    'ggml-small',     'Whisper small model (~466MB)'),
                ('ggml-medium',   'ggml-medium',    'Whisper medium model (~1.5GB)'),
                ('faster_whisper','faster-whisper', 'CUDA/CPU transcription fallback'),
                ('yt_dlp',        'yt-dlp',         'Video downloader'),
                ('cv2',           'opencv-python',  'Video frame processing'),
                ('curl_cffi',     'curl-cffi',      'Kick/Cloudflare bypass'),
                ('soundfile',     'soundfile',       'Audio processing for censor'),
                ('imagehash',     'imagehash',       'Image deduplication for thumbnails'),
            ]
            # pip-installable packages that can have an inline install button
            _pip_map = {
                'faster_whisper': 'faster-whisper',
                'cv2':            'opencv-python',
                'soundfile':      'soundfile',
                'curl_cffi':      'curl-cffi',
                'yt_dlp':         'yt-dlp',
                'imagehash':      'imagehash',
            }

            def _make_inline_install(pip_pkg, btn_widget, row_widget):
                """Inline install a pip package to PKGS_DIR with progress."""
                def _do():
                    self.after(0, lambda: btn_widget.config(
                        text='⟳ Installing...', state='disabled', bg=BG4, fg=FG2))
                    self.after(0, lambda: (
                        self.set_progress(f'⬇ Installing {pip_pkg}...', pct=5),
                        self.log(f'⬇ Installing {pip_pkg} to {PKGS_DIR}...', ACCENT2)
                    ))
                    import subprocess as _sp3
                    _nodeps2 = pip_pkg in {'faster-whisper', 'openai-whisper'}
                    _cmd2 = _pip_cmd([pip_pkg], ['--no-deps'] if _nodeps2 else [])
                    if _cmd2 is None:
                        self.after(0, lambda: btn_widget.config(text='❌ No Python 3.12', bg=RED, fg=FG, state='normal')); return
                    r2 = _sp3.run(_cmd2, capture_output=True, text=True, timeout=300)
                    if r2.returncode != 0 and _nodeps2:
                        r2 = _sp3.run(_pip_cmd([pip_pkg]), capture_output=True, text=True, timeout=300)
                    _ok2 = r2.returncode == 0
                    _ensure_pkgs_on_path()
                    def _done(ok=_ok2, pkg=pip_pkg, err=r2.stderr):
                        if ok:
                            # Invalidate import cache so new pkg is findable immediately
                            import importlib as _ilc, importlib.util as _ilu
                            _ensure_pkgs_on_path()
                            try:
                                mod = pkg.replace('-','_')
                                if mod in sys.modules: del sys.modules[mod]
                                _ilc.import_module(mod)
                            except: pass
                        self.set_progress(f'{"✅" if ok else "❌"} {pkg} {"installed" if ok else "failed"}',
                                         pct=100 if ok else 0)
                        self.log(f'{"✅" if ok else "❌"} {pkg}', GREEN if ok else RED)
                        if not ok and err:
                            self.log(f'  Error: {err[-200:]}', RED)
                        _refresh_dep_display()  # auto-refresh the whole list
                    self.after(0, _done)
                import threading; threading.Thread(target=_do, daemon=True).start()

            for key, label, desc in dep_display:
                ok = bool(statuses.get(key))
                dr = tk.Frame(dep_status_frame, bg=BG3); dr.pack(fill='x', pady=1)
                # Status dot
                dot = '✅' if ok else '❌'
                dot_fg = GREEN if ok else RED
                tk.Label(dr, text=dot, font=('Segoe UI', 9),
                        fg=dot_fg, bg=BG3, width=2).pack(side='left')
                tk.Label(dr, text=label, font=('Consolas', 8, 'bold'),
                        fg=FG if ok else YELLOW, bg=BG3, width=16, anchor='w').pack(side='left')
                tk.Label(dr, text=desc, font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left', padx=4)
                if not ok:
                    pip_pkg = _pip_map.get(key)
                    if pip_pkg:
                        # Inline install button — installs to PKGS_DIR
                        _ibtn = tk.Button(dr, text='⬇ Install', font=('Segoe UI', 7, 'bold'),
                                         bg=ACCENT, fg='#000', relief='flat', bd=0,
                                         cursor='hand2', padx=8, pady=1)
                        _ibtn.pack(side='right', padx=4)
                        _ibtn.config(command=lambda p=pip_pkg, b=_ibtn, r=dr:
                                     _make_inline_install(p, b, r))
                    else:
                        tk.Label(dr, text='use buttons below', font=('Segoe UI', 7),
                                fg=FG3, bg=BG3).pack(side='right', padx=4)

        _refresh_dep_display()
        self._dep_refresh_fn = _refresh_dep_display  # store for auto-refresh
        # Auto-refresh after short delay so ffmpeg detection catches up
        self.after(800, _refresh_dep_display)

        # Action buttons
        btn_grid = tk.Frame(s7, bg=BG3); btn_grid.pack(fill='x', pady=(4,0))

        def _install_ffmpeg_ui():
            for w in btn_grid.winfo_children():
                if getattr(w, '_is_ffmpeg_btn', False):
                    w.config(text='⟳ Downloading...', state='disabled', bg=BG4)
            self.set_busy(True)
            self.set_progress('⬇ Downloading ffmpeg...', pct=5)
            def _do():
                try:
                    self.log('⬇ Installing ffmpeg...', ACCENT2)
                    path = ensure_ffmpeg()
                    self.after(0, lambda: (
                        self.log(f'✅ ffmpeg ready: {path}', GREEN),
                        self.set_busy(False),
                        self.set_progress('✅ ffmpeg installed', pct=100),
                        _refresh_dep_display()
                    ))
                except Exception as e:
                    self.after(0, lambda err=e: (
                        self.log(f'❌ ffmpeg install failed: {err}', RED),
                        self.set_busy(False),
                        self.set_progress('❌ ffmpeg failed', pct=0)
                    ))
            import threading; threading.Thread(target=_do, daemon=True).start()

        def _install_wcpp_ui():
            self.set_busy(True)
            self.set_progress('⬇ Installing whisper.cpp...', pct=5)
            def _do():
                try:
                    self.log('⬇ Installing whisper.cpp (GPU transcription)...', ACCENT2)
                    def _cb(msg):
                        self.after(0, lambda m=msg: (
                            self.log(f'[whisper.cpp] {m}', FG2),
                            # Drive progress bar from download percentage lines
                            self.set_progress(f'[whisper.cpp] {m[:60]}', pct=None)
                            if 'Model:' not in m else None
                        ))
                        # Parse model download % to drive bar
                        import re as _re2
                        _pm = _re2.match(r'Model:\s*(\d+)%', msg)
                        if _pm:
                            self.after(0, lambda p=int(_pm.group(1)):
                                self.set_progress(f'⬇ Downloading model... {p}%', pct=p))
                    auto_install_whispercpp(model_size='base', status_cb=_cb)
                    self.after(0, lambda: (
                        self.log('✅ whisper.cpp installed', GREEN),
                        self.set_busy(False),
                        self.set_progress('✅ whisper.cpp ready', pct=100),
                        _refresh_dep_display()
                    ))
                except Exception as e:
                    self.after(0, lambda err=e: (
                        self.log(f'❌ whisper.cpp failed: {err}', RED),
                        self.set_busy(False),
                        self.set_progress('❌ whisper.cpp failed', pct=0)
                    ))
            import threading; threading.Thread(target=_do, daemon=True).start()

        def _install_model_ui(size):
            def _do():
                try:
                    self.log(f'⬇ Downloading ggml-{size} model...', ACCENT2)
                    self.set_progress(f'⬇ Downloading whisper {size} model...', pct=5)
                    # Try faster_whisper (may not be importable yet in same session after install)
                    try:
                        import importlib as _il
                        _fw = _il.import_module('faster_whisper')
                        _fw.WhisperModel(size, device='cpu', compute_type='int8',
                                        download_root=str(_app_path('whisper_models')))
                        self.after(0, lambda: (
                            self.log(f'✅ ggml-{size} ready', GREEN),
                            self.set_progress(f'✅ whisper {size} model ready', pct=100),
                            _refresh_dep_display()
                        ))
                        return
                    except (ImportError, Exception) as _fw_err:
                        self.log(f'  faster_whisper not available ({_fw_err}), downloading ggml file directly...', FG2)

                    # Direct ggml download fallback (no Python package needed)
                    import urllib.request as _ur
                    model_dir = _app_path('whisper_cpp') / 'models'
                    model_dir.mkdir(parents=True, exist_ok=True)
                    model_path = model_dir / f'ggml-{size}.bin'
                    if model_path.exists():
                        self.log(f'✅ ggml-{size}.bin already exists', GREEN)
                        self.after(0, lambda: (
                            self.set_progress(f'✅ whisper {size} model ready', pct=100),
                            _refresh_dep_display()
                        ))
                        return
                    model_url = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                                 f'ggml-{size}.bin')
                    _sizes = {'tiny': 75, 'base': 142, 'small': 466, 'medium': 1500}
                    self.log(f'  Downloading from HuggingFace (~{_sizes.get(size, 142)}MB)...', FG2)
                    def _reporthook(count, block, total):
                        if total > 0 and count % 200 == 0:
                            pct = min(95, int(count * block / total * 100))
                            self.after(0, lambda p=pct: self.set_progress(
                                f'⬇ Downloading ggml-{size}.bin...', pct=p))
                    _ur.urlretrieve(model_url, str(model_path), reporthook=_reporthook)
                    if model_path.exists() and model_path.stat().st_size > 1000:
                        self.after(0, lambda: (
                            self.log(f'✅ ggml-{size}.bin ready ({model_path.stat().st_size//1024//1024}MB)', GREEN),
                            self.set_progress(f'✅ ggml-{size} model ready', pct=100),
                            self.after(100, _refresh_dep_display)
                        ))
                    else:
                        self.after(0, lambda: (
                            self.log(f'❌ Download failed — file missing or empty', RED),
                            self.set_progress('❌ Download failed', pct=0)
                        ))
                except Exception as e:
                    self.after(0, lambda err=e: (
                        self.log(f'❌ model {size} failed: {err}', RED),
                        self.set_progress('❌ Download failed', pct=0)
                    ))
            import threading; threading.Thread(target=_do, daemon=True).start()

        # Row 1: ffmpeg + whisper.cpp
        r1 = tk.Frame(btn_grid, bg=BG3); r1.pack(fill='x', pady=2)
        ffmpeg_btn = tk.Button(r1, text='⬇  Install ffmpeg', font=('Segoe UI', 9, 'bold'),
                 bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=12, pady=5,
                 command=_install_ffmpeg_ui)
        ffmpeg_btn._is_ffmpeg_btn = True
        ffmpeg_btn.pack(side='left', padx=(0,8))
        tk.Label(r1, text='Auto-downloads ~90MB from github.com/BtbN/FFmpeg-Builds',
                font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left')

        r2 = tk.Frame(btn_grid, bg=BG3); r2.pack(fill='x', pady=2)
        tk.Button(r2, text='⬇  Install whisper.cpp (GPU)', font=('Segoe UI', 9, 'bold'),
                 bg=BG4, fg=FG, relief='flat', bd=0, cursor='hand2', padx=12, pady=5,
                 command=_install_wcpp_ui).pack(side='left', padx=(0,8))
        tk.Label(r2, text='Enables AMD/Intel Vulkan GPU transcription — much faster',
                font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left')

        # Row 3: Whisper models
        r3 = tk.Frame(btn_grid, bg=BG3); r3.pack(fill='x', pady=(6,2))
        tk.Label(r3, text='Whisper models:', font=('Segoe UI', 8, 'bold'),
                fg=FG, bg=BG3).pack(side='left', padx=(0,8))
        for sz, size_mb, recommended in [
            ('tiny',   '75MB',  False),
            ('base',   '145MB', True),
            ('small',  '466MB', False),
            ('medium', '1.5GB', False),
        ]:
            label = f'⬇ {sz} ({size_mb}){"  ★" if recommended else ""}'
            tk.Button(r3, text=label, font=('Segoe UI', 8),
                     bg=ACCENT if recommended else BG4,
                     fg='#000' if recommended else FG,
                     relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                     command=lambda s=sz: _install_model_ui(s)).pack(side='left', padx=(0,4))

        # Refresh button
        r4 = tk.Frame(btn_grid, bg=BG3); r4.pack(fill='x', pady=(8,0))
        tk.Button(r4, text='🔍  Refresh Status', font=('Segoe UI', 8),
                 bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=10, pady=3,
                 command=_refresh_dep_display).pack(side='left')
        tk.Label(r4, text='Check again after installing',
                font=('Segoe UI', 7), fg=FG2, bg=BG3).pack(side='left', padx=8)

        _footer = tk.Label(inner, text='ClipFinder — @MarsScumbags',
                font=FONT_SMALL, fg=FG3, bg=BG, cursor='hand2')
        _footer.pack(pady=(20,4))
        _footer.bind('<Button-1>', lambda e: __import__('webbrowser').open('https://x.com/MarsScumbags'))
        tk.Button(inner, text='☕  Support ClipFinder — Buy Me a Coffee',
                 font=('Segoe UI',8), bg=BG3, fg=ACCENT2,
                 relief='flat', bd=0, cursor='hand2', padx=12, pady=5,
                 command=lambda: __import__('webbrowser').open(
                     'https://www.paypal.com/donate/?business=networkchasemedia%40gmail.com&currency_code=USD')
                 ).pack(pady=(0,20))

    def _refresh_provider_status(self):
        """Show which API providers have keys configured."""
        for w in self._prov_status_frame.winfo_children():
            if getattr(w, '_is_status_row', False):
                w.destroy()
        has_any = False
        # Friendly display names
        _display = {
            'Google Gemini (Free)':    'Gemini',
            'Groq (Free)':             'Groq',
            'OpenRouter (Free models)':'OpenRouter',
        }
        # Read live from v_keys StringVars (not cached _keys)
        live_keys = {p: v.get().strip() for p, v in self.v_keys.items()}
        for pname, key in live_keys.items():
            if pname.startswith('_'): continue
            has_key = bool(key.strip())
            if has_key: has_any = True
            _extras = [k for k in getattr(self,'_extra_keys',{}).get(pname,[]) if k]
            _rl_provs = getattr(self, '_rl_provs', set())
            _is_rl = pname in _rl_provs
            r = tk.Frame(self._prov_status_frame, bg=BG2)
            r._is_status_row = True
            r.pack(fill='x', pady=2)
            dot_color = YELLOW if _is_rl else (GREEN if has_key else FG3)
            tk.Label(r, text='●', font=('Segoe UI', 10), fg=dot_color, bg=BG2).pack(side='left')
            display_name = _display.get(pname, pname)
            _key_suffix = f' (+{len(_extras)} more)' if _extras else ''
            tk.Label(r, text=f' {display_name}{_key_suffix}', font=FONT_SMALL,
                    fg=FG if has_key else FG2, bg=BG2).pack(side='left')
            if _is_rl:
                status = f'⏳ Rate-limited ({1+len(_extras)} keys)'
            elif _extras:
                status = f'✓ Ready ({1+len(_extras)} keys)'
            elif has_key:
                status = '✓ Ready'
            else:
                status = 'No key — add above'
            status_color = YELLOW if _is_rl else (GREEN if has_key else YELLOW)
            tk.Label(r, text=status, font=FONT_SMALL, fg=status_color, bg=BG2).pack(side='right')
        # Unsplash status row (separate from AI providers)
        us_key = self._keys.get('_unsplash', '') or (
            self.v_unsplash_key.get().strip() if hasattr(self, 'v_unsplash_key') else '')
        us_has = bool(us_key.strip())
        us_r = tk.Frame(self._prov_status_frame, bg=BG2)
        us_r._is_status_row = True
        us_r.pack(fill='x', pady=2)
        tk.Label(us_r, text='●', font=('Segoe UI', 10),
                fg=GREEN if us_has else FG3, bg=BG2).pack(side='left')
        tk.Label(us_r, text=' Unsplash', font=FONT_SMALL,
                fg=FG if us_has else FG2, bg=BG2).pack(side='left')
        tk.Label(us_r, text='✓ Ready' if us_has else 'No key — add above',
                font=FONT_SMALL, fg=GREEN if us_has else YELLOW, bg=BG2).pack(side='right')
        if not has_any:
            r = tk.Frame(self._prov_status_frame, bg=BG2)
            r._is_status_row = True
            r.pack(fill='x', pady=4)
            tk.Label(r, text='⚠️  No API keys configured — add at least one above to find clips',
                    font=FONT_SMALL, fg=YELLOW, bg=BG2).pack(anchor='w')
        # Auto-refresh every 30s to reflect rate limit changes
        self.after(30000, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)


    def _auto_select_provider(self):
        """Auto-select best available provider based on configured keys."""
        priority = ['Google Gemini (Free)', 'Groq (Free)', 'OpenRouter (Free models)']
        for pname in priority:
            if self._keys.get(pname, '').strip():
                self.v_provider.set(pname)
                self.v_key.set(self._keys[pname])
                self._refresh_prov_btns()
                self.log(f'Auto-selected provider: {pname}', FG2)
                return


        """AI Music Removal using Demucs — strips background music, keeps vocals."""
        tk.Label(p, text='🎵  AI MUSIC REMOVAL', font=('Segoe UI', 11, 'bold'),
                fg=ACCENT, bg=BG).pack(anchor='w', padx=20, pady=(14,2))
        tk.Label(p, text='Strip copyrighted background music from clips. Keeps vocals and speech.',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=20, pady=(0,10))

        sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        sec.pack(fill='x', padx=16, pady=(0,8))
        inner = tk.Frame(sec, bg=BG2); inner.pack(fill='x', padx=12, pady=10)

        # Video file
        tk.Label(inner, text='Video:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_mr_video = tk.StringVar()
        vf = tk.Frame(inner, bg=BG3); vf.pack(side='left', fill='x', expand=True)
        tk.Entry(vf, textvariable=self.v_mr_video, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(vf, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_mr_video.set(
                     filedialog.askopenfilename(
                         filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')]
                     ) or self.v_mr_video.get())
                 ).pack(side='right')
        tk.Button(inner, text='Use Clip Finder video', font=FONT_SMALL,
                 bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8,
                 command=lambda: self.v_mr_video.set(self.v_video.get())
                 ).pack(side='left', padx=8)

        # Output folder
        out_row = tk.Frame(sec, bg=BG2); out_row.pack(fill='x', padx=12, pady=(0,8))
        tk.Label(out_row, text='Output:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_mr_out = tk.StringVar(value=self.cfg.get('outdir',''))
        of = tk.Frame(out_row, bg=BG3); of.pack(side='left', fill='x', expand=True)
        tk.Entry(of, textvariable=self.v_mr_out, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(of, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_mr_out.set(
                     filedialog.askdirectory() or self.v_mr_out.get())
                 ).pack(side='right')

        # Options
        opt_sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        opt_sec.pack(fill='x', padx=16, pady=(0,8))
        opt_inner = tk.Frame(opt_sec, bg=BG2); opt_inner.pack(fill='x', padx=12, pady=10)

        tk.Label(opt_inner, text='Model:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_mr_model = tk.StringVar(value='htdemucs')
        for val, lbl, hint in [
            ('htdemucs',    'HTDemucs',    'Best quality — recommended'),
            ('mdx_extra',   'MDX Extra',   'Faster, good quality'),
            ('htdemucs_ft', 'HTDemucs FT', 'Fine-tuned, slower'),
        ]:
            f = tk.Frame(opt_inner, bg=BG2); f.pack(side='left', padx=(12,0))
            tk.Radiobutton(f, text=lbl, variable=self.v_mr_model, value=val,
                          font=FONT_SMALL, fg=FG, bg=BG2,
                          selectcolor=BG3, activebackground=BG2,
                          cursor='hand2').pack(side='left')
            tk.Label(f, text=hint, font=('Segoe UI',7), fg=FG3, bg=BG2).pack(side='left', padx=(2,0))

        # Keep options
        keep_row = tk.Frame(opt_sec, bg=BG2); keep_row.pack(fill='x', padx=12, pady=(0,10))
        tk.Label(keep_row, text='Keep:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_mr_keep_vocals = tk.BooleanVar(value=True)
        self.v_mr_keep_other  = tk.BooleanVar(value=False)
        tk.Checkbutton(keep_row, text='Vocals', variable=self.v_mr_keep_vocals,
                      font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, cursor='hand2').pack(side='left', padx=(8,0))
        tk.Checkbutton(keep_row, text='Other (SFX/ambience)', variable=self.v_mr_keep_other,
                      font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, cursor='hand2').pack(side='left', padx=(8,0))
        tk.Label(keep_row, text='Music (drums/bass/etc) is always removed',
                font=('Segoe UI',7), fg=FG3, bg=BG2).pack(side='left', padx=8)

        # Run button
        btn_row = tk.Frame(p, bg=BG); btn_row.pack(fill='x', padx=16, pady=8)
        tk.Button(btn_row, text='🎵  REMOVE MUSIC',
                 font=('Segoe UI',10,'bold'), bg=ACCENT, fg='#000',
                 relief='flat', bd=0, cursor='hand2', padx=20, pady=8,
                 command=self._run_music_removal).pack(side='left')
        tk.Label(btn_row, text='Runs locally — no API needed. Requires Demucs (auto-installs).',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=12)

        self.mr_status_lbl = tk.Label(p, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.mr_status_lbl.pack(fill='x', padx=20, pady=4)

    def _run_music_removal(self):
        """Run Demucs to separate music from vocals — keeps vocals stem, discards music."""
        vid = self.v_mr_video.get().strip()
        out = self.v_mr_out.get().strip()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No video', 'Select a video file first.'); return
        if not out:
            messagebox.showerror('No output', 'Select an output folder first.'); return

        model     = self.v_mr_model.get()
        keep_vox  = self.v_mr_keep_vocals.get()
        keep_other= self.v_mr_keep_other.get()
        ff        = ensure_ffmpeg()

        self.set_busy(True)
        self.mr_status_lbl.config(text='⏳ Installing Demucs if needed...', fg=ACCENT2)
        self.log('🎵 Music Removal: starting...', ACCENT2)

        def _run():
            try:
                import subprocess as _sp, sys as _sys, tempfile as _tmp
                _ensure_pkgs_on_path()

                # Check demucs + dependencies installed
                missing = []
                for _m in ('demucs', 'torch', 'torchaudio'):
                    try: __import__(_m)
                    except ImportError: missing.append(_m)
                if missing:
                    self.log(f'❌ Missing: {", ".join(missing)} — install in Settings → Update Modules', RED)
                    self.after(0, lambda: self.mr_status_lbl.config(
                        text=f'❌ Missing: {", ".join(missing)} — install in Settings', fg=RED))
                    return
                # Patch torchaudio to use soundfile backend — avoids torchcodec DLL issues on Windows
                try:
                    import torchaudio as _ta
                    _ta.set_audio_backend('soundfile')
                    self.log('[Music] Using soundfile audio backend', FG2)
                except Exception as _tae:
                    self.log(f'[Music] torchaudio backend note: {_tae}', FG2)

                # Step 1: Extract audio from video
                self.after(0, lambda: self.mr_status_lbl.config(text='⏳ Extracting audio...', fg=ACCENT2))
                self.log('Step 1: Extracting audio...', FG2)
                self.set_progress('🎵 Music Removal: extracting audio...', pct=10)
                tmp_dir = Path(_tmp.mkdtemp())
                audio_path = str(tmp_dir / 'input_audio.wav')
                _sp.run([ff, '-y', '-i', vid, '-vn', '-ar', '44100',
                         '-ac', '2', '-f', 'wav', audio_path],
                        stdout=_sp.PIPE, stderr=_sp.PIPE, check=True)

                # Step 2: Run Demucs separation
                self.after(0, lambda: self.mr_status_lbl.config(
                    text=f'⏳ Separating stems with {model}... (this takes a while)', fg=ACCENT2))
                self.log(f'Step 2: Running Demucs [{model}]...', FG2)
                self.set_progress(f'🎵 Music Removal: separating stems [{model}]...', pct=30)
                sep_out = str(tmp_dir / 'separated')
                # Demucs command — patch torchaudio via python -c before demucs runs
                import os as _os_dm
                _dm_env = dict(_os_dm.environ)
                # Force torchaudio to use soundfile — avoids torchcodec/DLL issues
                _dm_env['TORCHAUDIO_BACKEND'] = 'soundfile'
                _dm_env['TORCH_AUDIO_USE_SOUNDFILE'] = '1'
                # Write a temp launcher script that patches torchaudio before demucs runs
                import tempfile as _tmp2
                _launcher = str(Path(_tmp2.gettempdir()) / 'cf_demucs_launcher.py')
                with open(_launcher, 'w') as _lf:
                    _pkgs_path = str(PKGS_DIR)
                    _lf.write(f"""import sys
sys.path.insert(0, r'{_pkgs_path}')
import soundfile as sf
import torch
import torchaudio

def _sf_load(path, *args, **kwargs):
    data, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return torch.tensor(data.T), sr

def _sf_save(path, src, sample_rate, *args, **kwargs):
    import numpy as np
    data = src.numpy().T  # (channels, samples) -> (samples, channels)
    sf.write(str(path), data, sample_rate)

torchaudio.load = _sf_load
torchaudio.save = _sf_save

from demucs.__main__ import main
sys.exit(main())
""")
                _dm_cmd = [_sys.executable, _launcher,
                           '-n', model,
                           '--two-stems', 'vocals',
                           '--out', sep_out,
                           audio_path]
                _dm_r = _sp.run(_dm_cmd, capture_output=True, text=True, env=_dm_env)
                if _dm_r.returncode != 0:
                    self.log(f'Demucs error: {_dm_r.stderr[-500:]}', RED)
                    raise RuntimeError(f'Demucs failed: {_dm_r.stderr[-200:]}')

                # Step 3: Find stems and mix the ones we want
                self.log('Step 3: Mixing selected stems...', FG2)
                if getattr(self, '_cancel_requested', False): return
                self.set_progress('🎵 Music Removal: mixing stems...', pct=75)
                self.after(0, lambda: self.mr_status_lbl.config(text='⏳ Mixing stems...', fg=ACCENT2))
                # two-stems output: vocals.wav and no_vocals.wav
                sep_track = Path(sep_out) / model / 'input_audio'
                # Try .wav first (default), then .mp3
                def _find_stem(name):
                    for ext in ('wav','mp3','flac'):
                        p = sep_track / f'{name}.{ext}'
                        if p.exists(): return str(p)
                    return None
                stems_to_mix = []
                if keep_vox:
                    v = _find_stem('vocals')
                    if v: stems_to_mix.append(v)
                if keep_other:
                    o = _find_stem('no_vocals')
                    if o: stems_to_mix.append(o)
                if not stems_to_mix:
                    v = _find_stem('vocals')
                    if v: stems_to_mix.append(v)
                if not stems_to_mix:
                    raise RuntimeError(f'No stems found in {sep_track} — check demucs output')

                # Mix stems back together
                mixed_audio = str(tmp_dir / 'mixed.mp3')
                if len(stems_to_mix) == 1:
                    import shutil as _sh
                    _sh.copy2(stems_to_mix[0], mixed_audio)
                else:
                    # amix all stems
                    inputs = []
                    for s in stems_to_mix:
                        inputs += ['-i', s]
                    _sp.run([ff, '-y'] + inputs +
                            ['-filter_complex', f'amix=inputs={len(stems_to_mix)}:duration=longest',
                             mixed_audio],
                            stdout=_sp.PIPE, stderr=_sp.PIPE, check=True)

                # Step 4: Merge cleaned audio back with original video
                self.log('Step 4: Merging with original video...', FG2)
                if getattr(self, '_cancel_requested', False): return
                self.set_progress('🎵 Music Removal: merging audio + video...', pct=90)
                self.after(0, lambda: self.mr_status_lbl.config(text='⏳ Merging audio + video...', fg=ACCENT2))
                stem = Path(vid).stem
                out_path = str(Path(out) / f'{stem} - NoMusic - ClipFinder.mp4')
                _vcodec, _acodec, _extra = get_encoder(ff)
                _sp.run([ff, '-y',
                         '-i', vid,
                         '-i', mixed_audio,
                         '-c:v', 'copy',
                         '-c:a', _acodec,
                         '-map', '0:v:0',
                         '-map', '1:a:0',
                         '-shortest',
                         out_path],
                        stdout=_sp.PIPE, stderr=_sp.PIPE, check=True)

                # Cleanup
                import shutil as _sh2
                _sh2.rmtree(str(tmp_dir), ignore_errors=True)

                size = Path(out_path).stat().st_size / 1024 / 1024
                self.log(f'✅ Done: {Path(out_path).name} ({size:.1f}MB)', GREEN)
                self.after(0, lambda: self.mr_status_lbl.config(
                    text=f'✅ {Path(out_path).name}', fg=GREEN))
                self.after(0, lambda: messagebox.showinfo('Music Removed',
                    f'Saved: {Path(out_path).name}\nLocation: {out}'))

            except Exception as _e:
                import traceback as _tb
                self.log(f'Music Removal error: {_tb.format_exc()}', RED)
                self.after(0, lambda: self.mr_status_lbl.config(text=f'❌ {_e}', fg=RED))
            finally:
                self.set_busy(False)

        threading.Thread(target=_run, daemon=True).start()

    def _build_music_removal_tab(self, p):
        """AI Music Removal using Demucs — strips background music, keeps vocals."""
        tk.Label(p, text='🎵  AI MUSIC REMOVAL', font=('Segoe UI', 10, 'bold'),
                fg=ACCENT, bg=BG).pack(anchor='w', padx=16, pady=(12,2))
        tk.Label(p, text='Strip copyrighted background music. Keeps vocals and speech. Runs locally — no API needed.',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=16, pady=(0,8))

        sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        sec.pack(fill='x', padx=16, pady=(0,6))
        inner = tk.Frame(sec, bg=BG2); inner.pack(fill='x', padx=12, pady=8)

        tk.Label(inner, text='Video:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_mr_video = tk.StringVar()
        vf = tk.Frame(inner, bg=BG3); vf.pack(side='left', fill='x', expand=True)
        tk.Entry(vf, textvariable=self.v_mr_video, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(vf, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_mr_video.set(
                     filedialog.askopenfilename(
                         filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')]
                     ) or self.v_mr_video.get())
                 ).pack(side='right')
        tk.Button(inner, text='Use Clip Finder video', font=FONT_SMALL,
                 bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8,
                 command=lambda: self.v_mr_video.set(self.v_video.get())
                 ).pack(side='left', padx=8)

        out_row = tk.Frame(sec, bg=BG2); out_row.pack(fill='x', padx=12, pady=(0,8))
        tk.Label(out_row, text='Output:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        self.v_mr_out = tk.StringVar(value=self.cfg.get('outdir',''))
        of = tk.Frame(out_row, bg=BG3); of.pack(side='left', fill='x', expand=True)
        tk.Entry(of, textvariable=self.v_mr_out, font=FONT_SMALL,
                bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                ).pack(side='left', fill='x', expand=True)
        tk.Button(of, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                 relief='flat', bd=0, cursor='hand2', padx=6,
                 command=lambda: self.v_mr_out.set(
                     filedialog.askdirectory() or self.v_mr_out.get())
                 ).pack(side='right')

        opt = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        opt.pack(fill='x', padx=16, pady=(0,6))
        opt_i = tk.Frame(opt, bg=BG2); opt_i.pack(fill='x', padx=12, pady=8)
        tk.Label(opt_i, text='Model:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_mr_model = tk.StringVar(value='htdemucs')
        for val, lbl2, hint in [
            ('htdemucs','HTDemucs','Best quality'),
            ('mdx_extra','MDX Extra','Faster'),
            ('htdemucs_ft','HTDemucs FT','Fine-tuned'),
        ]:
            tk.Radiobutton(opt_i, text=f'{lbl2} ({hint})', variable=self.v_mr_model, value=val,
                          font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                          activebackground=BG2, cursor='hand2').pack(side='left', padx=(10,0))

        keep_row = tk.Frame(opt, bg=BG2); keep_row.pack(fill='x', padx=12, pady=(0,8))
        tk.Label(keep_row, text='Keep:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.v_mr_keep_vocals = tk.BooleanVar(value=True)
        self.v_mr_keep_other  = tk.BooleanVar(value=False)
        tk.Checkbutton(keep_row, text='Vocals', variable=self.v_mr_keep_vocals,
                      font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, cursor='hand2').pack(side='left', padx=(8,0))
        tk.Checkbutton(keep_row, text='Other (SFX/ambience)', variable=self.v_mr_keep_other,
                      font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, cursor='hand2').pack(side='left', padx=(8,0))
        tk.Label(keep_row, text='Drums/bass always removed',
                font=('Segoe UI',7), fg=FG3, bg=BG2).pack(side='left', padx=8)

        btn_row = tk.Frame(p, bg=BG); btn_row.pack(fill='x', padx=16, pady=6)
        tk.Button(btn_row, text='🎵  REMOVE MUSIC',
                 font=('Segoe UI',10,'bold'), bg=ACCENT, fg='#000',
                 relief='flat', bd=0, cursor='hand2', padx=20, pady=8,
                 command=self._run_music_removal).pack(side='left')
        try:
            import demucs as _dm_chk  # noqa
            _demucs_ok = True
        except ImportError:
            _demucs_ok = False
        if not _demucs_ok:
            tk.Label(btn_row, text='⚠ Demucs not installed — go to Settings → Update Modules',
                    font=FONT_SMALL, fg=YELLOW, bg=BG).pack(side='left', padx=12)
        self.mr_status_lbl = tk.Label(p, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.mr_status_lbl.pack(fill='x', padx=16)

    def _build_censor_tab(self, p):
        # Load saved word list
        saved_words = self.cfg.get('censor_words', None)
        self._censor_words = saved_words if saved_words is not None else list(self.CENSOR_WORD_LIST)

        # ── Top bar: always-visible controls ─────────────────────────────────
        top = tk.Frame(p, bg=BG2)
        top.pack(fill='x', padx=0, pady=0)

        self.censor_deep_var = tk.BooleanVar(value=False)

        # Row 1: Video in + Output + style all on one line
        r1 = tk.Frame(top, bg=BG2); r1.pack(fill='x', padx=8, pady=(8,3))

        # Input video
        tk.Label(r1, text='Video:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.censor_video_var = tk.StringVar()
        vf = tk.Frame(r1, bg=BG3); vf.pack(side='left', fill='x', expand=True, padx=(3,6))
        tk.Entry(vf, textvariable=self.censor_video_var, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(vf, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.censor_video_var.set(
                      filedialog.askopenfilename(
                          filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')]
                      ) or self.censor_video_var.get())
                  ).pack(side='right')
        tk.Button(r1, text='📋', font=FONT_SMALL, bg=BG2, fg=ACCENT2,
                  relief='flat', bd=0, cursor='hand2', padx=4,
                  command=lambda: self.censor_video_var.set(self.v_video.get())
                  ).pack(side='left')

        # Output folder
        tk.Label(r1, text='Out:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left', padx=(6,0))
        of = tk.Frame(r1, bg=BG3); of.pack(side='left', fill='x', expand=True, padx=(3,0))
        self.censor_out_var = tk.StringVar(value=self.cfg.get('censor_outdir', str(Path.home()/'Downloads')))
        tk.Entry(of, textvariable=self.censor_out_var, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(of, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.censor_out_var.set(
                      filedialog.askdirectory() or self.censor_out_var.get())
                  ).pack(side='right')
        self.censor_out_var.trace_add('write', lambda *_: (
            self.cfg.update({'censor_outdir': self.censor_out_var.get()}), save_cfg(self.cfg)))

        # Row 2: Replace style + MP3 + AI toggle + go button all on one line
        r2 = tk.Frame(top, bg=BG2); r2.pack(fill='x', padx=8, pady=(0,6))

        tk.Label(r2, text='Replace:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        self.censor_style = tk.StringVar(value=self.cfg.get('censor_style','beep'))
        for val, lbl in [('beep','📢 Beep'), ('silence','🔇 Silence'), ('mp3','🎵 MP3')]:
            tk.Radiobutton(r2, text=lbl, variable=self.censor_style, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                           activebackground=BG2, relief='flat', cursor='hand2',
                           command=self._censor_refresh_style
                           ).pack(side='left', padx=(4,0))
        self.censor_style.trace_add('write', lambda *_: (
            self.cfg.update({'censor_style': self.censor_style.get()}), save_cfg(self.cfg)))

        # MP3 inline (always visible)
        tk.Label(r2, text='MP3:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left', padx=(8,0))
        mp3f = tk.Frame(r2, bg=BG3); mp3f.pack(side='left', fill='x', expand=True, padx=(3,6))
        self.censor_mp3_var = tk.StringVar(value=self.cfg.get('censor_mp3',''))
        tk.Entry(mp3f, textvariable=self.censor_mp3_var, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(mp3f, text='...', font=FONT_SMALL, bg=BG2, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=5,
                  command=lambda: self.censor_mp3_var.set(
                      filedialog.askopenfilename(
                          filetypes=[('Audio','*.mp3 *.wav *.ogg'),('All','*.*')]
                      ) or self.censor_mp3_var.get())
                  ).pack(side='right')
        self.censor_mp3_var.trace_add('write', lambda *_: (
            self.cfg.update({'censor_mp3': self.censor_mp3_var.get()}), save_cfg(self.cfg)))

        # AI toggle + detect label
        self.censor_ai_pass = tk.BooleanVar(value=self.cfg.get('censor_ai_pass', False))
        tk.Checkbutton(r2, text='🤖 AI filter', variable=self.censor_ai_pass,
                       font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                       activebackground=BG2, relief='flat', cursor='hand2',
                       command=lambda: (
                           self.cfg.update({'censor_ai_pass': self.censor_ai_pass.get()}),
                           save_cfg(self.cfg))
                       ).pack(side='left', padx=(4,8))

        # Go + queue buttons
        tk.Checkbutton(r2, text='🔍 Deep Scan (medium model)',
                      variable=self.censor_deep_var,
                      font=FONT_SMALL, fg=ACCENT2, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, relief='flat', cursor='hand2'
                      ).pack(side='left', padx=(0,8))
        self.censor_go_btn = tk.Button(r2, text='🔇 CENSOR',
                                       font=('Segoe UI', 9,'bold'),
                                       bg=ACCENT, fg='#000', relief='flat', bd=0,
                                       cursor='hand2', padx=12, pady=4,
                                       activebackground=ACCENT2,
                                       command=self._censor_start)
        self.censor_go_btn.pack(side='left', padx=(0,4))
        tk.Button(r2, text='➕ Queue', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._censor_add_queue).pack(side='left', padx=(0,4))
        tk.Button(r2, text='▶ Run Queue', font=FONT_SMALL,
                  bg=GREEN, fg='#000', relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._censor_run_queue).pack(side='left')

        tk.Frame(top, bg=BORDER, height=1).pack(fill='x')

        # ── Bottom split: word list left, results right ───────────────────────
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True)

        # Left: word list + queue (compact)
        wl_frame = tk.Frame(body, bg=BG, width=220)
        wl_frame.pack(side='left', fill='y')
        wl_frame.pack_propagate(False)
        tk.Frame(body, bg=BORDER, width=1).pack(side='left', fill='y')

        # Right: results
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        # Word list
        wl_hdr = tk.Frame(wl_frame, bg=BG); wl_hdr.pack(fill='x', padx=8, pady=(8,2))
        tk.Label(wl_hdr, text='BANNED WORDS', font=('Segoe UI', 8,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Button(wl_hdr, text='💾', font=FONT_SMALL, bg=BG, fg=FG2,
                  relief='flat', bd=0, cursor='hand2',
                  command=self._censor_save_words).pack(side='right')
        tk.Button(wl_hdr, text='↺', font=FONT_SMALL, bg=BG, fg=FG2,
                  relief='flat', bd=0, cursor='hand2',
                  command=self._censor_reset_words).pack(side='right', padx=(0,4))
        tk.Label(wl_frame, text='One per line, case-insensitive',
                 font=('Segoe UI', 7), fg=FG2, bg=BG).pack(anchor='w', padx=8)
        wlw = tk.Frame(wl_frame, bg=BG3); wlw.pack(fill='both', expand=True, padx=8, pady=(3,4))
        self.censor_word_box = tk.Text(wlw, font=FONT_MONO_S, bg=BG3, fg=FG,
                                       insertbackground=ACCENT, relief='flat', bd=4,
                                       wrap='word', )
        self.censor_word_box.pack(fill='both', expand=True)
        _make_scrollbar(wlw, self.censor_word_box)
        self.censor_word_box.insert('1.0', chr(10).join(self._censor_words))

        # Queue listbox below word list
        tk.Label(wl_frame, text='QUEUE', font=('Segoe UI', 8,'bold'),
                 fg=ACCENT, bg=BG).pack(anchor='w', padx=8, pady=(4,1))
        qw = tk.Frame(wl_frame, bg=BG3); qw.pack(fill='x', padx=8, pady=(0,4))
        self.censor_queue_lb = tk.Listbox(qw, font=('Segoe UI', 7), bg=BG3, fg=FG2,
                                           selectbackground=ACCENT, selectforeground='#000',
                                           relief='flat', bd=4, height=3, activestyle='none')
        self.censor_queue_lb.pack(fill='x')
        tk.Button(wl_frame, text='🗑 Clear queue', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', pady=3,
                  command=self._censor_clear_queue).pack(fill='x', padx=8, pady=(0,4))

        self.censor_status = tk.Label(wl_frame, text='Ready.',
                                      font=FONT_SMALL, fg=FG2, bg=BG,
                                      wraplength=200, justify='left')
        self.censor_status.pack(anchor='w', padx=8, pady=(0,4))

        # Results
        rh = tk.Frame(right, bg=BG); rh.pack(fill='x', padx=8, pady=(8,4))
        tk.Label(rh, text='RESULTS', font=('Segoe UI', 8,'bold'), fg=ACCENT, bg=BG).pack(side='left')
        self.censor_result_lbl = tk.Label(rh, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self.censor_result_lbl.pack(side='left', padx=6)
        tk.Button(rh, text='🗑 Clear', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                  command=lambda: [w.destroy() for w in self.censor_results_frame.winfo_children()] or
                  self.censor_result_lbl.config(text='')
                  ).pack(side='right')

        rw = tk.Frame(right, bg=BG3); rw.pack(fill='both', expand=True, padx=8, pady=(0,8))
        rcv = tk.Canvas(rw, bg=BG3, bd=0, highlightthickness=0)
        _make_scrollbar(rw, rcv)
        rcv.pack(side='left', fill='both', expand=True)
        
        
        self.censor_results_frame = tk.Frame(rcv, bg=BG3)
        self.censor_results_frame.bind('<Configure>',
            lambda e: rcv.configure(scrollregion=rcv.bbox('all')))
        rcv.create_window((0,0), window=self.censor_results_frame, anchor='nw', tags='ri')
        rcv.bind('<Configure>', lambda e: rcv.itemconfig('ri', width=e.width))
        rcv.bind('<MouseWheel>', lambda e: rcv.yview_scroll(int(-1*(e.delta/120)),'units'))
        tk.Label(self.censor_results_frame,
                 text='\n  Censor a video to see results here.\n',
                 font=FONT_MONO_S, fg=FG2, bg=BG3).pack(pady=20)

    def _censor_refresh_style(self):
        pass  # MP3 field always visible in new compact layout

    def _censor_save_words(self):
        words = [w.strip().lower() for w in
                 self.censor_word_box.get('1.0','end').splitlines() if w.strip()]
        self._censor_words = words
        self.cfg['censor_words'] = words
        save_cfg(self.cfg)
        self._censor_set_status(f'Saved {len(words)} words.', GREEN)

    def _censor_reset_words(self):
        self._censor_words = list(self.CENSOR_WORD_LIST)
        self.censor_word_box.delete('1.0','end')
        self.censor_word_box.insert('1.0', chr(10).join(self._censor_words))
        self._censor_save_words()

    def _censor_set_status(self, msg, color=None):
        def _do():
            try: self.censor_status.config(text=msg, fg=color or FG2)
            except: pass
        if threading.current_thread() is threading.main_thread(): _do()
        else: self.after(0, _do)

    def _censor_add_queue(self):
        vid = self.censor_video_var.get().strip()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No file', 'Select a valid video file first.')
            return
        self._censor_queue.append(vid)
        self.censor_queue_lb.insert('end', Path(vid).name)
        self._censor_set_status(f'{len(self._censor_queue)} video(s) in queue.')

    def _censor_clear_queue(self):
        self._censor_queue.clear()
        self.censor_queue_lb.delete(0, 'end')
        self._censor_set_status('Queue cleared.')

    def _censor_start(self):
        if self._censor_running: return
        vid = self.censor_video_var.get().strip()
        if not vid or not Path(vid).exists():
            messagebox.showerror('No file', 'Select a valid video file.')
            return
        self._censor_save_words()
        self._censor_running = True
        self.censor_go_btn.config(state='disabled', text='⏳  Processing...')
        self._censor_set_status('Starting...')
        threading.Thread(target=self._censor_run, args=([vid],), daemon=True).start()

    def _censor_run_queue(self):
        if self._censor_running: return
        if not self._censor_queue:
            messagebox.showwarning('Empty', 'Add videos to queue first.')
            return
        self._censor_save_words()
        self._censor_running = True
        self.censor_go_btn.config(state='disabled')
        videos = list(self._censor_queue)
        threading.Thread(target=self._censor_run, args=(videos,), daemon=True).start()

    def _censor_run(self, video_list):
        try:
            import tempfile as _tmp, numpy as _np
            from PIL import Image as _Img

            ff  = ensure_ffmpeg()
            out = self.censor_out_var.get().strip()
            Path(out).mkdir(parents=True, exist_ok=True)
            style    = self.censor_style.get()
            mp3_path = self.censor_mp3_var.get().strip()
            words    = [w.lower() for w in self._censor_words if w.strip()]

            for vi, vid in enumerate(video_list):
                vid_name = Path(vid).name
                self._censor_set_status(f'[{vi+1}/{len(video_list)}] Transcribing {vid_name}...')
                self.log(f'[Censor] Transcribing: {vid_name}')
                def _censor_prog(pct, msg, vi=vi, n=len(video_list)):
                    if pct is not None:
                        lbl = f'[{vi+1}/{n}] Transcribing... {pct}%'
                        self.after(0, lambda m=lbl, p=pct:
                            self.set_progress(m, step=2, total=4, pct=p))

                # ── Step 1: Transcribe with word timestamps ───────────────────
                # For censor, use at least 'small' model for better accuracy
                _censor_model = self.v_whisper.get()
                if _censor_model in ('auto', ''):
                    _censor_model = 'small'  # censor needs accuracy
                _model_order  = ['tiny','base','small','medium']
                if self.censor_deep_var.get():
                    _censor_model = 'medium'  # deep mode: best accuracy
                elif _model_order.index(_censor_model) < _model_order.index('small'):
                    _censor_model = 'small'   # minimum small for censor accuracy

                # Check if we can reuse existing transcript (no need to re-transcribe)
                _can_reuse = (Path(vid) == Path(self.v_video.get()) and
                              bool(self._whisper_segments) and
                              sum(1 for s in self._whisper_segments if s.get('words')) > 0)
                if _can_reuse:
                    self.log(f'[Censor] Will reuse current transcript — skipping re-transcription')
                else:
                    self.log(f'[Censor] Using whisper model: {_censor_model}')
                n_vids = len(video_list)
                self.set_progress(f'[{vi+1}/{n_vids}] Transcribing {vid_name}...',
                                 step=1, total=4, pct=0)
                if _can_reuse:
                    self.log(f'[Censor] Reusing existing transcript ({len(self._whisper_segments)} segs)')
                    result = {'segments': self._whisper_segments, 'language': 'en'}
                else:
                    # For censor we MUST have word timestamps — use faster-whisper directly
                    # whisper.cpp doesn't return word-level timestamps in its JSON output
                    self.log(f'[Censor] Using faster-whisper (word timestamps required)')
                    try:
                        _FW = _fresh_import('faster_whisper').WhisperModel
                        _fwc = _FWC(_censor_model, device='cpu', compute_type='int8')
                        # Extract audio first
                        import tempfile as _tmpc
                        _wav_tmp = str(Path(_tmpc.gettempdir()) / 'cf_censor_fw.wav')
                        subprocess.run([ff, '-y', '-i', vid, '-vn', '-ar', '16000',
                                       '-ac', '1', '-f', 'wav', _wav_tmp],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        _segs_iter, _info = _fwc.transcribe(
                            _wav_tmp, word_timestamps=True,
                            initial_prompt='Transcribe every word exactly as spoken including profanity.',
                            language=None, vad_filter=True)
                        _segs = []
                        for _seg in _segs_iter:
                            _sd = {'start': _seg.start, 'end': _seg.end, 'text': _seg.text}
                            if _seg.words:
                                _sd['words'] = [{'word': w.word, 'start': w.start, 'end': w.end}
                                               for w in _seg.words]
                            _segs.append(_sd)
                        result = {'segments': _segs, 'language': _info.language}
                        try: Path(_wav_tmp).unlink()
                        except: pass
                        self.log(f'[Censor] faster-whisper done: {len(_segs)} segs')
                    except Exception as _fwe:
                        self.log(f'[Censor] faster-whisper failed ({_fwe}), falling back to whisper.cpp')
                        result = _do_transcribe(vid, _censor_model,
                            initial_prompt='Transcribe every word exactly as spoken including profanity.',
                            ffmpeg_path=ff, use_word_timestamps=True,
                            progress_cb=_censor_prog)
                segs = result.get('segments', [])
                has_words = sum(1 for s in segs if s.get('words'))
                total_words = sum(len(s.get('words',[])) for s in segs)
                self.log(f'[Censor] {len(segs)} segments, {has_words} with word timestamps ({total_words} total words)')
                if not has_words:
                    self.log('[Censor] ⚠️ No word timestamps — will use segment-level detection', YELLOW)
                # Log each segment's text so we can verify all speech is captured
                for _si, _seg in enumerate(segs):
                    _wc = len(_seg.get('words', []))
                    self.log(f'[Censor] seg{_si+1} [{_seg["start"]:.1f}s]: "{_seg.get("text","").strip()}" ({_wc} words)')

                # ── Step 2: Find banned word timestamps ───────────────────────
                self._censor_set_status(f'[{vi+1}/{len(video_list)}] Scanning for banned words...')
                self.set_progress(f'[{vi+1}/{len(video_list)}] Scanning for banned words...',
                                 step=2, total=4, pct=25)
                hits = []  # list of (start, end, word)

                # Phonetic aliases — ONLY words that are clearly wrong transcriptions
                # of profanity, NOT actual normal words people say
                _PHONETIC = {
                    'fuck':        ['f*ck','fck','fuuuck','fuhh','ffff'],
                    'shit':        ['sh*t','shiit','shiiit'],
                    'bitch':       ['biatch','biotch','b*tch'],
                    'ass':         ['arse','a**'],
                    'motherfucker':['motherf','mfer','mf'],
                    'nigga':       ['n*gga','niggas'],
                    'nigger':      ['n*gger'],
                }
                # Build flat lookup: alias -> canonical banned word
                _alias_map = {}
                for _canon, _aliases in _PHONETIC.items():
                    for _a in _aliases:
                        _alias_map[''.join(c for c in _a.lower() if c.isalpha())] = _canon

                def _word_matches_banned(w_clean, banned_list):
                    """Check if a transcribed word matches any banned word."""
                    # Minimum length — never match single chars or 2-char words
                    if len(w_clean) < 2: return None

                    # Check phonetic aliases first
                    if w_clean in _alias_map:
                        _canon = _alias_map[w_clean]
                        if any(''.join(c for c in _b.lower() if c.isalpha()) == _canon
                               for _b in banned_list):
                            return _canon

                    for _b in banned_list:
                        b = ''.join(c for c in _b.lower() if c.isalpha())
                        # Skip banned words shorter than 3 chars (too many false positives)
                        if len(b) < 3 or not w_clean: continue
                        if len(b) <= 3:
                            # Very short (3 chars like "ass"): exact match OR
                            # starts compound word: "asshole", "asses" — not "asset", "classic"
                            if w_clean == b:
                                return _b
                            # Only allow compound if next char is h,e,i,s (asshole/asses)
                            if (w_clean.startswith(b + 'h') or
                                w_clean.startswith(b + 'es') or
                                w_clean.startswith(b + 'in')):
                                return _b
                        elif len(b) <= 5:
                            # Medium (fuck, shit, bitch): startswith catches fucking/shithead
                            if w_clean == b or w_clean.startswith(b):
                                return _b
                            # Contained in compound (motherfucker, bullshit)
                            if b in w_clean and len(w_clean) <= len(b) + 8:
                                return _b
                        else:
                            # Long words: exact or starts-with only
                            if w_clean == b or w_clean.startswith(b):
                                return _b
                    return None

                for seg in segs:
                    seg_words = seg.get('words', [])
                    if seg_words:
                        for wd in seg_words:
                            w_raw   = wd.get('word', '')
                            w_clean = ''.join(c for c in w_raw.lower() if c.isalpha())
                            if not w_clean: continue
                            matched = _word_matches_banned(w_clean, words)
                            if matched:
                                hits.append((
                                    max(0.0, wd['start'] - 0.15),  # start 0.15s early
                                    wd['end'] + 0.1,
                                    w_clean
                                ))
                    else:
                        # No word timestamps — estimate position within segment
                        seg_text   = seg.get('text', '').lower()
                        seg_clean  = ''.join(c if c.isalpha() else ' ' for c in seg_text)
                        seg_tokens = seg_clean.split()
                        seg_dur    = seg['end'] - seg['start']
                        for _ti, tok in enumerate(seg_tokens):
                            if _word_matches_banned(tok, words):
                                # Estimate position proportionally within segment
                                frac   = _ti / max(len(seg_tokens), 1)
                                word_t = seg['start'] + frac * seg_dur
                                # Start beep 0.15s early, cover full word + 0.1s tail
                                hits.append((max(0, word_t - 0.15), word_t + 0.6, tok))
                # ── Step 3: AI context pass (optional) ───────────────────────
                if self.censor_ai_pass.get() and hits:
                    self._censor_set_status('AI context pass...')
                    self.set_progress('AI filtering false positives...', step=3, total=4, pct=50)
                    hits = self._censor_ai_filter(segs, hits)

                self.log(f'[Censor] Found {len(hits)} words to censor: {[h[2] for h in hits]}', YELLOW if hits else GREEN)
                for _ht in hits:
                    self.log(f'[Censor]   "{_ht[2]}" at {_ht[0]:.2f}s–{_ht[1]:.2f}s')

                if not hits:
                    self.log(f'[Censor] No banned words found in {vid_name}', GREEN)
                    self.log(f'[Censor] Tip: If you know there are swear words, try enabling 🔍 Deep Scan with the medium model', FG2)
                    self._censor_set_status(f'No banned words found in {vid_name}', GREEN)
                    self.set_progress(f'No banned words found', pct=100)
                    self.after(0, lambda v=vid: self._censor_render_result(v, [], None))
                    continue

                # ── Step 4: Extract + patch audio ────────────────────────────
                self._censor_set_status(f'[{vi+1}/{len(video_list)}] Patching audio...')
                self.set_progress(f'[{vi+1}/{len(video_list)}] Patching audio — {len(hits)} words...',
                                 step=4, total=4, pct=75)
                tmp_dir = _tmp.mkdtemp(prefix='cf_censor_')
                try:
                    # Extract full audio as WAV
                    wav_in  = str(Path(tmp_dir) / 'audio_in.wav')
                    wav_out = str(Path(tmp_dir) / 'audio_out.wav')
                    subprocess.run([ff,'-y','-i',vid,'-vn','-ar','44100','-ac','2',
                                   '-f','wav',wav_in],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    try:
                        _sf = _fresh_import('soundfile')
                        _np2 = _fresh_import('numpy')
                    except ImportError:
                        raise ImportError('soundfile/numpy not installed. Go to Settings → Update Modules to install them.')
                    audio, sr = _sf.read(wav_in, dtype='float32')
                    n_ch = audio.shape[1] if audio.ndim == 2 else 1
                    self.log(f'[Censor] Audio: {len(audio)/sr:.1f}s, {sr}Hz, {n_ch}ch')

                    def _make_bleep_stereo(mono_bleep, length, channels):
                        """Tile mono bleep to required length and channels."""
                        if len(mono_bleep) < length:
                            reps = (length // len(mono_bleep)) + 2
                            mono_bleep = _np2.tile(mono_bleep, reps)
                        mono_bleep = mono_bleep[:length]
                        if channels == 2:
                            return _np2.stack([mono_bleep, mono_bleep], axis=1)
                        return mono_bleep

                    # Load bleep source
                    bleep_mono = None
                    if style == 'beep':
                        bleep_mono = self._censor_make_beep(sr)
                    elif style == 'mp3' and mp3_path and Path(mp3_path).exists():
                        raw, bsr = _sf.read(mp3_path, dtype='float32')
                        # Convert to mono if stereo
                        bleep_mono = raw.mean(axis=1) if raw.ndim == 2 else raw
                        if bsr != sr:
                            # Simple resample via repeat/decimate
                            ratio = sr / bsr
                            new_len = int(len(bleep_mono) * ratio)
                            bleep_mono = _np2.interp(
                                _np2.linspace(0, len(bleep_mono), new_len),
                                _np2.arange(len(bleep_mono)), bleep_mono
                            ).astype('float32')

                    # Apply censoring
                    audio_patched = audio.copy()
                    for start_t, end_t, word in hits:
                        s = int(start_t * sr)
                        e = int(end_t   * sr)
                        e = min(e, len(audio_patched))
                        if e <= s:
                            self.log(f'[Censor] ⚠️ Zero-length hit at {start_t:.2f}s, skipping')
                            continue
                        seg_len = e - s
                        self.log(f'[Censor] Censoring "{word}" samples {s}–{e} ({seg_len} samples)')
                        if style == 'silence':
                            audio_patched[s:e] = 0.0
                        elif bleep_mono is not None:
                            patch = _make_bleep_stereo(bleep_mono, seg_len, n_ch)
                            audio_patched[s:e] = patch

                    # Verify patch was applied
                    diff = _np2.abs(audio_patched - audio).max()
                    self.log(f'[Censor] Max audio diff after patch: {diff:.4f} (0=unchanged)')
                    if diff < 0.001:
                        self.log('[Censor] ⚠️ Audio unchanged — patch may have failed!', YELLOW)

                    _sf.write(wav_out, audio_patched, sr)

                    # Mux patched audio back into video
                    out_name = f'{Path(vid).stem}_censored.mp4'
                    out_path = str(Path(out) / out_name)
                    # Log wav_out size to confirm it exists and has data
                    wav_sz = Path(wav_out).stat().st_size if Path(wav_out).exists() else 0
                    self.log(f'[Censor] wav_out size: {wav_sz//1024}KB')

                    r = subprocess.run(
                        [ff,'-y',
                         '-i', vid,
                         '-i', wav_out,
                         '-map', '0:v:0',
                         '-map', '1:a:0',
                         '-c:v', 'copy',
                         '-c:a', 'aac',
                         '-b:a', '192k',
                         '-avoid_negative_ts', 'make_zero',
                         out_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    mux_err = (r.stderr or b'').decode(errors='replace')
                    if r.returncode == 0:
                        out_sz = Path(out_path).stat().st_size if Path(out_path).exists() else 0
                        self.log(f'[Censor] ✅ Saved: {out_name} ({out_sz//1024}KB)', GREEN)
                        self.after(0, lambda v=vid, h=hits, op=out_path:
                            self._censor_render_result(v, h, op))
                    else:
                        self.log(f'[Censor] ❌ Mux failed (rc={r.returncode}): {mux_err[-300:]}', RED)
                finally:
                    import shutil as _sh
                    _sh.rmtree(tmp_dir, ignore_errors=True)

            total = len(video_list)
            self._censor_set_status(f'Done! {total} video(s) censored → {out}', GREEN)
            self.after(0, lambda t=total, o=out: (
                self.set_progress(f'✅ Done — {t} video(s) censored', pct=100),
                messagebox.showinfo('Done', f'Censored {t} video(s)\nSaved to: {o}')
            ))

        except Exception:
            err = traceback.format_exc()
            self.log(f'[Censor] Error:\n{err}', RED)
            self._censor_set_status('Error — check log.', RED)
        finally:
            self._censor_running = False
            self.after(0, lambda: self.censor_go_btn.config(
                state='normal', text='🔇  CENSOR VIDEO'))
            self._censor_clear_queue()

    def _censor_make_beep(self, sr, freq=1000, duration=None):
        """Generate a sine wave beep at given frequency."""
        import numpy as _np
        t = _np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        beep = (_np.sin(2 * _np.pi * freq * t) * 0.7).astype('float32')
        # Fade in/out to avoid clicks
        fade = int(sr * 0.01)
        beep[:fade]  *= _np.linspace(0, 1, fade)
        beep[-fade:] *= _np.linspace(1, 0, fade)
        return beep

    def _censor_ai_filter(self, segs, hits):
        """Use AI to verify hits in context — removes false positives."""
        try:
            # Build context around each hit
            transcript = ' '.join(seg.get('text','') for seg in segs)
            word_list  = list(set(h[2] for h in hits))
            prompt = f"""You are a content moderation assistant.

The following words were found in a video transcript and may need to be censored for YouTube/TikTok:
Words found: {word_list}

Transcript excerpt:
{transcript[:4000]}

For each word, decide if it should be censored based on context:
- Censor if used as a slur, insult, or in a harmful context
- Do NOT censor if it's being quoted, discussed academically, or used in a clearly non-harmful way

Return ONLY a JSON object: {{"keep": ["word1", "word2"], "remove": ["word3"]}}
where "keep" = words to censor, "remove" = false positives to skip."""

            result_text = None
            for prov in [p for p in [self.v_provider.get()] +
                         list(PROVIDERS.keys()) if self._keys.get(p,'').strip()]:
                try:
                    result_text = self._call_provider_raw(prov, prompt)
                    break
                except Exception:
                    continue

            if result_text:
                import json as _j, re as _re
                m = _re.search(r'\{.*\}', result_text, _re.DOTALL)
                if m:
                    data = _j.loads(m.group(0))
                    keep_words = set(w.lower() for w in data.get('keep', []))
                    if keep_words:
                        hits = [h for h in hits if h[2].lower() in keep_words]
                        self.log(f'[Censor] AI filtered to {len(hits)} confirmed hits')
        except Exception as ex:
            import traceback
            self.log(f'[Censor] AI filter error: {ex}', YELLOW)
            self.log(traceback.format_exc()[:300], YELLOW)
        return hits

    def _censor_render_result(self, vid, hits, out_path):
        """Show result card in right panel."""
        card = tk.Frame(self.censor_results_frame, bg=BG2,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', padx=6, pady=5)
        inner = tk.Frame(card, bg=BG2); inner.pack(fill='x', padx=10, pady=8)

        # Header
        hdr = tk.Frame(inner, bg=BG2); hdr.pack(fill='x')
        status_icon = '✅' if out_path else 'ℹ️'
        tk.Label(hdr, text=f'{status_icon} {Path(vid).name}',
                 font=('Segoe UI', 9,'bold'), fg=FG, bg=BG2).pack(side='left')

        if hits:
            tk.Label(inner, text=f'{len(hits)} word(s) censored',
                     font=FONT_SMALL, fg=YELLOW, bg=BG2).pack(anchor='w', pady=(2,0))
            # Show what was censored
            words_str = ', '.join(set(h[2] for h in hits))
            tk.Label(inner, text=f'Words: {words_str}',
                     font=FONT_SMALL, fg=FG2, bg=BG2, wraplength=420).pack(anchor='w')
            # Timeline of hits
            if len(hits) <= 20:
                times_str = '  '.join(f'{ts(h[0])}' for h in hits)
                tk.Label(inner, text=f'At: {times_str}',
                         font=('Courier New',7), fg=FG2, bg=BG2,
                         wraplength=420, justify='left').pack(anchor='w')
        else:
            tk.Label(inner, text='No banned words found — video is clean!',
                     font=FONT_SMALL, fg=GREEN, bg=BG2).pack(anchor='w', pady=(2,0))

        if out_path:
            btn_row = tk.Frame(inner, bg=BG2); btn_row.pack(anchor='w', pady=(6,0))
            tk.Button(btn_row, text='📂 Open folder', font=FONT_SMALL,
                      bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                      padx=8, pady=3,
                      command=lambda: os.startfile(str(Path(out_path).parent))
                      ).pack(side='left', padx=(0,6))
            tk.Button(btn_row, text='▶ Open video', font=FONT_SMALL,
                      bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                      padx=8, pady=3,
                      command=lambda p=out_path: os.startfile(p)
                      ).pack(side='left')

        # Update result count
        n = len(self.censor_results_frame.winfo_children())
        self.censor_result_lbl.config(text=f'{n} video(s) processed')

    # ═══════════════════════════════════════════════════════════════════════════
    # END CENSOR TAB
    # ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    def _prelaunch_install():
        import subprocess as _sp2, sys as _sys2, tempfile as _tf2, os as _os2, threading as _thr3
        _CNW = 0x08000000
        _flag  = USER_DIR / 'pending_update.flag'
        _stamp = USER_DIR / 'install_done.stamp'
        _ALL = [('faster_whisper', 'faster-whisper'), ('whisper', 'openai-whisper'), ('google.genai', 'google-genai'), ('groq', 'groq'), ('openai', 'openai'), ('yt_dlp', 'yt-dlp==2025.9.26'), ('curl_cffi', 'curl-cffi'), ('PIL', 'Pillow'), ('cv2', 'opencv-python'), ('imagehash', 'imagehash'), ('mediapipe', 'mediapipe'), ('soundfile', 'soundfile'), ('numpy', 'numpy'), ('requests', 'requests'), ('demucs', 'demucs'), ('torch', 'torch'), ('torchaudio', 'torchaudio'), ('pydantic_core', 'pydantic-core'), ('pydantic', 'pydantic'), ('fontTools', 'fonttools')]
        _force = _flag.exists() or not _stamp.exists()
        if not _force:
            _miss = []
            for _m, _p in _ALL:
                try: __import__(_m.split('.')[0])
                except: _miss.append(_p)
            try: import pydantic_core.core_schema
            except:
                if 'pydantic-core' not in [x.split()[0] for x in _miss]: _miss.append('pydantic-core')
            if not _miss: return
        _req = set()
        if _flag.exists():
            try: _req = set(_flag.read_text().strip().splitlines())
            except: pass
            try: _flag.unlink()
            except: pass
        if 'all' in _req or not _stamp.exists():
            _todo = [p for _, p in _ALL]
        else:
            _todo = list(_req)
            for _m, _p in _ALL:
                try: __import__(_m.split('.')[0])
                except:
                    if _p not in _todo: _todo.append(_p)
        if not _todo: _stamp.touch(); return
        _lines = [
            'import subprocess, sys',
            'pkgs_dir = ' + repr(str(PKGS_DIR)),
            'todo = ' + repr(_todo),
            'total = len(todo)',
            'for i, pkg in enumerate(todo):',
            '    parts = pkg.split()',
            '    print(f"PROGRESS:{i}:{total}:{parts[0]}", flush=True)',
            '    cmd = [sys.executable, "-m", "pip", "install"] + parts + ["--target", pkgs_dir, "--upgrade", "--quiet", "--no-warn-script-location"]',
            '    subprocess.run(cmd, timeout=300, creationflags=0x08000000)',
            'print("DONE", flush=True)',
        ]
        _tf = _tf2.mktemp(suffix='_cf.py')
        try:
            with open(_tf, 'w', encoding='utf-8') as _f: _f.write('\n'.join(_lines))
            import tkinter as _tk2, tkinter.ttk as _ttk2
            _s = _tk2.Tk()
            _s.title('ClipFinder — Setting Up')
            _s.configure(bg='#111111')
            _s.resizable(False, False)
            _s.attributes('-topmost', True)
            _sw, _sh = 540, 175
            _sx = (_s.winfo_screenwidth()-_sw)//2
            _sy = (_s.winfo_screenheight()-_sh)//2
            _s.geometry(str(_sw)+'x'+str(_sh)+'+'+str(_sx)+'+'+str(_sy))
            _brd = _tk2.Frame(_s, bg='#ff8c00', padx=1, pady=1); _brd.pack(fill='both', expand=True, padx=8, pady=8)
            _inn = _tk2.Frame(_brd, bg='#111111'); _inn.pack(fill='both', expand=True)
            _tk2.Label(_inn, text='✂  ClipFinder', font=('Segoe UI',13,'bold'), fg='#ff8c00', bg='#111111').pack(pady=(12,2))
            _sv = _tk2.StringVar(value='Installing '+str(len(_todo))+' package'+('s' if len(_todo)!=1 else '')+'...')
            _tk2.Label(_inn, textvariable=_sv, font=('Segoe UI',9), fg='#cccccc', bg='#111111').pack()
            _pb = _ttk2.Progressbar(_inn, length=460, mode='indeterminate'); _pb.pack(pady=(8,2), padx=20); _pb.start(15)
            _bv = _tk2.StringVar(value='Starting...')
            _tk2.Label(_inn, textvariable=_bv, font=('Segoe UI',7), fg='#666', bg='#111111').pack()
            _tk2.Label(_inn, text='⚠  May appear frozen — this is normal. Takes 3–5 min on first launch only.',
                font=('Segoe UI',7), fg='#ff8c00', bg='#111111').pack(pady=(2,0))
            _tk2.Label(_inn, text='ClipFinder will open automatically when done.',
                font=('Segoe UI',7), fg='#444', bg='#111111').pack()
            _s.update()
            _n = len(_todo)
            _proc = _sp2.Popen([_sys2.executable, _tf], stdout=_sp2.PIPE, stderr=_sp2.DEVNULL,
                text=True, bufsize=1, creationflags=_CNW)

            # Read stdout in a thread, update UI via queue (not after() — mainloop not running yet)
            import queue as _q2
            _updates = _q2.Queue()
            def _read():
                for _ln in _proc.stdout:
                    _ln = _ln.strip()
                    if _ln.startswith('PROGRESS:'):
                        try:
                            _, _i, _t, _nm = _ln.split(':', 3)
                            _updates.put((int(_i), int(_t), _nm))
                        except: pass
                _updates.put(None)  # signal done
            _thr3.Thread(target=_read, daemon=True).start()

            # Poll loop — keeps tkinter alive and drains the update queue
            while True:
                try:
                    _msg = _updates.get_nowait()
                    if _msg is None:
                        break
                    _pi, _pt, _pn = _msg
                    _pb.stop(); _pb.config(mode='determinate')
                    _pb['value'] = int(_pi / _pt * 100)
                    _sv.set(f'Installing ({_pi+1}/{_pt})...')
                    _bv.set(_pn)
                except _q2.Empty:
                    pass
                _s.update()
                _sp2.time.sleep(0.05) if hasattr(_sp2, 'time') else None
                import time as _t2; _t2.sleep(0.05)

            _proc.wait()
            _pb['value'] = 100
            _sv.set('Done! Launching ClipFinder...')
            _bv.set('ClipFinder will open automatically')
            _s.update()
            _stamp.touch()
            _s.after(1200, _s.destroy); _s.mainloop()
        except Exception: pass
        finally:
            try: _os2.unlink(_tf)
            except: pass
    _prelaunch_install()
    app = App()
    app.mainloop()