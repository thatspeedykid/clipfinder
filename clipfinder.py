"""
ClipFinder — AI Drama Clip Extractor
Run: python clipfinder.py  OR  ClipFinder.exe

When running as EXE: the app launches immediately.
Use Settings → Update Modules to install AI/transcription packages.
"""

APP_VERSION = "1.3.9.0"

import subprocess
import sys
import os

# Add ClipFinder pkgs to path immediately — before ANY other imports
# This ensures numpy, cv2, and all packages find each other correctly
_cf_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
_cf_pkgs = os.path.join(_cf_appdata, 'ClipFinder', 'pkgs')
if os.path.isdir(_cf_pkgs) and _cf_pkgs not in sys.path:
    sys.path.insert(0, _cf_pkgs)

# NOTE: clipfinder_core.py is no longer used. Every name this block used to import (prompts, ts,
# get_encoder, _do_transcribe, ...) is defined in this file - the core copy was dead code that
# had drifted from it, and the auto-download of it only added a failure point. Retired in 1.4.0.

# vision_refs folder and default reference images are bootstrapped in _check_first_run()

# ── App directory — where the app is installed (read-only in Program Files) ───
from pathlib import Path as _PathBase
if getattr(sys, 'frozen', False):
    APP_DIR = _PathBase(sys.executable).parent
else:
    APP_DIR = _PathBase(__file__).parent

# ── Point python-vlc at bundled VLC DLLs if present ─────────────────────────
# This lets the Editor tab work without a separate VLC install
import os as _os_vlc
_vlc_bundle = APP_DIR / 'vlc'
if _vlc_bundle.exists() and (_vlc_bundle / 'libvlc.dll').exists():
    _os_vlc.environ['PYTHON_VLC_LIB_PATH'] = str(_vlc_bundle / 'libvlc.dll')
    _os_vlc.environ['PYTHON_VLC_MODULE_PATH'] = str(_vlc_bundle / 'plugins')
    # Also add to DLL search path
    try:
        import ctypes as _ct_vlc
        _ct_vlc.windll.kernel32.AddDllDirectory(str(_vlc_bundle))
    except Exception:
        pass

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

# Add torch CUDA DLLs to PATH AND DLL search path so ctranslate2 finds them
# torch+cu121 bundles cudart, cublas etc in torch/lib
_torch_lib_early = USER_DIR / 'pkgs' / 'torch' / 'lib'
if _torch_lib_early.exists():
    _tl_str = str(_torch_lib_early)
    if _tl_str not in _os2.environ.get('PATH', ''):
        _os2.environ['PATH'] = _tl_str + _os2.pathsep + _os2.environ.get('PATH', '')
    # os.add_dll_directory is the correct Windows API for DLL search paths
    # This is what ctranslate2 actually uses to find CUDA DLLs
    try:
        _os2.add_dll_directory(_tl_str)
    except (AttributeError, OSError):
        pass  # Python < 3.8 or path doesn't exist

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
    """Build a pip install command targeting USER_DIR/pkgs (argv list, or None if no Python found)."""
    py = pm_python()
    if py is None:
        return None
    return py + ['-m', 'pip', 'install', '--target', str(target or PKGS_DIR), '--upgrade', '--quiet',
                 '--no-warn-script-location'] + (extra_args or []) + list(packages)


def _pip_cmd_safe(packages, extra_args=None):
    """Kept for compatibility - same as _pip_cmd."""
    return _pip_cmd(packages, extra_args)


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


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE MANAGER - package updates, isolated engines (Demucs) and app self-update
# ══════════════════════════════════════════════════════════════════════════════
# begin-update-manager
# Why it is built this way (each point is a bug users actually hit):
#   * `pip install --target PKGS_DIR` fails on Windows whenever ClipFinder (or a second copy) has a
#     .pyd/.dll from that folder loaded, leaving half-updated packages. So an update is downloaded and
#     import-tested in a STAGING folder while the app runs, then swapped into PKGS_DIR at the next
#     start, before anything is imported (pm_apply_staged). A failed swap rolls back.
#   * `pip --target --upgrade` leaves the old *.dist-info behind. The swap removes the old version's
#     files using its RECORD, so nothing stale is left.
#   * Updating pydantic-core (or numpy, torch, ...) as a side effect of updating something else breaks
#     other packages, so ABI-sensitive packages are never overwritten unless they are the target.
#   * Demucs needs its own torch/numpy. It lives in an isolated environment (envs/demucs) that the app
#     never imports; it is only run in a subprocess, so it can be rebuilt and swapped safely.
#   * One failed package must not abort the rest, pip errors must be visible, and a "done" marker must
#     never be written for a failed install.
import os as _um_os, re as _um_re, json as _um_json, time as _um_time, shutil as _um_sh, csv as _um_csv
import subprocess as _um_sp, threading as _um_thr, urllib.request as _um_ur, urllib.error as _um_ue

STAGE_DIR       = USER_DIR / 'pkgs_staging'
BACKUP_DIR      = USER_DIR / 'pkgs_backup'
ENVS_DIR        = USER_DIR / 'envs'
UPDATE_LOG      = USER_DIR / 'update.log'
_UM_PYPI_CACHE  = USER_DIR / 'pypi_cache.json'
CPU_TORCH_INDEX = 'https://download.pytorch.org/whl/cpu'
APP_REPO        = 'thatspeedykid/clipfinder'
_UM_UA          = 'ClipFinder-Updater'
_UM_CNW         = 0x08000000 if _um_os.name == 'nt' else 0        # CREATE_NO_WINDOW


def um_log(msg):
    """Append to update.log (rotated at 1 MB) and echo to the console."""
    line = f'{_um_time.strftime("%Y-%m-%d %H:%M:%S")}  {msg}'
    try:
        if UPDATE_LOG.exists() and UPDATE_LOG.stat().st_size > 1_000_000:
            UPDATE_LOG.replace(UPDATE_LOG.with_name('update.log.1'))
        with open(UPDATE_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass
    try:
        print(f'[CF] {msg}')
    except Exception:
        pass


# ── versions ─────────────────────────────────────────────────────────────────
def _pm_norm(name):
    return _um_re.sub(r'[-_.]+', '_', str(name)).lower()


def _pm_vkey(v):
    """Sortable key for a version string. 1.0 == 1.0.0; pre-releases sort before the release."""
    m = _um_re.match(r'\s*v?(\d+(?:\.\d+)*)(.*)$', str(v).split('+')[0])       # drop the local part (2.14.0+cpu)
    if not m:
        return ((0,), 0)
    rel = [int(x) for x in m.group(1).split('.')]
    while len(rel) > 1 and rel[-1] == 0:
        rel.pop()
    tail = m.group(2).lower()
    pre = 0 if _um_re.match(r'^[.\-_]?(a|b|c|rc|alpha|beta|pre|preview)[.\-_]?\d*', tail) or 'dev' in tail else 1
    return (tuple(rel), pre)


def _pm_satisfies(ver, spec):
    """True if `ver` satisfies a specifier string such as '>=2.24,<3' (empty spec = always)."""
    if not spec:
        return True
    vk = _pm_vkey(ver)
    for clause in [c.strip() for c in str(spec).split(',') if c.strip()]:
        m = _um_re.match(r'^(===|==|!=|~=|>=|<=|>|<)\s*(\S+)$', clause)
        if not m:
            continue
        op, want = m.groups()
        if want.endswith('.*'):                                   # ==1.2.* / !=1.2.*
            pre = tuple(int(x) for x in want[:-2].split('.') if x.isdigit())
            has = vk[0][:len(pre)] == pre
            if (op == '==' and not has) or (op == '!=' and has):
                return False
            continue
        wk = _pm_vkey(want)
        if op in ('==', '===') and vk != wk: return False
        if op == '!=' and vk == wk: return False
        if op == '>=' and vk < wk: return False
        if op == '<=' and vk > wk: return False
        if op == '>' and vk <= wk: return False
        if op == '<' and vk >= wk: return False
        if op == '~=':
            rel = list(wk[0]) + [0]
            if vk < wk or vk[0][:max(1, len(wk[0]) - 1)] != wk[0][:max(1, len(wk[0]) - 1)]:
                return False
    return True


# ── registry ─────────────────────────────────────────────────────────────────
# policy: 'latest'  keep on the newest release (sites/APIs change constantly)
#         'compat'  newest release that still satisfies `spec` (major-version fence for the SDKs)
#         'keep'    install when missing / outside `spec`, never bump automatically (ABI-sensitive)
# required: installed automatically at start-up when missing; optional ones are offered in Settings.
PKG_REGISTRY = [
    dict(name='yt-dlp', extras='default,curl-cffi', mod='yt_dlp', group='Downloader', policy='latest',
         spec='>=2026.8.19', required=True, desc='Video downloader. Sites change constantly, so this one is kept on the newest release'),
    dict(name='curl-cffi', mod='curl_cffi', group='Downloader', policy='compat', spec='>=0.10,<0.17',
         required=True, desc='Browser impersonation for Kick / TikTok (yt-dlp accepts only 0.10 - 0.16)'),
    dict(name='requests', mod='requests', group='Downloader', policy='keep', spec='>=2.32.2,<3',
         required=True, desc='HTTP client'),
    dict(name='google-genai', mod='google.genai', group='AI providers', policy='compat', spec='>=2.24,<3',
         required=True, desc='Gemini provider'),
    dict(name='groq', mod='groq', group='AI providers', policy='compat', spec='>=1.7,<2',
         required=True, desc='Groq provider'),
    dict(name='openai', mod='openai', group='AI providers', policy='compat', spec='>=3.16,<4',
         required=True, desc='OpenRouter / OpenAI-compatible provider'),
    dict(name='faster-whisper', mod='faster_whisper', group='Transcription', policy='keep', spec='>=1.2.1,<2',
         required=True, desc='Transcription engine (CPU / NVIDIA)'),
    dict(name='openai-whisper', mod='whisper', group='Transcription', policy='keep', spec='==20250625',
         required=False, no_deps=True, needs=['torch'], desc='Fallback transcription engine (needs PyTorch)'),
    dict(name='torch', mod='torch', group='Transcription', policy='keep', spec='>=2.1', required=False,
         index=CPU_TORCH_INDEX, timeout=5400, desc='PyTorch (CPU) - only needed by the openai-whisper fallback'),
    dict(name='Pillow', mod='PIL', group='Media', policy='keep', spec='>=10', required=True, desc='Image processing'),
    dict(name='numpy', mod='numpy', group='Media', policy='keep', spec='>=1.26,<2.6', required=True,
         desc='Numeric processing'),
    dict(name='opencv-contrib-python', alt=['opencv-python', 'opencv-python-headless', 'opencv-contrib-python-headless'],
         mod='cv2', group='Media', policy='keep', spec='>=4.8', required=True, timeout=3600,
         desc='Video frame analysis, face tracking, upscaling'),
    dict(name='imagehash', mod='imagehash', group='Media', policy='keep', spec='>=4.3', required=True,
         desc='Duplicate image detection'),
    dict(name='soundfile', mod='soundfile', group='Media', policy='keep', spec='>=0.12', required=True,
         desc='Audio read/write (Censor tab)'),
    dict(name='fonttools', mod='fontTools', group='Media', policy='keep', spec='>=4.40', required=True,
         desc='Font handling (Burn Subtitles)'),
    dict(name='ddgs', mod='ddgs', group='Tools', policy='latest', spec='>=9', required=True,
         desc='Web image search (Thumbnail Finder). Scrapes search engines, so keep it fresh'),
    dict(name='python-vlc', mod=None, group='Tools', policy='keep', spec='>=3.0.21203', required=False,
         desc='Inline video player in the Editor (also needs VLC media player installed)'),
]

# Never overwritten as a side effect of updating something else (ABI / DLL sensitive).
_PM_PROTECT = {'numpy', 'torch', 'torchaudio', 'scipy', 'numba', 'llvmlite', 'onnxruntime', 'ctranslate2', 'av',
               'opencv_python', 'opencv_contrib_python', 'opencv_python_headless', 'opencv_contrib_python_headless',
               'mediapipe', 'pillow', 'tokenizers'}
# Distributions that must move together (a new pydantic with an old pydantic_core raises SystemError).
_PM_GROUPS = [{'pydantic', 'pydantic_core'}, {'numba', 'llvmlite'},
              {'opencv_python', 'opencv_contrib_python', 'opencv_python_headless', 'opencv_contrib_python_headless'}]
_PM_SKIP_TOP = {'bin', 'Scripts', 'share', 'include', '__pycache__'}


def pm_entry(name):
    n = _pm_norm(name)
    for e in PKG_REGISTRY:
        if _pm_norm(e['name']) == n or n in [_pm_norm(a) for a in e.get('alt', [])]:
            return e
    return None


def pm_requirement(e):
    """pip requirement string for a registry entry, e.g. 'yt-dlp[default,curl-cffi]>=2026.8.19'."""
    extras = f'[{e["extras"]}]' if e.get('extras') else ''
    return f'{e["name"]}{extras}{e.get("spec", "")}'


# ── what is installed ─────────────────────────────────────────────────────────
_DIST_RE = _um_re.compile(r'^(?P<n>.+?)-(?P<v>\d[^-]*)\.dist-info$')


def pm_installed(root=None):
    """{normalised name: [(version, dist-info path), ...]} sorted oldest -> newest."""
    root = _PathBase(root or PKGS_DIR)
    out = {}
    try:
        for p in root.iterdir():
            m = _DIST_RE.match(p.name)
            if m and p.is_dir():
                out.setdefault(_pm_norm(m.group('n')), []).append((m.group('v'), p))
    except OSError:
        return {}
    return {n: sorted(vs, key=lambda t: _pm_vkey(t[0])) for n, vs in out.items()}


def pm_version(e, inst=None):
    """Installed version of a registry entry (also matches its `alt` distributions), or None."""
    inst = inst if inst is not None else pm_installed()
    for n in [e['name']] + list(e.get('alt', [])):
        vs = inst.get(_pm_norm(n))
        if vs:
            return vs[-1][0]
    return None


# ── PyPI (cached) ─────────────────────────────────────────────────────────────
def _pm_pyok(req):
    """Does the running Python satisfy a release's requires_python?"""
    if not req:
        return True
    return _pm_satisfies('%d.%d.%d' % sys.version_info[:3], req)


def pm_pypi_releases(name, timeout=10, max_age=6 * 3600, force=False):
    """{version: requires_python} of the installable (non-yanked, final) releases, or None if unreachable.
    Cached on disk so the Settings page and the start-up check do not hammer PyPI."""
    key = _pm_norm(name)
    cache = {}
    try:
        cache = _um_json.loads(_UM_PYPI_CACHE.read_text(encoding='utf-8')) if _UM_PYPI_CACHE.exists() else {}
    except Exception:
        cache = {}
    ent = cache.get(key)
    if ent and not force and _um_time.time() - ent.get('t', 0) < max_age:
        return ent['v']
    try:
        req = _um_ur.Request(f'https://pypi.org/pypi/{name}/json', headers={'User-Agent': _UM_UA})
        with _um_ur.urlopen(req, timeout=timeout) as r:
            data = _um_json.loads(r.read().decode('utf-8'))
        rels = {}
        for ver, files in (data.get('releases') or {}).items():
            if not files or all(f.get('yanked') for f in files):
                continue
            if _pm_vkey(ver)[1] == 0:                     # skip pre-releases
                continue
            rels[ver] = next((f.get('requires_python') for f in files if f.get('requires_python')), '') or ''
        cache[key] = {'t': _um_time.time(), 'v': rels}
        try:
            _UM_PYPI_CACHE.write_text(_um_json.dumps(cache), encoding='utf-8')
        except Exception:
            pass
        return rels
    except Exception:
        return ent['v'] if ent else None                 # stale cache beats nothing when offline


def pm_best_version(name, spec='', force=False):
    """Newest release that satisfies `spec` and can be installed on this Python, or None."""
    rels = pm_pypi_releases(name, force=force)
    if not rels:
        return None
    ok = [v for v, rp in rels.items() if _pm_satisfies(v, spec) and _pm_pyok(rp)]
    return max(ok, key=_pm_vkey) if ok else None


def pm_plan(entries=None, online=True, force=False):
    """One row per registry entry:
       state = 'missing' | 'below' (installed but outside the allowed range) | 'outdated' | 'ok'
       plus installed / latest versions, so the UI and the start-up sync share one decision."""
    entries = entries if entries is not None else PKG_REGISTRY
    inst = pm_installed()
    rows = []
    lock = _um_thr.Lock()

    def _one(e):
        cur = pm_version(e, inst)
        row = dict(e, installed=cur, latest=None, state='ok')
        if online:
            row['latest'] = pm_best_version(e['name'], e.get('spec', '') if e['policy'] == 'compat' else '', force=force)
        if cur is None:
            row['state'] = 'missing'
        elif e.get('spec') and not _pm_satisfies(cur, e['spec']):
            row['state'] = 'below'
        elif row['latest'] and _pm_vkey(row['latest']) > _pm_vkey(cur):
            row['state'] = 'outdated' if e['policy'] in ('latest', 'compat') else 'newer'
        with lock:
            rows.append(row)

    if online and len(entries) > 1:
        ts = [_um_thr.Thread(target=_one, args=(e,), daemon=True) for e in entries]
        for t in ts: t.start()
        for t in ts: t.join(timeout=25)
    else:
        for e in entries: _one(e)
    order = {e['name']: i for i, e in enumerate(entries)}
    return sorted(rows, key=lambda r: order.get(r['name'], 999))


# ── running pip & friends ─────────────────────────────────────────────────────
def _um_kill(p):
    try:
        if _um_os.name == 'nt':
            _um_sp.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True, creationflags=_UM_CNW)
        else:
            p.kill()
    except Exception:
        try: p.kill()
        except Exception: pass


def _um_run(cmd, tag='', on_line=None, timeout=3600, cancel=None, env=None, cwd=None):
    """Run cmd, stream its output to update.log / on_line, honour a timeout and a cancel Event.
    -> (returncode, last lines, state) with state 'ok' | 'timeout' | 'cancelled'."""
    import collections
    p = _um_sp.Popen(cmd, stdout=_um_sp.PIPE, stderr=_um_sp.STDOUT, stdin=_um_sp.DEVNULL, text=True,
                     encoding='utf-8', errors='replace', bufsize=1, creationflags=_UM_CNW, env=env, cwd=cwd)
    tail = collections.deque(maxlen=60)
    state = {'v': 'ok'}
    done = _um_thr.Event()

    def _watch():
        t0 = _um_time.time()
        while not done.is_set():
            if cancel is not None and cancel.is_set():
                state['v'] = 'cancelled'; _um_kill(p); return
            if _um_time.time() - t0 > timeout:
                state['v'] = 'timeout'; _um_kill(p); return
            done.wait(0.4)

    w = _um_thr.Thread(target=_watch, daemon=True)
    w.start()
    try:
        for raw in p.stdout:
            line = _um_re.sub(r'\x1b\[[0-9;]*m', '', raw).strip()
            if not line:
                continue
            tail.append(line)
            um_log(f'{tag} {line[:300]}')
            if on_line:
                try: on_line(line)
                except Exception: pass
        rc = p.wait()
    finally:
        done.set()
    return rc, '\n'.join(tail), state['v']


def pm_python():
    """argv prefix of the interpreter to use for pip / helper scripts (never the frozen launcher EXE)."""
    exe = _PathBase(sys.executable)
    if exe.name.lower() in ('python.exe', 'python3.exe', 'python', 'python3', 'pythonw.exe'):
        if exe.name.lower() == 'pythonw.exe' and (exe.parent / 'python.exe').exists():
            return [str(exe.parent / 'python.exe')]
        return [str(exe)]
    import shutil as _sh
    py = _sh.which('py')
    if py:
        try:
            if _um_sp.run([py, '-3.12', '--version'], capture_output=True, timeout=8, creationflags=_UM_CNW).returncode == 0:
                return [py, '-3.12']
        except Exception:
            pass
    for name in ('python3.12', 'python3.12.exe', 'python.exe', 'python3.exe', 'python', 'python3'):
        found = _sh.which(name)
        if found and _PathBase(found).resolve() != exe.resolve():
            return [found]
    for pat in (r'C:\Python312\python.exe', r'C:\Program Files\Python312\python.exe',
                _um_os.environ.get('LOCALAPPDATA', '') + r'\Programs\Python\Python312\python.exe'):
        if _PathBase(pat).exists():
            return [pat]
    return None


_PIP_FLAGS = ['--disable-pip-version-check', '--no-input', '--progress-bar', 'off',
              '--no-warn-script-location', '--prefer-binary']


def pm_ensure_pip(on_line=None):
    py = pm_python()
    if not py:
        return False
    if _um_sp.run(py + ['-m', 'pip', '--version'], capture_output=True, creationflags=_UM_CNW).returncode == 0:
        return True
    um_log('pip missing - bootstrapping with ensurepip')
    rc, _, _ = _um_run(py + ['-m', 'ensurepip', '--upgrade'], 'ensurepip', on_line, timeout=300)
    return rc == 0


def _pm_explain(tail):
    """Turn the tail of a pip log into a short message a user can act on."""
    t = tail or ''
    tl = t.lower()
    if 'resolutionimpossible' in tl or 'conflict' in tl:
        return 'Version conflict between packages (see update.log). Try "Repair".'
    if 'could not find a version' in tl or 'no matching distribution' in tl:
        return 'No matching release for this Python version (see update.log).'
    if any(x in tl for x in ('connection', 'timed out', 'getaddrinfo', 'max retries', 'ssl')):
        return 'Network problem while downloading - check your connection and try again.'
    if 'access is denied' in tl or 'permission' in tl:
        return 'A file is in use. Close other ClipFinder windows and try again.'
    if 'no space left' in tl or 'disk full' in tl:
        return 'Not enough disk space.'
    last = [l for l in t.splitlines() if l.strip()][-1:] or ['pip failed']
    return last[0][:200]


def pm_constraints():
    """Constraints file pinning the protected packages to what is installed, so a joint resolve never
    picks an incompatible numpy/torch/... (they are downloaded but skipped at swap time)."""
    lines = []
    for n, vs in pm_installed().items():
        if n in _PM_PROTECT and vs:
            lines.append(f'{n.replace("_", "-")}=={vs[-1][0].split("+")[0]}')
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    f = STAGE_DIR / '_constraints.txt'
    f.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return f if lines else None


def pm_verify(mod, dirs, timeout=240):
    """Import `mod` in a fresh interpreter whose sys.path starts with `dirs`. -> (ok, error text)."""
    if not mod:
        return True, ''
    py = pm_python()
    if not py:
        return False, 'no Python interpreter found'
    code = ('import sys; sys.path[:0] = %r; import importlib; m = importlib.import_module(%r); '
            'print(getattr(m, "__version__", ""))' % ([str(d) for d in dirs], mod))
    env = dict(_um_os.environ)
    env['PYTHONNOUSERSITE'] = '1'
    env.pop('PYTHONPATH', None)
    try:
        r = _um_sp.run(py + ['-c', code], capture_output=True, text=True, timeout=timeout, env=env,
                       creationflags=_UM_CNW)
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
    if r.returncode == 0:
        return True, (r.stdout or '').strip()
    return False, ((r.stderr or r.stdout or '').strip().splitlines() or ['import failed'])[-1][:300]


def pm_stage(entries, on_line=None, cancel=None):
    """Download `entries` (registry dicts) into a fresh staging folder in ONE pip transaction, so the
    resolver picks one consistent set. Entries with no_deps (source-only wheels) are staged separately.
    Verifies every module imports from the staged copy. -> list of result dicts (one per transaction)."""
    if not pm_ensure_pip(on_line):
        return [dict(ok=False, names=[e['name'] for e in entries], error='pip is not available for this Python')]
    joint = [e for e in entries if not e.get('no_deps')]
    solo = [e for e in entries if e.get('no_deps')]
    results = []
    for group in ([joint] if joint else []) + [[e] for e in solo]:
        if cancel is not None and cancel.is_set():
            break
        results.append(_pm_stage_group(group, on_line, cancel))
    return results


def _pm_stage_group(group, on_line, cancel):
    names = [e['name'] for e in group]
    batch = STAGE_DIR / (_um_time.strftime('%Y%m%d-%H%M%S') + '-' + _pm_norm(names[0])[:24])
    _um_sh.rmtree(batch, ignore_errors=True)
    batch.mkdir(parents=True, exist_ok=True)
    py = pm_python()
    cmd = py + ['-m', 'pip', 'install', '--target', str(batch), '--upgrade'] + _PIP_FLAGS
    indexes = {e['index'] for e in group if e.get('index')}
    for ix in indexes:
        cmd += ['--extra-index-url', ix]
    if any(e.get('no_deps') for e in group):
        cmd += ['--no-deps']
    cons = pm_constraints()
    if cons and not any(e.get('no_deps') for e in group):
        cmd += ['-c', str(cons)]
    cmd += [pm_requirement(e) for e in group]
    timeout = max([e.get('timeout', 1800) for e in group] + [1800])
    um_log('staging ' + ', '.join(pm_requirement(e) for e in group))
    rc, tail, state = _um_run(cmd, 'pip', on_line, timeout=timeout, cancel=cancel)
    if rc != 0 and state == 'ok':                         # one retry: most failures are network hiccups
        um_log('pip failed - retrying once')
        _um_sh.rmtree(batch, ignore_errors=True); batch.mkdir(parents=True, exist_ok=True)
        rc, tail, state = _um_run(cmd, 'pip', on_line, timeout=timeout, cancel=cancel)
    if state == 'cancelled':
        _um_sh.rmtree(batch, ignore_errors=True)
        return dict(ok=False, names=names, error='Cancelled')
    if state == 'timeout':
        _um_sh.rmtree(batch, ignore_errors=True)
        return dict(ok=False, names=names, error='Timed out - the download was too slow. Try again.')
    if rc != 0:
        _um_sh.rmtree(batch, ignore_errors=True)
        return dict(ok=False, names=names, error=_pm_explain(tail))
    inst = pm_installed(batch)
    versions = {e['name']: pm_version(e, inst) for e in group}
    for e in group:                                       # the exact thing we asked for must be there
        if versions[e['name']] is None:
            _um_sh.rmtree(batch, ignore_errors=True)
            return dict(ok=False, names=names, error=f'{e["name"]} was not installed by pip (see update.log)')
    for e in group:
        if e.get('mod'):
            ok, err = pm_verify(e['mod'], [batch, PKGS_DIR])          # staged copy first, live deps behind it
            if not ok:
                _um_sh.rmtree(batch, ignore_errors=True)
                um_log(f'verify failed for {e["name"]}: {err}')
                return dict(ok=False, names=names, error=f'{e["name"]} downloaded but does not import: {err}')
    (batch / '.ready').write_text(_um_json.dumps({'targets': names, 'versions': versions,
                                                  'time': _um_time.time()}), encoding='utf-8')
    um_log(f'staged OK: {versions}')
    return dict(ok=True, names=names, versions=versions, batch=str(batch))


# ── swap staged packages into PKGS_DIR (run before anything is imported) ──────
def _pm_record_files(dist_info):
    """Files (posix paths relative to the packages root) a distribution owns, from its RECORD."""
    out = []
    rec = _PathBase(dist_info) / 'RECORD'
    try:
        with open(rec, newline='', encoding='utf-8') as f:
            for row in _um_csv.reader(f):
                if not row or not row[0]:
                    continue
                p = row[0].replace('\\', '/')
                if p.startswith('../') or p.startswith('/') or ':' in p.split('/')[0]:
                    continue
                if p.split('/')[0] in _PM_SKIP_TOP:
                    continue
                out.append(p)
    except OSError:
        pass
    return out


def _pm_merge(batch, info):
    """Move one staged batch into PKGS_DIR. All-or-nothing: any failure (typically a locked .pyd) rolls the
    already-moved files back. -> result dict."""
    targets = {_pm_norm(n) for n in info.get('targets', [])}
    staged = pm_installed(batch)
    live = pm_installed(PKGS_DIR)
    take = set()
    for n, vs in staged.items():
        sv = vs[-1][0]
        if n in targets:
            take.add(n)
        elif n not in live:
            take.add(n)                                          # dependency we simply did not have yet
        elif n in _PM_PROTECT:
            continue                                             # never disturb ABI-sensitive packages
        elif _pm_vkey(sv) > _pm_vkey(live[n][-1][0]):
            take.add(n)                                          # newer dependency
    for grp in _PM_GROUPS:                                       # pydantic + pydantic_core move together
        if take & grp:
            take |= {n for n in grp if n in staged}
    if not take:
        return dict(ok=True, targets=sorted(targets), moved=0)
    stamp = _um_time.strftime('%Y%m%d-%H%M%S')
    bdir = BACKUP_DIR / stamp
    ops = []                                                     # ('b', live, backup) / ('i', live)
    try:
        # 1) take the OLD versions out of the way (their own files only)
        for n in sorted(take):
            for ver, dpath in live.get(n, []):
                rels = [r for r in _pm_record_files(dpath) if not r.startswith(dpath.name + '/')]
                for rel in rels:
                    src = PKGS_DIR / rel
                    if src.is_file():
                        dst = bdir / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        _um_os.replace(src, dst)
                        ops.append(('b', src, dst))
                if dpath.exists():                               # dist-info dir (and anything RECORD missed)
                    dst = bdir / dpath.name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    _um_os.replace(dpath, dst)
                    ops.append(('b', dpath, dst))
        # 2) put the NEW files in
        for n in sorted(take):
            dpath = staged[n][-1][1]
            for rel in [r for r in _pm_record_files(dpath) if not r.startswith(dpath.name + '/')]:
                src = batch / rel
                if not src.is_file():
                    continue
                dst = PKGS_DIR / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():                                 # untracked leftover: back it up too
                    bk = bdir / rel
                    bk.parent.mkdir(parents=True, exist_ok=True)
                    _um_os.replace(dst, bk)
                    ops.append(('b', dst, bk))
                _um_os.replace(src, dst)
                ops.append(('i', dst))
            dst = PKGS_DIR / dpath.name
            _um_os.replace(dpath, dst)
            ops.append(('i', dst))
        # 3) prove the merged result works before we commit to it
        for e in [pm_entry(t) for t in info.get('targets', [])]:
            if e and e.get('mod'):
                ok, err = pm_verify(e['mod'], [PKGS_DIR])
                if not ok:
                    raise RuntimeError(f'{e["name"]} does not import after the update: {err}')
    except Exception as ex:
        for op in reversed(ops):                                 # rollback
            try:
                if op[0] == 'i':
                    p = op[1]
                    if p.is_dir(): _um_sh.rmtree(p, ignore_errors=True)
                    elif p.exists(): p.unlink()
                else:
                    op[1].parent.mkdir(parents=True, exist_ok=True)
                    _um_os.replace(op[2], op[1])
            except Exception:
                pass
        um_log(f'swap failed and was rolled back: {ex}')
        return dict(ok=False, targets=sorted(targets), error=str(ex))
    for d in sorted({op[1].parent for op in ops if op[0] == 'b'}, key=lambda p: -len(p.parts)):
        try:                                                     # tidy empty package folders left behind
            while d != PKGS_DIR and d.is_dir() and not any(d.iterdir()):
                d.rmdir(); d = d.parent
        except Exception:
            pass
    return dict(ok=True, targets=sorted(targets), moved=len([o for o in ops if o[0] == 'i']),
                versions=info.get('versions', {}))


_UM_LOCK_FD = None


def um_acquire_instance_lock():
    """Hold an OS-level lock for the lifetime of this process. -> False if another ClipFinder already
    holds it. (Windows lets you rename a DLL that is loaded, so a swap would NOT fail under a running
    copy - it would just leave that copy with a half-changed package set. Hence this lock.)"""
    global _UM_LOCK_FD
    if _UM_LOCK_FD is not None:
        return True
    try:
        import msvcrt
    except ImportError:
        return True
    try:
        fd = open(USER_DIR / '.instance.lock', 'a+b')
        fd.seek(0)
        msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        _UM_LOCK_FD = fd
        return True
    except Exception:
        return False


def um_release_instance_lock():
    """Give the lock up (call right before starting the replacement process on a self-restart)."""
    global _UM_LOCK_FD
    try:
        if _UM_LOCK_FD is not None:
            _UM_LOCK_FD.close()
    except Exception:
        pass
    _UM_LOCK_FD = None


def pm_apply_staged():
    """Swap every verified staged batch into PKGS_DIR, but only when no other ClipFinder is running.
    Batches that cannot be swapped stay staged and are retried on the next start."""
    results = []
    try:
        if not um_acquire_instance_lock():                       # always take the lock: we ARE the running instance
            if pm_pending():
                um_log('another ClipFinder is running - staged updates wait for the next start')
            return results
        if not STAGE_DIR.exists():
            return results
        for batch in sorted(p for p in STAGE_DIR.iterdir() if p.is_dir()):
            ready = batch / '.ready'
            if not ready.exists():                               # aborted download: discard
                _um_sh.rmtree(batch, ignore_errors=True)
                continue
            try:
                info = _um_json.loads(ready.read_text(encoding='utf-8'))
            except Exception:
                _um_sh.rmtree(batch, ignore_errors=True)
                continue
            res = _pm_merge(batch, info)
            results.append(res)
            if res['ok']:
                _um_sh.rmtree(batch, ignore_errors=True)
                um_log(f'applied update: {res.get("versions")}')
            else:
                info['tries'] = info.get('tries', 0) + 1
                if info['tries'] >= 3:                           # do not retry forever
                    _um_sh.rmtree(batch, ignore_errors=True)
                    um_log(f'giving up on staged batch {batch.name}: {res.get("error")}')
                else:
                    ready.write_text(_um_json.dumps(info), encoding='utf-8')
    except Exception as e:
        um_log(f'pm_apply_staged error: {e}')
    if results:
        try:
            import importlib as _il
            _il.invalidate_caches()
        except Exception:
            pass
    return results


def pm_pending():
    """Names staged and waiting for the next start."""
    out = []
    try:
        for b in STAGE_DIR.iterdir():
            r = b / '.ready'
            if b.is_dir() and r.exists():
                out += _um_json.loads(r.read_text(encoding='utf-8')).get('targets', [])
    except Exception:
        pass
    return out


def pm_cleanup_backups(keep_days=3):
    """Drop old swap backups (run once the app has started fine)."""
    try:
        for d in BACKUP_DIR.iterdir():
            if d.is_dir() and _um_time.time() - d.stat().st_mtime > keep_days * 86400:
                _um_sh.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def pm_check_conflicts():
    """Requirement conflicts among the installed packages -> list of text lines (empty = consistent)."""
    py = pm_python()
    if not py:
        return ['no Python interpreter found']
    code = r'''
import sys, json
sys.path[:0] = [%r]
from importlib.metadata import distributions
try:
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.version import Version
except Exception as e:
    print(json.dumps(['cannot check: ' + str(e)])); raise SystemExit
dists = {}
for d in distributions(path=[%r]):
    dists[d.metadata['Name'].lower().replace('_', '-')] = d
bad = []
for name, d in dists.items():
    for r in (d.requires or []):
        try: req = Requirement(r)
        except Exception: continue
        if req.marker is not None and not req.marker.evaluate({'extra': ''}): continue
        dep = dists.get(req.name.lower().replace('_', '-'))
        if dep is None:
            continue
        if req.specifier and not req.specifier.contains(Version(dep.version), prereleases=True):
            bad.append('%%s requires %%s but %%s is installed' %% (name, r.split(';')[0].strip(), dep.version))
print(json.dumps(bad))
''' % (str(PKGS_DIR), str(PKGS_DIR))
    try:
        r = _um_sp.run(py + ['-c', code], capture_output=True, text=True, timeout=120, creationflags=_UM_CNW)
        return _um_json.loads((r.stdout or '[]').strip().splitlines()[-1])
    except Exception as e:
        return [f'conflict check failed: {e}']


# ── start-up sync: bring the REQUIRED packages to a working state ────────────
_UM_SYNC_STATE = USER_DIR / 'sync_state.json'


def pm_sync_needs():
    """Required packages that are missing or outside their allowed version range (offline, instant)."""
    plan = pm_plan([e for e in PKG_REGISTRY if e.get('required')], online=False)
    return [r for r in plan if r['state'] in ('missing', 'below')]


def _um_sync_state():
    try:
        return _um_json.loads(_UM_SYNC_STATE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def pm_sync_should_skip(cool_off=3 * 3600):
    """After a failed sync do not make the user wait again on every launch (e.g. while offline)."""
    st = _um_sync_state()
    return bool(st.get('fail_ts')) and _um_time.time() - st['fail_ts'] < cool_off


def pm_startup_sync(entries=None, status_cb=None, cancel=None):
    """Stage + apply the given entries (default: everything required that is missing / out of range).
    Never raises. -> dict(ok, changed=[names], failed=[(name, reason)], restart)."""
    out = dict(ok=True, changed=[], failed=[], restart=False)
    try:
        entries = entries if entries is not None else pm_sync_needs()
        if not entries:
            return out
        um_log('start-up sync: ' + ', '.join(e['name'] for e in entries))
        results = pm_stage(entries, on_line=status_cb, cancel=cancel)
        for r in results:
            if r['ok']:
                out['changed'] += r['names']
            else:
                out['failed'] += [(n, r.get('error', '')) for n in r['names']]
        if out['changed']:
            pm_apply_staged()
            still = set(_pm_norm(n) for n in pm_pending())
            loaded = [e for e in entries if e['name'] in out['changed'] and e.get('mod')
                      and e['mod'].split('.')[0] in sys.modules]
            out['restart'] = bool(still or loaded)                 # a loaded module must be re-imported fresh
        out['ok'] = not out['failed']
        try:
            if out['ok']:
                _UM_SYNC_STATE.write_text(_um_json.dumps({'ok_ts': _um_time.time()}), encoding='utf-8')
            else:
                _UM_SYNC_STATE.write_text(_um_json.dumps({'fail_ts': _um_time.time(), 'failed': out['failed']}), encoding='utf-8')
        except Exception:
            pass
    except Exception as e:
        um_log(f'start-up sync error: {e}')
        out.update(ok=False, failed=[('sync', str(e))])
    return out


def pm_repair_entries():
    """Turn requirement conflicts among the installed packages into things to (re)install.
    Rule: if the package being required is safe to change (e.g. pydantic-core), install the version the
    dependent needs; if it is ABI-sensitive (numpy, torch...), upgrade the DEPENDENT instead (numba for a
    numpy it cannot handle). -> list of registry-like dicts, [] when everything is consistent."""
    out = {}
    for line in pm_check_conflicts():
        m = _um_re.match(r'^(\S+) requires (.+?) but (\S+) is installed$', line)
        if not m:
            continue
        dependent, req = m.group(1), m.group(2).strip()
        nm = _um_re.match(r'[A-Za-z0-9_.\-]+', req)
        if not nm:
            continue
        dep = nm.group(0)
        if _pm_norm(dep) in _PM_PROTECT:
            target, spec = dependent, ''
        else:
            target, spec = dep, req[len(dep):].strip()
        out[_pm_norm(target)] = dict(name=target, spec=spec, mod=None, group='repair', policy='keep',
                                     required=False, desc=f'repair: {line}')
    return list(out.values())


# ── isolated engines (Demucs) ─────────────────────────────────────────────────
ENGINES = {
    'demucs': dict(
        title='Music Removal engine (Demucs)',
        reqs=['demucs>=4.1,<5',
              'numpy>=2,<2.6'],           # demucs imports numpy but does not declare it as a dependency
        index=CPU_TORCH_INDEX,
        verify='import demucs, torch, numpy, sphn',
        module='demucs',
        timeout=5400),
}


def eng_root(name):
    return ENVS_DIR / name


def eng_status(name):
    """{'installed', 'version', 'torch', 'path', 'size_mb'} without importing anything."""
    root = eng_root(name)
    inst = pm_installed(root) if root.exists() else {}
    mod = ENGINES[name]['module']
    v = inst.get(_pm_norm(mod))
    tv = inst.get('torch')
    ok = bool(v) and (root / mod).exists()
    return dict(installed=ok, version=v[-1][0] if v else None, torch=tv[-1][0] if tv else None, path=str(root))


def eng_env(name):
    """Environment for running the engine in a subprocess: ONLY the engine's folder on the path."""
    env = dict(_um_os.environ)
    env['PYTHONPATH'] = str(eng_root(name))
    env['PYTHONNOUSERSITE'] = '1'
    env['TORCH_HOME'] = str(USER_DIR / 'models' / 'torch')
    env['HF_HOME'] = str(USER_DIR / 'models' / 'hf')
    env['PYTHONIOENCODING'] = 'utf-8'
    for k in ('PYTHONHOME', 'PYTHONSTARTUP'):
        env.pop(k, None)
    return env


def eng_install(name, on_line=None, cancel=None):
    """Build (or rebuild) an engine in a side folder, smoke-test it, then swap it in. The current working
    engine is kept untouched until the new one has proven itself, and restored if anything fails."""
    spec = ENGINES[name]
    if not pm_ensure_pip(on_line):
        return dict(ok=False, error='pip is not available for this Python')
    root, nxt, prev = eng_root(name), ENVS_DIR / f'{name}_next', ENVS_DIR / f'{name}_prev'
    ENVS_DIR.mkdir(parents=True, exist_ok=True)
    for d in (nxt, prev):
        _um_sh.rmtree(d, ignore_errors=True)
    nxt.mkdir(parents=True)
    py = pm_python()
    cmd = py + ['-m', 'pip', 'install', '--target', str(nxt), '--upgrade'] + _PIP_FLAGS
    if spec.get('index'):
        cmd += ['--extra-index-url', spec['index']]
    cmd += spec['reqs']
    um_log(f'building engine {name}: {spec["reqs"]}')
    rc, tail, state = _um_run(cmd, f'pip[{name}]', on_line, timeout=spec.get('timeout', 3600), cancel=cancel)
    if rc != 0 and state == 'ok':
        um_log('engine build failed - retrying once')
        _um_sh.rmtree(nxt, ignore_errors=True); nxt.mkdir(parents=True)
        rc, tail, state = _um_run(cmd, f'pip[{name}]', on_line, timeout=spec.get('timeout', 3600), cancel=cancel)
    if rc != 0 or state != 'ok':
        _um_sh.rmtree(nxt, ignore_errors=True)
        return dict(ok=False, error={'cancelled': 'Cancelled', 'timeout': 'Timed out - try again on a faster connection.'}.get(state, _pm_explain(tail)))
    env = eng_env(name)
    env['PYTHONPATH'] = str(nxt)
    r = _um_sp.run(py + ['-c', spec['verify'] + '; print("engine-ok")'], capture_output=True, text=True, env=env,
                   timeout=240, creationflags=_UM_CNW)
    if 'engine-ok' not in (r.stdout or ''):
        err = ((r.stderr or '').strip().splitlines() or ['smoke test failed'])[-1][:300]
        _um_sh.rmtree(nxt, ignore_errors=True)
        um_log(f'engine {name} failed its smoke test: {err}')
        return dict(ok=False, error=f'Installed but failed its self-test: {err}')
    try:
        if root.exists():
            _um_os.replace(root, prev)
        _um_os.replace(nxt, root)
    except Exception as e:
        try:
            if prev.exists() and not root.exists():
                _um_os.replace(prev, root)
        except Exception:
            pass
        return dict(ok=False, error=f'Could not swap the new engine in ({e}). Close other ClipFinder windows and retry.')
    _um_sh.rmtree(prev, ignore_errors=True)
    st = eng_status(name)
    um_log(f'engine {name} ready: {st}')
    return dict(ok=True, **st)


def eng_remove(name):
    _um_sh.rmtree(eng_root(name), ignore_errors=True)


def eng_run(name, args, on_line=None, cancel=None, timeout=6 * 3600, cwd=None):
    """Run `python -m <module> args` inside the engine. -> (returncode, output tail, state)."""
    py = pm_python()
    return _um_run(py + ['-m', ENGINES[name]['module']] + list(args), name, on_line, timeout=timeout,
                   cancel=cancel, env=eng_env(name), cwd=cwd)


# ── app self-update ───────────────────────────────────────────────────────────
def app_version_key(v):
    return _pm_vkey(str(v).lstrip('vV'))


def app_latest_release(timeout=12):
    """Newest published release: {'version', 'tag', 'notes', 'assets': {name: url}, 'url'} or None.
    Uses the GitHub API and falls back to the (un-rate-limited) releases/latest redirect."""
    try:
        req = _um_ur.Request(f'https://api.github.com/repos/{APP_REPO}/releases/latest',
                             headers={'User-Agent': _UM_UA, 'Accept': 'application/vnd.github+json'})
        with _um_ur.urlopen(req, timeout=timeout) as r:
            d = _um_json.loads(r.read().decode('utf-8'))
        tag = d.get('tag_name', '')
        return dict(version=tag.lstrip('vV'), tag=tag, notes=d.get('body') or '',
                    assets={a['name']: a['browser_download_url'] for a in d.get('assets', [])},
                    url=d.get('html_url', f'https://github.com/{APP_REPO}/releases/latest'))
    except Exception as e:
        um_log(f'GitHub API release lookup failed ({e}) - trying redirect')
    try:
        class _NoRedirect(_um_ur.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = _um_ur.build_opener(_NoRedirect)
        req = _um_ur.Request(f'https://github.com/{APP_REPO}/releases/latest', headers={'User-Agent': _UM_UA})
        try:
            op.open(req, timeout=timeout)
        except _um_ue.HTTPError as h:
            loc = h.headers.get('Location', '')
            m = _um_re.search(r'/tag/(v?[\d.]+)', loc)
            if m:
                tag = m.group(1)
                return dict(version=tag.lstrip('vV'), tag=tag, notes='', assets={},
                            url=f'https://github.com/{APP_REPO}/releases/tag/{tag}')
    except Exception as e:
        um_log(f'release redirect lookup failed: {e}')
    return None


def _um_download(url, dest, timeout=30, on_bytes=None):
    """Stream a URL to `dest` (with a real timeout - urlretrieve has none and hangs forever offline)."""
    req = _um_ur.Request(url, headers={'User-Agent': _UM_UA})
    tmp = _PathBase(str(dest) + '.part')
    with _um_ur.urlopen(req, timeout=timeout) as r, open(tmp, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        got = 0
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if on_bytes:
                on_bytes(got, total)
    _um_os.replace(tmp, dest)
    return dest


def app_source_version(text):
    m = _um_re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, _um_re.M)
    return m.group(1) if m else None


def app_download(rel, work_dir, on_status=None):
    """Download and VALIDATE the new clipfinder.py for release `rel`. Returns the file path; raises
    RuntimeError with a readable message if anything is wrong (nothing is installed here)."""
    import ast as _ast
    work = _PathBase(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    tag = rel['tag'] or f'v{rel["version"]}'
    urls = []
    if rel.get('assets', {}).get('clipfinder.py'):
        urls.append(rel['assets']['clipfinder.py'])
    urls.append(f'https://raw.githubusercontent.com/{APP_REPO}/{tag}/clipfinder.py')
    last = None
    dest = work / 'clipfinder.py.new'
    for u in urls:
        try:
            if on_status: on_status(f'Downloading {tag}...')
            _um_download(u, dest)
            text = dest.read_text(encoding='utf-8')
            _ast.parse(text)                                     # must be valid Python
            compile(text, 'clipfinder.py', 'exec')
            ver = app_source_version(text)
            if ver is None or 'if __name__' not in text:
                raise ValueError('the downloaded file does not look like ClipFinder')
            if app_version_key(ver) != app_version_key(rel['version']):
                raise ValueError(f'release {tag} contains clipfinder.py {ver}, which is not the version it advertises')
            if len(text) < 200_000:
                raise ValueError('the downloaded file is suspiciously small')
            return dest
        except Exception as e:
            last = e
            um_log(f'update download from {u} failed: {e}')
    raise RuntimeError(f'Could not download a valid update: {last}')


def app_install(new_file, target, backup_dir=None):
    """Atomically replace `target` with `new_file`, keeping the previous version for rollback."""
    target = _PathBase(target)
    backup_dir = _PathBase(backup_dir or (USER_DIR / 'app_backups'))
    backup_dir.mkdir(parents=True, exist_ok=True)
    old_ver = 'old'
    try:
        old_ver = app_source_version(target.read_text(encoding='utf-8')) or 'old'
    except Exception:
        pass
    keep = backup_dir / f'clipfinder-{old_ver}.py'
    if target.exists():
        _um_sh.copy2(target, keep)
    staged = target.with_name(target.name + '.new')
    _um_sh.copy2(new_file, staged)
    _um_os.replace(staged, target)                               # atomic on the same volume
    try:                                                         # keep only the two newest backups
        olds = sorted(backup_dir.glob('clipfinder-*.py'), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in olds[2:]:
            p.unlink()
    except Exception:
        pass
    (USER_DIR / 'update_pending.json').write_text(_um_json.dumps(
        {'from': old_ver, 'to': app_source_version(_PathBase(target).read_text(encoding='utf-8')),
         'time': _um_time.time(), 'attempts': 0, 'target': str(target), 'backup': str(keep)}), encoding='utf-8')
    return keep


def app_rollback():
    """Restore the previous clipfinder.py saved by app_install(). -> (ok, message)."""
    try:
        info = _um_json.loads((USER_DIR / 'update_pending.json').read_text(encoding='utf-8'))
        bak, target = _PathBase(info['backup']), _PathBase(info['target'])
    except Exception:
        baks = sorted((USER_DIR / 'app_backups').glob('clipfinder-*.py'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not baks:
            return False, 'No previous version is saved.'
        bak, target = baks[0], _PathBase(__file__)
    if not bak.exists():
        return False, 'The saved previous version is missing.'
    tmp = target.with_name(target.name + '.rb')
    _um_sh.copy2(bak, tmp)
    _um_os.replace(tmp, target)
    try:
        (USER_DIR / 'update_pending.json').unlink()
    except Exception:
        pass
    return True, f'Restored {bak.name}'


def app_startup_guard():
    """Called at start-up. If an update was installed but the new version failed to reach a healthy
    running state twice, put the previous version back automatically."""
    f = USER_DIR / 'update_pending.json'
    try:
        if not f.exists():
            return None
        info = _um_json.loads(f.read_text(encoding='utf-8'))
        info['attempts'] = info.get('attempts', 0) + 1
        if info['attempts'] > 2:
            ok, msg = app_rollback()
            um_log(f'auto-rollback after failed start: {msg}')
            return 'rolled_back' if ok else None
        f.write_text(_um_json.dumps(info), encoding='utf-8')
    except Exception:
        pass
    return None


def app_mark_healthy():
    """Called once the window has been up for a few seconds: the update is confirmed good."""
    try:
        (USER_DIR / 'update_pending.json').unlink()
    except Exception:
        pass


def app_set_registry_version(version):
    """Keep Windows' Add/Remove Programs entry in step with a self-update (best effort)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipFinder', 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, 'DisplayVersion', 0, winreg.REG_SZ, str(version))
            winreg.SetValueEx(k, 'DisplayName', 0, winreg.REG_SZ, f'ClipFinder {version}')
    except Exception:
        pass


def app_relaunch_cmd(script):
    """argv that starts the app again from `script` (never the frozen launcher)."""
    py = pm_python() or [sys.executable]
    if py[0].lower().endswith('python.exe') and _PathBase(py[0]).with_name('pythonw.exe').exists():
        py = [str(_PathBase(py[0]).with_name('pythonw.exe'))] + py[1:]      # no console window
    return py + [str(script)] + sys.argv[1:]
# end-update-manager


def _dist_version(pip_name):
    """Installed version of a distribution WITHOUT importing it, or None.

    Importing cv2 / numpy / google.genai / ... to see if they exist takes seconds, and doing it on
    the UI thread froze the window at start-up. This reads the *.dist-info folders in PKGS_DIR
    (exact name match, newest wins) and falls back to importlib.metadata for site-packages."""
    import re as _re_d
    want = _re_d.sub(r'[-_.]+', '_', _re_d.split(r'[=<>!~\s\[;]', str(pip_name).strip())[0]).lower()
    best = None
    try:
        for d in PKGS_DIR.iterdir():
            n = d.name
            if not n.endswith('.dist-info'):
                continue
            base, _, ver = n[:-len('.dist-info')].rpartition('-')
            if _re_d.sub(r'[-_.]+', '_', base).lower() != want or not ver:
                continue
            key = tuple(int(x) for x in _re_d.findall(r'\d+', ver)[:5])
            if best is None or key > best[0]:
                best = (key, ver)
    except OSError:
        pass
    if best:
        return best[1]
    try:
        import importlib.metadata as _md
        return _md.version(str(pip_name).split()[0])
    except Exception:
        return None


def _ensure_pkgs_on_path():
    """Add package dirs to sys.path so installed packages are found."""
    import importlib as _il
    # 1. PKGS_DIR (user-installed via Settings → Update Modules)
    PKGS_DIR.mkdir(exist_ok=True)
    pkg_str = str(PKGS_DIR)
    # Always ensure PKGS_DIR is at position 0 — overrides any system-level broken packages
    if pkg_str in sys.path:
        sys.path.remove(pkg_str)
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
    # Invalidate import caches so Python picks up newly installed packages
    _il.invalidate_caches()
    # Bust any cached broken provider imports so fresh ones load from PKGS_DIR
    # NOTE: do NOT bust torch/torchaudio — busting them breaks CUDA DLL initialization
    import sys as _sys_bust
    for _bmod in ['groq', 'openai', 'google.genai']:
        for _k in list(_sys_bust.modules.keys()):
            if _k == _bmod or _k.startswith(_bmod + '.'):
                try: del _sys_bust.modules[_k]
                except: pass

# Swap in package updates that were downloaded + verified last session. This has to happen here,
# before anything below imports from PKGS_DIR, and only when no other ClipFinder is running.
pm_apply_staged()
_ensure_pkgs_on_path()  # run immediately at import time

# Add portable Node.js to PATH if installed
def _ensure_node_on_path():
    import os as _os3
    _node_exe = USER_DIR / 'node' / 'node.exe'
    if _node_exe.exists():
        _nd = str(_node_exe.parent)
        if _nd not in _os3.environ.get('PATH', ''):
            _os3.environ['PATH'] = _nd + _os3.pathsep + _os3.environ.get('PATH', '')
_ensure_node_on_path()

# Add torch's bundled CUDA DLLs to PATH so ctranslate2 finds them
# torch+cu121 ships cublas, cudart etc in torch/lib — no separate CUDA toolkit needed
def _ensure_torch_cuda_on_path():
    import os as _os4
    _torch_lib = PKGS_DIR / 'torch' / 'lib'
    if _torch_lib.exists():
        _tl = str(_torch_lib)
        if _tl not in _os4.environ.get('PATH', ''):
            _os4.environ['PATH'] = _tl + _os4.pathsep + _os4.environ.get('PATH', '')
_ensure_torch_cuda_on_path()

# (Removed: a startup loop that called PKGS_DIR.rglob('*.py') and chmod'ed the first 300 files.
#  On Windows chmod only toggles the read-only flag, and the rglob walked all ~14k files of a
#  normal install on EVERY launch - ~2s warm and far longer on a cold disk with antivirus.)

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
    """Kept for compatibility. Missing/outdated packages are handled by the update manager in
    _prelaunch_install() (with a progress window) - installing silently at import time froze the
    start for minutes and ignored failures."""
    return


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

# Pre-patch curl_cffi — intercept ANY missing submodule or attribute dynamically
try:
    import sys as _sys_cffi, types as _types_cffi, importlib.abc as _iabc_cffi

    class _CurlDummy:
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, item): return _CurlDummy()
        def __int__(self): return 0
        def __str__(self): return ''
        def __bool__(self): return False
        def __iter__(self): return iter([])

    def _make_cffi_stub(name):
        _stub = _types_cffi.ModuleType(name)
        _stub.__getattr__ = lambda n, D=_CurlDummy: D
        _sys_cffi.modules[name] = _stub
        return _stub

    class _CurlCffiFinder(_iabc_cffi.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if not fullname.startswith('curl_cffi.'): return None
            try:
                import importlib.util as _ilu
                if _ilu.find_spec(fullname): return None
            except Exception: pass
            if fullname not in _sys_cffi.modules:
                _make_cffi_stub(fullname)
            import importlib.machinery as _imach_cffi
            return _imach_cffi.ModuleSpec(fullname, None)
        def create_module(self, spec):
            return _sys_cffi.modules.get(spec.name) or _make_cffi_stub(spec.name)
        def exec_module(self, module): pass

    if not any(type(f).__name__ == '_CurlCffiFinder' for f in _sys_cffi.meta_path):
        _sys_cffi.meta_path.insert(0, _CurlCffiFinder())

    # Patch any already-loaded curl_cffi submodules missing attributes
    for _k, _m in list(_sys_cffi.modules.items()):
        if _k.startswith('curl_cffi.') and not hasattr(_m, '__getattr__'):
            try: _m.__getattr__ = lambda n: _CurlDummy
            except Exception: pass
except Exception:
    pass

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
    _um_download(url, zip_path, timeout=60)   # urlretrieve has no timeout - a stalled link hung forever
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


_NODE_MIN_MAJOR = 22
_NODE_URL = 'https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip'   # Node 24 LTS "Krypton"
_NODE_MAJOR_CACHE = {}

def _node_major(exe):
    """Major version of a node executable (0 if it does not run). Cached per path."""
    if exe in _NODE_MAJOR_CACHE:
        return _NODE_MAJOR_CACHE[exe]
    import subprocess as _sp
    major = 0
    try:
        r = _sp.run([exe, '--version'], capture_output=True, text=True, timeout=15, creationflags=_UM_CNW)
        m = _um_re.match(r'v(\d+)\.', (r.stdout or '').strip())
        major = int(m.group(1)) if m else 0
    except Exception:
        major = 0
    _NODE_MAJOR_CACHE[exe] = major
    return major

def find_nodejs():
    """A Node.js >= 22 that yt-dlp can use as its YouTube JS runtime, or None (no download here)."""
    import shutil as _sh
    own = USER_DIR / 'node' / 'node.exe'
    for c in (str(own) if own.exists() else None, _sh.which('node')):
        if c and _node_major(c) >= _NODE_MIN_MAJOR:
            return c
    return None

def ensure_nodejs(status_cb=None):
    """Path to Node.js >= 22, downloading the portable Windows build (~35MB) if none is usable.
    yt-dlp needs a JavaScript runtime to solve YouTube's player challenges; an older Node
    (the 20.x that earlier versions installed) is too old for its solver. Returns None on failure."""
    import zipfile as _zf, platform as _pl
    def _say(msg):
        print(msg)
        if status_cb:
            try: status_cb(msg)
            except Exception: pass
    found = find_nodejs()
    if found:
        return found
    if _pl.system() != 'Windows':
        _say('Please install Node.js 22 or newer: https://nodejs.org')
        return None
    node_dir = USER_DIR / 'node'
    node_exe = node_dir / 'node.exe'
    try:
        node_dir.mkdir(parents=True, exist_ok=True)
        zip_path = node_dir / 'node_dl.zip'
        _say('Downloading Node.js 24 (one time, ~35MB) for YouTube...')
        _um_download(_NODE_URL, zip_path, timeout=60)
        new_exe = node_dir / 'node.exe.new'
        with _zf.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('/node.exe') and name.count('/') == 1:
                    with z.open(name) as s, open(new_exe, 'wb') as d:
                        _um_sh.copyfileobj(s, d)
                    break
        try: zip_path.unlink()
        except OSError: pass
        if not new_exe.exists() or new_exe.stat().st_size < 10_000_000:
            raise RuntimeError('node.exe missing from the downloaded archive')
        _um_os.replace(new_exe, node_exe)
        _NODE_MAJOR_CACHE.pop(str(node_exe), None)
        if _node_major(str(node_exe)) >= _NODE_MIN_MAJOR:
            _say(f'Node.js ready: {node_exe}')
            return str(node_exe)
        _say('The downloaded Node.js did not start')
    except Exception as e:
        _say(f'Node.js download failed: {str(e)[:120]}')
    return None

def yt_js_runtime_opts(status_cb=None, download=True):
    """yt-dlp options that give it a JS runtime for YouTube ({} if none can be found)."""
    exe = ensure_nodejs(status_cb) if download else find_nodejs()
    if not exe:
        return {}
    return {'js_runtimes': {'node': {'path': exe}}}


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
FG2     = '#A6A099'   # secondary text — raised for readable contrast on near-black bg
FG3     = '#7E7A73'   # tertiary / faint hints (below FG2 in the hierarchy)
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
        # Verified Sep 2026. gemini-2.0-* were shut down 2026-06-01. Order = UI order;
        # models[0] is the default. 'roles' = same ids ordered per job (see _ai_models).
        'models': ['gemini-3.5-flash-lite', 'gemini-3.8-flash',
                   'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
        'roles': {
            'tiny':    ['gemini-3.5-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash'],
            'write':   ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
            'extract': ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
            'vision':  ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
        },
        'url':    'https://aistudio.google.com/apikey',
        'note':   'Free — no credit card needed',
    },
    'Groq (Free)': {
        'lib':    'groq',
        # Verified Sep 2026. llama-3.3-70b-versatile and llama-3.1-8b-instant were
        # SHUT DOWN 2026-08-16 (also qwen3-32b / llama-4-scout 2026-07-17). Free plan
        # = 30 RPM, 8K tokens/min per model, so keep each request small (see
        # _GROQ_MAX_PROMPT_CHARS); gpt-oss are reasoning models (see _groq_kwargs).
        'models': [
            'openai/gpt-oss-120b',       # main: extraction, posts, tweets
            'openai/gpt-oss-20b',        # fast: scoring / tiny calls / fallback
            'qwen/qwen3.8-27b',          # preview, multimodal fallback
        ],
        'roles': {
            'tiny':    ['openai/gpt-oss-20b', 'openai/gpt-oss-120b'],
            'write':   ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b'],
            'extract': ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b'],
            'vision':  ['qwen/qwen3.8-27b'],
        },
        'url':    'https://console.groq.com',
        'note':   'Free — no credit card needed',
    },
    'OpenRouter (Free models)': {
        'lib':    'openrouter',
        # Verified against the live OpenRouter catalog (Sep 2026). Gone: llama-3.3-70b
        # :free, qwen3-next-80b :free, nemotron-nano-9b-v2 :free. openrouter/auto is
        # PAID (variable price) - the free router is openrouter/free. Free ':free'
        # models are capped at 20 req/min and 50 req/day (1000/day with $10 credit).
        'models': [
            'deepseek/deepseek-v4-flash-0731:free',     # 1M ctx, best free extraction (always reasons)
            'nvidia/nemotron-3-super-120b-a12b:free',   # 262k ctx
            'nex-agi/nex-n2.5-pro:free',                # 262k ctx, reasoning can be off
            'google/gemma-4-31b-it:free',               # 262k ctx, no forced reasoning
            'qwen/qwen3.8-27b:free',                    # multimodal
            'nex-agi/nex-n2.5-mini:free',               # small / fast
            'openrouter/free',                          # OR free router - last resort
        ],
        'roles': {
            'tiny':    ['nex-agi/nex-n2.5-mini:free', 'google/gemma-4-31b-it:free', 'openrouter/free'],
            'write':   ['nex-agi/nex-n2.5-pro:free', 'google/gemma-4-31b-it:free', 'openrouter/free'],
            'extract': ['deepseek/deepseek-v4-flash-0731:free', 'nvidia/nemotron-3-super-120b-a12b:free',
                        'nex-agi/nex-n2.5-pro:free', 'google/gemma-4-31b-it:free',
                        'qwen/qwen3.8-27b:free', 'nex-agi/nex-n2.5-mini:free', 'openrouter/free'],
            'vision':  ['nex-agi/nex-n2.5-pro:free', 'qwen/qwen3.8-27b:free',
                        'google/gemma-4-31b-it:free', 'openrouter/free'],
        },
        'url':    'https://openrouter.ai/keys',
        'note':   'Free — no credit card needed',
    },
}

# ── AI model roles + SDK-shape helpers ────────────────────────────────────────
# PROVIDERS is the ONE place model ids live. Every runtime list comes from
# _ai_models(provider, role) which filters out ids marked dead at runtime.
# Roles: tiny = 50-300 token calls (scoring, handle lookup, image labels),
#        write = posts/tweets, extract = long-transcript clip JSON, vision = images.
# The helpers below hide per-model parameter quirks (thinking, reasoning tokens,
# temperature) and the three response shapes (google-genai / groq+openai / raw
# OpenRouter JSON), so call sites stay one-liners.
_GROQ_MAX_PROMPT_CHARS = 13000   # Groq free plan: 8K tokens/min per model (prompt + max output)

def _provider_data(prov):
    """PROVIDERS entry by display name or by lib key ('gemini'/'groq'/'openrouter')."""
    d = PROVIDERS.get(prov)
    if d is not None:
        return d
    for _d in PROVIDERS.values():
        if _d.get('lib') == prov:
            return _d
    return {}

def _ai_models(prov, role=None):
    """Ordered live (not dead) model ids for a provider, best-first for `role`."""
    data = _provider_data(prov)
    base = [m for m in data.get('models', []) if m not in _DEAD_MODELS]
    if role:
        pref = [m for m in data.get('roles', {}).get(role, []) if m in base]
        if pref:
            return pref
    return base

def _ai_model(prov, role=None):
    ms = _ai_models(prov, role)
    return ms[0] if ms else ''

def _pick_model(prov, chosen='', role=None):
    """`chosen` if it is still a live model of `prov`, else the provider's best live model."""
    live = _ai_models(prov)
    if chosen and chosen in live:
        return chosen
    ms = _ai_models(prov, role)
    if not ms:
        raise ValueError(f'No models left for {prov} (all marked unavailable)')
    return ms[0]

def _safe_text(resp):
    """Stripped text from a google-genai response, a groq/openai SDK response or a
    raw OpenRouter JSON dict. Returns '' (never None) when there is no text."""
    try:
        if resp is None:
            return ''
        if isinstance(resp, str):
            return resp.strip()
        if isinstance(resp, dict):
            ch = resp.get('choices') or []
            c0 = ch[0] if ch and isinstance(ch[0], dict) else {}
            txt = (c0.get('message') or {}).get('content') or c0.get('text')
            return txt.strip() if isinstance(txt, str) else ''
        choices = getattr(resp, 'choices', None)
        if choices:
            msg = getattr(choices[0], 'message', None)
            txt = getattr(msg, 'content', None) if msg is not None else None
            if isinstance(txt, list):   # content-part lists
                txt = ''.join((p.get('text', '') if isinstance(p, dict) else getattr(p, 'text', '')) or '' for p in txt)
            return txt.strip() if isinstance(txt, str) else ''
        try:
            txt = getattr(resp, 'text', None)   # google-genai: None on empty/blocked/max-tokens
        except Exception:
            txt = None
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
        for cand in (getattr(resp, 'candidates', None) or []):
            parts = getattr(getattr(cand, 'content', None), 'parts', None) or []
            t = ''.join(p.text for p in parts
                        if isinstance(getattr(p, 'text', None), str) and not getattr(p, 'thought', False))
            if t.strip():
                return t.strip()
    except Exception:
        pass
    return ''

_RATE_RE = re.compile(r'\b(?:429|503|413)\b|rate[ _-]?limit|too many requests|request too large|'
                      r'quota|resource_exhausted|temporarily|upstream|unavailable|overloaded|\bcapacity\b')
_NOT_GONE_RE = re.compile(r'\b(?:401|402|403|429)\b|invalid api key|api key not valid|api_key_invalid|'
                          r'user not found|unauthorized|forbidden')
_GONE_RE = re.compile(r'\b404\b|model_not_found|not_found|no endpoints|decommission|'
                      r'no longer (?:supported|available)|has been shut ?down|does not exist')

def _is_rate_limit_error(e):
    """True for rate-limit / quota / overload errors. (The old bare 'rate' substring also
    matched 'generateContent' and 'separate' - do not reintroduce it.)"""
    s = str(e).lower()
    if 'could not parse' in s:
        return False
    return bool(_RATE_RE.search(s))

def _is_model_gone_error(e):
    """True when the API says this MODEL id is retired/unknown (404, model_not_found,
    decommissioned). Auth errors such as OpenRouter's 401 'User not found.' are NOT."""
    s = str(e).lower()
    if _NOT_GONE_RE.search(s):
        return False
    return bool(_GONE_RE.search(s))

def _gemini_ver(model):
    m = re.search(r'gemini-(\d+)(?:\.(\d+))?', str(model or '').lower())
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

def _gemini_config(model, max_tokens, temperature=None, json=False, think='min'):
    """GenerateContentConfig kwargs for `model`.
    Thinking tokens count against max_output_tokens, so the thinking control is per model
    family and the cap gets headroom for it:
      2.5-*      thinking_budget=0 (off); think='low' -> 1024
      3.5-*-lite/3.5/3.6   thinking_level 'minimal' (think='low' -> 'low')
      3.7/3.8-flash, pro   cannot go below 'low', so they always get 'low' + a bigger cap
    Gemini 3.x: temperature is omitted (Google recommends the default 1.0).
    json=True -> response_mime_type application/json."""
    m = str(model or '').lower()
    ver = _gemini_ver(m)
    cap = int(max_tokens)
    cfg = {}
    if ver >= (3, 0):
        lvl = 'low' if (ver >= (3, 7) or 'pro' in m or think == 'low') else 'minimal'
        cfg['thinking_config'] = {'thinking_level': lvl}
        cap += 1024 if lvl == 'low' else 256
    else:
        if temperature is not None:
            cfg['temperature'] = temperature
        if ver >= (2, 5):
            budget = 1024 if think == 'low' else (128 if 'pro' in m else 0)
            cfg['thinking_config'] = {'thinking_budget': budget}
            cap += budget
    cfg['max_output_tokens'] = min(cap, 65536)
    if json:
        cfg['response_mime_type'] = 'application/json'
    cfg['automatic_function_calling'] = {'disable': True}   # silences the SDK 2.x AFC warning
    return cfg

_GEMINI_OPTIONAL_CFG = ('thinking_config', 'automatic_function_calling')

def _gemini_generate(client, model, contents, config):
    """client.models.generate_content; if the SDK/model rejects the optional thinking/AFC
    keys (older SDK, unexpected model behaviour) retry once without them."""
    try:
        return client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as e:
        s = str(e).lower()
        if (any(k in config for k in _GEMINI_OPTIONAL_CFG) and not _RATE_RE.search(s)
                and any(x in s for x in ('thinking', 'automatic_function_calling', 'extra_forbidden', 'extra inputs'))):
            cfg2 = {k: v for k, v in config.items() if k not in _GEMINI_OPTIONAL_CFG}
            return client.models.generate_content(model=model, contents=contents, config=cfg2)
        raise

def _gemini_complete(key, role, contents, max_tokens, temperature=None, json=False,
                     think='min', models=None, client=None):
    """One Gemini text call with model fallback -> stripped text ('' if every model was empty).
    Rate-limit / retired-model errors move on to the next model and the last one is raised only
    if nothing answered; any other error raises immediately. The Client is bound to a variable:
    a temporary Client is garbage-collected and closed before the request runs."""
    if client is None:
        from google import genai as _g
        client = _g.Client(api_key=key)
    last = None
    for m in (models or _ai_models('gemini', role)):
        try:
            resp = _gemini_generate(client, m, contents, _gemini_config(m, max_tokens, temperature, json, think))
        except Exception as e:
            if _is_model_gone_error(e):
                _mark_model_dead(m)
            elif not _is_rate_limit_error(e):
                raise
            last = e
            continue
        t = _safe_text(resp)
        if t:
            return t
    if last is not None:
        raise last
    return ''

def _groq_kwargs(model, max_tokens, json=False):
    """chat.completions kwargs for a Groq model. gpt-oss and qwen3.x are reasoning models whose
    reasoning tokens count against max_completion_tokens, so they get low effort + headroom.
    reasoning_format is only valid for qwen (and is mutually exclusive with include_reasoning,
    which is what gpt-oss uses). json=True -> response_format json_object (prompt must say JSON
    and must ask for an OBJECT, not a bare array)."""
    m = str(model or '').lower()
    cap = int(max_tokens)
    kw = {}
    if 'gpt-oss' in m:
        kw['reasoning_effort'] = 'low'
        kw['include_reasoning'] = False
        cap += 512
    elif 'qwen3' in m:
        if cap <= 400:
            kw['reasoning_effort'] = 'none'
        else:
            kw['reasoning_effort'] = 'low'
            kw['reasoning_format'] = 'hidden'
            cap += 512
    kw['max_completion_tokens'] = cap
    if json:
        kw['response_format'] = {'type': 'json_object'}
    return kw

_GROQ_OPTIONAL_KW = ('reasoning_effort', 'include_reasoning', 'reasoning_format', 'response_format')

def _groq_chat(client, **kw):
    """client.chat.completions.create; on a 400 that blames the reasoning/JSON options
    (not a retired model) retry once without them."""
    try:
        return client.chat.completions.create(**kw)
    except Exception as e:
        s = str(e).lower()
        if ('400' in s and not _is_model_gone_error(e)
                and any(x in s for x in ('reasoning', 'response_format', 'json'))
                and any(k in kw for k in _GROQ_OPTIONAL_KW)):
            return client.chat.completions.create(**{k: v for k, v in kw.items() if k not in _GROQ_OPTIONAL_KW})
        raise

def _groq_complete(key, role, messages, max_tokens, temperature=None, json=False,
                   models=None, client=None):
    """One Groq text call with model fallback -> stripped text ('' if every model was empty)."""
    if client is None:
        from groq import Groq as _G
        client = _G(api_key=key)
    last = None
    for m in (models or _ai_models('groq', role)):
        kw = _groq_kwargs(m, max_tokens, json)
        if temperature is not None:
            kw['temperature'] = temperature
        try:
            resp = _groq_chat(client, model=m, messages=messages, **kw)
        except Exception as e:
            if _is_model_gone_error(e):
                _mark_model_dead(m)
            elif not _is_rate_limit_error(e):
                raise
            last = e
            continue
        t = _safe_text(resp)
        if t:
            return t
    if last is not None:
        raise last
    return ''

def _openrouter_kwargs(model, max_tokens):
    """{'max_tokens', 'extra_body'} for an OpenRouter model. Models that always reason get
    reasoning effort 'low' and headroom (reasoning tokens count against max_tokens on most
    providers; a too-small cap returns content=None)."""
    m = str(model or '').lower()
    cap = int(max_tokens)
    extra = {}
    if any(x in m for x in ('deepseek-v4', 'nemotron-3-super', 'qwen3.8')):
        extra = {'reasoning': {'effort': 'low'}}
        cap += 4096
    return {'max_tokens': cap, 'extra_body': extra}

def _openrouter_complete(key, role, messages, max_tokens, temperature=None, models=None, timeout=45):
    """Raw OpenRouter chat call with model fallback -> stripped text. Handles error bodies that
    arrive with HTTP 200 and null content. 401/402/daily-cap errors raise immediately (no model
    can fix them); dead-looking models are skipped for this call only (never persisted: a 404
    'No endpoints found' can also be an account privacy setting)."""
    import requests as _rq
    last = None
    for m in list(models or _ai_models('openrouter', role))[:3]:
        kw = _openrouter_kwargs(m, max_tokens)
        body = {'model': m, 'messages': messages, 'max_tokens': kw['max_tokens']}
        body.update(kw['extra_body'])
        if temperature is not None:
            body['temperature'] = temperature
        r = _rq.post('https://openrouter.ai/api/v1/chat/completions',
                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                              'HTTP-Referer': 'https://github.com/thatspeedykid/clipfinder'},
                     json=body, timeout=timeout)
        try:
            j = r.json()
        except Exception:
            j = {}
        err = j.get('error') if isinstance(j, dict) else None
        if err or r.status_code >= 400:
            err = err if isinstance(err, dict) else {}
            msg = str(err.get('message') or (r.text or '')[:120] or 'error')
            code = r.status_code if r.status_code >= 400 else err.get('code', 0)
            last = Exception(f'OpenRouter error code: {code} - {msg[:200]}')
            if str(code) in ('401', '402') or 'per-day' in msg.lower():
                raise last
            continue
        t = _safe_text(j)
        if t:
            return t
    if last is not None:
        raise last
    return ''

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
  {
    "start": "HH:MM:SS",
    "end":   "HH:MM:SS",
    "title": "Short label for this segment",
    "reason": "Why this is good content",
    "score": 9,
    "order": 1
  }
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

TITLE: News headline style — "She admits the prank went too far" not "Funny clip" — use REAL names from the transcript, never invent names.
If a VIDEO TITLE is provided, extract the names of people mentioned in it and use those names in titles and descriptions when those people speak.

UNIQUENESS: Every clip MUST cover a DIFFERENT moment with a DIFFERENT title. Do NOT output multiple clips about the same topic or event. Spread clips across the full transcript — different timestamps, different topics, different people speaking.

LENGTH CHECK: Before outputting, verify each clip is between 60-160 seconds.
Calculate: convert end and start to seconds, subtract. If under 60s, extend or drop it.

Return ONLY a raw JSON array. NO markdown. NO backticks. NO ```json. NO explanation before or after. Start your response with [ and end with ]. Nothing else.
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
If names above are blank or "Unknown", extract the names of people being interviewed from the VIDEO TITLE if provided, or infer names from the transcript itself (e.g. when the interviewer says "So [Name], tell me about...").

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
  {
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "speaker": "Sophie",
    "title": "Punchy title max 8 words",
    "reason": "One sentence why this goes viral",
    "score": 9
  }
]

TRANSCRIPT:
{transcript}
"""




# Config lives next to the EXE/script so settings survive across launches
# This ensures _setup_done, API keys, folders etc persist properly
CONFIG_FILE  = USER_DIR / 'clipfinder_config.json'
SESSION_FILE = USER_DIR / 'clipfinder_session.json'


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

_LIVE_CFG = None   # the App's own cfg dict (set in App.__init__) - see save_cfg
_CFG_SHARED_KEYS = ('dead_models', 'dead_models_ts', 'groq_tpd_until')   # written by workers via load_cfg/save_cfg

def load_cfg():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        # Missing file = first run. A file that exists but does not parse is corrupt: fall back to the
        # last good copy (.bak) so API keys are not silently lost on the next save.
        try:
            if CONFIG_FILE.exists():
                return json.loads(Path(str(CONFIG_FILE) + '.bak').read_text())
        except Exception:
            pass
        return {}

_CFG_LOCK = threading.Lock()

def save_cfg(d):
    try:
        # Keys that background workers persist through their own load_cfg()/save_cfg() round trip
        # would be overwritten by the next save of the App's long-lived cfg dict, so mirror them.
        if _LIVE_CFG is not None and d is not _LIVE_CFG:
            for _k in _CFG_SHARED_KEYS:
                if _k in d:
                    _LIVE_CFG[_k] = d[_k]
        # Atomic write (temp file + replace) so a crash mid-write can never leave a truncated config
        _tmp = Path(f'{CONFIG_FILE}.{os.getpid()}.{threading.get_ident()}.tmp')
        _tmp.write_text(json.dumps(d, indent=2))
        os.replace(_tmp, CONFIG_FILE)
        try:
            _um_sh.copyfile(CONFIG_FILE, str(CONFIG_FILE) + '.bak')
        except Exception:
            pass
    except Exception as _se:
        print(f'[CF] save_cfg failed: {_se}')

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

    # Only text-entry widgets get this menu; don't replace other widgets' own <Button-3> bindings
    if type(widget).__name__ not in ('Entry', 'Text', 'ScrolledText'):
        return
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
    global _GPU_DETECT_FAILED
    _GPU_DETECT_FAILED = False
    try:
        r = subprocess.run([ff, '-encoders'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        enc_list = (r.stdout or b'').decode(errors='replace') + (r.stderr or b'').decode(errors='replace')

        # NVIDIA NVENC
        if 'h264_nvenc' in enc_list:
            # Quick test that NVENC actually works (card must be connected)
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if test.returncode == 0:
                print('[CF] GPU: NVIDIA NVENC detected')
                return 'h264_nvenc', 'aac', ['-preset', 'p5', '-rc', 'vbr', '-cq', '18', '-b:v', '0', '-maxrate', '20M', '-profile:v', 'high', '-b:a', '192k']

        # AMD AMF (Windows)
        if 'h264_amf' in enc_list:
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_amf', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if test.returncode == 0:
                print('[CF] GPU: Intel QSV detected')
                return 'h264_qsv', 'aac', ['-preset', 'medium', '-global_quality', '18', '-look_ahead', '1', '-b:a', '192k']

    except Exception as ex:
        _GPU_DETECT_FAILED = True   # probe timed out / ffmpeg missing: get_encoder must not cache this
        print(f'[CF] GPU detection failed: {ex}')

    print('[CF] CPU: libx264 — high quality')
    return 'libx264', 'aac', [
        '-preset', 'slow', '-crf', '18', '-profile:v', 'high',
        '-movflags', '+faststart', '-b:a', '192k',
    ]

# Cache result so we only probe once per session
_GPU_ENCODER_CACHE = None
_GPU_DETECT_FAILED = False   # last detect_gpu_encoder() hit an exception (transient), not a clean "no GPU"
_GPU_DETECT_TRIES = 0

# Models permanently decommissioned — auto-populated when 400 decommissioned error hit
# Persisted to config so dead models are never retried across sessions
_DEAD_MODELS: set = set()
# A persisted dead mark is only trusted for this long, so a model that comes back (or was
# marked by a transient/misclassified error) is retried instead of blacklisted forever.
_DEAD_MODEL_TTL = 7 * 86400

def _mark_model_dead(model: str):
    """Mark a model as decommissioned: removed from the provider lists for this run and
    remembered in config (with a timestamp) for _DEAD_MODEL_TTL."""
    global _DEAD_MODELS
    # Never strip a provider's LAST model - keep it so the real API error stays visible
    for prov_data in PROVIDERS.values():
        _ms = prov_data.get('models') if isinstance(prov_data, dict) else None
        if _ms and model in _ms and not [m for m in _ms if m != model]:
            print(f'[CF] Not removing {model}: it is the only model left for this provider')
            return
    _DEAD_MODELS.add(model)
    # Remove from PROVIDERS in memory
    for prov_data in PROVIDERS.values():
        if isinstance(prov_data, dict) and 'models' in prov_data:
            if model in prov_data['models']:
                prov_data['models'].remove(model)
                print(f'[CF] Removed decommissioned model: {model}')
    # Persist to config (id -> epoch seconds; 'dead_models' list kept for older builds)
    try:
        import time as _dm_t
        cfg = load_cfg()
        ts = cfg.get('dead_models_ts')
        ts = ts if isinstance(ts, dict) else {}
        ts[model] = _dm_t.time()
        cfg['dead_models_ts'] = ts
        cfg['dead_models'] = sorted(ts)
        save_cfg(cfg)
    except Exception:
        pass

def _load_dead_models():
    """Load recently-decommissioned models from config on startup. Entries older than
    _DEAD_MODEL_TTL, entries with no timestamp (legacy permanent list) and entries that are
    no longer in any provider list are dropped, so a stale list can never blacklist a valid model."""
    try:
        import time as _dm_t
        cfg = load_cfg()
        ts = cfg.get('dead_models_ts')
        ts = ts if isinstance(ts, dict) else {}
        known = {m for d in PROVIDERS.values() if isinstance(d, dict) for m in d.get('models', [])}
        now = _dm_t.time()
        keep = {m: t for m, t in ts.items()
                if isinstance(t, (int, float)) and now - t < _DEAD_MODEL_TTL and m in known}
        for m in keep:
            _owners = [d for d in PROVIDERS.values() if isinstance(d, dict) and m in d.get('models', [])]
            if any(len(d['models']) <= 1 for d in _owners):
                continue   # would empty a provider - see _mark_model_dead
            _DEAD_MODELS.add(m)
            for d in _owners:
                d['models'].remove(m)
        if keep != ts or set(cfg.get('dead_models', [])) != set(keep):
            cfg['dead_models_ts'] = keep
            cfg['dead_models'] = sorted(keep)
            save_cfg(cfg)
    except Exception:
        pass
_GPU_ENCODER_RESET = False
def detect_encoder_name():
    try:
        v,_,_ = get_encoder(ensure_ffmpeg())
        return v
    except: return "cpu"

def get_encoder(ff):
    global _GPU_ENCODER_CACHE, _GPU_DETECT_TRIES
    if _GPU_ENCODER_CACHE is None:
        res = detect_gpu_encoder(ff)
        _GPU_DETECT_TRIES += 1
        if _GPU_DETECT_FAILED and _GPU_DETECT_TRIES < 3:
            return res   # transient probe failure (timeout / AV scan): do not cache, retry next call
        _GPU_ENCODER_CACHE = res
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

def _detect_whisper_device(use_gpu=True):
    """Detect best available compute device for whisper transcription.
    Returns (device, compute_type, label)
    use_gpu=False forces CPU-only mode."""
    global _WHISPER_DEVICE_CACHE
    if _WHISPER_DEVICE_CACHE and use_gpu:
        return _WHISPER_DEVICE_CACHE

    # ── GPU disabled by user ─────────────────────────────────────────────────
    if not use_gpu:
        try:
            import faster_whisper as _fw_check  # noqa
            return ('cpu', 'int8', 'CPU int8 (GPU disabled)')
        except ImportError:
            return ('cpu', 'int8', 'CPU (GPU disabled)')

    # ── 0. NVIDIA CUDA — whisper.cpp cublas binary ───────────────────────────
    # Use whisper.cpp with cuBLAS instead of faster-whisper+ctranslate2
    # Avoids ctranslate2/cuDNN version hell entirely — just needs NVIDIA driver
    try:
        import subprocess as _sp_nv
        _nv = _sp_nv.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                         capture_output=True, text=True, timeout=3)
        if _nv.returncode == 0 and _nv.stdout.strip():
            _gpu_name = _nv.stdout.strip().split('\n')[0].strip()
            # Check if cublas whisper.cpp binary exists
            _wcpp_cuda = _app_path('whisper_cpp_cuda')
            _wcpp_cuda_exe = _wcpp_cuda / 'whisper-whisper-cli.exe'
            if _wcpp_cuda_exe.exists():
                _WHISPER_DEVICE_CACHE = ('cpu', 'int8', f'NVIDIA CUDA ({_gpu_name}) ⚡')
                return _WHISPER_DEVICE_CACHE
            else:
                # NVIDIA detected but cublas binary not installed yet
                _WHISPER_DEVICE_CACHE = ('cpu', 'int8', f'NVIDIA GPU ({_gpu_name}) — click Install NVIDIA CUDA in Settings')
                return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # Only reach whisper.cpp if CUDA is NOT available
    # ── 1. whisper.cpp + Vulkan (AMD/Intel only) ─────────────────────────────
    _wcpp = _find_whispercpp()
    if _wcpp and _find_whispercpp_model('base'):
        # Check if this is a new RDNA4 card that isn't supported yet
        try:
            import subprocess as _sp_vk, platform as _pl_vk
            if _pl_vk.system() == 'Windows':
                # Check GPU generation via wmic
                _wmic = _sp_vk.run(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                    capture_output=True, text=True, timeout=5)
                _gpu_name = _wmic.stdout.lower()
                _is_rdna4 = any(x in _gpu_name for x in ['rx 9', '9600', '9700', '9800', '9900'])
                if _is_rdna4:
                    # RDNA4 detected — whisper.cpp Vulkan won't use GPU yet
                    _WHISPER_DEVICE_CACHE = ('cpu', 'int8',
                        'CPU int8 ⚠ RDNA4 GPU not yet supported by whisper.cpp')
                    return _WHISPER_DEVICE_CACHE
        except: pass
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'whisper.cpp Vulkan GPU ⚡')
        return _WHISPER_DEVICE_CACHE

    # ── 2. torch-directml (AMD/Intel on Windows) ──────────────────────────────
    try:
        import torch_directml as _dml
        if _dml.device_count() > 0:
            _WHISPER_DEVICE_CACHE = ('directml', 'float16', 'AMD/Intel DirectML GPU')
            return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # ── 3. CPU int8 via CTranslate2 — still 4x faster than openai-whisper ────
    try:
        import faster_whisper as _fw_check  # noqa
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'CPU int8 (faster-whisper)')
    except ImportError:
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'Not installed — use Settings → Update Modules')
    return _WHISPER_DEVICE_CACHE



_WCPP_INSTALL_MUTEX = threading.Lock()  # held only WHILE an install runs, so a failed one can be retried

def auto_install_whispercpp(model_size='base', status_cb=None):
    """Auto-download whisper-whisper-cli.exe (Vulkan) + ggml model for AMD/Intel GPU.
    Raises RuntimeError if the install did not complete (or one is already running)."""
    if not _WCPP_INSTALL_MUTEX.acquire(blocking=False):
        raise RuntimeError('whisper.cpp install already running')
    try:
        return _auto_install_whispercpp_impl(model_size, status_cb)
    finally:
        _WCPP_INSTALL_MUTEX.release()

def _auto_install_whispercpp_impl(model_size='base', status_cb=None):
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
        _size_b = real_exe.stat().st_size
        if _size_b < 50_000:   # whisper-cli.exe itself is only ~0.5MB (the GPU code lives in the DLLs)
            _log(f'Binary exists but only {_size_b//1024}KB — too small, deleting and re-downloading...')
            real_exe.unlink()
        else:
            _log(f'Binary already exists: {real_exe.name} ({_size_b//1024}KB)')
    if not real_exe.exists():
        _log('Downloading whisper-whisper-cli.exe (Vulkan)...')
        tmp_zip = Path(_tf.gettempdir()) / 'whispercpp.zip'
        asset_url = None

        # Known-good direct asset URL. (The official ggml-org releases/latest API now lists no assets and
        # the old v1.7.x vulkan zips / SourceForge mirror all return 404, so discovery was dead code.)
        if not asset_url:
            fallbacks = [
                # jerryshell dedicated Vulkan Windows build — has ggml-vulkan.dll
                'https://github.com/jerryshell/whisper.cpp-windows-vulkan-bin/releases/latest/download/whisper.cpp-windows-vulkan.zip',
            ]
            for fb in fallbacks:
                try:
                    _log(f'Trying: {fb.split("/")[-1]}')
                    _um_download(fb, tmp_zip, timeout=60)
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
            raise RuntimeError('Could not find a whisper.cpp download (check your internet connection)')

        # Download if not already got from fallback loop
        if not tmp_zip.exists() or tmp_zip.stat().st_size < 100000:
            _log('Downloading zip...')
            try:
                _last_pct = [-10]
                def _dlprogress(got, total):
                    if total > 0:
                        pct = min(100, int(got / total * 100))
                        if pct >= _last_pct[0] + 10:
                            _last_pct[0] = pct
                            _log(f'Downloading... {pct}%')
                _um_download(asset_url, tmp_zip, timeout=60, on_bytes=_dlprogress)
            except Exception as e:
                _log(f'Download failed: {e}')
                raise RuntimeError(f'whisper.cpp download failed: {e}')

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

            # Verify this is actually a Vulkan build
            _has_vulkan_dll = (install_dir / 'ggml-vulkan.dll').exists()
            _log(f'ggml-vulkan.dll present: {_has_vulkan_dll}')
            if not _has_vulkan_dll:
                _log('⚠ This build does not include ggml-vulkan.dll — NOT a Vulkan build!')
                _log('  Trying known-good Vulkan fallback URLs...')
                def _wipe_install_files():
                    # Remove only the extracted files - never models/ (already-downloaded ggml models)
                    for _f in install_dir.iterdir():
                        try:
                            if _f.is_file():
                                _f.unlink()
                        except OSError:
                            pass
                    models_dir.mkdir(parents=True, exist_ok=True)
                _wipe_install_files()
                _vulkan_fallbacks = [
                    # jerryshell/whisper.cpp-windows-vulkan-bin — dedicated Vulkan Windows builds
                    'https://github.com/jerryshell/whisper.cpp-windows-vulkan-bin/releases/latest/download/whisper.cpp-windows-vulkan.zip',
                ]
                for _vfb in _vulkan_fallbacks:
                    try:
                        _log(f'Trying Vulkan build: {_vfb.split("/")[-1]}')
                        _um_download(_vfb, tmp_zip, timeout=60)
                        if tmp_zip.exists() and tmp_zip.stat().st_size > 100000:
                            import zipfile as _vzf
                            with _vzf.ZipFile(str(tmp_zip), 'r') as _vz:
                                for _vzname in _vz.namelist():
                                    _vbn = Path(_vzname).name
                                    if not _vbn or _vzname.endswith('/'): continue
                                    _vdata = _vz.read(_vzname)
                                    if len(_vdata) > 0:
                                        (install_dir / _vbn).write_bytes(_vdata)
                            tmp_zip.unlink(missing_ok=True)
                            if (install_dir / 'ggml-vulkan.dll').exists():
                                _log('✅ Vulkan build installed successfully!')
                                break
                            else:
                                _wipe_install_files()
                    except Exception as _vfe:
                        _log(f'Vulkan fallback failed: {_vfe}')
                        continue

        except Exception as e:
            _log(f'Extraction failed: {e}')
            raise RuntimeError(f'whisper.cpp extraction failed: {e}')

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
            raise RuntimeError('whisper.cpp binary not found after extraction')

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
        _dl_tmp = model_path.with_name(model_path.name + '.dl')   # only renamed to .bin once complete
        try:
            _mstat = [0, 0, -5]   # got, total, last logged pct
            def _reporthook(got, total):
                _mstat[0], _mstat[1] = got, total
                if total > 0:
                    pct = min(100, int(got / total * 100))
                    if pct >= _mstat[2] + 5:
                        _mstat[2] = pct
                        _log(f'Model: {pct}%')
            _um_download(model_url, _dl_tmp, timeout=60, on_bytes=_reporthook)
            if _mstat[1] > 0 and _mstat[0] < _mstat[1]:
                raise OSError(f'incomplete download ({_mstat[0]} of {_mstat[1]} bytes)')
            if _dl_tmp.stat().st_size < 1_000_000:
                raise OSError('downloaded model file is too small')
            os.replace(_dl_tmp, model_path)
            _log(f'Model ready: {model_path.name}')
        except Exception as e:
            for _junk in (_dl_tmp, Path(str(_dl_tmp) + '.part')):
                try: _junk.unlink()
                except OSError: pass
            _log(f'Model download failed: {e}')
            raise RuntimeError(f'whisper.cpp model download failed: {e}')

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
        # -vn: skip video decode (audio-only is ~5x faster); 1 s windows; long VODs need a long timeout
        cmd = [ffmpeg_path, '-nostdin', '-i', video_path, '-vn',
               '-af', 'aresample=16000,asetnsamples=n=16000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
               '-f', 'null', '-']
        r = _sp.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3600)
        output = (r.stderr or '') + (r.stdout or '')

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
            cmd2 = [ffmpeg_path, '-nostdin', '-i', video_path, '-vn',
                   '-af', 'silencedetect=noise=-30dB:d=0.5',
                   '-f', 'null', '-']
            r2 = _sp.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3600)
            loud_times = []
            for m in _re.finditer(r'silence_end: ([\d.]+)', r2.stderr or ''):
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
        r = _sp.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
        output = (r.stderr or '') + (r.stdout or '')
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

def _find_whispercpp_model(model_size, model_dir=None):
    """Find ggml model — checks auto-install dir first."""
    model_map = {'tiny':'tiny','base':'base','small':'small','medium':'medium','large':'large-v3'}
    name = model_map.get(model_size, model_size)
    search_dirs = []
    if model_dir:
        search_dirs.append(Path(model_dir))
    search_dirs += [
        _app_path('whisper_cpp') / 'models',
        _app_path('whisper_cpp_cuda') / 'models',
        _app_path('whisper.cpp') / 'models',
        Path('C:/whisper.cpp/models'),
        Path.home() / '.cache' / 'whisper',
    ]
    for d in search_dirs:
        for pattern in [f'ggml-{name}.bin', f'ggml-{name}-q5_0.bin', f'ggml-{name}-q8_0.bin']:
            p = d / pattern
            if p.exists(): return str(p)
    return None

def _smart_cutoff_secs(initial_prompt, duration):
    """Smart Transcribe: parse 'ignore/skip last N hour(s)/minute(s)' from the instructions.
    Returns the second at which to stop transcribing, or None."""
    m = re.search(r'(?:ignore|skip|don.t.process|dont.process)\s+(?:the\s+)?last\s+(\d+(?:\.\d+)?)\s*(hour|hr|minute|min)',
                  (initial_prompt or '').lower())
    if not m or not duration:
        return None
    cut = duration - int(float(m.group(1)) * (3600 if 'h' in m.group(2) else 60))
    return cut if cut > 0 else None


def _do_transcribe(vid, model_size, initial_prompt=None, ffmpeg_path=None, progress_cb=None, use_word_timestamps=False, use_gpu=True, log_cb=None):
    """Transcribe with best available backend:
    1. whisper.cpp + Vulkan (AMD/Intel/NVIDIA GPU on Windows — fastest)
    2. faster-whisper + CUDA (NVIDIA only)
    3. faster-whisper CPU int8 (always works, 4x faster than openai-whisper)
    4. openai-whisper CPU fallback
    use_gpu=False skips all GPU paths and forces CPU-only.
    """
    _ensure_pkgs_on_path()  # always check PKGS_DIR before importing whisper
    _do_transcribe._cancelled = False  # clear any stale cancel flag left by an earlier cancelled task
    # Note: do NOT bust faster_whisper/ctranslate2/torch — busting them
    # breaks CUDA DLL initialization and causes GPU to not be detected
    import os as _os, warnings as _wn
    _wn.filterwarnings('ignore')
    _os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
    _os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
    _os.environ.setdefault('HF_HUB_VERBOSITY', 'error')

    # Patch ffmpeg into PATH
    if ffmpeg_path and ffmpeg_path != 'ffmpeg':
        ff_dir = str(Path(ffmpeg_path).parent)
        _os.environ['PATH'] = ff_dir + _os.pathsep + _os.environ.get('PATH', '')

    # ── Detect device ─────────────────────────────────────────────────────────
    _device_auto, _compute_auto, _dev_label_auto = _detect_whisper_device(use_gpu=use_gpu)

    # ── NVIDIA CUDA — whisper.cpp cublas binary ───────────────────────────────
    _has_nvidia = 'NVIDIA CUDA' in _dev_label_auto and use_gpu
    _wcpp_cuda_dir = _app_path('whisper_cpp_cuda')
    _wcpp_cuda_exe = _wcpp_cuda_dir / 'whisper-whisper-cli.exe'
    _has_cuda = _has_nvidia and _wcpp_cuda_exe.exists()

    # ── 1. whisper.cpp with Vulkan — AMD/Intel GPU only ──────────────────────
    _wcpp = (_find_whispercpp() if use_gpu and not _has_cuda else None)
    _wmodel = _find_whispercpp_model(model_size) if _wcpp else None

    # If NVIDIA cublas binary exists, use it instead
    if _has_cuda:
        _wcpp = str(_wcpp_cuda_exe)
        _wmodel = _find_whispercpp_model(model_size, model_dir=_wcpp_cuda_dir / 'models')
        if not _wmodel:
            _wmodel = _find_whispercpp_model(model_size)
    # whisper.cpp is run with -oj (segment-level JSON only, no per-token data), so callers that
    # need word timestamps (Censor / Auto Edit) must use faster-whisper.
    if use_word_timestamps:
        _wcpp = None
        _wmodel = None
    _wc_dir = None  # per-run temp dir for the whisper.cpp wav/json (removed in the finally below)
    if _wcpp and _wmodel:
        try:
            import subprocess as _sp2, tempfile as _tf2, json as _j2, re as _re2, shutil as _sh_wc
            print(f'[CF] whisper.cpp found: {_wcpp}')
            print(f'[CF] Whisper device: Vulkan GPU (whisper.cpp)')

            # Extract audio to wav first (unique temp dir so concurrent runs / stale files can't clash)
            ff2 = ffmpeg_path or 'ffmpeg'
            _wc_dir = Path(_tf2.mkdtemp(prefix='cf_wcpp_'))
            tmp_wav = _wc_dir / 'audio.wav'
            _rc_ff = _sp2.run([ff2, '-y', '-i', vid, '-ar', '16000', '-ac', '1',
                               '-f', 'wav', str(tmp_wav)],
                              stdout=_sp2.PIPE, stderr=_sp2.PIPE)

            if _rc_ff.returncode == 0 and tmp_wav.exists() and tmp_wav.stat().st_size > 1000:
                # Output goes to same dir as wav file, named <stem>.json
                out_base = str(tmp_wav.with_suffix(''))  # no extension
                json_out = Path(out_base + '.json')

                # Get video duration for smart transcribe cutoff
                _vid_duration = 0
                try:
                    import subprocess as _sp_dur, re as _re_dur2
                    _r_dur = _sp_dur.run([str(ff2), '-i', str(vid)], capture_output=True,
                                         text=True, timeout=10, errors='replace')
                    _dm2 = _re_dur2.search(r'Duration: (\d+):(\d+):(\d+)', _r_dur.stderr)
                    if _dm2:
                        _vid_duration = int(_dm2.group(1))*3600 + int(_dm2.group(2))*60 + int(_dm2.group(3))
                except Exception:
                    pass

                # Build command — use -oj for JSON output (newer builds)
                cmd = [_wcpp,
                       '-m', _wmodel,
                       '-f', str(tmp_wav),
                       '-oj',
                       '--output-file', out_base,
                       '-t', '4',
                       '-bo', '5',
                       '-bs', '5',
                       '-l', 'auto',
                       # ── Hallucination suppression ──────────────────────────
                       '-et', '2.4',    # entropy threshold — kills looping/repetition
                       '-lpt', '-0.7',  # logprob threshold — drops low-confidence segments
                       '-wt', '0.01',   # word threshold — avoids near-silence transcription
                       '--no-fallback', # skip temperature fallback that causes hallucinations
                       # NOTE: a '-vth' flag used to be passed here. whisper-cli has no such option
                       # (only -vt/--vad-threshold, which needs --vad and a VAD model), so it exited
                       # with "unknown argument" and every GPU transcription fell back to slow CPU.
                ]
                if initial_prompt:
                    clean_prompt = initial_prompt[:200].replace('"', "'").strip()
                    cmd += ['--prompt', clean_prompt]

                # Smart Transcribe — parse instructions for time cutoffs and pass -d to whisper.cpp
                # This skips transcribing sections entirely — genuinely faster
                # log_cb is only passed by UI callers (Clip Finder / Post Studio), which own the checkbox;
                # the checkbox state is persisted in the config (log_cb is a lambda, never a bound method).
                _smart_on = False
                try:
                    _smart_on = bool(log_cb) and bool(load_cfg().get('smart_transcribe', False))
                except Exception:
                    pass
                if _smart_on and initial_prompt:
                    _cut_secs = _smart_cutoff_secs(initial_prompt, _vid_duration)
                    if _cut_secs:
                        cmd += ['-d', str(int(_cut_secs * 1000))]  # -d takes milliseconds
                        if log_cb: log_cb(f'⚡ Smart Transcribe: stopping at {int(_cut_secs//60)}:{int(_cut_secs%60):02d} (skipping the end as instructed)', '#88ccff')

                print(f'[CF] whisper.cpp cmd: {" ".join(cmd)}')
                # Use Popen to stream output for live progress
                import re as _re_wcpp, os as _os_wcpp
                # Set PATH to include whisper_cpp dir so vulkan-1.dll and ggml DLLs are found
                _wcpp_dir = str(Path(_wcpp).parent)
                _wcpp_env = dict(_os_wcpp.environ)
                _wcpp_env['PATH'] = _wcpp_dir + _os_wcpp.pathsep + _wcpp_env.get('PATH', '')
                _wcpp_env['GGML_VULKAN_DEBUG'] = '0'
                proc = _sp2.Popen(cmd, stdout=_sp2.PIPE, stderr=_sp2.PIPE, env=_wcpp_env,
                                  encoding=None)  # read as bytes to avoid cp1252 decode error
                # Get video duration for percentage
                try:
                    import cv2 as _cv_dur
                    _cap_dur = _cv_dur.VideoCapture(vid)
                    _dur_wcpp = _cap_dur.get(_cv_dur.CAP_PROP_FRAME_COUNT) / max(_cap_dur.get(_cv_dur.CAP_PROP_FPS), 1)
                    _cap_dur.release()
                except: _dur_wcpp = 0
                stdout_lines = []
                stderr_lines = []
                _cancelled = [False]
                # Read stderr (whisper.cpp writes progress there)
                import threading as _th_wcpp
                def _read_stderr():
                    for line in proc.stderr:
                        if _cancelled[0]: break
                        decoded = line.decode(errors='replace').strip()
                        stderr_lines.append(decoded)
                        # Parse timestamp: [HH:MM:SS.mmm --> ...] or [MM:SS.mmm --> ...]
                        _tm = _re_wcpp.search(r'\[(\d+):(\d+):(\d+\.\d+)\s*-->', decoded)
                        if _tm and progress_cb and _dur_wcpp > 0:
                            hrs, mins, secs = int(_tm.group(1)), int(_tm.group(2)), float(_tm.group(3))
                            cur = hrs * 3600 + mins * 60 + secs
                            pct = min(99, int(cur / _dur_wcpp * 100))
                            dm, ds = divmod(int(cur), 60)
                            tm, ts = divmod(int(_dur_wcpp), 60)
                            progress_cb(pct, f'Transcribing (GPU)... {dm}:{ds:02d} / {tm}:{ts:02d}  ({pct}%)')
                        else:
                            _tm2 = _re_wcpp.search(r'\[(\d+):(\d+\.\d+)\s*-->', decoded)
                            if _tm2 and progress_cb and _dur_wcpp > 0:
                                mins, secs = int(_tm2.group(1)), float(_tm2.group(2))
                                cur = mins * 60 + secs
                                pct = min(99, int(cur / _dur_wcpp * 100))
                                dm, ds = divmod(int(cur), 60)
                                tm, ts = divmod(int(_dur_wcpp), 60)
                                progress_cb(pct, f'Transcribing (GPU)... {dm}:{ds:02d} / {tm}:{ts:02d}  ({pct}%)')
                def _read_stdout():
                    for line in proc.stdout:
                        if _cancelled[0]: break
                        stdout_lines.append(line.decode(errors='replace'))

                # Emulated progress timer — runs alongside real parsing as fallback
                import time as _time_wcpp
                _emu_start = _time_wcpp.time()
                def _emulate_progress():
                    while proc.poll() is None and not _cancelled[0]:
                        _time_wcpp.sleep(3)
                        if _cancelled[0]: break
                        _elapsed = _time_wcpp.time() - _emu_start
                        if _dur_wcpp > 0 and progress_cb:
                            # Estimate based on ~0.3x realtime for GPU transcription
                            _est_total = _dur_wcpp * 0.35
                            _pct = min(95, int(_elapsed / max(_est_total, 1) * 100))
                            _em, _es = divmod(int(_elapsed * (_dur_wcpp / max(_est_total, 1))), 60)
                            _tm2, _ts2 = divmod(int(_dur_wcpp), 60)
                            progress_cb(_pct, f'Transcribing (GPU)... ~{_em}:{_es:02d} / {_tm2}:{_ts2:02d}  ({_pct}%)')
                t1 = _th_wcpp.Thread(target=_read_stderr, daemon=True); t1.start()
                t2 = _th_wcpp.Thread(target=_read_stdout, daemon=True); t2.start()
                t3 = _th_wcpp.Thread(target=_emulate_progress, daemon=True); t3.start()
                # Store proc so cancel can kill it
                _active_procs = getattr(_do_transcribe, '_active_procs', [])
                _active_procs.append(proc)
                _do_transcribe._active_procs = _active_procs
                try:
                    proc.wait(timeout=3600)
                finally:
                    # On timeout (or any error) never leave the whisper.cpp process running
                    if proc.poll() is None:
                        try:
                            proc.kill(); proc.wait(timeout=10)
                        except Exception:
                            pass
                    _do_transcribe._active_procs = [p for p in getattr(_do_transcribe, '_active_procs', []) if p is not proc]
                    # Let the readers drain the pipes first, then tell them (and the progress timer) to stop
                    t1.join(timeout=5); t2.join(timeout=5)
                    _cancelled[0] = True
                # Cancelled by the user (_cancel_task killed the process): don't run any retry / fallback
                if getattr(_do_transcribe, '_cancelled', False):
                    print('[CF] whisper.cpp cancelled')
                    return {'segments': [], 'language': 'en', '_cancelled': True}
                stderr_txt = '\n'.join(stderr_lines)
                stdout_txt = '\n'.join(stdout_lines)

                # Log whisper.cpp output to ClipFinder log for debugging
                if stderr_txt.strip():
                    if log_cb:
                        for _line in stderr_txt.split('\n')[:20]:  # first 20 lines
                            if _line.strip():
                                log_cb(f'[whisper.cpp] {_line}', FG3)
                    else:
                        print(f'[CF] whisper.cpp stderr:\n{stderr_txt[:800]}')

                if progress_cb and any('[' in l and '-->' in l for l in stderr_lines):
                    progress_cb(99, 'Finalising transcript...')

                # Detect if Vulkan GPU actually ran — must see device detection AND actual transcription
                _vulkan_device = 'ggml_vulkan: found' in stderr_txt.lower() or 'ggml_vulkan: 0 =' in stderr_txt.lower()
                # whisper-cli prints its '[t0 --> t1] text' segment lines to stdout (not stderr)
                _actually_ran = any('[' in l and '-->' in l for l in stderr_lines + stdout_lines)
                _error_exit = 'error: unknown argument' in stderr_txt or 'usage:' in stderr_txt
                _vulkan_used = _vulkan_device and _actually_ran and not _error_exit
                _gpu_fallback = not _vulkan_used
                if _gpu_fallback and log_cb:
                    log_cb('ℹ whisper.cpp GPU status unknown — check Task Manager for GPU usage', FG2)
                elif _vulkan_used and log_cb:
                    log_cb('✅ Vulkan GPU confirmed active', GREEN)
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
                    return {'segments': segments, 'language': (data.get('result') or {}).get('language') or 'en'}
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

                    # (The old '-oj' -> '--output-json' retry was removed: they are exact aliases, so it
                    #  just re-ran the identical hour-long command with no way to cancel it.)
        except Exception as _wcpp_err:
            print(f'[CF] whisper.cpp error: {_wcpp_err}, falling back...')
        finally:
            if _wc_dir is not None:
                _sh_wc.rmtree(_wc_dir, ignore_errors=True)
    elif _wcpp and not _wmodel:
        print(f'[CF] whisper.cpp: no ggml-{model_size}.bin — downloading now...')
        try:
            import urllib.request as _ur2, threading as _thr2
            _models_dir = _app_path('whisper_cpp', 'models')
            _models_dir.mkdir(parents=True, exist_ok=True)
            _gname      = {'large': 'large-v3'}.get(model_size, model_size)  # same mapping as _find_whispercpp_model
            _model_dst  = _models_dir / f'ggml-{_gname}.bin'
            _model_url  = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                          f'ggml-{_gname}.bin')
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
            # Download to a .part file with a socket timeout, then publish atomically so an
            # interrupted/truncated download can never be picked up as a valid model later.
            _part = _model_dst.with_name(_model_dst.name + '.part')
            try:
                with _ur2.urlopen(_model_url, timeout=60) as _resp, open(_part, 'wb') as _fh:
                    _total = int(_resp.headers.get('Content-Length') or 0)
                    _done = 0
                    while True:
                        _chunk = _resp.read(1 << 20)
                        if not _chunk:
                            break
                        _fh.write(_chunk)
                        _done += len(_chunk)
                        _hook(_done, 1, _total)
                if _total and _part.stat().st_size != _total:
                    raise IOError('truncated download')
                os.replace(_part, _model_dst)
            except BaseException:
                try: _part.unlink()
                except OSError: pass
                raise
            print(f'[CF] Downloaded: {_model_dst.name}')
            # Re-find model and retry
            _wmodel = str(_model_dst)
        except Exception as _mdl_err:
            print(f'[CF] Model download failed: {_mdl_err}')

    # ── 2. faster-whisper with CUDA/CPU ───────────────────────────────────────
    try:
        _FW = _fresh_import('faster_whisper').WhisperModel
        device, compute_type, device_label = _detect_whisper_device(use_gpu=use_gpu)
        print(f'[CF] Whisper device: {device_label}')

        if device == 'directml':
            # faster-whisper doesn't support DirectML — use openai-whisper + torch-directml
            raise RuntimeError('directml: route to openai-whisper+directml')

        # Verify ctranslate2 actually supports CUDA before trying
        if device == 'cuda':
            try:
                import ctranslate2 as _ct2
                _ct2_cuda = 'cuda' in _ct2.get_supported_compute_types('cuda')
                if not _ct2_cuda:
                    if log_cb: log_cb('⚠ CUDA not available — using CPU. Go to Settings → Install NVIDIA CUDA Support.', YELLOW)
                    device, compute_type = 'cpu', 'int8'
            except Exception as _ct2e:
                if log_cb: log_cb(f'⚠ ctranslate2 check failed ({_ct2e}) — using CPU', YELLOW)
                device, compute_type = 'cpu', 'int8'

        fw_model = None
        try:
            fw_model = _FW(
                model_size,
                device=device,
                compute_type=compute_type,
                num_workers=2,
                cpu_threads=0,
                download_root=str(_app_path('whisper_models')),
            )
            print(f'[CF] faster-whisper loaded on {device} ({compute_type})')
            if log_cb: log_cb(f'✅ Transcribing on {device_label}', GREEN)
        except Exception as _cuda_err:
            if device == 'cuda':
                print(f'[CF] CUDA load failed ({_cuda_err}) — falling back to CPU int8')
                if log_cb: log_cb('⚠ CUDA failed to load — falling back to CPU. Re-install CUDA torch in Settings.', YELLOW)
                # Reset device cache so next run re-detects
                global _WHISPER_DEVICE_CACHE
                _WHISPER_DEVICE_CACHE = None
                fw_model = _FW(
                    model_size, device='cpu', compute_type='int8',
                    num_workers=2, cpu_threads=0,
                    download_root=str(_app_path('whisper_models')),
                )
            else:
                raise

        # Get video duration for progress calculation
        try:
            _cv2t = _fresh_import('cv2')
            _cap = _cv2t.VideoCapture(vid)
            _dur = _cap.get(_cv2t.CAP_PROP_FRAME_COUNT) / max(_cap.get(_cv2t.CAP_PROP_FPS) or 30, 1)
            _cap.release()
        except Exception:
            _dur = 0

        # Smart Transcribe: stop at the cutoff parsed from the instructions ("ignore last N hours")
        _smart_cut = None
        try:
            if initial_prompt and log_cb and load_cfg().get('smart_transcribe', False):
                _smart_cut = _smart_cutoff_secs(initial_prompt, _dur)
                if _smart_cut is not None:
                    log_cb(f'⚡ Smart Transcribe: stopping at {int(_smart_cut//60)}:{int(_smart_cut%60):02d} (skipping the end as instructed)', '#88ccff')
        except Exception:
            _smart_cut = None

        segs_iter, info = fw_model.transcribe(
            vid,
            initial_prompt=initial_prompt or '',
            word_timestamps=use_word_timestamps,
            vad_filter=True,
            vad_parameters={
                'min_silence_duration_ms': 400,
                'speech_pad_ms': 200,
                'threshold': 0.6,           # more aggressive silence filtering
            },
            beam_size=5,
            best_of=5,
            temperature=0.0,
            no_speech_threshold=0.6,        # drop segments whisper thinks are silence
            compression_ratio_threshold=2.4, # kill looping/repetition (same as -et)
            log_prob_threshold=-0.7,        # drop low-confidence segments
            condition_on_previous_text=False, # CRITICAL: prevents "Go. Go. Go." repeat loops
        )

        # Consume iterator and report progress
        segments = []
        for seg in segs_iter:
            # Check cancel flag (set by _cancel_task via _do_transcribe._cancelled)
            if getattr(_do_transcribe, '_cancelled', False):
                _do_transcribe._cancelled = False
                return {'segments': segments, 'language': getattr(info, 'language', 'en'), '_cancelled': True}
            if _smart_cut is not None and seg.start >= _smart_cut:
                break  # Smart Transcribe cutoff reached
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
        # Remember a real failure (not "not installed" / the DirectML routing signal) so it can be
        # shown instead of a misleading "install faster-whisper" message if openai-whisper is missing too.
        _fw_failure = None if (isinstance(fw_err, ImportError) or str(fw_err).startswith('directml:')) else str(fw_err)
        if _fw_failure and log_cb:
            log_cb(f'⚠ faster-whisper failed: {_fw_failure}', YELLOW)
        print('[CF] Falling back to openai-whisper...')

    # ── Fallback: openai-whisper, with DirectML if available ────────────────
    try:
        import whisper as _w
    except ImportError:
        if _fw_failure:
            raise RuntimeError(f'Transcription failed: {_fw_failure}') from None
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


# ── Kick.com resolver ─────────────────────────────────────────────────────────
# In 2026 Kick moved public VOD ids to UUIDv7 and a new web API. The legacy
# kick.com/api/v1/video/<uuid> endpoint (still what yt-dlp's extractor calls)
# answers 404 for those ids, so ClipFinder resolves the HLS master playlist
# itself and hands yt-dlp / ffmpeg a plain m3u8 URL. The playlist is public,
# so no login is needed for normal VODs.
_KICK_UUID    = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
_KICK_VOD_RE  = re.compile(r'(?:^|//)(?:www\.)?kick\.com/(?:(?P<slug>[\w\-]+)/videos|video)/(?P<vid>' + _KICK_UUID + ')', re.I)
_KICK_CLIP_RE = re.compile(r'(?:/clips/|[?&]clip=)(?P<clip>clip_[\w\-]+)', re.I)
_KICK_PAGE_RE = re.compile(r'^https?://(?:www\.)?kick\.com/', re.I)   # page URLs only - not the stream./clips. CDN hosts
_KICK_UA      = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                 'Chrome/131.0.0.0 Safari/537.36')


class KickError(Exception):
    """A Kick URL could not be resolved. The message is written for the end user."""


def _kick_get(url, token=None, timeout=20, binary=False):
    """GET a Kick URL -> (http_status, body_text) - or body bytes when binary=True.

    Kick sits behind Cloudflare, so use curl_cffi with Chrome TLS impersonation when it
    is installed (newest target first, older ones for old curl_cffi builds); otherwise
    fall back to plain requests."""
    hdrs = {'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://kick.com/', 'Origin': 'https://kick.com'}
    if token:
        hdrs['Authorization'] = f'Bearer {token}'
    try:
        from curl_cffi import requests as _cr
    except Exception:
        _cr = None
    if _cr is not None:
        for target in ('chrome', 'chrome131', 'chrome124', 'chrome120'):
            try:
                r = _cr.get(url, headers=hdrs, impersonate=target, timeout=timeout)
                return r.status_code, (r.content if binary else r.text)
            except Exception as e:
                msg = str(e).lower()
                if 'impersonat' in msg or 'not supported' in msg or 'unknown' in msg:
                    continue      # this curl_cffi build does not know that target
                break             # network / TLS problem - try plain requests
    import requests as _rq
    r = _rq.get(url, headers={**hdrs, 'User-Agent': _KICK_UA}, timeout=timeout)
    return r.status_code, (r.content if binary else r.text)


def _kick_json(url, token=None, timeout=20):
    """GET + parse JSON -> (status, parsed_or_None)."""
    status, text = _kick_get(url, token, timeout)
    try:
        return status, json.loads(text)
    except Exception:
        return status, None


def _kick_session_token(cookies_path):
    """Kick's session_token (used as a Bearer token) from a Netscape cookies.txt, or None."""
    try:
        if not cookies_path or not Path(cookies_path).exists():
            return None
        import http.cookiejar as _cj, urllib.parse as _up
        jar = _cj.MozillaCookieJar(str(cookies_path))
        jar.load(ignore_discard=True, ignore_expires=True)
        for ck in jar:
            if ck.name == 'session_token' and 'kick.com' in ck.domain:
                return _up.unquote(ck.value)
    except Exception:
        pass
    return None


def _kick_secs(value, ms=False):
    """Kick durations: seconds from the current web API, milliseconds from the legacy API."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return 0
    return int(v / 1000) if ms else int(v)


def _kick_pick_thumb(thumb, min_width=380):
    """Smallest thumbnail in a Kick {src, srcSet} dict that is still >= min_width px wide
    (sharp on a scaled display, but ~30 KB instead of the 130 KB full-size image)."""
    if not isinstance(thumb, dict):
        return thumb or ''
    sset = thumb.get('srcSet') or thumb.get('srcset') or ''
    opts = sorted((int(w), u) for u, w in re.findall(r'(\S+)\s+(\d+)w', sset))
    for w, u in opts:
        if w >= min_width:
            return u
    return opts[-1][1] if opts else (thumb.get('src') or '')


def kick_thumbnail(url, cache_dir=None, size=(192, 108)):
    """Download a VOD / clip thumbnail (Kick, Twitch or YouTube; cached on disk) -> PIL RGB image cropped to `size`, or None."""
    try:
        import hashlib, io
        from PIL import Image, ImageOps
        data = None
        cpath = None
        if cache_dir is not None:
            cpath = Path(cache_dir) / (hashlib.sha1(url.encode('utf-8')).hexdigest()[:24] + '.webp')
            if cpath.exists() and cpath.stat().st_size > 500:
                data = cpath.read_bytes()
        if data is None:
            if re.match(r'https?://[^/]*kick\.com/', url, re.I):
                st, data = _kick_get(url, timeout=15, binary=True)
            else:
                import requests as _rq
                _r = _rq.get(url, timeout=15, headers={'User-Agent': _KICK_UA})
                st, data = _r.status_code, _r.content
            if st != 200 or not data or len(data) < 500:
                return None
            if cpath is not None:
                try:
                    cpath.parent.mkdir(parents=True, exist_ok=True)
                    cpath.write_bytes(data)
                except Exception:
                    pass
        im = Image.open(io.BytesIO(data)).convert('RGB')
        return ImageOps.fit(im, size, Image.LANCZOS)
    except Exception:
        return None


def kick_thumb_badge(im, text, live=False):
    """Draw a small duration (or red LIVE) badge in the bottom-right corner of a thumbnail."""
    try:
        from PIL import ImageDraw, ImageFont
        im = im.copy()
        d = ImageDraw.Draw(im, 'RGBA')
        try:
            font = ImageFont.truetype('segoeuib.ttf', 12)
        except Exception:
            font = ImageFont.load_default()
        text = 'LIVE' if live else text
        l, t, r, b = d.textbbox((0, 0), text, font=font)
        w, h = r - l + 10, b - t + 8
        x1, y1 = im.width - 6, im.height - 6
        d.rounded_rectangle((x1 - w, y1 - h, x1, y1), radius=4,
                            fill=(220, 38, 38, 235) if live else (0, 0, 0, 200))
        d.text((x1 - w + 5 - l, y1 - h + 4 - t), text, font=font, fill=(255, 255, 255, 255))
        return im
    except Exception:
        return im


def _kick_expired(iso):
    """True if an ISO-8601 timestamp such as original_expires_at is already in the past."""
    try:
        import datetime as _dt
        t = _dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        return t < _dt.datetime.now(_dt.timezone.utc)
    except Exception:
        return False


def kick_resolve(url, token=None, log=None):
    """Resolve a kick.com VOD or clip page URL into a direct HLS/MP4 URL.

    Returns {'kind': 'vod'|'clip', 'id', 'stream_url', 'title', 'channel',
    'duration' (seconds), 'is_live', 'expires'}. Raises KickError with an
    actionable message when nothing works. `log(msg, color)` is optional."""
    _log = log or (lambda *_a, **_k: None)
    m = _KICK_CLIP_RE.search(url)
    if m:
        return _kick_resolve_clip(m.group('clip'), token, _log)
    m = _KICK_VOD_RE.search(url)
    if m:
        return _kick_resolve_vod(m.group('slug'), m.group('vid').lower(), url, token, _log)
    raise KickError('That does not look like a Kick VOD or clip link.\n'
                    'Expected https://kick.com/<channel>/videos/<id> or .../clips/clip_<id>.')


def _kick_resolve_clip(clip_id, token, log):
    codes = []
    for ep in (f'https://kick.com/api/v2/clips/{clip_id}/play', f'https://kick.com/api/v2/clips/{clip_id}'):
        try:
            st, d = _kick_json(ep, token)
        except Exception as e:
            codes.append(f'error {str(e)[:50]}')
            continue
        codes.append(str(st))
        clip = d.get('clip') if isinstance(d, dict) and isinstance(d.get('clip'), dict) else (d if isinstance(d, dict) else {})
        stream = clip.get('clip_url') or clip.get('video_url')
        if st == 200 and stream:
            ch = clip.get('channel') or {}
            return {'kind': 'clip', 'id': clip_id, 'stream_url': stream, 'title': clip.get('title'),
                    'channel': ch.get('slug') or ch.get('username'), 'duration': clip.get('duration'),
                    'is_live': False, 'expires': None}
    log(f'Kick clip lookup: HTTP {", ".join(codes)}', YELLOW)
    if '403' in codes:
        raise KickError('Kick blocked the request (HTTP 403 / Cloudflare).\n'
                        'Add a cookies.txt exported from a logged-in kick.com session in the Downloader settings, '
                        'or update curl-cffi via Settings -> Update All Packages.')
    if '404' in codes:
        raise KickError('Kick clip not found - it may have been deleted, or the link is wrong.')
    raise KickError(f'Could not load the Kick clip (HTTP {", ".join(codes)}).')


def _kick_resolve_vod(slug, vid, page_url, token, log):
    notes = []                     # what each attempt returned - shown if everything fails
    hints = {'private': False, 'expired': False}

    def _result(data, stream, ms=False):
        ch  = data.get('channel') or {}
        ls  = data.get('livestream') or {}
        lch = ls.get('channel') or {}
        return {'kind': 'vod', 'id': vid, 'stream_url': stream,
                'title': data.get('title') or data.get('session_title') or ls.get('session_title'),
                'channel': ch.get('slug') or lch.get('slug') or slug,
                'duration': _kick_secs(data.get('duration') or ls.get('duration'), ms),
                'is_live': bool(data.get('is_live') or ls.get('is_live')),
                'expires': data.get('original_expires_at')}

    # 1) Current web API (UUIDv7 ids). Needs the numeric channel id, so look the slug up first.
    chan_id = None
    if slug:
        try:
            st, d = _kick_json(f'https://kick.com/api/v2/channels/{slug}', token)
            notes.append(f'channel lookup HTTP {st}')
            if st == 200 and isinstance(d, dict):
                chan_id = d.get('id')
            elif st == 404:
                raise KickError(f'Kick channel "{slug}" was not found - check the link.')
        except KickError:
            raise
        except Exception as e:
            notes.append(f'channel lookup failed: {str(e)[:60]}')
    if chan_id:
        try:
            st, d = _kick_json(f'https://web.kick.com/api/v1/channels/{chan_id}/videos/{vid}', token)
            notes.append(f'web API HTTP {st}')
            data = d.get('data') if isinstance(d, dict) else None
            if st == 200 and isinstance(data, dict):
                if data.get('recording_url'):
                    return _result(data, data['recording_url'])
                hints['private'] = data.get('status') not in (None, '', 'public')
                hints['expired'] = _kick_expired(data.get('original_expires_at'))
        except Exception as e:
            notes.append(f'web API failed: {str(e)[:60]}')

    # 2) Legacy id (UUIDv4 links, and old kick.com/video/<uuid> links).
    try:
        st, d = _kick_json(f'https://kick.com/api/v1/video/{vid}', token)
        notes.append(f'legacy API HTTP {st}')
        if st == 200 and isinstance(d, dict) and d.get('source'):
            return _result(d, d['source'], ms=True)
    except Exception as e:
        notes.append(f'legacy API failed: {str(e)[:60]}')

    # 3) Last resort: the page itself embeds the recording URL in its payload.
    try:
        st, html = _kick_get(page_url, token, 25)
        notes.append(f'page HTTP {st}')
        if st == 200:
            t = html.replace('\\"', '"').replace('\\/', '/')
            m = re.search(r'"recording_url":"(https?://[^"]+?\.m3u8[^"]*)"', t)
            if m:
                md = re.search(r'<meta name="description" content="([^"]*)"', html)
                return {'kind': 'vod', 'id': vid, 'stream_url': m.group(1),
                        'title': md.group(1) if md else None, 'channel': slug,
                        'duration': 0, 'is_live': False, 'expires': None}
    except Exception as e:
        notes.append(f'page failed: {str(e)[:60]}')

    log('Kick VOD lookup: ' + '; '.join(notes), YELLOW)
    if hints['expired']:
        raise KickError('This Kick VOD has expired - Kick removes VODs after about 30 days.')
    if hints['private']:
        raise KickError('This Kick VOD is not public (subscribers-only or private).\n'
                        'Add a cookies.txt exported from a kick.com account that can watch it.')
    if any('HTTP 403' in n for n in notes):
        raise KickError('Kick blocked the request (HTTP 403 / Cloudflare).\n'
                        'Add a cookies.txt exported from a logged-in kick.com session in the Downloader settings, '
                        'or update curl-cffi via Settings -> Update All Packages.')
    if any('HTTP 404' in n for n in notes) and not any('failed' in n for n in notes):
        raise KickError('Kick VOD not found - it may have been deleted or expired, or the link is wrong.')
    raise KickError('Could not get a stream URL for this Kick VOD (' + '; '.join(notes) + ').')


def kick_list_vods(slug, token=None):
    """A channel's recent VODs, newest first, as dicts for the VOD browser:
    id, url, title, duration (seconds), created (YYYY-MM-DD), views, thumb, is_live."""
    st, d = _kick_json(f'https://kick.com/api/v2/channels/{slug}', token)
    if st == 404:
        raise KickError(f'Kick channel "{slug}" was not found.')
    if st != 200 or not isinstance(d, dict) or not d.get('id'):
        raise KickError(f'Kick channel lookup failed (HTTP {st}).' +
                        ('\nKick blocked the request - add a cookies.txt in Downloader settings.' if st == 403 else ''))
    out = []
    st, dd = _kick_json(f'https://web.kick.com/api/v1/channels/{d["id"]}/videos', token)
    rows = dd.get('data') if st == 200 and isinstance(dd, dict) else None
    for v in (rows if isinstance(rows, list) else []):
        vid = v.get('id')
        if not vid:
            continue
        thumb = _kick_pick_thumb(v.get('thumbnail'))
        out.append({'id': vid, 'url': f'https://kick.com/{slug}/videos/{vid}',
                    'title': v.get('title') or 'Untitled VOD', 'duration': _kick_secs(v.get('duration')),
                    'created': (v.get('start_time') or '')[:10], 'views': int(v.get('viewer_count') or 0),
                    'thumb': thumb, 'is_live': bool(v.get('is_live'))})
    if not out:        # legacy list: UUIDv4 ids, millisecond durations
        st, ld = _kick_json(f'https://kick.com/api/v2/channels/{slug}/videos', token)
        for v in (ld if isinstance(ld, list) else []):
            vid = (v.get('video') or {}).get('uuid')
            if not vid:
                continue
            thumb = _kick_pick_thumb(v.get('thumbnail'))
            out.append({'id': vid, 'url': f'https://kick.com/{slug}/videos/{vid}',
                        'title': v.get('session_title') or 'Untitled VOD',
                        'duration': _kick_secs(v.get('duration'), ms=True),
                        'created': (v.get('start_time') or v.get('created_at') or '')[:10],
                        'views': int(v.get('views') or 0), 'thumb': thumb, 'is_live': bool(v.get('is_live'))})
    return out


def kick_list_clips(slug, token=None, limit=40):
    """A channel's clips (newest first) in the same dict shape as kick_list_vods."""
    st, d = _kick_json(f'https://kick.com/api/v2/channels/{slug}/clips?cursor=0&sort=date&time=all', token)
    if st == 404:
        raise KickError(f'Kick channel "{slug}" was not found.')
    if st != 200 or not isinstance(d, dict):
        raise KickError(f'Kick clip list failed (HTTP {st}).' +
                        ('\nKick blocked the request - add a cookies.txt in Downloader settings.' if st == 403 else ''))
    out = []
    for c in (d.get('clips') or []):
        cid = c.get('id')
        if not cid:
            continue
        out.append({'id': cid, 'url': f'https://kick.com/{slug}/clips/{cid}',
                    'title': c.get('title') or 'Untitled clip', 'duration': _kick_secs(c.get('duration')),
                    'created': (c.get('created_at') or '')[:10], 'views': int(c.get('views') or c.get('view_count') or 0),
                    'thumb': c.get('thumbnail_url') or '', 'is_live': False})
        if len(out) >= limit:
            break
    return out


class BrowseError(Exception):
    """A channel browser lookup failed. The message is written for the end user."""


_TWITCH_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'     # Twitch's own public web client id


def twitch_list(login, kind='vods', limit=40):
    """A Twitch channel's past broadcasts ('vods') or clips ('clips') -> (items, note).
    Uses Twitch's public GraphQL endpoint (no login needed, same data the website shows)."""
    import requests as _rq
    login = re.sub(r'[^\w]', '', login or '').lower()
    if not login:
        raise BrowseError('Type a Twitch channel name first.')
    if kind == 'clips':
        # newest interesting clips first: try the last week, widen until something is found
        periods = ('LAST_WEEK', 'LAST_MONTH', 'ALL_TIME')
        sel = ('clips(first:%d, criteria:{period:$p, sort:VIEWS_DESC}){edges{node{slug title durationSeconds createdAt '
               'viewCount thumbnailURL(width:480,height:272) broadcaster{login}}}}' % limit)
    else:
        periods = ('ALL_TIME',)
        sel = ('videos(first:%d, type:ARCHIVE, sort:TIME){edges{node{id title lengthSeconds createdAt viewCount '
               'previewThumbnailURL(width:480,height:272)}}}' % limit)
    q = 'query($login:String!,$p:ClipsPeriod){user(login:$login){login ' + sel + '}}'
    if kind != 'clips':
        q = q.replace(',$p:ClipsPeriod', '')
    hdrs = {'Client-ID': _TWITCH_CLIENT_ID, 'Content-Type': 'application/json'}
    note = ''
    for per in periods:
        var = {'login': login}
        if kind == 'clips':
            var['p'] = per
        r = _rq.post('https://gql.twitch.tv/gql', headers=hdrs, json={'query': q, 'variables': var}, timeout=20)
        if r.status_code != 200:
            raise BrowseError(f'Twitch lookup failed (HTTP {r.status_code}).')
        j = r.json()
        if isinstance(j, dict) and j.get('errors') and not j.get('data'):
            raise BrowseError('Twitch lookup failed: ' + str(j['errors'][0].get('message', ''))[:120])
        user = ((j or {}).get('data') or {}).get('user')
        if not user:
            raise BrowseError(f'Twitch channel "{login}" was not found.')
        edges = ((user.get('clips') if kind == 'clips' else user.get('videos')) or {}).get('edges') or []
        out = []
        for e in edges:
            n = (e or {}).get('node') or {}
            if kind == 'clips':
                slug = n.get('slug')
                if not slug:
                    continue
                who = (n.get('broadcaster') or {}).get('login') or login
                out.append({'id': slug, 'url': f'https://www.twitch.tv/{who}/clip/{slug}', 'title': n.get('title') or 'Untitled clip',
                            'duration': int(n.get('durationSeconds') or 0), 'created': (n.get('createdAt') or '')[:10],
                            'views': int(n.get('viewCount') or 0), 'thumb': n.get('thumbnailURL') or '', 'is_live': False})
            else:
                vid = n.get('id')
                if not vid:
                    continue
                th = n.get('previewThumbnailURL') or ''
                out.append({'id': vid, 'url': f'https://www.twitch.tv/videos/{vid}', 'title': n.get('title') or 'Untitled broadcast',
                            'duration': int(n.get('lengthSeconds') or 0), 'created': (n.get('createdAt') or '')[:10],
                            'views': int(n.get('viewCount') or 0), 'thumb': '' if '404_processing' in th else th,
                            'is_live': False})
        if out:
            if kind == 'clips':
                note = {'LAST_WEEK': 'top clips of the last 7 days', 'LAST_MONTH': 'top clips of the last 30 days',
                        'ALL_TIME': 'top clips of all time'}[per]
            return out, note
    return [], ''


def youtube_list(channel, section='videos', limit=40):
    """A YouTube channel tab ('streams' / 'videos' / 'shorts') -> (items, note) via yt-dlp's flat extractor."""
    import yt_dlp
    ch = (channel or '').strip()
    if not ch:
        raise BrowseError('Type a YouTube @handle or channel link first.')
    m = re.match(r'https?://(?:www\.|m\.)?youtube\.com/((?:@|channel/|c/|user/)[^/?#]+)', ch, re.I)
    if m:
        base = 'https://www.youtube.com/' + m.group(1)
    elif re.match(r'^UC[\w-]{20,}$', ch):
        base = 'https://www.youtube.com/channel/' + ch
    else:
        base = 'https://www.youtube.com/@' + ch.lstrip('@').replace(' ', '')
    opts = {'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist', 'playlistend': limit,
            'skip_download': True, 'socket_timeout': 20}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(f'{base}/{section}', download=False)
    except Exception as e:
        msg = str(e)
        if 'does not have a' in msg and 'tab' in msg:
            return [], f'This channel has no {section.title()} tab.'
        if 'does not exist' in msg.lower() or '404' in msg or 'not found' in msg.lower():
            raise BrowseError(f'YouTube channel "{ch}" was not found.')
        raise BrowseError('YouTube lookup failed: ' + re.sub(r'\x1b\[[0-9;]*m', '', msg).replace('ERROR: ', '')[:160])
    out = []
    for e in (info or {}).get('entries') or []:
        vid = (e or {}).get('id')
        if not vid:
            continue
        if not re.match(r'^[\w-]{11}$', str(vid)):      # nested playlists / shelves are not videos
            continue
        ls = e.get('live_status')
        out.append({'id': vid,
                    'url': e.get('url') or (f'https://www.youtube.com/shorts/{vid}' if section == 'shorts' else f'https://www.youtube.com/watch?v={vid}'),
                    'title': e.get('title') or 'Untitled', 'duration': int(e.get('duration') or 0),
                    'created': (str(e.get('upload_date') or '')[:4] + '-' + str(e.get('upload_date') or '')[4:6] + '-' + str(e.get('upload_date') or '')[6:8]) if e.get('upload_date') else '',
                    'views': int(e.get('view_count') or 0), 'thumb': f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg',
                    'is_live': ls == 'is_live'})
        if len(out) >= limit:
            break
    return out, ''


BROWSE_PLATFORMS = (('kick', '🎮 Kick', 'Kick username', 'nicklee'),
                    ('twitch', '🟣 Twitch', 'Twitch channel', 'xqc'),
                    ('youtube', '▶ YouTube', 'YouTube @handle or link', '@MrBeast'))
BROWSE_SECTIONS = {'kick':    (('vods', '📼 VODs'), ('clips', '✂ Clips')),
                   'twitch':  (('vods', '📼 VODs'), ('clips', '✂ Clips')),
                   'youtube': (('streams', '🔴 Streams'), ('videos', '🎞 Videos'), ('shorts', '📱 Shorts'))}


def browse_normalize(platform, text):
    """Channel name from what the user typed (accepts a pasted channel link)."""
    t = (text or '').strip()
    if platform == 'youtube':
        return t
    m = re.match(r'(?:https?://)?(?:www\.)?(?:kick\.com|twitch\.tv)/([\w\-]+)', t, re.I)
    if m:
        t = m.group(1)
    return t.lstrip('@').strip().lower()


def browse_list(platform, channel, section, token=None):
    """Dispatch to the platform backend -> (items, note). Raises KickError / BrowseError with user-facing text."""
    if platform == 'kick':
        if not channel:
            raise BrowseError('Type a Kick username first.')
        return (kick_list_clips(channel, token) if section == 'clips' else kick_list_vods(channel, token)), ''
    if platform == 'twitch':
        return twitch_list(channel, 'clips' if section == 'clips' else 'vods')
    return youtube_list(channel, section)


# ══════════════════════════════════════════════════════════════════════════════
# POST STUDIO v2 - engine (pure functions, no GUI): prompt, parsing, hard-rule enforcement, checks
# ══════════════════════════════════════════════════════════════════════════════
# begin-post-studio-engine
PS_MASTER_PROMPT = """SOCIAL MEDIA CLIP / STREAMER NEWS CAPTION MASTER PROMPT
You are helping me run social-media clip/news accounts focused on streamers, influencers, internet personalities, Kick/Twitch/YouTube creators, viral moments, boxing, IRL streams, reality-style creator events, and online drama.
Your job is to take the transcript, description, or rough idea I give you and turn it into high-CTR platform-specific captions that sound like modern 2026 social media posts.
Do NOT write like a journalist or news article unless I specifically ask you to.

1. MY GENERAL STYLE
I want captions that are: Short. Punchy. Modern. Funny when appropriate. Curiosity-driven. High CTR. Easy to understand immediately. Focused on the most interesting moment. Written like something that would actually perform on social media.
Think: "Nobody expected this..." / "[Person] just did something unexpected 👀" / "BRO REALLY…" / "THIS GOT WEIRD 😭💀" / "DANA WHITE JUST…"
Do NOT make every caption sound exactly like those examples. Create fresh hooks.
The caption should make someone want to watch the clip rather than explain every detail.
Avoid turning the caption into a complete transcript or article.

2. ALWAYS FIND THE BEST ANGLE
When I give you a transcript, don't simply summarize it. First identify the strongest angle: funniest moment, most surprising statement, most controversial statement, biggest reaction, most absurd moment, unexpected interaction, viral quote, conflict/drama, embarrassing moment, unexpected reveal, person getting roasted, person admitting something, person reacting to something, wild claim, unexpected punchline.
Then build the caption around THAT.
If the transcript has multiple possible angles, choose the one with the strongest social-media hook unless I specifically tell you which angle to use.
If I say something like "Use the tortilla part" or "Make it about Dana calling the rumors bullshit", then follow that exact angle.

3. DO NOT OVEREXPLAIN
Bad: "During a recent conversation, NinaDrama spoke with Dana White about various topics including social media, upcoming fights, and the spread of misinformation online..."
Good: "DANA WHITE SAYS 99.9% OF FIGHT NEWS IS BULLSHIT 😭💀"
Then explain just enough to make the clip understandable.

4. PLATFORM OUTPUT
Unless I specifically request only one platform, give me: 1. TikTok 2. Instagram 3. YouTube Shorts 4. X.
Each should be individually written for that platform. Do NOT simply copy the same caption four times. The wording should be meaningfully different while keeping the same core story.

5. TIKTOK
Always include an ON-SCREEN HOOK, then the caption. The TikTok hook should be extremely short and attention-grabbing. Examples of style: DANA WHITE SAYS 99.9% OF FIGHT NEWS IS BULLSHIT 😭 / TREY IS ALREADY LEAVING 😭💀 / THIS GOT WEIRD FAST 😭💀 / BRO ACTUALLY DID IT 😭
The caption itself should be concise. Use relevant hashtags, usually around 2-5. Don't hashtag-stuff.

6. INSTAGRAM
Always include an ON-SCREEN HOOK, then the Instagram caption. The IG hook should be different from TikTok's hook when possible. Instagram captions can be slightly more conversational. Use a few relevant hashtags. Usually 2-5 is enough.

7. YOUTUBE SHORTS
Always include an ON-SCREEN HOOK, then a Title, then a Description. The YouTube title needs to be clickable and concise.
IMPORTANT: The YouTube Shorts title should include a relevant hashtag in the title itself. Example: Dana White Says 99.9% of UFC Rumors Are Bullshit 😭 #UFC
The description should give enough context for the viewer to understand the clip without becoming an article. Use relevant hashtags in the description too.

8. X / TWITTER
X is different. Do NOT include an ON-SCREEN HOOK. Write the actual post.
IMPORTANT: NEVER use hashtags on X. Do not put hashtags at the end.
Also: NEVER use an em dash (—) in X captions. Use commas, periods, ellipses, parentheses, or separate sentences instead.
X captions should feel native to X. They can be slightly more conversational and provocative.
Example: Dana White says 99.9% of the fight stuff posted on social media is absolute bullshit 😭💀 "If the UFC didn't announce it and Dana didn't announce it, why are you pulling this shit out of your ass?"
Do not automatically quote the transcript. Only use a quote when it is the strongest part.

9. WRITING STYLE
Use natural internet language. Words like bro, literally, actually, really, somehow, meanwhile, apparently, just, already, ended up, got caught, gets exposed, goes off, loses it, folds, drops, wild, insane can be used when they fit. Do not force slang into every caption.

10. EMOJIS
Use emojis sparingly. Common ones: 😭 💀 😂 👀 😳 🚨 🥊 🤯. Usually 1-3 emojis is enough. Don't put an emoji after every sentence. Don't make captions look like spam.

11. CAPS
Use capitalization strategically for emphasis. Examples: 99.9% OF IT IS BULLSHIT / NIBBLES HER / BACK IN THE CLOSET / KEPT HIS WORD. Don't capitalize the entire caption unless I specifically ask for it.

12. FACTUAL ACCURACY
This is extremely important. Do not turn something merely alleged, disputed, or claimed into an established fact.
If something is unverified, use language such as: allegedly, reportedly, claims, according to the clip, according to [person], amid accusations, after the controversy, following the incident.
Do not invent details. Do not invent names. Do not invent motives. Do not invent what happened off-camera.
If I give you a transcript, stay grounded in the transcript.
If I correct a detail, the correction overrides your previous wording.

13. WHEN SOMETHING IS DISPUTED
If two people disagree about what happened, don't present one person's version as objective fact.
Instead of: "GreatWhiteMike falsely called the cops..."
Use: "Nick Lee confronts GreatWhiteMike over calling the cops, while Mike insists he was actually jumped."
This is especially important for drama/controversy captions.

14. VIOLENCE
Violent moments can be described if they are relevant to the clip, but don't make them unnecessarily graphic. Words like gets dropped, gets knocked out, gets punched, gets tackled, gets into a scuffle, gets chased, gets confronted are generally preferable to graphic descriptions.
If the violence was consensual/staged/part of an event, make that clear. Example: "He consented to the punch... then immediately got DROPPED 💀"
Do not imply an unprovoked assault if the context says the person consented.

15. SEXUAL / SENSITIVE CONTEXT
Keep captions non-explicit unless the context genuinely requires more detail.
If a person was involved in controversial comments about minors, do NOT call the person a "pedophile" as an established fact unless there is an authoritative factual basis. Instead use: "controversial comments about minors", "comments involving minors", "amid accusations involving comments about minors", "after a disturbing song involving children".
Do not reproduce disturbing sexual lyrics involving minors. Focus on the event rather than repeating the content.

16. IMPORTANT SEEEX RULE
Always mention SeeEx when the clip is from Nick Lee's SeeEx event until I explicitly tell you "You don't need to mention SeeEx anymore." This applies naturally to TikTok captions, Instagram captions, YouTube titles/descriptions, and X posts.
Use SeeEx, not random variations like "See Ex." Use #SeeEx on TikTok/Instagram/YouTube when appropriate. DO NOT use #SeeEx on X because X captions should not have hashtags.
If I explicitly say "This isn't SeeEx" then DO NOT mention SeeEx.

17. SEEEX CONTEXT
SeeEx is Nick Lee's event involving streamers/creators and reality-show-style dynamics. Relevant people that may appear include: Nick Lee, Nick White, Ice Poseidon, DariusIRL, XenaTheWitch, TreyLivings, Glink, NerdBallerTV, M1keDanger, GreatWhiteMike, Chicken Andy, Burt Bronx, FishTank-related participants.
Do not automatically include every relevant person. Only mention people who are actually relevant to the clip.

18. SEEEX EXAMPLES / CORRECTIONS
DariusIRL / XenaTheWitch / TreyLivings / Glink: A previous clip involved DariusIRL and XenaTheWitch screaming while TreyLivings got into a scuffle. Meanwhile Glink was badly playing Pink Floyd on guitar. The desired angle was: TWO COMPLETELY DIFFERENT MOODS AT SEEEX 😭💀. The important joke was that Glink was badly playing Pink Floyd while chaos was happening. Don't remove the "badly" if I'm asking for that joke.
TreyLivings: Trey has a recurring joke about always leaving. If a clip involves Trey leaving, phrases like "Classic Trey 😭💀" can work.
Chicken Andy / XenaTheWitch: There was a SeeEx clip where Chicken Andy was challenged to prove he wasn't racist and was told to kiss a Black girl. IMPORTANT CORRECTION: He did NOT kiss XenaTheWitch. He NIBBLED HER. If revisiting that clip, say NIBBLES HER, not "kisses her." Do not add Darius to that clip.
M1keDanger / NerdBallerTV: They had a first-ever boxing match at SeeEx. There was girlfriend drama surrounding the fight. IMPORTANT: If mentioning the girlfriend cheating claim, treat it as alleged/unverified. The user likes the joke: "NerdBallerTV at least kept his word and showed up to fight him." Do not present the girlfriend allegation as independently verified fact.
Glink / closet: A previous clip involved people opening a closet and discovering Glink sleeping inside after his ex-girlfriend rage quit. The joke was: GLINK IS BACK IN THE CLOSET 😭💀. The wording should clearly refer to the literal closet situation and not imply anything beyond the joke.
Ice Poseidon / whale tiger: There was a comedic SeeEx clip involving Ice Poseidon and someone dressed as a whale/tiger. The desired phrase was: ICE POSEIDON GOT ASSAULTED BY A WHALE TIGER 😭💀. The context was that Ice tried to get her eliminated and then got chased around. Keep the comedic/event context clear.
GreatWhiteMike: GreatWhiteMike was kicked out of SeeEx after an argument involving the police being called. Nick Lee disputed Mike's version of events. Mike insisted he had been jumped. Nick questioned why police were called and argued the situation was being treated as content. IMPORTANT: Do not say Mike "faked" being attacked unless there is actual evidence. Frame it as a dispute.
Burt Bronx: Burt Bronx was permanently banned from Kick amid controversy involving disturbing comments/song content about minors. IMPORTANT: Do NOT call him a pedophile as an established fact. Use "permanently banned" when that is the documented event. Use "disturbing song involving children" or "controversial comments about minors" rather than reproducing the lyrics.
Burt Bronx / SeeEx / gimp suit: IMPORTANT CORRECTION: Burt was NOT wearing a gimp suit when he was eliminated. He was eliminated earlier because of the inappropriate/disturbing song involving children. He later returned to SeeEx wearing a gimp suit. He asked to be punished for his words. He gave consent to the punch. Someone from FishTank then punched/dropped him. Therefore, if writing this clip: Correct: "Burt Bronx had already been eliminated from SeeEx after a disturbing song involving children. He later returned in a gimp suit and asked to be punished..." Incorrect: "Burt was eliminated while wearing a gimp suit." The gimp suit happened later. Also don't imply the punch was an unprovoked assault because Burt consented to it.

19. CURRENT EXAMPLE: IDUNCLE TALKING ABOUT SEEEX
If I give you a transcript where Iduncle discusses whether Nick Lee and Ice Poseidon "fumbled" SeeEx: The important nuance is: he thinks the original concept was a fumble; the event itself is not necessarily a flop; it is wild; a lot is happening; it keeps attention; people are still watching; but it isn't really about exes anymore; it has become much more chaotic/degenerate than the original concept. Don't turn his opinion into an objective statement. Good angle: IDUNCLE THINKS SEEEX IS A FUMBLE... BUT NOT A FLOP 😭 Then explain that his criticism is about the event drifting away from the original exes concept.

20. DANA WHITE / UFC EXAMPLE
If I give you a clip of NinaDrama talking to Dana White about UFC rumors: A strong angle is Dana saying that 99.9% of fight information on social media is bullshit. The context: Elias reportedly said he wants to fight again; Elias and Justin were going back and forth; Dana hasn't seen some of the social-media posts; Dana says he stays away from fight-related social media because much of it is bullshit; NinaDrama points out that pages constantly post "this fight is happening"; Dana questions why people announce fights when the UFC/Dana haven't announced them. Strong hook: DANA WHITE SAYS 99.9% OF FIGHT NEWS IS BULLSHIT 😭 Do not make the clip about the unrelated tortilla conversation unless I specifically ask for that angle.

21. IF I GIVE YOU A ROUGH DESCRIPTION
Sometimes I won't provide a full transcript. I may say something like "Mizkif reacts to..." or "Ice gets chased by..." or "Dana talks about fake UFC rumors." Use the information I give you and create the captions. Do not ask unnecessary clarification questions if the basic story is clear.

22. IF I ASK TO "TRY AGAIN"
Do NOT simply change two words. Make the hook and framing genuinely different. For example: Version 1: "DANA WHITE SAYS 99.9% OF FIGHT NEWS IS BULLSHIT 😭" Version 2: "DANA WHITE IS DONE WITH UFC RUMOR PAGES 💀" Version 3: "DANA WHITE HAS ONE QUESTION FOR UFC RUMOR ACCOUNTS 😭" These are actually different angles.

23. IF I SAY "MAKE IT FUNNIER"
Keep the factual setup but add the joke/punchline. Usually the funniest line should come toward the end. Example: "Meanwhile Glink is standing there badly playing Pink Floyd like nothing is happening 😂" or "Bro really tried to eliminate her and became the one getting chased 😭💀". Don't turn the entire caption into a joke if the actual event needs context.

24. IF I SAY "SHORTEN IT"
Actually shorten it. Remove unnecessary setup. Keep: 1. Who 2. What happened 3. The hook/punchline. Don't just remove one sentence.

25. IF I SAY "MAKE IT MORE VIRAL"
Increase curiosity and punchiness without inventing information. Use: stronger opening, more surprising framing, shorter sentences, better punchline, more direct wording, one strong emoji moment. Do not use fake claims simply to make it more viral.

26. IF I GIVE YOU A QUOTE
If there is a particularly strong quote, you can build the caption around it. Example: "If the UFC didn't announce it and Dana didn't announce it, why are you pulling this shit out of your ass?" That can be the centerpiece. But don't overquote the transcript. Use only the strongest part.

27. TAGGING / CREATOR-SPECIFIC RULES
Aishah Sofey: X must include "Aishah Sofey" (do not rely only on the @handle). TikTok: tag @aishah and include #aishahsofey. Instagram: tag @aishahsofey in the caption and include #aishahsofey. YouTube Shorts: tag @hiaishahsofey.
Adrianah Lee: correct spelling is "Adrianah Lee", NOT "Adriana Lee".
Rellik: correct spelling is "Rellik The Clown". Do not change the spelling.

28. DO NOT RANDOMLY ADD PEOPLE
If the clip is about Chicken Andy and XenaTheWitch, don't add Darius because he's associated with other SeeEx clips. If the clip is about Dana White and NinaDrama, don't mention Nick Lee or SeeEx. Only use people who belong in the specific clip.

29. DO NOT MIX CLIPS
I may send several clips in the same conversation. Treat each new clip as its own piece of content unless I explicitly say they are connected. Don't accidentally carry details from the previous clip into the next one.

30. WHEN I SAY "THIS ISN'T SEEEX"
Immediately stop using SeeEx in that clip. Do not force SeeEx into captions just because previous clips were from SeeEx.

31. HASHTAG RULES
TikTok / Instagram / YouTube: use only relevant hashtags, e.g. #SeeEx #IcePoseidon #NickLee or #DanaWhite #NinaDrama #UFC. X: NO HASHTAGS. EVER unless I specifically ask for them. Do not use random generic hashtags like #Viral #FYP #Trending unless I specifically ask for them.

32. WRITING FORMAT
For each platform, structure the response clearly. The actual finished platform copy should be clean and ready to paste.

33. MOST IMPORTANT RULE
When I give you a transcript, don't overthink it. Find the one moment people would stop scrolling for and build around it. The goal is not: "What happened in this conversation?" The goal is: "What part of this conversation would make someone stop scrolling and watch?" Then write the caption around that moment.
If I give you a specific angle, that overrides your choice. If I correct something, the correction overrides everything previously written. If I say "make it different," actually rewrite it. If I say "make it funnier," add a real punchline. If I say "shorter," make it shorter. If I say "this isn't SeeEx," remove SeeEx. If I say "always mention SeeEx," mention SeeEx naturally until I tell you otherwise.
"""

PS_PLATFORMS = [   # key, label, colour, fields
    ('tiktok',    '🎵 TikTok',       '#69c9d0', ('hook', 'caption')),
    ('instagram', '📸 Instagram',    '#e1306c', ('hook', 'caption')),
    ('youtube',   '▶ YouTube Shorts', '#ff4444', ('hook', 'title', 'description')),
    ('x',         '𝕏 X / Twitter',   '#1d9bf0', ('post',)),
]
PS_FIELD_LABEL = {'hook': 'ON-SCREEN HOOK', 'caption': 'CAPTION', 'title': 'TITLE', 'description': 'DESCRIPTION', 'post': 'POST'}
PS_SECTION_NAME = {'tiktok': 'TIKTOK', 'instagram': 'INSTAGRAM', 'youtube': 'YOUTUBE SHORTS', 'x': 'X'}

PS_TASKS = {
    'new':     '',
    'retry':   'TRY AGAIN (rule 22): the previous version is shown below. Do NOT just change two words. Make the hook and the framing genuinely different (a different angle unless the user forced one).',
    'funnier': 'MAKE IT FUNNIER (rule 23): keep the factual setup of the previous version below but add a real joke/punchline, usually near the end. Do not turn the whole caption into a joke if the event needs context.',
    'shorter': 'SHORTEN IT (rule 24): actually shorten the previous version below. Remove unnecessary setup. Keep only who, what happened, and the hook/punchline.',
    'viral':   'MAKE IT MORE VIRAL (rule 25): stronger opening, more surprising framing, shorter sentences, a better punchline, one strong emoji moment. Do NOT invent claims to do it.',
    'fix':     'APPLY THE USER CORRECTION below (rule 33: the correction overrides everything previously written). Keep everything else about the previous version unless the correction requires changing it.',
}

PS_OUTPUT_CONTRACT = """
OUTPUT FORMAT (this is machine-parsed - follow it EXACTLY, no markdown, no bold, no commentary before or after):
### ANGLE
<one short line: the angle you built the captions around>
### TIKTOK
ON-SCREEN HOOK: <text>
CAPTION: <text (may span several lines)>
### INSTAGRAM
ON-SCREEN HOOK: <text>
CAPTION: <text (may span several lines)>
### YOUTUBE SHORTS
ON-SCREEN HOOK: <text>
TITLE: <title that already contains one relevant hashtag>
DESCRIPTION: <text (may span several lines)>
### X
POST: <text, no hashtags, no em dash>
Write ONLY the platform sections listed under PLATFORMS REQUESTED (always keep the ### ANGLE section). The captions are final, paste-ready copy."""

_PS_SEEEX_MODES = {
    'auto':   'SEEEX MODE: AUTO. Mention SeeEx (rule 16) ONLY if the transcript/description shows the clip is from Nick Lee\'s SeeEx event. If it is clearly not, do not mention it (rule 28/30).',
    'always': 'SEEEX MODE: ALWAYS. The user says this clip is from Nick Lee\'s SeeEx event: mention SeeEx naturally in every platform (rule 16), and use #SeeEx on TikTok/Instagram/YouTube but never on X.',
    'never':  'SEEEX MODE: NEVER. The user says "This isn\'t SeeEx": do NOT mention SeeEx anywhere (rule 30).',
}

_PS_TAG = r'(?<![\w&])#[A-Za-z_]\w*'      # a hashtag (not '#1' or an HTML entity)
_PS_BANNED_TAGS = {'viral', 'fyp', 'foryou', 'foryoupage', 'trending', 'explorepage', 'viralvideo', 'fypage', 'fy', 'foryourpage'}
_PS_EMOJI_RE = None


def ps_clean_transcript(text, limit=12000):
    """Strip [HH:MM:SS] stamps and collapse whitespace; keep the start of very long transcripts."""
    t = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:->|→|-)\s*\d{1,2}:\d{2}(?::\d{2})?)?\]\s*', '', text or '')
    t = re.sub(r'[ \t]+', ' ', t).strip()
    return t[:limit]


def ps_build_prompt(transcript, platforms, angle='', people='', handles=None, seex='auto', notes='',
                    task='new', previous=None, correction='', transcript_limit=12000):
    """-> (system_text, user_text). `previous` is the prior result dict of the SAME clip (for iterations)."""
    plat_names = [PS_SECTION_NAME[k] for k, *_ in PS_PLATFORMS if k in platforms]
    sysm = PS_MASTER_PROMPT + '\n' + PS_OUTPUT_CONTRACT
    parts = ['CLIP TRANSCRIPT / DESCRIPTION (stay grounded in this, do not invent anything):',
             ps_clean_transcript(transcript, transcript_limit) or '(none - work only from the notes below)', '']
    if people.strip():
        parts.append(f'PEOPLE IN THIS CLIP: {people.strip()}   (only these belong in the captions)')
    if angle.strip():
        parts.append(f'ANGLE OVERRIDE (rule 2: follow this angle exactly): {angle.strip()}')
    parts.append(_PS_SEEEX_MODES.get(seex, _PS_SEEEX_MODES['auto']))
    hs = {k: v for k, v in (handles or {}).items() if v}
    if hs:
        parts.append('CREATOR HANDLES (use them per rule 27 where relevant): ' + '; '.join(f'{k}: {v}' for k, v in hs.items()))
    if notes.strip():
        parts.append('STANDING RULES FROM THE USER (always apply):\n' + notes.strip())
    if correction.strip():
        parts.append('USER CORRECTION / INSTRUCTION (overrides everything, rule 33): ' + correction.strip())
    if task in PS_TASKS and PS_TASKS[task]:
        parts.append('')
        parts.append(PS_TASKS[task])
        if previous:
            parts.append('PREVIOUS VERSION OF THIS SAME CLIP:\n' + ps_format_result(previous, only=platforms))
    parts.append('')
    parts.append('PLATFORMS REQUESTED: ' + ', '.join(plat_names))
    return sysm, '\n'.join(parts)


def ps_format_result(res, only=None):
    """Render a result dict back into the output-contract text (used for iterations and export)."""
    out = []
    if res.get('angle'):
        out.append('### ANGLE\n' + res['angle'])
    for key, _lbl, _c, fields in PS_PLATFORMS:
        if key not in res or (only and key not in only):
            continue
        out.append('### ' + PS_SECTION_NAME[key])
        for f in fields:
            if res[key].get(f):
                out.append(f'{PS_FIELD_LABEL[f]}: {res[key][f]}')
    return '\n'.join(out)


def ps_parse(text):
    """Parse the model's reply into {'angle': str, 'tiktok': {...}, ...}. Tolerates markdown noise."""
    t = (text or '').replace('\r\n', '\n')
    t = re.sub(r'^\s*```[a-zA-Z]*\s*$', '', t, flags=re.M)              # code fences
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)                              # **bold**
    heads = list(re.finditer(r'^[ \t]*(?:#{1,4}[ \t]*|={2,}[ \t]*)?(ANGLE|TIKTOK|TIK TOK|INSTAGRAM|YOUTUBE SHORTS?|YOUTUBE|X(?:\s*/\s*TWITTER)?|TWITTER)[ \t]*(?:={2,})?[ \t]*:?[ \t]*$',
                              t, flags=re.M | re.I))
    res = {}
    for i, m in enumerate(heads):
        name = m.group(1).upper().replace(' ', '')
        body = t[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(t)].strip()
        if name == 'ANGLE':
            res['angle'] = body.splitlines()[0].strip() if body else ''
            continue
        key = {'TIKTOK': 'tiktok', 'INSTAGRAM': 'instagram', 'YOUTUBESHORT': 'youtube', 'YOUTUBESHORTS': 'youtube',
               'YOUTUBE': 'youtube', 'X': 'x', 'X/TWITTER': 'x', 'TWITTER': 'x'}.get(name)
        if not key:
            continue
        labels = 'ON[- ]?SCREEN HOOK|HOOK|CAPTION|TITLE|DESCRIPTION|POST|TWEET'
        fields = {}
        fm = list(re.finditer(rf'^[ \t]*({labels})[ \t]*:[ \t]*', body, flags=re.M | re.I))
        for j, f in enumerate(fm):
            val = body[f.end(): fm[j + 1].start() if j + 1 < len(fm) else len(body)].strip()
            lab = f.group(1).upper().replace('-', '').replace(' ', '')
            fld = {'ONSCREENHOOK': 'hook', 'HOOK': 'hook', 'CAPTION': 'caption', 'TITLE': 'title',
                   'DESCRIPTION': 'description', 'POST': 'post', 'TWEET': 'post'}[lab]
            fields[fld] = val.strip().strip('"').strip() if fld in ('hook', 'title') else val
        if key == 'x' and not fields.get('post') and body and not fm:
            fields['post'] = body                                          # X reply without a label
        if fields:
            res[key] = fields
    return res


def _ps_count_emoji(s):
    return len(re.findall('[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF⭐⬆✅]', s or ''))


def ps_enforce(res, platforms=None, seex='auto', people='', transcript=''):
    """Apply the HARD rules automatically and collect notes.
    -> (fixed result dict, fixes [what was changed], warnings [things a human should look at])."""
    import copy
    r = copy.deepcopy(res)
    fixes, warns = [], []

    def fix(cond, msg):
        if cond:
            fixes.append(msg)

    # ---- X: no hashtags, no em dash, no on-screen hook
    if 'x' in r:
        p = r['x'].get('post', '')
        n_tags = len(re.findall(_PS_TAG, p))
        p2 = re.sub(r'\s*' + _PS_TAG, '', p)
        fix(n_tags, f'X: removed {n_tags} hashtag{"s" if n_tags != 1 else ""} (rule 8/31)')
        n_dash = p2.count('—') + p2.count('―')
        p2 = re.sub(r'\s*[—―]\s*', ', ', p2)
        fix(n_dash, f'X: replaced {n_dash} em dash{"es" if n_dash != 1 else ""} with commas (rule 8)')
        p2 = re.sub(r',\s*,', ',', p2)
        p2 = re.sub(r'[ \t]+\n', '\n', p2).strip()
        r['x'] = {'post': p2}
        if len(p2) > 280:
            warns.append(f'X post is {len(p2)} characters (limit 280 unless you have Premium)')
    # ---- generic hashtags on the others + count
    for k in ('tiktok', 'instagram'):
        if k not in r:
            continue
        cap = r[k].get('caption', '')
        tags = re.findall(_PS_TAG, cap)
        bad = [t for t in tags if t[1:].lower() in _PS_BANNED_TAGS]
        if bad:
            for t in bad:
                cap = re.sub(r'\s*' + re.escape(t) + r'\b', '', cap)
            fixes.append(f'{k.title()}: removed generic hashtag{"s" if len(bad) > 1 else ""} {" ".join(bad)} (rule 31)')
        tags = re.findall(_PS_TAG, cap)
        if len(tags) > 5:
            n_seen = [0]
            def _limit(m):
                n_seen[0] += 1
                return m.group(0) if n_seen[0] <= 5 else ''
            cap = re.sub(r'\s*' + _PS_TAG, _limit, cap)
            fixes.append(f'{k.title()}: trimmed hashtags to 5 (rule 5/6)')
            tags = re.findall(_PS_TAG, cap)
        if len(tags) < 2:
            warns.append(f'{k.title()}: only {len(tags)} hashtag (rules suggest 2-5)')
        r[k]['caption'] = re.sub(r'[ \t]{2,}', ' ', cap).strip()
    # ---- YouTube: hashtag in the title
    if 'youtube' in r:
        y = r['youtube']
        title = y.get('title', '')
        if title and not re.search(_PS_TAG, title):
            tag = None
            m = re.search(_PS_TAG, y.get('description', ''))
            if m:
                tag = m.group(0)
            elif seex == 'always':
                tag = '#SeeEx'
            if tag:
                y['title'] = f'{title.rstrip()} {tag}'
                fixes.append(f'YouTube: added {tag} to the title (rule 7)')
            else:
                warns.append('YouTube title has no hashtag (rule 7 wants one in the title)')
        if len(y.get('title', '')) > 100:
            warns.append(f'YouTube title is {len(y["title"])} characters (limit 100)')
    # ---- spelling normalisation everywhere (SeeEx, Adrianah, Rellik)
    def norm(s, hook=False):
        if hook:   # hooks are usually ALL CAPS: keep SEEEX in caps, only repair a split "SEE EX"
            s = re.sub(r'\bSee[\s\-]Ex\b', lambda m: 'SEEEX' if m.group(0).isupper() else 'SeeEx', s, flags=re.I)
        else:
            s = re.sub(r'\bSee[\s\-]?Ex\b', 'SeeEx', s, flags=re.I)
        s = re.sub(r'(?<![\w&])#see[\s\-_]?ex\b', '#SeeEx', s, flags=re.I)
        s = re.sub(r'\bAdriana\s+Lee\b', 'Adrianah Lee', s)
        s = re.sub(r'\bRel+[iy]c?k\s+the\s+clown\b', 'Rellik The Clown', s, flags=re.I)
        return s
    changed = False
    for k in ('tiktok', 'instagram', 'youtube', 'x'):
        for f, v in list((r.get(k) or {}).items()):
            nv = norm(v, hook=(f == 'hook'))
            if nv != v:
                r[k][f] = nv; changed = True
    fix(changed, 'Normalised spelling (SeeEx / Adrianah Lee / Rellik The Clown)')
    # ---- SeeEx mode checks
    text_after = ' '.join(str(v) for k in ('tiktok', 'instagram', 'youtube', 'x') for v in (r.get(k) or {}).values())
    has_seex = bool(re.search(r'see\s?ex', text_after, flags=re.I))
    if seex == 'never' and has_seex:
        warns.append('SeeEx MODE is "Never" but the copy mentions SeeEx (rule 30)')
    if seex == 'always':
        for k, name in (('tiktok', 'TikTok'), ('instagram', 'Instagram'), ('youtube', 'YouTube'), ('x', 'X')):
            if k in r and not re.search(r'see\s?ex', ' '.join(r[k].values()), flags=re.I):
                warns.append(f'{name}: SeeEx is not mentioned (mode is "Always", rule 16)')
    if 'x' in r and re.search(r'#see\s?ex', r['x'].get('post', ''), flags=re.I):
        warns.append('X mentions #SeeEx as a hashtag (never on X)')
    # ---- creator rules
    both = (people or '') + ' ' + (transcript or '') + ' ' + text_after
    if re.search(r'aishah\s*sofey|aishahsofey', both, flags=re.I):
        if 'x' in r and not re.search(r'Aishah Sofey', r['x'].get('post', '')):
            warns.append('Aishah Sofey: the X post must include her name "Aishah Sofey", not only the @handle (rule 27)')
    # ---- soft checks: emojis, all caps, risky claims
    for k in ('tiktok', 'instagram', 'youtube', 'x'):
        for f, v in (r.get(k) or {}).items():
            if _ps_count_emoji(v) > 3 and f in ('caption', 'post', 'description'):
                warns.append(f'{PS_SECTION_NAME[k].title()} {f}: {_ps_count_emoji(v)} emojis (rule 10 says 1-3)')
            if f in ('caption', 'post') and len(v) > 40 and v == v.upper() and re.search(r'[A-Z]', v):
                warns.append(f'{PS_SECTION_NAME[k].title()} {f} is ALL CAPS (rule 11)')
    if re.search(r'\b(pedophile|pedo|paedophile|groomer|predator|rapist)\b', text_after, flags=re.I):
        warns.append('Uses a criminal label as fact. Rule 15: say "controversial comments about minors" / "permanently banned" instead')
    if re.search(r'\b(falsely|faked|fake(?:d)?\s+(?:it|being)|liar|lied|lying)\b', text_after, flags=re.I):
        warns.append('Accuses someone of lying/faking. Rule 13: frame disputes as "X says... while Y insists..."')
    if re.search(r'\b(assault(?:ed)?|attack(?:ed)?)\b', text_after, flags=re.I) and re.search(r'\b(consent|asked to be|agreed to|staged|part of the event)\b', transcript or '', flags=re.I):
        warns.append('Transcript mentions consent/staging but the copy says assaulted/attacked (rule 14)')
    if re.search(r'\ballegedly|reportedly|claims?\b', text_after, flags=re.I) is None and re.search(r'\b(cheat(?:ed|ing)?|scam(?:med)?|stole|steal)\b', text_after, flags=re.I):
        warns.append('Alleged wrongdoing stated as fact? Rule 12: use "allegedly / reportedly / claims"')
    for k, name in (('tiktok', 'TikTok'), ('instagram', 'Instagram'), ('youtube', 'YouTube Shorts')):
        if platforms and k in platforms and not (r.get(k) or {}).get('hook'):
            warns.append(f'{name}: no on-screen hook was produced')
    return r, fixes, warns


def ps_creator_reminders(people='', transcript='', handles=None):
    """Manual to-dos from the creator-specific rules (things the copy itself cannot do)."""
    both = (people or '') + ' ' + (transcript or '')
    out = []
    if re.search(r'aishah\s*sofey|aishahsofey', both, flags=re.I):
        out.append('Aishah Sofey: tag @aishahsofey in the X comments BEFORE the clip blows up. TikTok: tag @aishah + #aishahsofey. '
                   'Instagram: tag @aishahsofey in the video + caption + #aishahsofey. YouTube Shorts: tag @hiaishahsofey.')
    return out


def ps_key_pool(keys, extra_keys, extra_enabled):
    """Ordered [(provider, key)] for writing: Gemini first (long prompt friendly), then OpenRouter, then Groq
    (its free tier only allows ~8K tokens/minute, too small for the master prompt on long clips)."""
    pool = []
    for prov, lib in (('Google Gemini (Free)', 'gemini'), ('OpenRouter (Free models)', 'openrouter'), ('Groq (Free)', 'groq')):
        ks = [keys.get(prov, '').strip()]
        ex = extra_keys.get(prov, [])
        en = list(extra_enabled.get(prov, [])) + [True] * max(0, len(ex) - len(extra_enabled.get(prov, [])))
        ks += [k for k, e in zip(ex, en) if e]
        pool += [(lib, k) for k in ks if k]
    return pool
# end-post-studio-engine


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'ClipFinder {APP_VERSION} — AI Clip Extractor')
        self.geometry('1200x860')
        # Load previously decommissioned models so we never retry them
        _load_dead_models()
        # Restore Groq TPD state if it hasn't expired yet
        try:
            import time as _tpd_init
            _tpd_cfg = load_cfg()
            _tpd_until = _tpd_cfg.get('groq_tpd_until', 0)
            if _tpd_until > _tpd_init.time():
                self._groq_tpd_exhausted = True
                _hrs = int((_tpd_until - _tpd_init.time()) / 3600)
                print(f'[CF] Groq daily limit active — resets in ~{_hrs}h')
        except Exception:
            pass
        # Set window + taskbar icon
        try:
            _ico_search = [
                _PathBase(__file__).parent / 'clipfinder.ico',
                _PathBase(sys.executable).parent / 'clipfinder.ico',
                USER_DIR.parent / 'clipfinder.ico',
            ]
            for _ico_path in _ico_search:
                if _ico_path.exists():
                    self.iconbitmap(str(_ico_path))
                    try:
                        import ctypes
                        _u32 = ctypes.windll.user32
                        _ico_str = str(_ico_path)
                        _LR_LOADFROMFILE = 0x00000010
                        _IMAGE_ICON      = 1
                        # SM_CXICON/SM_CYICON = taskbar icon size, already DPI-scaled by Windows
                        # e.g. 32 at 100%, 40 at 125%, 48 at 150%, 64 at 200%
                        _sz_lg = _u32.GetSystemMetrics(11)  # SM_CXICON
                        _sz_sm = _u32.GetSystemMetrics(49)  # SM_CXSMICON
                        _hicon_lg = _u32.LoadImageW(None, _ico_str, _IMAGE_ICON, _sz_lg, _sz_lg, _LR_LOADFROMFILE)
                        _hicon_sm = _u32.LoadImageW(None, _ico_str, _IMAGE_ICON, _sz_sm, _sz_sm, _LR_LOADFROMFILE)
                        _WM_SETICON = 0x0080
                        _hwnd = int(self.frame(), 16)
                        if _hicon_lg: _u32.SendMessageW(_hwnd, _WM_SETICON, 1, _hicon_lg)
                        if _hicon_sm: _u32.SendMessageW(_hwnd, _WM_SETICON, 0, _hicon_sm)
                    except Exception:
                        pass
                    break
        except Exception:
            pass
        self.minsize(1000, 750)
        self.configure(bg=BG)

        self.cfg = load_cfg()
        global _LIVE_CFG
        _LIVE_CFG = self.cfg

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
        self.v_use_gpu_whisper = tk.BooleanVar(value=self.cfg.get('use_gpu_whisper', True))
        self.v_status   = tk.StringVar(value='Ready.')

        self.clips      = []
        self.clip_vars  = []
        self.transcript = ''
        self.srt_result = None
        self.running    = False
        self._cancel_requested = False
        self._ff_procs = []                    # running export ffmpeg processes (killed by Cancel)
        self._ff_lock  = threading.Lock()
        # App-level rate-limit tracking — persists across runs, visible to Settings panel
        import threading as _thr_init
        self._rl_provs      = set()        # providers currently rate-limited
        self._rl_since      = {}           # prov -> time.time() when marked RL
        self._rl_provs_lock = _thr_init.Lock()
        # Extra API keys per provider for round-robin rotation
        self._extra_keys = {
            'Google Gemini (Free)':    [k.strip() for k in self.cfg.get('key_gemini_extra','').split(',') if k.strip()],
            'Groq (Free)':             [k.strip() for k in self.cfg.get('key_groq_extra','').split(',') if k.strip()],
            'OpenRouter (Free models)':[k.strip() for k in self.cfg.get('key_openrouter_extra','').split(',') if k.strip()],
        }
        # Per-provider per-key enabled flags: cfg stores comma-sep 0/1 matching extra keys order
        self._extra_keys_enabled = {
            'Google Gemini (Free)':    [bool(int(x)) for x in self.cfg.get('key_gemini_extra_enabled','').split(',') if x in ('0','1')],
            'Groq (Free)':             [bool(int(x)) for x in self.cfg.get('key_groq_extra_enabled','').split(',') if x in ('0','1')],
            'OpenRouter (Free models)':[bool(int(x)) for x in self.cfg.get('key_openrouter_extra_enabled','').split(',') if x in ('0','1')],
        }
        self._key_index = {}
        # Auto-cooldown: (prov_name, key_fingerprint) -> epoch time when key re-enables
        # Keys are auto-paused 30-40 min on 429/401 when secondary keys exist
        self._key_cooldowns  = {}
        self._key_cd_lock    = _thr_init.Lock()
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
        self.v_cookies_browser = tk.StringVar(value=self.cfg.get('cookies_browser', ''))
        self.v_auto_load   = tk.BooleanVar(value=self.cfg.get('auto_load', True))
        self.v_auto_transcribe = tk.BooleanVar(value=self.cfg.get('auto_transcribe', False))
        # Auto-load and auto-transcribe are mutually exclusive (both off = just show the
        # "Download complete" popup). Guard against a config that has both switched on.
        if self.v_auto_load.get() and self.v_auto_transcribe.get():
            self.v_auto_transcribe.set(False)
        self._pending_transcribe = None   # file waiting for a download queue to finish
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
        self.v_auto_transcribe.trace_add('write', self._dl_autosave)
        def _make_exclusive(changed, other):
            def _cb(*_):
                if changed.get() and other.get():
                    other.set(False)
            return _cb
        self.v_auto_load.trace_add('write', _make_exclusive(self.v_auto_load, self.v_auto_transcribe))
        self.v_auto_transcribe.trace_add('write', _make_exclusive(self.v_auto_transcribe, self.v_auto_load))

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
        self.after(1500, self._refresh_prov_btns)
        self.after(2000, self._refresh_provider)
        # Apply right-click menus to all text inputs across the whole app
        self.after(200, lambda: apply_rightclick_to_all(self, self))
        self.after(300, self._fix_all_scrollbars)
        self.after(400, self._bind_global_mousewheel)
        self.after(800, self._check_first_run)

        # Launch counter (the old "update packages every 10 launches" prompt is gone: fast-moving modules are
        # now kept fresh in the background, see _uc_background)
        try:
            self.cfg['launch_count'] = int(self.cfg.get('launch_count', 0)) + 1
            save_cfg(self.cfg)
        except Exception:
            pass
        self.after(25000, self._uc_background)

        def _on_close():
            # Kill any running whisper.cpp subprocess
            for _p in getattr(_do_transcribe, '_active_procs', []):
                try: _p.kill()
                except: pass
            _do_transcribe._active_procs = []
            try: self._save_settings()
            except Exception: pass
            try: self.destroy()
            except: pass
            import os as _osx; _osx._exit(0)
        self.protocol("WM_DELETE_WINDOW", _on_close)
        # Pre-check ffmpeg — FIND ONLY, never download at startup
        # (App update check + banner: see _uc_background / _uc_show_banner - runs ~25s after launch,
        #  never blocks start-up, and falls back to the un-rate-limited releases redirect.)

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
        # NOTE: the Settings tab used to be pre-built here ~4s after launch. Tk work can only run on
        # the UI thread, so that froze the window for several seconds right when the user started
        # using it. It now builds on first click (see _switch_nb / _ensure_tab_built).
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
        logo_f = tk.Frame(hdr, bg=BG2); logo_f.pack(side='left', padx=(14, 6))
        # App icon left of text — load from PNG for sharpness, fallback to ICO
        try:
            from PIL import Image as _PI3, ImageTk as _PT3
            _hdr_frame = None
            # Prefer the 512px PNG next to the exe/script — much sharper than pulling from ICO
            for _ip in [_PathBase(__file__).parent / 'clipfinder_logo_512.png',
                        _PathBase(sys.executable).parent / 'clipfinder_logo_512.png',
                        _PathBase(__file__).parent / 'clipfinder.ico',
                        _PathBase(sys.executable).parent / 'clipfinder.ico']:
                if _ip.exists():
                    _hdr_img = _PI3.open(str(_ip)).convert('RGBA')
                    # Downscale from large source for crisp result
                    _hdr_frame = _hdr_img.resize((40, 40), _PI3.LANCZOS)
                    break
            if _hdr_frame:
                self._hdr_icon = _PT3.PhotoImage(_hdr_frame)
                tk.Label(logo_f, image=self._hdr_icon, bg=BG2).pack(side='left', padx=(0, 4))
        except Exception: pass
        tk.Label(logo_f, text='CLIP', font=('Segoe UI', 17, 'bold'),
                 fg=ACCENT, bg=BG2).pack(side='left')
        tk.Label(logo_f, text='FINDER', font=('Segoe UI', 17, 'bold'),
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
            ('clips',       '✂',  'Clip Finder'),
            ('transcript',  '📝', 'Transcript'),
            ('poststudio',  '🚀', 'Post Studio'),
            ('downloader',  '⬇',  'Downloader'),
            ('thumbs',      '🖼', 'Thumbnails'),
            ('editor',      '🎬', 'Editor'),
            ('studio',      '🔬', 'Studio'),
            ('censor',      '🔇', 'Censor'),
            ('music',       '🎵', 'Music Removal'),
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
            'poststudio': (self._build_post_studio_tab,),
            'downloader': (self._build_dl_tab,),
            'thumbs':     (self._build_thumb_tab,),
            'editor':     (self._build_editor_tab,),
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
                    try:
                        builders[0](self.nb_frames[key])
                    except Exception as _tab_err:
                        import traceback as _tb
                        print(f'[CF] Tab build error ({key}): {_tab_err}')
                        _tb.print_exc()
                        tk.Label(self.nb_frames[key],
                                 text=f'⚠ Tab failed to load: {_tab_err}\nCheck console for details.',
                                 font=FONT_SMALL, fg=RED, bg=BG, wraplength=400
                                 ).pack(expand=True)
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
            except Exception:  # ImportError, or OSError from a broken ctranslate2 DLL load
                _ensure_pkgs_on_path()
                try:
                    import faster_whisper; _already_set_up = True
                except Exception:
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
            for _ip in (_PathBase(__file__).parent / 'clipfinder.ico',
                        _PathBase(sys.executable).parent / 'clipfinder.ico',
                        USER_DIR.parent / 'clipfinder.ico'):
                if _ip.exists():
                    ov.iconbitmap(str(_ip)); break
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
        tk.Label(logo_row, text=f'  v{APP_VERSION}', font=('Segoe UI', 9),
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

        # Right-click context menu for log box
        def _log_right_click(e):
            _m = tk.Menu(self.log_box, tearoff=0, bg=BG3, fg=FG,
                         activebackground=ACCENT, activeforeground='#000',
                         relief='flat', bd=1)
            def _copy_selection():
                try:
                    txt = self.log_box.get('sel.first', 'sel.last')
                    self.clipboard_clear(); self.clipboard_append(txt)
                except: pass
            def _copy_all():
                txt = self.log_box.get('1.0', 'end').strip()
                self.clipboard_clear(); self.clipboard_append(txt)
            def _clear_log():
                self.log_box.config(state='normal')
                self.log_box.delete('1.0', 'end')
                self.log_box.config(state='disabled')
                self._log_buffer.clear()
            _m.add_command(label='Copy Selection', command=_copy_selection)
            _m.add_command(label='Copy All', command=_copy_all)
            _m.add_separator()
            _m.add_command(label='Clear Log', command=_clear_log)
            _m.tk_popup(e.x_root, e.y_root)
        self.log_box.bind('<Button-3>', _log_right_click)
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
        lbl(r2, 'Instructions:').pack(side='left')
        cw = tk.Frame(r2, bg=BG3); cw.pack(side='left', fill='x', expand=True, padx=(4,8))
        self.v_context = tk.Text(cw, height=2, font=FONT_SMALL, bg=BG3, fg=FG,
                                 insertbackground=ACCENT, relief='flat', bd=4, wrap='word')
        self.v_context.pack(fill='x')
        _ctx_ph_normal = 'ignore last hour · skip gambling · focus on drama · only clips of [name]  (transcript-based only)'
        _ctx_ph_vision = 'girl in white shirt · gambling scenes · outdoor moments · funny reactions  (visual AI — sees the video)'
        _ctx_ph = _ctx_ph_normal
        if not self.cfg.get('video_context',''):
            self.v_context.insert('1.0', _ctx_ph)
            self.v_context.config(fg=FG3)
        else:
            self.v_context.insert('1.0', self.cfg.get('video_context',''))
        def _ctx_focus_in(e):
            cur = self.v_context.get('1.0','end').strip()
            if cur in (_ctx_ph_normal, _ctx_ph_vision):
                self.v_context.delete('1.0','end')
                self.v_context.config(fg=FG)
        def _ctx_focus_out(e):
            val = self.v_context.get('1.0','end').strip()
            if not val or val in (_ctx_ph_normal, _ctx_ph_vision):
                _ph = _ctx_ph_vision if self.app_mode.get() == 'vision' else _ctx_ph_normal
                self.v_context.delete('1.0','end')
                self.v_context.insert('1.0', _ph)
                self.v_context.config(fg=FG3)
                val = ''
            else:
                self.v_context.config(fg=FG)
            self.cfg.update({'video_context': val})
            save_cfg(self.cfg)
        self.v_context.bind('<FocusIn>', _ctx_focus_in)
        self.v_context.bind('<FocusOut>', _ctx_focus_out)
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
        self.mode_vision_btn = tk.Button(r4, text='🎯 Vision', font=FONT_SMALL,
                                         relief='flat', bd=0, cursor='hand2', padx=7, pady=4,
                                         command=lambda: self._set_mode('vision'))
        self.mode_vision_btn.pack(side='left', padx=(0,2))

        self._refresh_mode_btns()

        # Smart transcribe — skip transcribing sections flagged in instructions
        tk.Frame(r4, bg=BORDER, width=1).pack(side='left', fill='y', padx=8)
        self.v_smart_transcribe = tk.BooleanVar(value=self.cfg.get('smart_transcribe', False))
        _st_chk = tk.Checkbutton(r4, text='⚡ Smart Transcribe',
                                  variable=self.v_smart_transcribe,
                                  font=FONT_SMALL, bg=BG2, fg=FG2,
                                  selectcolor=BG3, activebackground=BG2,
                                  relief='flat', bd=0, cursor='hand2',
                                  command=lambda: (self.cfg.update({'smart_transcribe': self.v_smart_transcribe.get()}), save_cfg(self.cfg)))
        _st_chk.pack(side='left', padx=(0,4))
        # Tooltip
        # (skipped while a job is running so it doesn't overwrite live progress)
        def _st_enter(e):
            if not (getattr(self, 'running', False) or getattr(self, '_ae_running', False)):
                self.set_progress('⚡ Smart Transcribe: skips transcribing sections you told it to ignore (e.g. "ignore last hour") — faster but permanent for this run')
        def _st_leave(e):
            if not (getattr(self, 'running', False) or getattr(self, '_ae_running', False)):
                self.set_progress('Ready')
        _st_chk.bind('<Enter>', _st_enter)
        _st_chk.bind('<Leave>', _st_leave)

        tk.Frame(r4, bg=BORDER, width=1).pack(side='left', fill='y', padx=8)

        # Action buttons on the right
        self.go_btn = tk.Button(r4, text='▶  FIND CLIPS',
                                font=('Segoe UI', 10,'bold'), bg=ACCENT, fg='#000',
                                relief='flat', bd=0, cursor='hand2', padx=16, pady=5,
                                activebackground=ACCENT2, command=self._start)
        self.go_btn.pack(side='right', padx=(0,4))

        # Heatmap transcribe button — only visible when heatmap mode is ON
        self._hm_transcribe_btn = tk.Button(
            r4, text='🌡 Transcribe', font=('Segoe UI', 9),
            bg=BG3, fg=ACCENT, relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
            activebackground=BG2, activeforeground=ACCENT,
            command=self._transcribe_only)
        # Hidden by default — _toggle_heatmap_mode shows/hides it

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
        tk.Label(self.interview_frame,
                 text='📝 Enter speaker names in the Names: field above (top right)',
                 font=('Segoe UI', 8), fg=ACCENT2, bg=BG2).pack(anchor='w', padx=4, pady=(2,4))

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

        # ── Drama Heatmap ──────────────────────────────────────────────────────
        # ── Drama Heatmap — single compact header row, expands only when data exists ──
        self._heatmap_frame = tk.Frame(p, bg=BG2)
        self._heatmap_frame.pack(fill='x', padx=8, pady=(2,0))

        # Single header row — all controls inline, nothing expands until data
        hm_hdr = tk.Frame(self._heatmap_frame, bg=BG2)
        hm_hdr.pack(fill='x')
        tk.Label(hm_hdr, text='🌡  DRAMA HEATMAP', font=('Segoe UI', 8, 'bold'),
                 fg=ACCENT, bg=BG2).pack(side='left')

        self._heatmap_mode_on = tk.BooleanVar(value=False)
        self._heatmap_toggle_btn = tk.Button(
            hm_hdr, text='OFF', font=('Segoe UI', 8, 'bold'),
            bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=6, pady=1,
            command=self._toggle_heatmap_mode)
        self._heatmap_toggle_btn.pack(side='left', padx=(6,0))

        # These only appear once heatmap has data
        self._hm_select_hot_btn = tk.Button(
            hm_hdr, text='🔴 Hot', font=('Segoe UI', 8),
            bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=6, pady=1,
            command=lambda: self._heatmap_select_by_score(threshold=self._hm_threshold.get()))
        self._hm_clear_btn = tk.Button(
            hm_hdr, text='✕ Clear', font=('Segoe UI', 8),
            bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=6, pady=1,
            command=self._heatmap_clear_selection)
        # Slider inline — label + compact slider
        self._hm_threshold = tk.IntVar(value=6)
        self._hm_slider_lbl = tk.Label(hm_hdr, text='min score:', font=('Segoe UI', 8),
                                        fg=FG2, bg=BG2)
        self._hm_slider = tk.Scale(
            hm_hdr, from_=1, to=10, orient='horizontal',
            variable=self._hm_threshold, font=('Segoe UI', 7),
            bg=BG2, fg=FG, troughcolor=BG3, activebackground=ACCENT,
            highlightthickness=0, bd=0, sliderrelief='flat', width=8, length=80,
            showvalue=True,
            command=lambda v: self._heatmap_select_by_score(threshold=int(v)))
        self._hm_token_lbl = tk.Label(hm_hdr, text='', font=('Segoe UI', 8),
                                       fg=ACCENT2, bg=BG2)
        self._hm_token_lbl.pack(side='right')

        # Canvas — hidden until data, compact height
        _hm_h = 32
        self._heatmap_canvas = tk.Canvas(
            self._heatmap_frame, bg=BG3, height=_hm_h,
            bd=0, highlightthickness=1, highlightbackground=BORDER,
            cursor='hand2')

        # Hover label — single line, shown only when canvas visible
        self._hm_hover_lbl = tk.Label(
            self._heatmap_frame, text='', font=('Segoe UI', 8),
            fg=FG2, bg=BG2, anchor='w')

        # Internal state
        self._hm_zones      = []
        self._hm_built      = False
        self._hm_total_segs = 0

        def _hm_on_click(event):
            if not self._hm_zones: return
            w = self._heatmap_canvas.winfo_width() or 1
            total_dur = self._hm_zones[-1]['end'] if self._hm_zones else 1
            t = (event.x / w) * total_dur
            for z in self._hm_zones:
                if z['start'] <= t <= z['end']:
                    z['selected'] = not z['selected']
                    self._heatmap_redraw()
                    self._hm_update_token_estimate()
                    break

        def _hm_get_zone_at(x):
            if not self._hm_zones: return None
            w = self._heatmap_canvas.winfo_width() or 1
            total_dur = self._hm_zones[-1]['end']
            t = (x / w) * total_dur
            for z in self._hm_zones:
                if z['start'] <= t <= z['end']:
                    return z
            return None

        def _hm_on_rightclick(event):
            z = _hm_get_zone_at(event.x)
            if not z: return
            vid = self.v_video.get().strip()
            placeholder = getattr(self, '_video_placeholder', '')
            has_file = vid and vid != placeholder and Path(vid).exists()

            menu = tk.Menu(self, tearoff=0, bg=BG2, fg=FG, activebackground=ACCENT,
                           activeforeground='#000', relief='flat', bd=1)

            def _fmt(s):
                s = int(s)
                return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

            menu.add_command(
                label=f'▶  Preview  {_fmt(z["start"])} → {_fmt(z["end"])}',
                command=lambda: self._heatmap_preview_zone(z) if has_file else
                    messagebox.showwarning('No video', 'Load a local video file to preview zones.\nURL-only sources must be downloaded first.'),
                state='normal' if has_file else 'disabled')
            menu.add_separator()
            menu.add_command(
                label='✓  Select this zone',
                command=lambda: [z.update({'selected': True}), self._heatmap_redraw(), self._hm_update_token_estimate()])
            menu.add_command(
                label='✕  Deselect this zone',
                command=lambda: [z.update({'selected': False}), self._heatmap_redraw(), self._hm_update_token_estimate()])
            menu.add_separator()
            menu.add_command(label='🔴  Select all hot zones',
                             command=lambda: self._heatmap_select_by_score(self._hm_threshold.get()))
            menu.add_command(label='✕  Clear all selections',
                             command=self._heatmap_clear_selection)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        def _hm_on_motion(event):
            if not self._hm_zones: return
            w = self._heatmap_canvas.winfo_width() or 1
            total_dur = self._hm_zones[-1]['end'] if self._hm_zones else 1
            t = (event.x / w) * total_dur
            def _fmt(s):
                s = int(s)
                return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            for z in self._hm_zones:
                if z['start'] <= t <= z['end']:
                    sel_txt = '✓ selected' if z['selected'] else 'click to select'
                    self._hm_hover_lbl.config(
                        text=f"  {_fmt(z['start'])} → {_fmt(z['end'])}  ·  score {z['score']}/10  ·  {sel_txt}")
                    break

        def _hm_on_leave(event):
            self._hm_hover_lbl.config(text='')

        self._heatmap_canvas.bind('<Button-1>',   _hm_on_click)
        self._heatmap_canvas.bind('<Button-3>',   _hm_on_rightclick)
        self._heatmap_canvas.bind('<Motion>',      _hm_on_motion)
        self._heatmap_canvas.bind('<Leave>',       _hm_on_leave)
        self._heatmap_canvas.bind('<Configure>',   lambda e: self._heatmap_redraw())

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Clips header + export bar ─────────────────────────────────────────
        hdr = tk.Frame(p, bg=BG); hdr.pack(fill='x', padx=8, pady=(4,0))
        tk.Label(hdr, text='AI CLIP SUGGESTIONS', font=('Segoe UI', 9,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
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

        # Select / Deselect All — right of export bar, orange text
        def _deselect_all():
            for v in self.clip_vars: v.set(False)
        def _select_all_clips():
            for v in self.clip_vars: v.set(True)
        tk.Button(exp_bar, text='☐ Deselect All', font=FONT_SMALL, bg=BG, fg=ACCENT,
                  relief='flat', bd=0, cursor='hand2',
                  command=_deselect_all).pack(side='right', padx=(0,4))
        tk.Button(exp_bar, text='☑ Select All', font=FONT_SMALL, bg=BG, fg=ACCENT,
                  relief='flat', bd=0, cursor='hand2',
                  command=_select_all_clips).pack(side='right', padx=(0,4))

        # Save / Load session buttons
        tk.Button(exp_bar, text='💾 Save Session', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                  command=self._save_session).pack(side='right', padx=(0,4))
        tk.Button(exp_bar, text='📂 Load Session', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10, pady=5,
                  command=self._load_session).pack(side='right', padx=(0,2))


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

        def _sb_click(e):
            h = max(_sb_cv.winfo_height(), 10)
            frac = e.y / h
            span = _sb_state['hi'] - _sb_state['lo']
            self.clip_canvas.yview_moveto(max(0, min(1-span, frac - span/2)))

        def _sb_press(e):
            _sb_state['drag_y'] = e.y
            h = max(_sb_cv.winfo_height(), 10)
            # Click in the trough (outside the thumb) jumps there; click on the thumb starts a drag
            if not (_sb_state['lo'] * h <= e.y <= _sb_state['hi'] * h):
                _sb_click(e)

        def _sb_drag(e):
            h = max(_sb_cv.winfo_height(), 10)
            dy = (e.y - (_sb_state['drag_y'] or e.y)) / h
            _sb_state['drag_y'] = e.y
            span = _sb_state['hi'] - _sb_state['lo']
            new_lo = max(0.0, min(1.0 - span, _sb_state['lo'] + dy))
            self.clip_canvas.yview_moveto(new_lo)

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


    # ── Channel browser (Downloader tab > "Browse channels") ──────────────────────
    # Kick / Twitch / YouTube channels with their VODs and clips (YouTube: Streams / Videos / Shorts)
    # as separate sections, with thumbnails. Backends: kick_list_vods/_clips, twitch_list, youtube_list.

    def _dl_set_mode(self, mode):
        """Downloader tab: 'download' (link box) or 'browse' (channel browser, built on first use)."""
        if mode == 'browse' and not getattr(self, '_br_built', False):
            self._br_built = True
            self._build_browser_panel(self._dl_browse)
        self._dl_mode = mode
        if mode == 'browse':
            self._dl_main.pack_forget()
            self._dl_browse.pack(fill='both', expand=True)
        else:
            self._dl_browse.pack_forget()
            self._dl_main.pack(fill='both', expand=True)
        for k, b in self._dl_mode_btns.items():
            b.config(bg=ACCENT if k == mode else BG3, fg='#000' if k == mode else FG2,
                     font=('Segoe UI', 9, 'bold') if k == mode else ('Segoe UI', 9))

    def _build_browser_panel(self, p):
        self._br_platform = self.cfg.get('br_platform', 'kick')
        if self._br_platform not in BROWSE_SECTIONS:
            self._br_platform = 'kick'
        self._br_section = {k: self.cfg.get('br_section_' + k, v[0][0]) for k, v in BROWSE_SECTIONS.items()}
        self._br_channels = dict(self.cfg.get('br_channels') or {})
        self._br_cache = {}
        self._br_req = 0
        self._br_thumb_gen = 0
        self._br_thumb_refs = []
        self._br_thumbs_loaded = 0
        self._br_ph_img = None

        # platform switch
        top = tk.Frame(p, bg=BG2); top.pack(fill='x')
        self._br_plat_btns = {}
        for key, label, _hint, _ex in BROWSE_PLATFORMS:
            b = tk.Button(top, text=label, font=('Segoe UI', 9), relief='flat', bd=0, cursor='hand2', padx=18, pady=7,
                          command=lambda k=key: self._br_set_platform(k))
            b.pack(side='left', padx=(8 if key == 'kick' else 2, 2), pady=6)
            self._br_plat_btns[key] = b
        tk.Label(top, text='Browse a channel, then Load / Edit / Download straight from the list.',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2).pack(side='left', padx=10)
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # channel + browse
        row = tk.Frame(p, bg=BG2); row.pack(fill='x', padx=12, pady=(8, 4))
        self._br_chan_lbl = tk.Label(row, text='', font=FONT_SMALL, fg=FG2, bg=BG2)
        self._br_chan_lbl.pack(side='left')
        ef = tk.Frame(row, bg=BG3); ef.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self._br_chan_var = tk.StringVar()
        self._br_entry = tk.Entry(ef, textvariable=self._br_chan_var, font=FONT_SMALL, bg=BG3, fg=FG,
                                  insertbackground=ACCENT, relief='flat', bd=4)
        self._br_entry.pack(side='left', fill='x', expand=True)
        self._br_entry.bind('<Return>', lambda e: self._br_fetch(force=True))
        self._br_go = tk.Button(row, text='🔍  Browse', font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000', relief='flat',
                                bd=0, cursor='hand2', padx=12, pady=5, activebackground=ACCENT2,
                                command=lambda: self._br_fetch(force=True))
        self._br_go.pack(side='left')

        # sections (VODs / Clips ...) - rebuilt for each platform
        self._br_sec_bar = tk.Frame(p, bg=BG2); self._br_sec_bar.pack(fill='x', padx=12, pady=(0, 6))
        self._br_sec_btns = {}
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # list
        outer = tk.Frame(p, bg=BG); outer.pack(fill='both', expand=True)
        cv = tk.Canvas(outer, bg=BG, bd=0, highlightthickness=0)
        _make_scrollbar(outer, cv)
        cv.pack(side='left', fill='both', expand=True)
        self._br_cv = cv
        self._br_list = tk.Frame(cv, bg=BG)
        win = cv.create_window((0, 0), window=self._br_list, anchor='nw')
        self._br_list.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        cv.bind('<Configure>', lambda e: cv.itemconfigure(win, width=e.width))
        _bind_mousewheel(cv, cv); _bind_mousewheel(self._br_list, cv)

        bot = tk.Frame(p, bg=BG2); bot.pack(fill='x', side='bottom')
        tk.Frame(bot, bg=BORDER, height=1).pack(fill='x')
        self._br_bot = tk.Label(bot, text='', font=('Segoe UI', 8), fg=FG2, bg=BG2, anchor='w')
        self._br_bot.pack(side='left', padx=10, pady=4)
        self._br_set_platform(self._br_platform, fetch=False)

    def _br_set_platform(self, plat, fetch=True):
        old = getattr(self, '_br_shown_plat', None)
        if old and old != plat:                    # remember what was typed for the platform we leave
            self._br_channels[old] = self._br_chan_var.get().strip()
        self._br_shown_plat = plat
        self._br_platform = plat
        self.cfg['br_platform'] = plat
        for k, b in self._br_plat_btns.items():
            b.config(bg=ACCENT if k == plat else BG3, fg='#000' if k == plat else FG2,
                     font=('Segoe UI', 9, 'bold') if k == plat else ('Segoe UI', 9))
        info = next(x for x in BROWSE_PLATFORMS if x[0] == plat)
        self._br_chan_lbl.config(text=info[2] + ':')
        self._br_chan_var.set(self._br_channels.get(plat, '') or info[3])
        for w in self._br_sec_bar.winfo_children():
            w.destroy()
        self._br_sec_btns = {}
        for key, label in BROWSE_SECTIONS[plat]:
            b = tk.Button(self._br_sec_bar, text=label, font=('Segoe UI', 9), relief='flat', bd=0, cursor='hand2',
                          padx=14, pady=4, command=lambda k=key: self._br_set_section(k))
            b.pack(side='left', padx=(0, 4))
            self._br_sec_btns[key] = b
        self._br_paint_sections()
        cached = self._br_cache.get(self._br_key())
        if cached is not None:
            self._br_render(*cached)
        else:
            self._br_show_message(f'Enter a {info[2].split(" ")[0]} channel and hit Browse.')
            self._br_bot.config(text='')
        if fetch and self._br_chan_var.get().strip() and cached is None and self._br_channels.get(plat):
            self._br_fetch()

    def _br_key(self):
        return (self._br_platform, browse_normalize(self._br_platform, self._br_chan_var.get()),
                self._br_section[self._br_platform])

    def _br_paint_sections(self):
        cur = self._br_section[self._br_platform]
        for k, b in self._br_sec_btns.items():
            b.config(bg=ACCENT2 if k == cur else BG3, fg='#000' if k == cur else FG2,
                     font=('Segoe UI', 9, 'bold') if k == cur else ('Segoe UI', 9))

    def _br_set_section(self, key):
        self._br_section[self._br_platform] = key
        self.cfg['br_section_' + self._br_platform] = key
        self._br_paint_sections()
        cached = self._br_cache.get(self._br_key())
        if cached is not None:
            self._br_render(*cached)
        elif self._br_chan_var.get().strip():
            self._br_fetch()

    def _br_show_message(self, text, color=None, title=None):
        for w in self._br_list.winfo_children():
            w.destroy()
        if title:
            tk.Label(self._br_list, text=title, font=('Segoe UI', 10, 'bold'), fg=color or FG, bg=BG).pack(pady=(24, 4))
        tk.Label(self._br_list, text=text, font=FONT_SMALL, fg=color or FG2, bg=BG, wraplength=640,
                 justify='center').pack(pady=(4 if title else 24, 0))
        self._br_thumb_gen += 1

    def _br_fetch(self, force=False):
        plat = self._br_platform
        chan = browse_normalize(plat, self._br_chan_var.get())
        section = self._br_section[plat]
        if not chan:
            self._br_show_message('Type a channel name first.', YELLOW)
            return
        key = (plat, chan, section)
        self._br_channels[plat] = self._br_chan_var.get().strip()
        self.cfg['br_channels'] = dict(self._br_channels)
        try: save_cfg(self.cfg)
        except Exception: pass
        if not force and key in self._br_cache:
            self._br_render(*self._br_cache[key])
            return
        self._br_req += 1
        req = self._br_req
        self._br_go.config(state='disabled', text='⏳ Loading...')
        self._br_show_message('⏳ Loading...')
        self._br_bot.config(text=f'Fetching {section} for {chan}...')
        cookies = (getattr(self, 'v_cookies', None) and self.v_cookies.get().strip()) or self.cfg.get('cookies_file', '').strip()
        cookies_ok = bool(cookies) and Path(cookies).exists()

        def _work():
            try:
                tok = _kick_session_token(cookies if cookies_ok else '') if plat == 'kick' else None
                items, note = browse_list(plat, chan, section, tok)
                self.after(0, lambda: self._br_done(req, key, items, note))
            except Exception as ex:
                _why = str(ex)
                self.after(0, lambda: self._br_fail(req, plat, _why))
        threading.Thread(target=_work, daemon=True).start()

    def _br_fail(self, req, plat, msg):
        if req != self._br_req:
            return
        self._br_go.config(state='normal', text='🔍  Browse')
        tip = ''
        if plat == 'kick' and ('403' in msg or 'blocked' in msg.lower()):
            tip = ('\n\nFix: add a Kick cookies.txt in Settings, or update curl-cffi in Settings > Update Center.')
        self._br_show_message(msg + tip, RED, title='⚠  Could not load the list')
        self._br_bot.config(text='Error')

    def _br_done(self, req, key, items, note):
        if req != self._br_req:
            return
        self._br_go.config(state='normal', text='🔍  Browse')
        self._br_cache[key] = (items, note, key)
        if key == self._br_key():
            self._br_render(items, note, key)

    def _br_render(self, items, note, key):
        plat, chan, section = key
        for w in self._br_list.winfo_children():
            w.destroy()
        label = dict(BROWSE_SECTIONS[plat]).get(section, section)
        if not items:
            self._br_show_message(note or f'Nothing found in {label} for {chan}.\n(The channel may have none, or they are private.)')
            self._br_bot.config(text='Nothing found')
            return
        self._br_bot.config(text=f'{len(items)} items in {label.split(" ", 1)[-1]} for {chan}' + (f'  -  {note}' if note else ''))
        jobs = []
        for it in items:
            title = it.get('title') or 'Untitled'
            dur = int(it.get('duration') or 0)
            dh, rem = divmod(dur, 3600); dm, ds = divmod(rem, 60)
            dur_str = f'{dh}h {dm}m' if dh else (f'{dm}m {ds}s' if dm else f'{ds}s')
            if it.get('is_live'):
                dur_str = '🔴 live now'
            url = it['url']
            card = tk.Frame(self._br_list, bg=BG2, cursor='hand2')
            card.pack(fill='x', padx=8, pady=(4, 0))
            th = tk.Label(card, image=self._br_placeholder(), bg=BG2, bd=0, cursor='hand2')
            th.pack(side='left', padx=(8, 0), pady=8)
            badge = (f'{dh}h {dm}m' if dh else f'{dm}:{ds:02d}') if dur else ''
            jobs.append((th, it.get('thumb', ''), badge, bool(it.get('is_live'))))
            info = tk.Frame(card, bg=BG2); info.pack(side='left', fill='both', expand=True, padx=10, pady=8)
            tk.Label(info, text=title, font=('Segoe UI', 9, 'bold'), fg=FG, bg=BG2, anchor='w', wraplength=420,
                     justify='left').pack(anchor='w')
            meta = f'🕒 {dur_str}'
            if it.get('created'):
                meta += f'   📅 {it["created"]}'
            if it.get('views'):
                meta += f'   👁 {int(it["views"]):,} views'
            tk.Label(info, text=meta, font=('Segoe UI', 8), fg=FG2, bg=BG2, anchor='w').pack(anchor='w', pady=(2, 0))
            btns = tk.Frame(card, bg=BG2); btns.pack(side='right', padx=8, pady=8)
            for text, bg, fg, cmd in (
                    ('▶ Load', ACCENT, '#000', lambda u=url, t=title: self._br_load(u, t)),
                    ('🎬 Edit', BG3, ACCENT, lambda u=url, t=title: self._ed_load_from_kick(u, t)),
                    ('⬇ Download', BG3, GREEN, lambda u=url: self._br_download(u)),
                    ('➕ Queue', BG3, FG2, lambda u=url: self._br_queue(u))):
                tk.Button(btns, text=text, font=FONT_SMALL, bg=bg, fg=fg, relief='flat', bd=0, cursor='hand2',
                          padx=10, pady=3, command=cmd).pack(fill='x', pady=(0, 3))
            th.bind('<Button-1>', lambda e, u=url, t=title: self._br_load(u, t))

            def _enter(e, c=card): c.config(bg=BG3)
            def _leave(e, c=card): c.config(bg=BG2)
            card.bind('<Enter>', _enter); card.bind('<Leave>', _leave)
            for ch in card.winfo_children():
                ch.bind('<Enter>', _enter); ch.bind('<Leave>', _leave)
            tk.Frame(self._br_list, bg=BORDER, height=1).pack(fill='x', padx=8)
        self._ps_wheel(self._br_list, self._br_cv)
        self._br_start_thumbs(jobs)

    def _br_placeholder(self):
        if self._br_ph_img is None:
            from PIL import Image, ImageTk
            self._br_ph_img = ImageTk.PhotoImage(Image.new('RGB', (192, 108), BG3))
        return self._br_ph_img

    def _br_start_thumbs(self, jobs):
        """Thumbnails load in a few background threads (disk cached). A generation counter drops results when
        the list was rebuilt (other channel / section) in the meantime."""
        import queue as _q, time as _tm
        self._br_thumb_gen += 1
        gen = self._br_thumb_gen
        self._br_thumb_refs = []          # PhotoImages must stay referenced or Tk shows blanks
        self._br_thumbs_loaded = 0
        cache = USER_DIR / 'kick_thumbs'   # (folder name kept from the Kick-only version: the uninstaller cleans it)
        try:                               # VODs expire after a few weeks - drop stale cache files
            for f in cache.glob('*.webp'):
                if _tm.time() - f.stat().st_mtime > 35 * 86400:
                    f.unlink()
        except Exception:
            pass
        todo = _q.Queue()
        for j in jobs:
            todo.put(j)

        def _worker():
            while gen == self._br_thumb_gen:
                try:
                    lbl, url, badge, live = todo.get_nowait()
                except _q.Empty:
                    return
                im = kick_thumbnail(url, cache) if url else None
                if im is not None and gen == self._br_thumb_gen:
                    if badge or live:
                        im = kick_thumb_badge(im, badge, live)
                    self.after(0, lambda l=lbl, i=im, g=gen: self._br_set_thumb(l, i, g))
        for _ in range(min(4, max(1, len(jobs)))):
            threading.Thread(target=_worker, daemon=True).start()

    def _br_set_thumb(self, label, im, gen):
        if gen != self._br_thumb_gen:
            return
        try:
            if not label.winfo_exists():
                return
            from PIL import ImageTk
            ph = ImageTk.PhotoImage(im)
            self._br_thumb_refs.append(ph)
            label.config(image=ph)
            self._br_thumbs_loaded += 1
        except Exception:
            pass

    # actions on a list item
    def _br_load(self, url, title):
        """Put the link in Clip Finder's video field (it downloads it when you hit FIND CLIPS)."""
        self.v_video.set(url)
        try:
            self._video_entry.config(fg=FG)
        except Exception:
            pass
        self._switch_nb('clips')
        self._switch_sub_clips('ai_clips')
        self.log(f'📺 Loaded: {title}', ACCENT)

    def _br_download(self, url):
        if getattr(self, '_dl_go_btn', None) is not None and self._dl_cancel_btn.winfo_manager():
            self._br_bot.config(text='A download is already running - use ➕ Queue to add this one.', fg=YELLOW)
            return
        self.v_dl_url.set(url)
        self._br_bot.config(text='⬇ Downloading... progress is in the log panel', fg=GREEN)
        self._dl_start()

    def _br_queue(self, url):
        try:
            cur = self._dl_queue_box.get('1.0', 'end').strip().splitlines()
            if url in cur:
                self._br_bot.config(text='Already in the download queue', fg=YELLOW)
                return
            self._dl_queue_box.insert('end', url + '\n')
            self._br_bot.config(text=f'➕ Added to the download queue ({len(cur) + 1} link(s)). Switch to "Download links" to start it.', fg=GREEN)
        except Exception:
            pass

    def _real_video(self):
        """Clip Finder video path, or '' when the entry only shows the placeholder hint."""
        v = self.v_video.get().strip()
        return '' if v == getattr(self, '_video_placeholder', '') else v

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
                 command=lambda: self.v_ae_video.set(self._real_video() or self.v_ae_video.get())
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
        if getattr(self, '_ae_running', False):
            messagebox.showinfo('Busy', 'Auto Edit is already running.'); return

        mode = self.v_ae_mode.get()
        db = {'light': '-45', 'balanced': '-35', 'aggressive': '-25'}.get(mode, '-35')


        Path(out).mkdir(parents=True, exist_ok=True)
        stem = Path(vid).stem
        out_path = str(Path(out) / f'{stem} - AutoEdit - ClipFinder.mp4')

        self._ae_running = True
        self._ae_procs = []
        self.set_busy(True)
        self.ae_status_lbl.config(text='⏳ Processing...', fg=ACCENT2)
        self.log(f'⚡ Auto Edit: {stem} [{mode}]', ACCENT2)

        def _run():
            work = None
            _out_started = False
            try:
                import subprocess as _sp, re as _re2, tempfile as _tmp2
                import shutil as _sh_ae, bisect as _bis
                _ensure_pkgs_on_path()

                def _ae_cancelled():
                    if getattr(self, '_cancel_requested', False):
                        self.after(0, lambda: self.ae_status_lbl.config(text='⛔ Cancelled', fg=YELLOW))
                        return True
                    return False

                def _ae_run(cmd, timeout=None):
                    """Run ffmpeg (killable via Cancel). Returns (returncode, stderr text)."""
                    if getattr(self, '_cancel_requested', False):
                        raise RuntimeError('Cancelled')
                    _p = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.PIPE)
                    self._ae_procs.append(_p)
                    try:
                        _o, _e = _p.communicate(timeout=timeout)
                    except _sp.TimeoutExpired:
                        _p.kill(); _p.communicate()
                        raise
                    finally:
                        try: self._ae_procs.remove(_p)
                        except ValueError: pass
                    return _p.returncode, (_e or b'').decode('utf-8', 'replace')

                def _ae_ff(cmd, timeout=None):
                    rc, err = _ae_run(cmd, timeout)
                    if rc != 0:
                        if getattr(self, '_cancel_requested', False):
                            raise RuntimeError('Cancelled')
                        raise RuntimeError('ffmpeg failed: ' + err[-400:])
                    return err

                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Checking ffmpeg...', fg=ACCENT2))
                ff = ensure_ffmpeg()
                if not (Path(ff).exists() or _sh_ae.which(ff)):
                    raise RuntimeError('ffmpeg not found - install it in Settings → Core Dependencies')

                # Step 1: Transcribe to get word timestamps
                self.log('[Auto Edit] Transcribing for word-level cuts...', FG2)
                if _ae_cancelled(): return
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
                if _ae_cancelled(): return

                # Step 2: Build keep segments from word timestamps + silence gaps
                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Detecting silence...', fg=ACCENT2))
                self.set_progress('Auto Edit: detecting silence...', pct=35)

                # Get total duration (ffmpeg exits non-zero here - only stderr matters)
                _, _di_err = _ae_run([ff,'-hide_banner','-i',vid], timeout=60)
                _dm = _re2.search(r'Duration: (\d+):(\d+):([\d.]+)', _di_err)
                total = (int(_dm.group(1))*3600 + int(_dm.group(2))*60 + float(_dm.group(3))) if _dm else 0

                # -vn: audio-only decode is far faster than decoding the video too
                _sil_err = _ae_ff([ff,'-hide_banner','-vn','-i',vid,'-af',f'silencedetect=noise={db}dB:d=0.3',
                                   '-f','null','-'], timeout=3600)
                if not total:
                    _tm = _re2.findall(r'time=(\d+):(\d+):([\d.]+)', _sil_err)
                    if _tm:
                        total = int(_tm[-1][0])*3600 + int(_tm[-1][1])*60 + float(_tm[-1][2])
                # Pair start/end events in order (starts can be slightly negative)
                sil_starts, sil_ends, _cur = [], [], None
                for _k, _v in _re2.findall(r'silence_(start|end): (-?[\d.]+(?:e[-+]?\d+)?)', _sil_err):
                    _v = max(0.0, float(_v))
                    if _k == 'start':
                        _cur = _v
                    elif _cur is not None:
                        sil_starts.append(_cur); sil_ends.append(_v); _cur = None
                if _cur is not None:  # silence runs to end of file
                    sil_starts.append(_cur); sil_ends.append(total if total else _cur)
                if not total and sil_ends:
                    total = max(sil_ends)
                self.log(f'[Auto Edit] Found {len(sil_starts)} silence gaps', FG2)

                # Build keep list — snap cuts to word boundaries if we have them
                _w_starts = sorted(ws for ws, _we in words)
                _w_ends = sorted(we for _ws, we in words)
                def _snap_to_word(t, snap='end'):
                    """Snap timestamp to nearest word start or end boundary."""
                    arr = _w_ends if snap == 'end' else _w_starts
                    if not arr:
                        return t
                    i = _bis.bisect_left(arr, t)
                    best, best_d = t, float('inf')
                    for k in (i-1, i):
                        if 0 <= k < len(arr) and abs(arr[k]-t) < best_d:
                            best, best_d = arr[k], abs(arr[k]-t)
                    # Only snap if within 0.5s — otherwise keep original
                    return best if best_d < 0.5 else t

                if sil_starts:
                    keeps = []
                    prev = 0.0
                    for ss, se in zip(sil_starts, sil_ends):
                        if ss > prev + 0.15:
                            # Snap cut-out point to nearest word end
                            # Snap cut-in point to nearest word start
                            # (clamped so a keep segment is never negative/overlapping)
                            snap_ss = max(prev, _snap_to_word(ss, snap='end'))
                            snap_se = max(snap_ss, _snap_to_word(se, snap='start'))
                            if snap_ss - prev >= 0.05:
                                keeps.append((prev, snap_ss))
                            prev = snap_se
                        else:
                            prev = max(prev, se)
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
                work = _tmp2.mkdtemp(prefix='cf_ae_')   # private dir; removed in finally
                concat_f = os.path.join(work, 'concat.txt')
                with open(concat_f, 'w', encoding='utf-8') as cf:
                    for j, (ks, ke) in enumerate(keeps):
                        seg_p = os.path.join(work, f's_{j}.mp4')
                        _ae_ff([ff,'-y','-ss',str(ks),'-to',str(ke),'-i',vid,
                                '-c','copy',seg_p])
                        _seg_q = seg_p.replace('\\', '/').replace("'", "'\\''")
                        cf.write(f"file '{_seg_q}'\n")

                # Step 4: Concat with CRF encode to fix size + AV sync
                if _ae_cancelled(): return
                self.after(0, lambda: self.ae_status_lbl.config(text='⏳ Encoding final video...', fg=ACCENT2))
                self.set_progress('Auto Edit: encoding...', pct=80)
                # Use GPU encoder for quality + speed, fallback to x264 CRF 18
                _ae_vcodec, _ae_acodec, _ae_extra = get_encoder(ff)
                # Drop any stale output from an earlier run so a failure can't be reported as success
                _out_started = True
                Path(out_path).unlink(missing_ok=True)
                _ae_ff([ff,'-y','-f','concat','-safe','0','-i',concat_f,
                        '-c:v',_ae_vcodec,'-c:a',_ae_acodec]+_ae_extra+[out_path],
                       timeout=max(3600, int(total*2)))

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
                _emsg = str(_e)
                if getattr(self, '_cancel_requested', False):
                    self.log('[Auto Edit] Cancelled', YELLOW)
                    self.after(0, lambda: self.ae_status_lbl.config(text='⛔ Cancelled', fg=YELLOW))
                else:
                    self.log(f'Auto Edit error: {_tb.format_exc()}', RED)
                    self.after(0, lambda m=_emsg: self.ae_status_lbl.config(text=f'❌ {m[:200]}', fg=RED))
                if _out_started:  # remove a truncated partial output
                    try: Path(out_path).unlink(missing_ok=True)
                    except OSError: pass
            finally:
                if work:
                    try: _sh_ae.rmtree(work, ignore_errors=True)
                    except Exception: pass
                self._ae_running = False
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
                  command=lambda: self.v_trans_file.set(self._real_video() or self.v_trans_file.get())
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

        tk.Frame(pane, bg=BORDER, width=1).pack(side='left', fill='y')

        # ── RIGHT: quick actions ──────────────────────────────────────────────
        right = tk.Frame(pane, bg=BG, width=170)
        right.pack(side='left', fill='y', padx=10, pady=8)
        right.pack_propagate(False)

        tk.Label(right, text='EXPORT', font=('Segoe UI', 9, 'bold'),
                 fg=ACCENT, bg=BG).pack(anchor='w', pady=(0, 8))

        def _copy_trans():
            txt = self.trans_box.get('1.0','end').strip() if hasattr(self,'trans_box') else ''
            if txt:
                self.clipboard_clear(); self.clipboard_append(txt)
                _cb.config(text='✅ Copied!', fg=GREEN)
                self.after(1500, lambda: _cb.config(text='📋 Copy Transcript', fg=FG))
        _cb = tk.Button(right, text='📋 Copy Transcript', font=FONT_SMALL,
                        bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                        padx=8, pady=6, command=_copy_trans)
        _cb.pack(fill='x', pady=(0,4))

        def _save_trans():
            import tkinter.filedialog as _fd
            _p = _fd.asksaveasfilename(defaultextension='.txt',
                filetypes=[('Text','*.txt'),('All','*.*')], initialfile='transcript.txt')
            if _p:
                txt = self.trans_box.get('1.0','end').strip() if hasattr(self,'trans_box') else ''
                open(_p,'w',encoding='utf-8').write(txt)
        tk.Button(right, text='💾 Save .txt', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                  padx=8, pady=6, command=_save_trans).pack(fill='x', pady=(0,12))

        tk.Frame(right, bg=BORDER, height=1).pack(fill='x', pady=(0,8))
        tk.Label(right, text='Generate posts from transcript:', font=('Segoe UI', 7), fg=FG3, bg=BG).pack(anchor='w')
        tk.Button(right, text='🚀 Post Studio →', font=FONT_SMALL,
                  bg='#1a2a1a', fg='#88ff88', relief='flat', bd=0,
                  cursor='hand2', padx=8, pady=6,
                  command=lambda: self._switch_nb('poststudio')).pack(fill='x', pady=(4,0))

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
                  command=lambda: self.v_sub_input.set(self._real_video() or self.v_trans_file.get())).pack(side='left', padx=(0, 4))
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
                'standard':  {'bold': True, 'italic': False, 'caps': False, 'color': '#FFFFFF', 'outline': '#000000', 'stroke': 3, 'bg': True,  'bg_opacity': 0,  'size': 48, 'karaoke': False, 'words': 6},
                'karaoke':   {'bold': True, 'italic': False, 'caps': False, 'color': '#FFFFFF', 'outline': '#000000', 'stroke': 4, 'bg': False, 'bg_opacity': 0,  'size': 52, 'karaoke': True,  'words': 6},
                'cinematic': {'bold': False,'italic': False, 'caps': True,  'color': '#FFFFFF', 'outline': '#000000', 'stroke': 2, 'bg': True,  'bg_opacity': 70, 'size': 44, 'karaoke': False, 'words': 6},
                'minimal':   {'bold': False,'italic': False, 'caps': False, 'color': '#FFFFFF', 'outline': '#000000', 'stroke': 1, 'bg': False, 'bg_opacity': 0,  'size': 36, 'karaoke': False, 'words': 6},
                'tiktok':    {'bold': True, 'italic': False, 'caps': True,  'color': '#FFFFFF', 'outline': '#FF0050', 'stroke': 5, 'bg': False, 'bg_opacity': 0,  'size': 56, 'karaoke': False, 'words': 3},
            }
            p = presets.get(preset, presets['standard'])
            self.v_sub_bold.set(p['bold']); self.v_sub_italic.set(p['italic'])
            self.v_sub_caps.set(p['caps']); self.v_sub_color.set(p['color'])
            self.v_sub_outline.set(p['outline']); self.v_sub_stroke.set(p['stroke'])
            self.v_sub_bg_on.set(p['bg']); self.v_sub_bg_opacity.set(p['bg_opacity'])
            self.v_sub_size.set(p['size'])
            self.v_sub_karaoke.set(p.get('karaoke', False)); self.v_sub_words.set(p.get('words', 6))
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
        # Clips rendered — nothing selected by default
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
                # Set the label text (this used to recurse into itself — a no-op
                # swallowed by the except, so provider notes/URL never showed)
                self.lbl_note.config(text=note_txt)
                self.lbl_url.config(text=url_txt)
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
            # _finish (queued earlier) already captured the flag on success; on failure/cancel
            # it must not leak into the next Downloader-tab download.
            self._load_after_dl = False
            try:
                self._dl_cancel_clip_btn.pack_forget()
                # On success the URL was replaced with the file path (button stays hidden);
                # if the URL is still there the download failed/was cancelled - offer retry.
                _still_url = self.v_video.get().strip()
                if _still_url.startswith('http') and not Path(_still_url).exists():
                    self._dl_btn.pack(side='right', padx=(2,0))
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
        _ensure_pkgs_on_path()

        # ── Check if AI packages installed ────────────────────────────────────
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

    def _save_settings(self):
        # (self._keys is already kept in sync with v_key by _on_key_changed and the
        #  Settings tab's _save_keys - do not re-flush v_key here, it can be stale)
        # Don't persist the grey placeholder text as real settings
        _ctx = self._ctx_text()
        _nm = self.v_names.get().strip() if hasattr(self, 'v_names') else ''
        if _nm == 'Mizkif, xQc, HasanAbi...': _nm = ''
        # Keep values that worker threads wrote straight to disk (not into self.cfg)
        try:
            _disk = load_cfg()
            for _k in ('launch_count', 'groq_tpd_until', 'dead_models'):
                if _k in _disk: self.cfg[_k] = _disk[_k]
        except Exception:
            pass
        # Merge everything into self.cfg so nothing gets lost
        self.cfg.update({
            'provider':          self.v_provider.get(),
            'model':             self.v_model.get(),
            'whisper':           self.v_whisper.get(),
            'use_gpu_whisper':   self.v_use_gpu_whisper.get() if hasattr(self, 'v_use_gpu_whisper') else True,
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
            'auto_transcribe':   self.v_auto_transcribe.get() if hasattr(self, 'v_auto_transcribe') else False,
            'thumb_outdir':      self.thumb_outdir_var.get() if hasattr(self, 'thumb_outdir_var') else '',
            'scan_folder':       self.v_scan_folder.get() if hasattr(self, 'v_scan_folder') else '',
            'up_out':            self.v_up_out.get() if hasattr(self, 'v_up_out') else '',
            'interview_mode':    self.interview_mode.get() if hasattr(self, 'interview_mode') else False,
            'interview_names':   _nm,
            'app_mode':          self.app_mode.get() if hasattr(self, 'app_mode') else 'normal',
            'video_context':     _ctx,
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

    def _quit(self):
        self._save_settings()
        global _GPU_ENCODER_CACHE
        _GPU_ENCODER_CACHE = None
        self.destroy()

    def log(self, msg, color=None):
        try: print(f'[CF] {msg}')
        except Exception: pass  # e.g. UnicodeEncodeError on a cp1252 redirected stdout
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
            _do_transcribe._cancelled = False  # drop a stale cancel left by a previous run
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
        # Kill any running export/queue ffmpeg process and any active Auto Edit ffmpeg process
        with self._ff_lock:
            _ffp = list(self._ff_procs)
        for _p in _ffp + list(getattr(self, '_ae_procs', [])):
            try: _p.kill()
            except Exception: pass
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

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE CENTER - app self-update, package versions/updates/repair, engines
    # (the logic lives in the module-level update manager; this is only the UI)
    # ══════════════════════════════════════════════════════════════════════════
    def _uc_app_file(self):
        return Path(__file__).resolve()

    def _uc_newer(self, rel):
        return bool(rel) and app_version_key(rel['version']) > app_version_key(APP_VERSION)

    def _relaunch_app(self, script=None):
        """Start a fresh ClipFinder and close this one - but only close once the new one is really up."""
        import subprocess as _sp, os as _os, time as _t
        script = script or self._uc_app_file()
        n = int(_os.environ.get('CF_RESTARTS', '0'))
        if n >= 3:
            messagebox.showinfo('Restart', 'Please start ClipFinder again manually.')
            return False
        try:
            um_release_instance_lock()                           # the new process takes it
            env = dict(_os.environ, CF_RESTARTS=str(n + 1))
            child = _sp.Popen(app_relaunch_cmd(script), env=env, close_fds=True,
                              creationflags=0x00000008 | 0x00000200)
            _t.sleep(1.6)
            if child.poll() is not None:
                raise RuntimeError(f'the new process exited immediately (code {child.returncode})')
        except Exception as e:
            um_acquire_instance_lock()
            um_log(f'relaunch failed: {e}')
            messagebox.showerror('Restart failed', f'ClipFinder could not restart itself:\n{e}\n\nPlease start it manually.')
            return False
        try:
            self.destroy()
        finally:
            _os._exit(0)

    def _apply_auto_update(self, new_version, release_data):
        """Download, validate and install a new ClipFinder release, then restart into it."""
        import threading as _thr
        win = tk.Toplevel(self)
        win.title('Updating ClipFinder')
        win.geometry('460x190')
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=f'⬇  Updating to ClipFinder v{new_version}', font=('Segoe UI', 11, 'bold'),
                 fg=ACCENT, bg=BG).pack(pady=(18, 6))
        st = tk.StringVar(value='Starting...')
        tk.Label(win, textvariable=st, font=FONT_SMALL, fg=FG2, bg=BG, wraplength=420, justify='center').pack()
        bar = self._uc_make_bar(win, 380)
        bar.pack(pady=12)
        bar.start()
        btn = tk.Button(win, text='Close', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, padx=14, pady=4,
                        command=win.destroy)

        def _say(msg):
            self.after(0, lambda: st.set(msg))

        def _work():
            try:
                target = self._uc_app_file()
                work = USER_DIR / '_update_work'
                newfile = app_download(release_data, work, _say)
                _say('Installing...')
                app_install(newfile, target)
                for name, rel in (('clipfinder_logo_512.png', 'assets/clipfinder_logo_512.png'), ('clipfinder.ico', 'clipfinder.ico')):
                    try:                                         # icons are best effort
                        _um_download(f'https://raw.githubusercontent.com/{APP_REPO}/{release_data["tag"]}/{rel}',
                                     target.parent / name, timeout=15)
                    except Exception:
                        pass
                app_set_registry_version(app_source_version(target.read_text(encoding='utf-8')) or new_version)
                _um_sh.rmtree(work, ignore_errors=True)
                _say('Done - restarting ClipFinder...')
                um_log(f'app updated to {new_version}')
                self.after(900, lambda: (win.destroy(), self._relaunch_app(target)))
            except Exception as e:
                um_log(f'app update failed: {e}')
                _why = str(e)                                   # `e` no longer exists once this block ends
                self.after(0, lambda: (bar.stop(), st.set(f'Update failed: {_why}\n\nNothing was changed - ClipFinder keeps running as it is.'),
                                       btn.pack(pady=4)))
        _thr.Thread(target=_work, daemon=True).start()

    # ── small canvas progress bar (indeterminate) ─────────────────────────────
    def _uc_make_bar(self, parent, width=400):
        cv = tk.Canvas(parent, width=width, height=6, bg=BG4, bd=0, highlightthickness=0)
        state = {'on': False, 'x': 0}

        def _tick():
            if not state['on']:
                return
            try:
                cv.delete('all')
                x = state['x'] % (width + 90)
                cv.create_rectangle(max(0, x - 90), 0, min(width, x), 6, fill=ACCENT, outline='')
                state['x'] += 9
                cv.after(28, _tick)
            except Exception:
                state['on'] = False

        cv.start = lambda: (state.update(on=True), _tick())
        cv.stop = lambda: (state.update(on=False), cv.delete('all'))
        return cv

    # ── launch-time + background checks ───────────────────────────────────────
    def _uc_show_banner(self, rel):
        """Inline 'update available' bar at the bottom of the window."""
        if getattr(self, '_uc_banner', None) is not None:
            try:
                if self._uc_banner.winfo_exists():
                    return
            except Exception:
                pass
        bar = tk.Frame(self, bg='#1e3a1e', height=32)
        bar.pack(side='bottom', fill='x')
        bar.pack_propagate(False)
        self._uc_banner = bar
        tk.Label(bar, text=f'⬆  ClipFinder v{rel["version"]} is available  -  you have v{APP_VERSION}',
                 font=('Segoe UI', 9, 'bold'), fg='#00ff88', bg='#1e3a1e').pack(side='left', padx=14)
        tk.Button(bar, text='⬇ Update now', font=('Segoe UI', 8, 'bold'), bg=ACCENT, fg='#000', relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=4,
                  command=lambda: (bar.destroy(), self._apply_auto_update(rel['version'], rel))).pack(side='left', padx=6)
        tk.Button(bar, text="What's new", font=('Segoe UI', 8), bg='#1e3a1e', fg='#00ff88', relief='flat', bd=0,
                  cursor='hand2', padx=8, pady=4, command=lambda: (self._switch_nb('settings'))).pack(side='left', padx=2)
        tk.Button(bar, text='✕', font=('Segoe UI', 10, 'bold'), fg='#00ff88', bg='#1e3a1e', relief='flat', bd=0,
                  cursor='hand2', padx=12, command=bar.destroy).pack(side='right', padx=8)
        self._uc_latest = rel

    def _uc_background(self):
        """Runs ~25s after launch: look for an app update, and keep yt-dlp & friends fresh (staged, applied
        at the next start - never while the app is using them)."""
        import threading as _thr

        def _work():
            try:
                if self.cfg.get('auto_check_updates', True):
                    rel = app_latest_release()
                    if self._uc_newer(rel):
                        self.after(0, lambda: self._uc_show_banner(rel))
                if self.cfg.get('auto_update_pkgs', True) and _um_time.time() - self.cfg.get('pkg_auto_ts', 0) > 12 * 3600:
                    self.cfg['pkg_auto_ts'] = _um_time.time()
                    save_cfg(self.cfg)
                    plan = pm_plan([e for e in PKG_REGISTRY if e['policy'] == 'latest'], online=True)
                    todo = [r for r in plan if r['state'] in ('outdated', 'below')]
                    if todo:
                        res = pm_stage(todo)
                        got = [f'{n} {v}' for r in res if r['ok'] for n, v in r['versions'].items()]
                        if got:
                            self.after(0, lambda g=got: self.log('⬆ Downloaded ' + ', '.join(g) + ' - applied next time you start ClipFinder', GREEN))
                            self.after(0, self._uc_refresh_pending)
            except Exception as e:
                um_log(f'background update check failed: {e}')
        _thr.Thread(target=_work, daemon=True).start()
        self.after(20000, app_mark_healthy)                       # a stable 45s = the update is confirmed good

    # ── Settings: Update Center ───────────────────────────────────────────────
    def _build_update_center(self, section):
        """Builds the ClipFinder Update + Update Modules + Music Removal engine sections."""
        import threading as _thr
        self._uc_busy = False
        self._uc_cancel = _thr.Event()
        self._uc_rows = []

        # ------------------------------------------------------------ ClipFinder update
        sa = section('⬆  ClipFinder Update', f'You are running v{APP_VERSION}')
        top = tk.Frame(sa, bg=BG3); top.pack(fill='x')
        self._uc_app_lbl = tk.Label(top, text='Click "Check for updates" to see if a newer version is available.',
                                    font=FONT_SMALL, fg=FG2, bg=BG3, anchor='w')
        self._uc_app_lbl.pack(side='left', fill='x', expand=True)
        btns = tk.Frame(sa, bg=BG3); btns.pack(fill='x', pady=(6, 0))
        self._uc_app_check = tk.Button(btns, text='🔍  Check for updates', font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000',
                                       relief='flat', bd=0, cursor='hand2', padx=12, pady=5, command=self._uc_check_app)
        self._uc_app_check.pack(side='left')
        self._uc_app_go = tk.Button(btns, text='⬇  Update now', font=('Segoe UI', 9, 'bold'), bg=BG4, fg=FG3,
                                    relief='flat', bd=0, padx=12, pady=5, state='disabled', command=self._uc_apply_latest)
        self._uc_app_go.pack(side='left', padx=6)
        tk.Button(btns, text='↶  Restore previous version', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=5, command=self._uc_rollback_app).pack(side='left', padx=(0, 6))
        tk.Button(btns, text='🌐  Releases page', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=5, command=lambda: __import__('webbrowser').open(f'https://github.com/{APP_REPO}/releases')
                  ).pack(side='left')
        self._uc_notes_holder = tk.Frame(sa, bg=BG3); self._uc_notes_holder.pack(fill='x')
        self._uc_notes = tk.Text(self._uc_notes_holder, height=7, font=('Consolas', 8), bg=BG4, fg=FG2, relief='flat', bd=6,
                                 wrap='word', state='disabled')
        self._uc_v_auto_app = tk.BooleanVar(value=self.cfg.get('auto_check_updates', True))
        self._uc_v_auto_pkg = tk.BooleanVar(value=self.cfg.get('auto_update_pkgs', True))

        def _save_toggles(*_):
            self.cfg['auto_check_updates'] = self._uc_v_auto_app.get()
            self.cfg['auto_update_pkgs'] = self._uc_v_auto_pkg.get()
            save_cfg(self.cfg)
        for txt, var in (('Check for ClipFinder updates when it starts', self._uc_v_auto_app),
                         ('Keep yt-dlp and other fast-moving modules up to date automatically (applied on next start)', self._uc_v_auto_pkg)):
            tk.Checkbutton(sa, text=txt, variable=var, command=_save_toggles, font=FONT_SMALL, fg=FG2, bg=BG3,
                           selectcolor=BG4, activebackground=BG3, cursor='hand2').pack(anchor='w', pady=(4, 0))

        # ------------------------------------------------------------ packages
        sp = section('🔄  Update Modules', 'Versions of everything ClipFinder is built on - update, install or repair')
        bar = tk.Frame(sp, bg=BG3); bar.pack(fill='x')
        self._uc_btn_check = tk.Button(bar, text='🔍  Check for updates', font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000',
                                       relief='flat', bd=0, cursor='hand2', padx=12, pady=5,
                                       command=lambda: self._uc_refresh(online=True, force=True))
        self._uc_btn_check.pack(side='left')
        self._uc_btn_all = tk.Button(bar, text='⬆  Update all', font=('Segoe UI', 9, 'bold'), bg=BG4, fg=FG, relief='flat',
                                     bd=0, cursor='hand2', padx=12, pady=5, command=self._uc_update_all)
        self._uc_btn_all.pack(side='left', padx=6)
        tk.Button(bar, text='🩹  Repair', font=FONT_SMALL, bg=BG4, fg=FG, relief='flat', bd=0, cursor='hand2', padx=10,
                  pady=5, command=self._uc_repair).pack(side='left')
        tk.Button(bar, text='📜  Update log', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=5, command=lambda: os.startfile(str(UPDATE_LOG)) if UPDATE_LOG.exists() else
                  messagebox.showinfo('Update log', 'Nothing has been logged yet.')).pack(side='left', padx=6)
        self._uc_cancel_btn = tk.Button(bar, text='✕ Cancel', font=FONT_SMALL, bg=RED, fg='#fff', relief='flat', bd=0,
                                        cursor='hand2', padx=10, pady=5, command=self._uc_cancel.set)
        self._uc_status = tk.Label(sp, text='', font=FONT_SMALL, fg=FG2, bg=BG3, anchor='w')
        self._uc_status.pack(fill='x', pady=(6, 0))
        self._uc_pbar = self._uc_make_bar(sp, 700)
        self._uc_pbar.pack(anchor='w', pady=(2, 0))
        self._uc_restart = tk.Frame(sp, bg='#1a3a1a')
        tk.Label(self._uc_restart, text='✅  Updates are ready - restart ClipFinder to finish', font=('Segoe UI', 9, 'bold'),
                 fg=GREEN, bg='#1a3a1a').pack(side='left', padx=10, pady=6)
        tk.Button(self._uc_restart, text='Restart now', font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000', relief='flat',
                  bd=0, cursor='hand2', padx=12, pady=3, command=lambda: self._relaunch_app()).pack(side='left')
        self._uc_table = tk.Frame(sp, bg=BG3); self._uc_table.pack(fill='x', pady=(8, 0))
        self._uc_log_box = tk.Text(sp, height=5, font=('Consolas', 7), bg=BG4, fg=FG3, relief='flat', bd=6, wrap='none', state='disabled')

        # first paint is instant and offline (reads the folder); Check for updates asks PyPI
        self._uc_refresh(online=False)
        self._uc_refresh_pending()
        self._install_all_fn = self._uc_install_required             # used by the first-run prompt
        self._dep_refresh_fn_uc = lambda: self._uc_refresh(online=False)

        # ------------------------------------------------------------ Music Removal engine
        se = section('🎵  Music Removal engine (Demucs)',
                     'Runs in its own environment, so updating it can never break anything else (and vice versa)')
        self._eng_lbl = tk.Label(se, text='', font=FONT_SMALL, fg=FG2, bg=BG3, anchor='w', justify='left')
        self._eng_lbl.pack(fill='x')
        er = tk.Frame(se, bg=BG3); er.pack(fill='x', pady=(6, 0))
        self._eng_btn = tk.Button(er, text='⬇  Install', font=('Segoe UI', 9, 'bold'), bg=ACCENT, fg='#000', relief='flat',
                                  bd=0, cursor='hand2', padx=12, pady=5, command=lambda: self._uc_engine_install('demucs'))
        self._eng_btn.pack(side='left')
        tk.Button(er, text='🗑  Remove', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=10,
                  pady=5, command=self._uc_engine_remove).pack(side='left', padx=6)
        self._uc_engine_refresh()

    # ── shared progress plumbing ──────────────────────────────────────────────
    def _uc_log(self, line):
        try:
            self._uc_log_box.pack(fill='x', pady=(6, 0))
            self._uc_log_box.config(state='normal')
            self._uc_log_box.insert('end', line[:160] + '\n')
            self._uc_log_box.see('end')
            self._uc_log_box.config(state='disabled')
            self._uc_status.config(text=line[:120], fg=FG2)
        except Exception:
            pass

    def _uc_set_busy(self, busy, text=''):
        self._uc_busy = busy
        try:
            if busy:
                self._uc_cancel.clear()
                self._uc_pbar.start()
                self._uc_cancel_btn.pack(side='right')
                self._uc_status.config(text=text, fg=ACCENT2)
                for b in (self._uc_btn_check, self._uc_btn_all):
                    b.config(state='disabled')
            else:
                self._uc_pbar.stop()
                self._uc_cancel_btn.pack_forget()
                for b in (self._uc_btn_check, self._uc_btn_all):
                    b.config(state='normal')
        except Exception:
            pass

    def _uc_refresh_pending(self):
        try:
            if pm_pending():
                self._uc_restart.pack(fill='x', pady=(6, 0), after=self._uc_pbar)
            else:
                self._uc_restart.pack_forget()
        except Exception:
            pass

    # ── app update handlers ───────────────────────────────────────────────────
    def _uc_check_app(self):
        import threading as _thr
        self._uc_app_check.config(state='disabled', text='Checking...')
        self._uc_app_lbl.config(text='Contacting GitHub...', fg=FG2)

        def _work():
            rel = app_latest_release()
            self.after(0, lambda: self._uc_check_app_done(rel))
        _thr.Thread(target=_work, daemon=True).start()

    def _uc_check_app_done(self, rel):
        self._uc_app_check.config(state='normal', text='🔍  Check for updates')
        if rel is None:
            self._uc_app_lbl.config(text='Could not reach GitHub - check your internet connection.', fg=YELLOW)
            return
        self._uc_latest = rel
        if self._uc_newer(rel):
            self._uc_app_lbl.config(text=f'⬆  v{rel["version"]} is available (you have v{APP_VERSION})', fg=GREEN)
            self._uc_app_go.config(state='normal', bg=ACCENT, fg='#000', cursor='hand2')
            self._uc_notes.pack(fill='x', pady=(6, 0))
            self._uc_notes.config(state='normal'); self._uc_notes.delete('1.0', 'end')
            self._uc_notes.insert('1.0', (rel.get('notes') or 'No release notes.')[:2500])
            self._uc_notes.config(state='disabled')
        else:
            self._uc_app_lbl.config(text=f'✅  You are up to date (v{APP_VERSION}).', fg=GREEN)
            self._uc_app_go.config(state='disabled', bg=BG4, fg=FG3)

    def _uc_apply_latest(self):
        rel = getattr(self, '_uc_latest', None)
        if not self._uc_newer(rel):
            return
        if messagebox.askyesno('Update ClipFinder', f'Update to v{rel["version"]} and restart now?\n\n'
                               'Your settings, keys and downloads are kept. The previous version is saved so you can go back.'):
            self._apply_auto_update(rel['version'], rel)

    def _uc_rollback_app(self):
        if not messagebox.askyesno('Restore previous version', 'Put back the version of ClipFinder that was installed before the '
                                   'last update, and restart?'):
            return
        ok, msg = app_rollback()
        if ok:
            messagebox.showinfo('Restored', msg + '\n\nClipFinder will restart.')
            self._relaunch_app()
        else:
            messagebox.showinfo('Restore previous version', msg)

    # ── package table ─────────────────────────────────────────────────────────
    def _uc_refresh(self, online=False, force=False):
        import threading as _thr
        if online:
            self._uc_set_busy(True, 'Checking PyPI for newer versions...')

            def _work():
                rows = pm_plan(online=True, force=force)
                self.after(0, lambda: (self._uc_set_busy(False), self._uc_render(rows, checked=True)))
            _thr.Thread(target=_work, daemon=True).start()
        else:
            self._uc_render(pm_plan(online=False), checked=False)

    def _uc_render(self, rows, checked):
        for w in self._uc_table.winfo_children():
            w.destroy()
        self._uc_rows = rows
        icon = {'ok': ('✅', GREEN), 'missing': ('○', FG3), 'below': ('⚠', YELLOW), 'outdated': ('⬆', ACCENT2), 'newer': ('•', FG2)}
        action = {'missing': '⬇ Install', 'below': '⬆ Fix', 'outdated': '⬆ Update', 'newer': '⬆ Upgrade', 'ok': '↻'}
        group = None
        todo = 0
        for r in rows:
            if r['group'] != group:
                group = r['group']
                tk.Label(self._uc_table, text=group.upper(), font=('Segoe UI', 7, 'bold'), fg=ACCENT, bg=BG3,
                         anchor='w').pack(fill='x', pady=(8, 1))
            fr = tk.Frame(self._uc_table, bg=BG3); fr.pack(fill='x', pady=1)
            ic, col = icon.get(r['state'], ('?', FG2))
            tk.Label(fr, text=ic, font=('Segoe UI', 9), fg=col, bg=BG3, width=2).pack(side='left')
            tk.Label(fr, text=r['name'], font=('Consolas', 8, 'bold'), fg=FG if r['installed'] else FG2, bg=BG3,
                     width=22, anchor='w').pack(side='left')
            inst = r['installed'] or ('not installed' + ('' if r['required'] else ' (optional)'))
            latest = f'  →  {r["latest"]}' if (checked and r['latest'] and r['state'] in ('outdated', 'below', 'newer')) else ''
            tk.Label(fr, text=f'{inst}{latest}', font=('Consolas', 8), fg=col if r['state'] != 'ok' else FG2, bg=BG3,
                     width=34, anchor='w').pack(side='left')
            tk.Label(fr, text=r.get('desc', ''), font=('Segoe UI', 7), fg=FG3, bg=BG3, anchor='w').pack(side='left', fill='x', expand=True)
            b = tk.Button(fr, text=action[r['state']], font=('Segoe UI', 8), bg=(ACCENT if r['state'] in ('missing', 'below', 'outdated') else BG4),
                          fg=('#000' if r['state'] in ('missing', 'below', 'outdated') else FG2), relief='flat', bd=0,
                          cursor='hand2', padx=8, pady=1, command=lambda e=r: self._uc_do([e], e['name']))
            b.pack(side='right')
            if r['state'] in ('missing', 'below', 'outdated') and (r['required'] or r['state'] != 'missing'):
                todo += 1
        self._uc_btn_all.config(text=f'⬆  Update all ({todo})' if todo else '⬆  Update all')
        if checked and not todo:
            self._uc_status.config(text='✅  Everything is up to date.', fg=GREEN)
        elif not checked:
            self._uc_status.config(text=f'{todo} update{"s" if todo != 1 else ""} needed - click "Check for updates" to see the latest versions.'
                                   if todo else '', fg=YELLOW if todo else FG2)

    def _uc_update_all(self):
        rows = [r for r in (self._uc_rows or pm_plan(online=False))
                if r['state'] in ('below', 'outdated') or (r['state'] == 'missing' and r['required'])]
        if not rows:
            messagebox.showinfo('Update all', 'Everything is up to date. Use "Check for updates" to look for newer versions.')
            return
        self._uc_do(rows, f'{len(rows)} module{"s" if len(rows) != 1 else ""}')

    def _uc_install_required(self):
        """Used by the first-run prompt: install every required module that is missing."""
        rows = [r for r in pm_plan(online=False) if r['state'] in ('missing', 'below') and r['required']]
        if rows:
            self._uc_do(rows, 'required modules')

    def _uc_repair(self):
        import threading as _thr
        if self._uc_busy:
            return
        self._uc_set_busy(True, 'Checking installed modules for conflicts...')

        def _work():
            entries = pm_repair_entries()
            self.after(0, lambda: self._uc_repair_go(entries))
        _thr.Thread(target=_work, daemon=True).start()

    def _uc_repair_go(self, entries):
        self._uc_set_busy(False)
        if not entries:
            self._uc_status.config(text='✅  No conflicts found between installed modules.', fg=GREEN)
            messagebox.showinfo('Repair', 'No conflicts found - the installed modules are consistent.')
            return
        names = ', '.join(e['name'] + (e.get('spec') or '') for e in entries)
        if messagebox.askyesno('Repair', f'Found modules that do not match each other. Reinstall these to fix it?\n\n{names}'):
            self._uc_do(entries, 'repair')

    def _uc_do(self, entries, label):
        """Download + verify entries in staging, then apply now if nothing they replace is loaded, else on restart."""
        import threading as _thr
        if self._uc_busy:
            return
        self._uc_set_busy(True, f'Downloading {label}...')
        self._uc_log_box.config(state='normal'); self._uc_log_box.delete('1.0', 'end'); self._uc_log_box.config(state='disabled')

        def _work():
            results = pm_stage(entries, on_line=lambda l: self.after(0, lambda l=l: self._uc_log(l)), cancel=self._uc_cancel)
            self.after(0, lambda: self._uc_done(entries, results))
        _thr.Thread(target=_work, daemon=True).start()

    def _uc_done(self, entries, results):
        self._uc_set_busy(False)
        ok = [n for r in results if r.get('ok') for n in r['names']]
        bad = [(n, r.get('error', '')) for r in results if not r.get('ok') for n in r['names']]
        loaded = [e['name'] for e in entries if e['name'] in ok and e.get('mod') and e['mod'].split('.')[0] in sys.modules]
        if ok and not loaded:
            pm_apply_staged()                                    # nothing they replace is in use: swap right now
            __import__('importlib').invalidate_caches()
        msg = []
        if ok:
            msg.append(('Installed ' if not loaded else 'Downloaded ') + ', '.join(ok) + ('' if not loaded else ' - restart ClipFinder to finish'))
        if bad:
            msg.append('Could not install: ' + '; '.join(f'{n} ({why})' for n, why in bad))
        for line in msg:
            self.log(('✅ ' if 'Could not' not in line else '⚠ ') + line, GREEN if 'Could not' not in line else YELLOW)
        self._uc_refresh(online=False)                            # redraws the table (and clears the status line)...
        self._uc_refresh_pending()
        self._uc_status.config(text='  |  '.join(msg) if msg else 'Cancelled.', fg=(YELLOW if bad else GREEN))   # ...so say the result last
        try:
            self._dep_refresh_fn()
        except Exception:
            pass

    # ── Music Removal engine ──────────────────────────────────────────────────
    def _uc_engine_refresh(self):
        try:
            st = eng_status('demucs')
            if st['installed']:
                self._eng_lbl.config(text=f'✅  Installed  -  Demucs {st["version"]}  +  PyTorch {st["torch"] or "?"}\n'
                                          f'Location: {st["path"]}', fg=FG2)
                self._eng_btn.config(text='↻  Update / Reinstall', bg=BG4, fg=FG)
            else:
                self._eng_lbl.config(text='Not installed. Music Removal needs a one-time download (about 700 MB).\n'
                                          'It installs into its own folder and does not touch your other modules.', fg=YELLOW)
                self._eng_btn.config(text='⬇  Install Music Removal engine', bg=ACCENT, fg='#000')
        except Exception:
            pass

    def _uc_engine_install(self, name='demucs', on_done=None, status_cb=None):
        """Build the engine in a side folder, self-test it, then swap it in. Safe to call from any tab."""
        import threading as _thr
        if getattr(self, '_uc_engine_busy', False):
            return
        self._uc_engine_busy = True
        cancel = _thr.Event()
        self.log('🎵 Installing the Music Removal engine (one-time download)...', ACCENT2)
        self.set_busy(True)
        self.set_progress('🎵 Installing Music Removal engine...', pct=None)

        def _line(l):
            self.after(0, lambda l=l: (self.set_progress(f'🎵 {l[:70]}', pct=None), status_cb(l) if status_cb else None))

        def _work():
            res = eng_install(name, on_line=_line, cancel=cancel)
            def _fin():
                self._uc_engine_busy = False
                self.set_busy(False)
                self.set_progress('', pct=0)
                self._uc_engine_refresh()
                if res['ok']:
                    self.log(f'✅ Music Removal engine ready (Demucs {res.get("version")})', GREEN)
                else:
                    self.log(f'❌ Music Removal engine: {res.get("error")}', RED)
                    messagebox.showerror('Music Removal engine', f'Could not install it:\n\n{res.get("error")}\n\nDetails are in the update log.')
                if on_done:
                    on_done(res)
            self.after(0, _fin)
        _thr.Thread(target=_work, daemon=True).start()

    def _uc_engine_remove(self):
        if eng_status('demucs')['installed'] and messagebox.askyesno('Remove engine', 'Remove the Music Removal engine and free the disk space?\nYou can install it again any time.'):
            eng_remove('demucs')
            self._uc_engine_refresh()

    def validate(self, need_ai=True, need_outdir=True):
        # Ensure pkgs/ is on path then check for whisper
        _ensure_pkgs_on_path()
        import importlib.util as _ilv
        _has_whisper = False
        # find_spec only locates the package - a real import here would load
        # ctranslate2 etc. on the UI thread (multi-second freeze, OSError on bad DLLs)
        for _wmod in ('faster_whisper', 'whisper'):
            try:
                if _ilv.find_spec(_wmod) is not None:
                    _has_whisper = True
                    break
            except Exception:
                pass
        # Also check by folder presence in PKGS_DIR (import may fail due to deps
        # but the package files are there and will work once deps load)
        if not _has_whisper:
            _has_whisper = (any(PKGS_DIR.glob('faster_whisper*')) or
                           any(PKGS_DIR.glob('whisper*')))
        # whisper.cpp alone is enough (_do_transcribe prefers it)
        if not _has_whisper:
            try: _has_whisper = bool(_find_whispercpp())
            except Exception: pass
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
        if mode == 'vision':
            from tkinter import messagebox as _mb
            _mb.showinfo('🎯 Vision Mode',
                'Vision Mode uses Gemini to visually analyze your video frames.\n\n'
                '✅ Can detect: clothing, scenes, gambling, visual context\n'
                '✅ Works for: "girl in white shirt", "outdoor scenes", "funny moments"\n\n'
                '⚠️ Takes 2-5x longer than Normal mode\n'
                '⚠️ Uses more Gemini API quota (sends video frames)\n'
                '⚠️ Best for videos under 60 minutes\n'
                '⚠️ Requires a Gemini API key in Settings\n\n'
                'Your Instructions box will be applied visually to the video.')
        self.app_mode.set(mode)
        self.interview_mode.set(mode == 'interview')
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
        if hasattr(self, 'mode_vision_btn'):
            self.mode_vision_btn.config(
                bg='#7C3AED' if m=='vision' else BG3, fg='#fff' if m=='vision' else FG)
        if hasattr(self, 'go_btn'):
            if m == 'vision':
                self.go_btn.config(text='🎯 VISION FIND CLIPS')
            else:
                self.go_btn.config(text='▶  FIND CLIPS')
        # Update instructions placeholder based on mode
        if hasattr(self, 'v_context'):
            _normal_ph = 'ignore last hour · skip gambling · focus on drama · only clips of [name]  (transcript-based only)'
            _vision_ph = 'girl in white shirt · gambling scenes · outdoor moments · funny reactions  (visual AI — sees the video)'
            cur = self.v_context.get('1.0', 'end').strip()
            if cur in (_normal_ph, _vision_ph, ''):
                self.v_context.config(state='normal')
                self.v_context.delete('1.0', 'end')
                self.v_context.insert('1.0', _vision_ph if m == 'vision' else _normal_ph)
                self.v_context.config(fg=FG3)

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

    # ── Drama Heatmap methods ─────────────────────────────────────────────────

    def _toggle_heatmap_mode(self):
        """Toggle heatmap mode on/off."""
        on = not self._heatmap_mode_on.get()
        self._heatmap_mode_on.set(on)
        if on:
            self._heatmap_toggle_btn.config(text='ON', bg=ACCENT, fg='#000')
            # Show transcribe button next to Find Clips
            self._hm_transcribe_btn.pack(side='right', padx=(0,4), before=self.go_btn)
            # If transcript already exists, build and show everything
            if hasattr(self, '_whisper_segments') and self._whisper_segments:
                self._heatmap_build(self._whisper_segments)
            else:
                self._hm_token_lbl.config(text='transcribe first', fg=FG2)
        else:
            self._heatmap_toggle_btn.config(text='OFF', bg=BG3, fg=FG2)
            # Hide transcribe button
            self._hm_transcribe_btn.pack_forget()
            # Hide all expanded elements
            self._heatmap_canvas.pack_forget()
            self._hm_hover_lbl.pack_forget()
            self._hm_select_hot_btn.pack_forget()
            self._hm_clear_btn.pack_forget()
            self._hm_slider_lbl.pack_forget()
            self._hm_slider.pack_forget()
            self._hm_token_lbl.config(text='')
            for z in self._hm_zones:
                z['selected'] = False

    def _heatmap_build(self, segments):
        """Score each ~60s chunk of the transcript and render the heatmap."""
        if not segments: return

        # Drama keywords weighted heavily
        _DRAMA_KEYWORDS = {
            'high': ['banned', 'exposed', 'leaked', 'cheating', 'drama', 'fight', 'arrested',
                     'sued', 'fired', 'lied', 'scam', 'racist', 'abuse', 'assault', 'criminal',
                     'grooming', 'underage', 'controversy', 'cancel', 'beef', 'diss', 'called out'],
            'med':  ['angry', 'mad', 'upset', 'crying', 'screaming', 'yelling', 'threatening',
                     'insane', 'crazy', 'wtf', 'hate', 'disgusting', 'pathetic', 'trash', 'clown',
                     'lying', 'fake', 'stupid', 'idiot', 'broke', 'homeless', 'embarrassing'],
            'low':  ['!', 'what', 'no way', 'bro', 'literally', 'actually', 'seriously', 'wait']
        }

        total_dur = segments[-1]['end'] if segments else 1
        chunk_size = 60  # seconds per zone

        zones = []
        t = 0.0
        while t < total_dur:
            t_end = min(t + chunk_size, total_dur)
            # Gather text for this window
            chunk_text = ' '.join(
                s['text'].lower() for s in segments
                if s['start'] < t_end and s['end'] > t
            )
            # Score it
            score = 1
            for kw in _DRAMA_KEYWORDS['high']:
                if kw in chunk_text: score += 2.5
            for kw in _DRAMA_KEYWORDS['med']:
                if kw in chunk_text: score += 1.2
            # Caps/exclamation ratio as excitement signal
            exclaim = chunk_text.count('!') + chunk_text.count('?!')
            score += min(exclaim * 0.4, 2.0)
            # Clamp to 1-10
            score = max(1, min(10, round(score)))
            zones.append({'start': t, 'end': t_end, 'score': score,
                          'selected': False, 'rect_id': None, 'score_id': None})
            t = t_end

        self._hm_zones = zones
        self._hm_built = True
        self._hm_total_segs = len(segments)

        # Auto-select hot zones by default
        self._heatmap_select_by_score(threshold=self._hm_threshold.get())

        # Now show all controls inline in header
        self._hm_select_hot_btn.pack(side='left', padx=(6,0))
        self._hm_clear_btn.pack(side='left', padx=(3,0))
        self._hm_slider_lbl.pack(side='left', padx=(8,2))
        self._hm_slider.pack(side='left')

        # Show canvas and hover label below header
        self._heatmap_canvas.pack(fill='x', pady=(2,0))
        self._hm_hover_lbl.pack(fill='x')
        self._heatmap_redraw()
        self._hm_update_token_estimate()

    def _heatmap_redraw(self):
        """Redraw all zone rectangles on the canvas."""
        if not self._hm_zones: return
        cv = self._heatmap_canvas
        cv.delete('all')
        w = cv.winfo_width() or 400
        h = 38
        total_dur = self._hm_zones[-1]['end']
        if total_dur <= 0: return

        for z in self._hm_zones:
            x1 = int((z['start'] / total_dur) * w)
            x2 = int((z['end']   / total_dur) * w)
            s  = z['score']  # 1-10

            # Color: cold=dark teal → warm=yellow → hot=red
            if s <= 3:
                r, g, b = 30, 80, 100
            elif s <= 5:
                r = int(30  + (s-3)/2 * 180)
                g = int(80  + (s-3)/2 * 140)
                b = int(100 - (s-3)/2 * 80)
            elif s <= 7:
                r = int(210 + (s-5)/2 * 30)
                g = int(220 - (s-5)/2 * 100)
                b = 20
            else:
                r = min(255, int(240 + (s-7)/3 * 15))
                g = max(0,   int(120 - (s-7)/3 * 120))
                b = 0
            fill_col = f'#{r:02x}{g:02x}{b:02x}'

            # Selected zones get a bright orange border + lighter fill
            if z['selected']:
                cv.create_rectangle(x1, 2, x2-1, h-2, fill=fill_col, outline=ACCENT, width=2)
                # Bright tick at bottom
                cv.create_rectangle(x1, h-5, x2-1, h-1, fill=ACCENT, outline='')
            else:
                # Dimmed
                dimmed = f'#{r//3:02x}{g//3:02x}{b//3:02x}'
                cv.create_rectangle(x1, 4, x2-1, h-4, fill=dimmed, outline='')

            # Score label inside zone if wide enough
            if (x2 - x1) > 24:
                cv.create_text((x1+x2)//2, h//2, text=str(s),
                               fill='#fff' if z['selected'] else '#555',
                               font=('Segoe UI', 7, 'bold'))

    def _heatmap_select_by_score(self, threshold=6):
        """Auto-select all zones at or above threshold score."""
        threshold = int(threshold)
        for z in self._hm_zones:
            z['selected'] = (z['score'] >= threshold)
        self._heatmap_redraw()
        self._hm_update_token_estimate()

    def _heatmap_clear_selection(self):
        """Deselect all zones."""
        for z in self._hm_zones:
            z['selected'] = False
        self._heatmap_redraw()
        self._hm_update_token_estimate()

    def _hm_update_token_estimate(self):
        """Show how much of the VOD is selected vs total."""
        if not self._hm_zones:
            self._hm_token_lbl.config(text='')
            return
        total = sum(z['end'] - z['start'] for z in self._hm_zones)
        selected = sum(z['end'] - z['start'] for z in self._hm_zones if z['selected'])
        if total <= 0:
            self._hm_token_lbl.config(text='')
            return
        pct = int(selected / total * 100)
        n_sel = sum(1 for z in self._hm_zones if z['selected'])
        n_tot = len(self._hm_zones)
        self._hm_token_lbl.config(
            text=f'{n_sel}/{n_tot} zones  ·  {pct}% of VOD selected')

    def _heatmap_preview_zone(self, zone):
        """Preview a heatmap zone using the same mechanism as clip card previews."""
        vid = self.v_video.get().strip()
        placeholder = getattr(self, '_video_placeholder', '')
        if not vid or vid == placeholder or not Path(vid).exists():
            messagebox.showwarning('No video', 'Load a local video file to preview zones.')
            return
        def _fmt(s):
            s = int(s)
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        clip = {
            'start': _fmt(zone['start']),
            'end':   _fmt(zone['end']),
            'title': f'heatmap_zone_{_fmt(zone["start"])}'
        }
        self.log(f'🌡 Previewing zone {clip["start"]} → {clip["end"]} (score {zone["score"]}/10)', ACCENT)
        self._open_clip_preview(vid, clip)

    def _hm_get_selected_transcript(self):
        """Return transcript lines filtered to only selected heatmap zones.
        Called by _start() when heatmap mode is on and zones are selected."""
        if not self._hm_zones or not any(z['selected'] for z in self._hm_zones):
            return None  # No selection — use full transcript
        if not hasattr(self, '_whisper_segments') or not self._whisper_segments:
            return None
        selected_lines = []
        for seg in self._whisper_segments:
            seg_mid = (seg['start'] + seg['end']) / 2
            for z in self._hm_zones:
                if z['selected'] and z['start'] <= seg_mid <= z['end']:
                    def _ts(s):
                        h2, rem = divmod(int(s), 3600)
                        m2, s2  = divmod(rem, 60)
                        return f'{h2:02d}:{m2:02d}:{s2:02d}'
                    selected_lines.append(f'[{_ts(seg["start"])}] {seg["text"].strip()}')
                    break
        return '\n'.join(selected_lines) if selected_lines else None


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
        _t = getattr(self, '_worker_thread', None)
        if _t is not None and _t.is_alive():
            messagebox.showinfo('Still stopping', 'The previous task is still shutting down. Try again in a few seconds.')
            return
        if not self.validate(need_ai=False, need_outdir=False): return
        self.running = True
        self.set_busy(True)
        self.log('Starting transcription...')
        self._worker_thread = threading.Thread(target=self._run_transcribe, args=(False,), daemon=True)
        self._worker_thread.start()

    def _start(self):
        if self.running: return
        _t = getattr(self, '_worker_thread', None)
        if _t is not None and _t.is_alive():
            messagebox.showinfo('Still stopping', 'The previous task is still shutting down. Try again in a few seconds.')
            return
        if not self.validate(need_ai=True): return
        mode = self.app_mode.get()
        if mode == 'interview':
            # Read from v_names (the visible Names: field) — interview_names_box removed from clip finder tab
            names = self.v_names.get().strip() if hasattr(self, 'v_names') else ''
            _ph = 'Mizkif, xQc, HasanAbi...'
            if names == _ph: names = ''
            self.cfg['interview_names'] = names
            save_cfg(self.cfg)

        self.running = True
        self.set_busy(True)
        self._show_empty()
        self.log('Starting...')
        self._worker_thread = threading.Thread(target=self._run_transcribe, args=(True,), daemon=True)
        self._worker_thread.start()


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
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
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
            self._last_transcribed_vid = str(vid)  # store immediately for thumbnail rendering
            model_size = self.v_whisper.get()
            # Store video duration for short-video clip length adjustment
            self._current_video_duration = 0  # reset so a previous video's value never leaks in
            try:
                import subprocess as _ffp_dur
                _ff_dur = find_ffmpeg() or 'ffmpeg'
                _r_dur = _ffp_dur.run([_ff_dur, '-i', vid], capture_output=True, text=True, timeout=10, errors='replace')
                import re as _re_dur2
                _dm = _re_dur2.search(r'Duration: (\d+):(\d+):(\d+)', _r_dur.stderr)
                if _dm:
                    self._current_video_duration = int(_dm.group(1))*3600 + int(_dm.group(2))*60 + int(_dm.group(3))
            except Exception:
                self._current_video_duration = 0
            if model_size in ('auto', '', None):
                # Smart auto: pick model based on video duration + GPU
                try:
                    import subprocess as _ffp, re as _re_dur
                    _ff_dur = ensure_ffmpeg()
                    _dur_r = _ffp.run([_ff_dur, '-i', vid],
                                      capture_output=True, text=True, timeout=10,
                                      errors='replace')
                    _dm = _re_dur.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur_r.stderr)
                    if _dm:
                        _h, _m, _s2 = _dm.groups()
                        _duration = int(_h)*3600 + int(_m)*60 + float(_s2)
                    else:
                        _duration = 0
                except Exception:
                    _duration = 0
                _use_gpu_auto = getattr(self, 'v_use_gpu_whisper', None)
                _use_gpu_auto = _use_gpu_auto.get() if _use_gpu_auto else True
                _dev_auto, _, _dev_label_auto = _detect_whisper_device(use_gpu=_use_gpu_auto)
                _has_gpu = _use_gpu_auto and any(x in _dev_label_auto for x in ('Vulkan', 'CUDA', 'DirectML', 'GPU'))
                if _use_gpu_auto and not _has_gpu:
                    # Check why GPU is unavailable
                    _wcpp = _find_whispercpp()
                    if not _wcpp:
                        _gpu_reason = 'whisper.cpp not installed — go to Settings → Core Dependencies'
                    else:
                        _gpu_reason = 'GPU not detected'
                    _dev_label_auto += f' (⚠ {_gpu_reason})'
                if _duration < 300:          # under 5 min
                    model_size = 'tiny' if not _has_gpu else 'base'
                elif _duration < 1200:       # 5-20 min
                    model_size = 'base'
                elif _duration < 3600:       # 20-60 min
                    model_size = 'small'
                else:                        # 60+ min VOD
                    model_size = 'medium' if _has_gpu else 'small'

                # If using whisper.cpp, cap to models actually downloaded
                if _has_gpu and 'whisper.cpp' in _dev_label_auto:
                    _wcpp_dir = _app_path('whisper_cpp')
                    _available = []
                    for _ms in ['tiny', 'base', 'small', 'medium']:
                        _mf = _wcpp_dir / 'models' / f'ggml-{_ms}.bin'
                        if _mf.exists():
                            _available.append(_ms)
                    if _available and model_size not in _available:
                        # Pick largest available model
                        _order = ['medium', 'small', 'base', 'tiny']
                        for _mo in _order:
                            if _mo in _available:
                                model_size = _mo
                                break
                self.log(f'[Auto] Video {_duration:.0f}s → whisper {model_size} (GPU={_has_gpu}, {_dev_label_auto})', FG2)
            self.log(f'Transcribing: {Path(vid).name}  [{model_size}]')

            _use_gpu_flag = getattr(self, 'v_use_gpu_whisper', None)
            _use_gpu_flag = _use_gpu_flag.get() if _use_gpu_flag else True

            _ff = ensure_ffmpeg()
            _ctx_prompt = self._ctx_text()

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
                                    progress_cb=_progress_cb,
                                    use_gpu=_use_gpu_flag,
                                    log_cb=lambda m, c=FG2: self.after(0, lambda: self.log(m, c)))
            self.ticker_on = False
            self.srt_result = result

            segs_raw = result.get('segments', [])
            self._whisper_segments = segs_raw
            self._whisper_vid = os.path.normcase(os.path.abspath(str(vid)))
            lines = []
            for seg in segs_raw:
                lines.append(f'[{ts(seg["start"])}] {seg["text"].strip()}')
            self.transcript = '\n'.join(lines)

            segs  = len(result.get('segments', []))
            words = len(self.transcript.split())

            def update_trans():
                if not hasattr(self, 'trans_box'): return  # tab not built yet
                self.trans_box.config(state='normal')
                self.trans_box.delete('1.0', 'end')
                self.trans_box.insert('1.0', self.transcript)
                self.trans_box.config(state='disabled')
                if hasattr(self, 'wcount_lbl'):
                    self.wcount_lbl.config(text=f'{segs} segments  ·  {words:,} words')
                # Only switch to transcript tab if this was a transcribe-only request
                if not then_ai:
                    self._switch_nb('transcript')
            self.after(0, update_trans)

            self.log(f'Transcription done: {segs} segments, {words:,} words', GREEN)
            self._last_transcribed_vid = str(vid)  # save for thumbnail rendering

            # Build heatmap if mode is on
            if getattr(self, '_heatmap_mode_on', None) and self._heatmap_mode_on.get():
                self.after(0, lambda s=segs_raw: self._heatmap_build(s))

            if then_ai:
                if not getattr(self, '_cancel_requested', False):
                    # Vision Mode: run visual frame analysis first to guide clip selection
                    if self.app_mode.get() == 'vision':
                        try:
                            _primary = self.cfg.get('key_gemini', '').strip()
                            _extras = [k.strip() for k in self.cfg.get('key_gemini_extra','').split(',') if k.strip()]
                            _gemini_keys = ([_primary] if _primary else []) + _extras
                            _instructions = self._ctx_text()
                            _vision_hits = self._run_vision_mode(vid, _instructions, _gemini_keys)
                            if _vision_hits:
                                _include_hits = _vision_hits.get('include', [])
                                _exclude_hits = _vision_hits.get('exclude', [])

                                # Pre-filter transcript: strip excluded sections before AI sees them
                                # Much more reliable than telling AI to "avoid" timestamps
                                if _exclude_hits:
                                    import re as _re_ts
                                    _orig_lines = self.transcript.split('\n')
                                    _filtered_lines = []
                                    _excluded_secs = sorted([h['timestamp'] for h in _exclude_hits])

                                    # Build excluded ranges — merge nearby timestamps into continuous blocks
                                    # If two excluded frames are within 3 minutes of each other,
                                    # treat everything between them as excluded too
                                    _merge_gap = 180  # 3 minutes
                                    _pad = 60  # extra padding before/after each block
                                    _ranges = []
                                    if _excluded_secs:
                                        _rs, _re2 = _excluded_secs[0] - _pad, _excluded_secs[0] + _pad
                                        for _es in _excluded_secs[1:]:
                                            if _es - _re2 <= _merge_gap:
                                                _re2 = _es + _pad  # extend current block
                                            else:
                                                _ranges.append((_rs, _re2))
                                                _rs, _re2 = _es - _pad, _es + _pad
                                        _ranges.append((_rs, _re2))

                                    self.log(f'🎯 Excluding {len(_ranges)} gambling block(s): ' +
                                             ', '.join(f'{int(r[0]//60)}:{int(r[0]%60):02d}-{int(r[1]//60)}:{int(r[1]%60):02d}' for r in _ranges), YELLOW)

                                    _stripped = 0
                                    for _tline in _orig_lines:
                                        _tm = _re_ts.match(r'\[(\d+):(\d+):(\d+)', _tline)
                                        if _tm:
                                            _lsec = int(_tm.group(1))*3600 + int(_tm.group(2))*60 + int(_tm.group(3))
                                            if any(_rs <= _lsec <= _re2 for _rs, _re2 in _ranges):
                                                _stripped += 1
                                                continue
                                        _filtered_lines.append(_tline)
                                    self.transcript = '\n'.join(_filtered_lines)
                                    _strip_msg = f'🎯 Vision pre-filter: stripped {_stripped} gambling lines — {len(_orig_lines)}→{len(_filtered_lines)} transcript lines'
                                    self.log(_strip_msg, GREEN)
                                    self.after(0, lambda: self.set_progress('⏳ Vision filtered transcript — AI finding clips... (may look frozen, let it run)', pct=45))

                                _vision_ctx = ''
                                if _include_hits:
                                    _ts_list = ', '.join(f'{int(h["timestamp"]//60)}:{int(h["timestamp"]%60):02d}' for h in _include_hits)
                                    _vision_ctx += f'\n\nVISION ANALYSIS — PRIORITIZE THESE TIMESTAMPS: {_ts_list}\nPrioritize clips at or near these timestamps.'
                                if _exclude_hits:
                                    _ts_excl = ', '.join(f'{int(h["timestamp"]//60)}:{int(h["timestamp"]%60):02d}' for h in _exclude_hits)
                                    _vision_ctx += f'\n\nNOTE: Gambling/casino content at {_ts_excl} was detected and removed from this transcript.'
                                self._vision_context = _vision_ctx
                            else:
                                self._vision_context = ''
                        except Exception as _ve:
                            self.log(f'⚠ Vision Mode error: {_ve}', YELLOW)
                            self.log('  Falling back to normal transcript analysis', FG2)
                            self._vision_context = ''
                    else:
                        self._vision_context = ''
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
                    _gemini_contents = 'IMPORTANT: Your entire response must be ONLY a JSON array starting with [. No ```json, no backticks, no text before or after the JSON.\n\n' + self._current_prompt
                    resp = _gemini_generate(client, try_model, _gemini_contents,
                                            _gemini_config(try_model, 8192, 0.3, json=True, think='low'))
                    return _safe_text(resp)
                except Exception as _e:
                    _es = str(_e)
                    # 429 = rate limit, 404 = model dead/not found — both try next model
                    if '429' in _es or 'RESOURCE_EXHAUSTED' in _es or '404' in _es or 'not found' in _es.lower() or 'NOT_FOUND' in _es:
                        last_err = _e; continue
                    raise
            raise last_err or Exception('Gemini quota exhausted')
        elif lib == 'groq':
            _ensure_pkgs_on_path()
            try:
                from groq import Groq as _G
            except ImportError:
                raise ImportError('groq package broken — go to Settings → Update All Packages')
            resp = _groq_chat(_G(api_key=key), model=model,
                              messages=[{'role': 'user', 'content': self._current_prompt}],
                              temperature=0.3, **_groq_kwargs(model, 3000))
            return _safe_text(resp)
        elif lib == 'openrouter':
            _ensure_pkgs_on_path()
            try:
                from openai import OpenAI as _O
            except ImportError:
                raise ImportError('openai package broken — go to Settings → Update All Packages')
            _or = _O(base_url='https://openrouter.ai/api/v1', api_key=key)
            resp = _or.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': self._current_prompt}],
                temperature=0.3, **_openrouter_kwargs(model, 8192))
            raw = _safe_text(resp)
            if resp.choices and resp.choices[0].finish_reason == 'length' and len(raw) > 100:
                self.log('[OpenRouter] Truncated — retrying condensed', YELLOW)
                resp2 = _or.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': self._current_prompt[:len(self._current_prompt)//2] + '\n\n[Top 3 clips as JSON only]'}],
                    temperature=0.3, **_openrouter_kwargs(model, 4096))
                raw = _safe_text(resp2)
            return raw
        raise ValueError(f'Unknown lib: {lib}')

    def _ctx_text(self):
        """Instructions box text, or '' when it only holds the grey placeholder."""
        if not hasattr(self, 'v_context'):
            return ''
        _t = self.v_context.get('1.0', 'end').strip()
        _phs = ('ignore last hour · skip gambling · focus on drama · only clips of [name]  (transcript-based only)',
                'girl in white shirt · gambling scenes · outdoor moments · funny reactions  (visual AI — sees the video)')
        return '' if _t in _phs else _t

    def _call_provider(self, prov_name, transcript_chunk):
        """Call a single provider, rotating through all configured keys. Returns clip list or raises."""
        data  = PROVIDERS[prov_name]
        lib   = data['lib']
        # A saved/selected model that is retired or dead falls back to the provider's best live one
        model = _pick_model(prov_name, self.v_model.get() if self.v_provider.get() == prov_name else '', 'extract')

        # Key pool: primary + enabled extras (disabled keys kept in cfg but skipped)
        _primary  = self._keys.get(prov_name, '').strip()
        _extras   = getattr(self, '_extra_keys', {}).get(prov_name, [])
        _enabled  = getattr(self, '_extra_keys_enabled', {}).get(prov_name, [])
        # Pad enabled list with True for any extras that don't have a flag yet
        _enabled_padded = _enabled + [True] * max(0, len(_extras) - len(_enabled))
        _active_extras  = [k for k, en in zip(_extras, _enabled_padded) if en and k]
        _all_keys = [k for k in [_primary] + _active_extras if k]
        _disabled_count = sum(1 for en in _enabled_padded[:len(_extras)] if not en)

        # ── Auto-cooldown filtering ────────────────────────────────────────────
        # Keys on cooldown are skipped — but only if other keys are available
        import time as _ktime
        def _key_fp(k): return k[:8] + k[-4:] if len(k) > 12 else k  # fingerprint for logging
        def _is_on_cooldown(k):
            _exp = self._key_cooldowns.get((prov_name, k), 0)
            return _ktime.time() < _exp
        def _cd_remaining(k):
            return max(0, int(self._key_cooldowns.get((prov_name, k), 0) - _ktime.time()))

        _cooled_keys = [k for k in _all_keys if _is_on_cooldown(k)]
        _key_pool    = [k for k in _all_keys if not _is_on_cooldown(k)]

        # Always log key pool state so we can diagnose issues
        self.log(f'[{prov_name}] Key pool: {len(_all_keys)} total, {len(_key_pool)} ready, {len(_cooled_keys)} on cooldown', FG2)
        if not _key_pool and _all_keys:
            _soonest = min(_all_keys, key=lambda k: self._key_cooldowns.get((prov_name, k), 0))
            _wait = _cd_remaining(_soonest)
            self.log(f'[{prov_name}] All keys on cooldown — soonest ready in {_wait//60}m{_wait%60:02d}s. Using anyway...', YELLOW)
            _key_pool = _all_keys

        if not _key_pool:
            if _disabled_count and not _primary:
                raise ValueError(f'No active API key for {prov_name} — all extra keys are disabled. Enable them in Settings.')
            raise ValueError(f'No API key for {prov_name}')

        if _cooled_keys:
            _total_all = len(_all_keys)
            for _ck in _cooled_keys:
                _rem = _cd_remaining(_ck)
                self.log(f'[{prov_name}] Key ..{_key_fp(_ck)} auto-paused — resumes in {_rem//60}m{_rem%60:02d}s', FG2)
            self.log(f'[{prov_name}] Using {len(_key_pool)}/{_total_all} keys ({len(_cooled_keys)} on cooldown)', FG2)
        elif _disabled_count:
            _total_all = 1 + len(_extras) if _primary else len(_extras)
            self.log(f'[{prov_name}] Using {len(_key_pool)}/{_total_all} keys ({_disabled_count} disabled in Settings)', FG2)

        # Build prompt
        ctx_raw = self._ctx_text()

        # Build smart context block — parse user instructions as AI directives
        context_block = ''
        # Inject vision mode results if available
        _vision_ctx = getattr(self, '_vision_context', '')
        if ctx_raw:
            context_block = f'''== ⚠️ MANDATORY EDITOR INSTRUCTIONS — MUST FOLLOW EXACTLY ==
The user has given you STRICT instructions. Violating ANY of these is a failure:

{ctx_raw}

ENFORCEMENT RULES:
- "ignore the last X minutes/hours" → calculate the timestamp and REJECT any clip whose start time is within that range. Do NOT output those clips.
- "ignore/skip [topic]" → if ANY part of a clip mentions that topic, REJECT the entire clip. Do not include it.
- "focus on [person/topic]" → ONLY include clips featuring that person or topic. Reject everything else.
- "only clips from [person]" → the speaker in the clip MUST be that person. Reject all others.
- Time ranges "skip X:XX:XX-X:XX:XX" → reject any clip overlapping that range.
Before outputting EACH clip, verify it passes ALL instructions above. If it fails ANY check, do not include it.
== END MANDATORY INSTRUCTIONS ==

'''

        # Auto-extract video title from filename — helps AI know who's in the video
        _vid_path = self.v_video.get().strip() if hasattr(self, 'v_video') else ''
        _vid_title = ''
        if _vid_path:
            import re as _re2
            _vid_title = Path(_vid_path).stem
            # Strip common suffixes like "- ClipFinder", "- Part 1", timestamps
            _vid_title = _re2.sub(r'\s*[-–]\s*ClipFinder.*$', '', _vid_title, flags=_re2.IGNORECASE)
            _vid_title = _re2.sub(r'\s*[-–]\s*Part\s*\d+.*$', '', _vid_title, flags=_re2.IGNORECASE)
            _vid_title = _re2.sub(r'\[.*?\]', '', _vid_title).strip()
        if _vid_title:
            context_block = f'VIDEO TITLE: {_vid_title}\n' + context_block
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
        if _vision_ctx:
            context_block += _vision_ctx + '\n'
        import re as _re
        ts_matches = _re.findall(r'\[(\d{2}:\d{2}:\d{2})', transcript_chunk)
        section_note = f'SECTION: {ts_matches[0]} → {ts_matches[-1]}. Find clips within this range only.\n' if len(ts_matches) >= 2 else ''
        app_mode = self.app_mode.get() if hasattr(self,'app_mode') else 'normal'
        if app_mode == 'interview':
            _ph = 'Mizkif, xQc, HasanAbi...'
            # Use the Names: field (top right of clip finder tab) — visible and familiar
            names = self.v_names.get().strip() if hasattr(self, 'v_names') else ''
            if names == _ph: names = ''
            # Also check interview_names_box as fallback (transcript sidebar)
            if not names and hasattr(self, 'interview_names_box'):
                try: names = self.interview_names_box.get('1.0', 'end').strip()
                except: pass
            names_list = ', '.join(n.strip() for n in names.replace(',','\n').splitlines() if n.strip()) or 'Unknown'
            prompt = INTERVIEW_CLIP_PROMPT.replace('{transcript}', transcript_chunk) \
                                          .replace('{names}', names_list) \
                                          .replace('{context_block}', context_block + section_note)
        else:
            prompt = AI_PROMPT.replace('{transcript}', transcript_chunk) \
                               .replace('{context_block}', context_block + section_note) \
                               .replace('{names_block}', names_block)

        # For very short videos (under 90s), relax clip length requirements
        _vid_dur = getattr(self, '_current_video_duration', 0)
        if _vid_dur and _vid_dur < 90:
            prompt = prompt.replace(
                'MINIMUM: 1 minute 00 seconds (60 seconds) — NO EXCEPTIONS',
                f'MINIMUM: 10 seconds (video is only {int(_vid_dur)}s total — use the whole thing if needed)'
            ).replace(
                'MAXIMUM: 2 minutes 40 seconds (160 seconds)',
                f'MAXIMUM: {int(_vid_dur)} seconds (full video length)'
            ).replace(
                'REJECT any clip under 60 seconds — do not output it.',
                'Include the clip even if it is short — this is a short video.'
            ).replace(
                'If under 60s, extend or drop it.',
                'Short clips are fine for short videos.'
            )

        # Append instructions reminder at the END so AI sees them right before outputting
        if ctx_raw:
            prompt += f'\n\n⚠️ FINAL CHECK BEFORE OUTPUT: Re-read these instructions and verify EVERY clip passes: {ctx_raw}\nRemove any clip that violates these instructions before outputting.'

        # Try each key in pool — ONLY rotate on confirmed rate-limit (429 / RESOURCE_EXHAUSTED)
        # Non-RL errors (auth, parse, network) raise immediately — no rotation
        _last_err = None
        _rotated  = False  # track if we've rotated at all this call
        for _ki, key in enumerate(_key_pool):
            try:
                if lib == 'gemini':
                    from google import genai as _g
                    client = _g.Client(api_key=key)
                    try_models = [model] + [m for m in _ai_models(prov_name, 'extract') if m != model]
                    last_merr = None
                    raw = None
                    _all_models_rl = True  # assume all rate-limited until one succeeds
                    _empty_err = None
                    for try_model in try_models:
                        try:
                            resp = _gemini_generate(client, try_model, prompt,
                                                    _gemini_config(try_model, 8192, 0.3, json=True, think='low'))
                            raw = _safe_text(resp)
                            if not raw:   # blocked / all tokens spent thinking -> next model
                                raw = None
                                last_merr = Exception('Gemini returned an empty response (blocked or out of tokens)')
                                continue
                            last_merr = None
                            _all_models_rl = False
                            break
                        except Exception as _e:
                            _es = str(_e)
                            if '429' in _es or 'RESOURCE_EXHAUSTED' in _es or 'quota' in _es.lower():
                                last_merr = _e; continue
                            if _is_model_gone_error(_e):
                                # Model retired/unavailable (404 / decommissioned) — mark dead and try next
                                _mark_model_dead(try_model)
                                self.log(f'⚠ Gemini model {try_model} unavailable — removed', YELLOW)
                                continue
                            _all_models_rl = False
                            raise
                    if last_merr is not None:
                        # All models rate-limited/empty for this key — raise so outer loop tries next key
                        self.log(f'[Google Gemini (Free)] Key {_ki+1}: no model returned a result', YELLOW)
                        raise last_merr
                    if raw is None and _empty_err is not None:
                        raise _empty_err
                    if raw is None:
                        raise Exception('All Gemini models unavailable (404) — update models list')

                elif lib == 'groq':
                    # Skip Groq if daily token limit already hit this session
                    if getattr(self, '_groq_tpd_exhausted', False):
                        raise Exception('Groq daily token limit exhausted — try again tomorrow')
                    _ensure_pkgs_on_path()
                    try:
                        from groq import Groq as _G
                    except ImportError:
                        raise ImportError('groq package broken — go to Settings → Update All Packages')
                    _groq_prompt = prompt
                    # Try each model — rotate on 429 to avoid hammering rate-limited model
                    all_groq_models = _ai_models(prov_name, 'extract') or [model]
                    groq_try_models = [m for m in ([model] + [m for m in all_groq_models if m != model]) if m not in _DEAD_MODELS]
                    raw = None
                    for _gm in groq_try_models:
                        # Free plan = 8K tokens/min per model: cap the request, but cut the TRANSCRIPT
                        # (not the prompt tail, which holds the instructions and the transcript's end)
                        _max_chars = _GROQ_MAX_PROMPT_CHARS
                        _cur_prompt = _groq_prompt
                        if len(_groq_prompt) > _max_chars:
                            _room = _max_chars - (len(_groq_prompt) - len(transcript_chunk))
                            if _room < 2000:
                                self.log(f'[Groq] {_gm}: prompt overhead leaves no room for transcript — skipping model', YELLOW)
                                continue
                            self.log(f'[Groq] {_gm}: truncating transcript chunk {len(transcript_chunk):,}->{_room:,} chars (8K tokens/min free limit)', YELLOW)
                            _cur_prompt = _groq_prompt.replace(
                                transcript_chunk, transcript_chunk[:_room] + '\n[Transcript truncated]', 1)
                        try:
                            resp = _groq_chat(_G(api_key=key), model=_gm,
                                              messages=[{'role':'user','content':_cur_prompt}],
                                              temperature=0.3, **_groq_kwargs(_gm, 2000))
                            if resp and resp.choices and resp.choices[0] and resp.choices[0].message:
                                raw = _safe_text(resp)
                                if raw:
                                    break
                                raw = None   # empty (reasoning ate the budget) -> next model
                        except Exception as _ge:
                            _ges = str(_ge)
                            if '429' in _ges or '413' in _ges:
                                # Check if it's daily token limit exhausted (TPD) vs per-minute (TPM)
                                if 'tokens per day' in _ges.lower() or 'TPD' in _ges:
                                    if not hasattr(self, '_groq_tpd_exhausted'):
                                        self._groq_tpd_exhausted = True
                                        self.log('⚠ Groq daily token limit reached — skipping Groq until tomorrow', YELLOW)
                                        import time as _tpd_t
                                        self.cfg['groq_tpd_until'] = _tpd_t.time() + 86400
                                        save_cfg(self.cfg)
                                    break
                                continue
                            if '403' in _ges and 'access denied' in _ges.lower():
                                # Groq 403 = account blocked or daily limit hit
                                if not hasattr(self, '_groq_tpd_exhausted'):
                                    self._groq_tpd_exhausted = True
                                    self.log('⚠ Groq access denied (403) — daily limit or account issue. Skipping until tomorrow.', YELLOW)
                                    import time as _tpd_t2
                                    self.cfg['groq_tpd_until'] = _tpd_t2.time() + 86400
                                    save_cfg(self.cfg)
                                break
                            if _is_model_gone_error(_ge) or ('400' in _ges and any(x in _ges.lower() for x in ['decommissioned', 'no longer support', 'deprecated', 'not found', 'does not exist'])):
                                # 400 model_decommissioned or 404 model_not_found
                                _mark_model_dead(_gm)
                                self.log(f'⚠ Model {_gm} decommissioned — removed automatically', YELLOW)
                                continue
                            raise
                    if raw is None:
                        # Phrased so _is_key_rl matches and the next key in the pool is tried
                        raise Exception('429 rate_limit_exceeded: all Groq models rate-limited (or returned no text) for this key')

                elif lib == 'openrouter':
                    _ensure_pkgs_on_path()
                    try:
                        from openai import OpenAI as _O
                    except ImportError:
                        raise ImportError('OpenAI package broken — go to Settings → Update All Packages')
                    _or = _O(base_url='https://openrouter.ai/api/v1', api_key=key)
                    if not hasattr(self, '_dead_or_models'): self._dead_or_models = {}  # model -> expiry timestamp
                    import time as _or_time
                    # Clear expired entries
                    self._dead_or_models = {m: exp for m, exp in self._dead_or_models.items() if _or_time.time() < exp}
                    _or_all = _ai_models(prov_name, 'extract')
                    _or_models = [m for m in _or_all if m not in self._dead_or_models] or list(_or_all)
                    _or_raw = None
                    for _orm in _or_models:
                        try:
                            _r = _or.chat.completions.create(
                                model=_orm, messages=[{'role':'user','content':prompt}],
                                temperature=0.3, **_openrouter_kwargs(_orm, 8192))
                            # Guard against None choices (OpenRouter error responses)
                            if not _r or not _r.choices or not _r.choices[0] or not _r.choices[0].message:
                                self._dead_or_models[_orm] = _or_time.time() + 600  # 10 min retry
                                self.log(f'[OpenRouter] {_orm} returned empty response, skipping...', YELLOW)
                                continue
                            _or_raw = _r.choices[0].message.content
                            if _or_raw: _or_raw = _or_raw.strip()
                            if not _or_raw:
                                self._dead_or_models[_orm] = _or_time.time() + 1800
                                continue
                            if _r.choices[0].finish_reason == 'length' and _or_raw:
                                self.log('[OpenRouter] Truncated — retrying condensed', YELLOW)
                                _r2 = _or.chat.completions.create(
                                    model=_orm,
                                    messages=[{'role':'user','content':prompt[:len(prompt)//2]+'\n\n[Top 3 clips JSON only]'}],
                                    temperature=0.3, **_openrouter_kwargs(_orm, 4096))
                                _or_raw = _safe_text(_r2) or _or_raw
                            break
                        except Exception as _orme:
                            _es = str(_orme).lower()
                            _ec = str(_orme)
                            if re.search(r'\b40[12]\b', _ec):
                                raise   # bad key / no credits: no other model can fix it (and 'User not found.' is not a dead model)
                            if '404' in _ec or 'no endpoints' in _es:
                                self._dead_or_models[_orm] = _or_time.time() + 1800  # 30 min
                                self.log(f'[OpenRouter] {_orm} dead (404), trying next model...', YELLOW)
                                continue
                            elif ('429' in _ec or 'temporarily' in _es or 'unavailable' in _es
                                  or 'overloaded' in _es or 'provider returned error' in _es
                                  or 'rate limit' in _es or 'rate_limit' in _es or 'rate-limit' in _es):
                                # Model is rate-limited or temporarily down — try next model
                                self._dead_or_models[_orm] = _or_time.time() + 300  # 5 min retry
                                self.log(f'[OpenRouter] {_orm} temporarily unavailable, trying next model...', YELLOW)
                                continue
                            raise
                    if _or_raw is None:
                        _dead_list = ', '.join(self._dead_or_models) if self._dead_or_models else 'unknown'
                        raise Exception(f'All OpenRouter models unavailable (tried: {_dead_list}). '
                                        'Free-tier models may be down. Try Gemini or Groq instead.')
                    raw = _or_raw
                else:
                    raise ValueError(f'Unknown lib: {lib}')


                if _rotated:
                    self.log(f'[{prov_name}] Key {_ki+1} succeeded after rotation', GREEN)
                break  # success — exit key loop

            except Exception as _ke:
                _ks = str(_ke).lower()
                _ks_raw = str(_ke)
                # Log exact error so we can diagnose
                self.log(f'[{prov_name}] Key {_ki+1} error: {_ks_raw[:150]}', FG2)
                # Strict rate-limit detection — only rotate on confirmed API signals
                _is_key_rl = (
                    ('429' in _ks and '404' not in _ks) or
                    'resource_exhausted' in _ks or
                    'too many requests' in _ks or
                    'rate limit exceeded' in _ks or
                    'rate_limit_exceeded' in _ks or
                    ('quota' in _ks and ('exceeded' in _ks or 'exhausted' in _ks))
                )
                # 401 — bad/expired key: auto-pause if we have other keys, else raise
                # (Gemini reports a bad key as 400 INVALID_ARGUMENT 'API key not valid' / API_KEY_INVALID)
                _is_auth_err = (
                    '401' in _ks or 'unauthorized' in _ks or 'invalid api key' in _ks or
                    'api key not valid' in _ks or 'api_key_invalid' in _ks or
                    'authentication' in _ks
                )
                # These are never fixable by rotation
                # (403/forbidden only count when the error is not really a 429 that merely mentions them)
                _is_hard_fatal = (
                    (('403' in _ks or 'forbidden' in _ks) and not _is_key_rl) or
                    'could not parse' in _ks or
                    'all openrouter models unavailable' in _ks
                )
                if _is_hard_fatal:
                    raise  # raise immediately, don't try other keys

                _should_pause = _is_key_rl or _is_auth_err
                _has_more_keys = _ki < len(_key_pool) - 1

        # Auto-cooldown: Gemini RPM resets in ~60s, daily quota in 24h
        # Groq: ~60s RPM reset. OpenRouter: varies. Use short cooldown first, escalate.
                if _should_pause and _has_more_keys:
                    # Smart cooldown: short for RPM-based limits (Gemini/Groq), longer for quota
                    import random as _rnd
                    _prev_cd  = self._key_cooldowns.get((prov_name, key), 0)
                    _has_prev = _prev_cd > _ktime.time() - 300  # was on cooldown recently
                    if 'gemini' in prov_name.lower():
                        _cd_secs = 90 if not _has_prev else _rnd.randint(55, 65) * 60
                    elif 'groq' in prov_name.lower():
                        _cd_secs = _rnd.randint(55, 70)
                    else:
                        _cd_secs = _rnd.randint(30, 40) * 60
                    _cd_disp = f'{_cd_secs//60}m{_cd_secs%60:02d}s' if _cd_secs >= 60 else f'{_cd_secs}s'
                    with self._key_cd_lock:
                        self._key_cooldowns[(prov_name, key)] = _ktime.time() + _cd_secs
                    _reason = 'rate-limited (429)' if _is_key_rl else 'auth error (401)'
                    self.log(
                        f'[{prov_name}] Key {_ki+1}/{len(_key_pool)} {_reason} — '
                        f'paused {_cd_disp} → trying key {_ki+2}...',
                        YELLOW)
                    def _schedule_resume(pn=prov_name, k=key, secs=_cd_secs):
                        def _resume_log():
                            import time as _rt
                            _rt.sleep(secs)
                            if self._key_cooldowns.get((pn, k), 0) <= _rt.time() + 5:
                                self.after(0, lambda: self.log(
                                    f'[{pn}] Key ..{_key_fp(k)} cooldown expired — re-enabled', GREEN))
                                with self._key_cd_lock:
                                    self._key_cooldowns.pop((pn, k), None)
                        import threading as _thr_r
                        _thr_r.Thread(target=_resume_log, daemon=True).start()
                    _schedule_resume()
                    _last_err = _ke
                    _rotated  = True
                    continue

                if _should_pause and not _has_more_keys:
                    import random as _rnd2
                    if 'gemini' in prov_name.lower():
                        _cd_secs2 = 90
                    elif 'groq' in prov_name.lower():
                        _cd_secs2 = _rnd2.randint(55, 70)
                    else:
                        _cd_secs2 = _rnd2.randint(30, 40) * 60
                    _cd_disp2 = f'{_cd_secs2//60}m{_cd_secs2%60:02d}s' if _cd_secs2 >= 60 else f'{_cd_secs2}s'
                    with self._key_cd_lock:
                        self._key_cooldowns[(prov_name, key)] = _ktime.time() + _cd_secs2
                    _reason2 = 'rate-limited' if _is_key_rl else 'auth error'
                    self.log(
                        f'[{prov_name}] Only key {_reason2} — paused {_cd_disp2} for next run',
                        YELLOW)
                    raise

                # Unknown error — raise immediately, no rotation
                raise

        # Parse JSON response
        clean = raw.strip()
        # Strip ALL markdown code fences (Gemini loves wrapping in ```json)
        clean = re.sub(r'```(?:json|JSON)?\s*', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'```\s*$', '', clean, flags=re.MULTILINE)
        clean = clean.replace('`', '').strip()
        # Strip any preamble text before the JSON array/object
        # Gemini sometimes says "Here are the clips:" before the JSON
        _arr_start = clean.find('[')
        _obj_start = clean.find('{')
        if _arr_start == -1 and _obj_start == -1:
            raise ValueError(f'Could not parse AI response: {raw[:200]}')
        # Pick whichever comes first
        if _arr_start != -1 and (_obj_start == -1 or _arr_start < _obj_start):
            clean = clean[_arr_start:]
        elif _obj_start != -1:
            clean = clean[_obj_start:]
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, list): return parsed
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list): return v
        except json.JSONDecodeError:
            pass

        # Try to repair truncated JSON — Gemini sometimes cuts off mid-response
        # Strategy: find all complete objects and wrap them in an array
        try:
            # Find the last complete object (ends with })
            last_complete = -1
            depth = 0
            in_str = False
            esc = False
            for i, ch in enumerate(clean):
                if esc: esc = False; continue
                if ch == '\\' and in_str: esc = True; continue
                if ch == '"' and not esc: in_str = not in_str; continue
                if in_str: continue
                if ch == '{': depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0: last_complete = i
            if last_complete > 0:
                repaired = clean[:last_complete+1]
                # Wrap in array if needed
                repaired = repaired.strip()
                if not repaired.startswith('['):
                    repaired = '[' + repaired
                if not repaired.endswith(']'):
                    repaired = repaired + ']'
                # Remove trailing comma before ]
                repaired = re.sub(r',\s*\]', ']', repaired)
                parsed = json.loads(repaired)
                if isinstance(parsed, list) and parsed:
                    return parsed
        except Exception:
            pass
        raise ValueError(f'Could not parse AI response: {raw[:200]}')

    def _run_vision_mode(self, vid, instructions, gemini_keys):
        """Vision Mode: sample video frames and send to Gemini for visual analysis."""
        import base64 as _b64, tempfile as _tmpf, time as _t
        _ensure_pkgs_on_path()
        import cv2 as _cv

        self.log('🎯 Vision Mode: sampling video frames...', ACCENT)
        self.set_progress('🎯 Vision Mode: extracting frames...', pct=5)

        cap = _cv.VideoCapture(str(vid))
        fps = cap.get(_cv.CAP_PROP_FPS) or 30
        total_frames = cap.get(_cv.CAP_PROP_FRAME_COUNT)
        duration = total_frames / fps
        cap.release()

        # Sample 1 frame every 30 seconds — good balance for long videos
        sample_interval = 30
        frame_times = list(range(0, int(duration), sample_interval))
        # Cap frame count here — ref images adjusted after load but we need a hard cap now
        _hard_cap = 60
        if len(frame_times) > _hard_cap:
            import random as _rnd_pre
            frame_times = sorted(_rnd_pre.sample(frame_times, _hard_cap))

        self.log(f'🎯 Sampling {len(frame_times)} frames from {int(duration/60)}min video...', FG2)

        # Extract frames
        frames_b64 = []
        cap = _cv.VideoCapture(str(vid))
        for ts in frame_times:
            cap.set(_cv.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            if not ret: continue
            # Resize to reduce tokens — 640px wide
            h, w = frame.shape[:2]
            if w > 640:
                frame = _cv.resize(frame, (640, int(h * 640 / w)))
            _, buf = _cv.imencode('.jpg', frame, [_cv.IMWRITE_JPEG_QUALITY, 70])
            frames_b64.append((ts, _b64.b64encode(buf.tobytes()).decode()))
        cap.release()

        self.log(f'🎯 Extracted {len(frames_b64)} frames — sending to Gemini Vision...', FG2)
        self.set_progress('🎯 Vision Mode: analyzing frames...', pct=20)

        if not frames_b64:
            raise Exception('Could not extract frames from video')

        # Build Gemini vision prompt
        # Load reference images from vision_refs folder
        _refs_dir = _app_path('vision_refs')
        _refs_dir.mkdir(exist_ok=True)
        _ref_images = []
        for _ref_file in sorted(_refs_dir.glob('*.png')) + sorted(_refs_dir.glob('*.jpg')) + sorted(_refs_dir.glob('*.jpeg')):
            try:
                import base64 as _b64r
                _ref_b64 = _b64r.b64encode(_ref_file.read_bytes()).decode()
                _ref_label = _ref_file.stem.replace('_', ' ').replace('-', ' ')
                _ref_images.append((_ref_label, _ref_b64, _ref_file.suffix.lower()))
            except Exception:
                pass

        # Build reference section for prompt
        _ref_prompt = ''
        if _ref_images:
            _ref_names = ', '.join(f'"{r[0]}"' for r in _ref_images)
            _ref_prompt = f'\n\nREFERENCE IMAGES PROVIDED: You will see {len(_ref_images)} reference image(s) at the start labeled: {_ref_names}. Use these as visual examples — if the user says "no gambling" and a reference shows a gambling site, flag any frame that looks like those references as something to EXCLUDE.'

        # Further reduce if we have reference images (they consume context space)
        max_frames = 30 if _ref_images else 60
        if len(frames_b64) > max_frames:
            import random as _rnd
            frames_b64 = sorted(_rnd.sample(frames_b64, max_frames), key=lambda x: x[0])
            self.log(f'🎯 Reduced to {max_frames} frames (reference images present)', FG2)

        vision_prompt = f"""You are analyzing video frames to find the best viral clips for a streaming content channel.

USER INSTRUCTIONS: {instructions or 'Find the most viral, dramatic, or entertaining moments'}{_ref_prompt}

You are looking at {len(frames_b64)} frames sampled every {sample_interval} seconds from a {int(duration/60)} minute video.
Each frame has a timestamp showing when it occurs in the video.

For each interesting moment you find, look at the visual content and identify:
- What is visually happening (people, actions, emotions, scene)
- Whether this matches the user's instructions
- The timestamp of this frame

If a frame shows content the user said to AVOID (e.g. "no gambling", "skip casino scenes") — still include it in the JSON but set confidence to 0.1 and set reason to start with "EXCLUDE: " so it can be filtered out.

Return a JSON array of ALL notable timestamps including exclusions. Format:
[
  {{"timestamp": 45, "reason": "Person reacting dramatically", "confidence": 0.9}},
  {{"timestamp": 180, "reason": "EXCLUDE: Gambling/casino site visible — slot machine game on screen", "confidence": 0.1}}
]

Only include confidence > 0.5 for things to FIND. Always include EXCLUDE entries regardless of confidence.
Return ONLY the JSON array, no other text."""

        # Build content with frames
        from google import genai as _gv
        if not gemini_keys:
            raise Exception('No Gemini API key — add one in Settings for Vision Mode')

        # Build multipart content — reference images first, then video frames
        contents = [vision_prompt]

        # Inject reference images at the start so Gemini knows what to look for/avoid
        for _ref_label, _ref_b64, _ref_ext in _ref_images:
            _mime = 'image/jpeg' if _ref_ext in ('.jpg', '.jpeg') else 'image/png'
            contents.append(f'\n[REFERENCE IMAGE: {_ref_label}]')
            contents.append({'inline_data': {'mime_type': _mime, 'data': _ref_b64}})
        if _ref_images:
            contents.append('\n[End of reference images — video frames follow:]')
        for ts, b64 in frames_b64:
            mm, ss = divmod(int(ts), 60)
            contents.append(f'\n[Frame at {mm}:{ss:02d}]')
            contents.append({
                'inline_data': {
                    'mime_type': 'image/jpeg',
                    'data': b64
                }
            })

        # Try each key + model combination with progressive frame reduction on failure
        raw = None
        last_vision_err = None
        vision_models = _ai_models('gemini', 'vision')
        # Progressive frame counts: try full → half → quarter
        # Each image frame ~1000-2000 tokens, so fewer frames = less likely to hit TPM
        # Even decimation (keeps coverage of the whole video); skip an attempt that is not smaller
        _frame_attempts = [frames_b64]
        for _sub in (frames_b64[::2], frames_b64[::4]):
            if 0 < len(_sub) < len(_frame_attempts[-1]):
                _frame_attempts.append(_sub)

        for _fattempt, _frames_subset in enumerate(_frame_attempts):
            if _fattempt > 0:
                self.log(f'🎯 Retrying with {len(_frames_subset)} frames (was {len(_frame_attempts[_fattempt-1])})...', FG2)
                # Rebuild contents with fewer frames
                contents = [vision_prompt]
                for _ref_label, _ref_b64, _ref_ext in _ref_images:
                    _mime = 'image/jpeg' if _ref_ext in ('.jpg', '.jpeg') else 'image/png'
                    contents.append(f'\n[REFERENCE IMAGE: {_ref_label}]')
                    contents.append({'inline_data': {'mime_type': _mime, 'data': _ref_b64}})
                if _ref_images:
                    contents.append('\n[End of reference images — video frames follow:]')
                for ts, b64 in _frames_subset:
                    mm, ss = divmod(int(ts), 60)
                    contents.append(f'\n[Frame at {mm}:{ss:02d}]')
                    contents.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})

            for _vkey in gemini_keys:
                for _vmodel in vision_models:
                    try:
                        from google import genai as _gv
                        client = _gv.Client(api_key=_vkey)
                        self.log(f'🎯 Trying {_vmodel} with {len(_frames_subset)} frames...', FG2)
                        resp = _gemini_generate(client, _vmodel, contents,
                                                _gemini_config(_vmodel, 8192, 0.2, json=True))
                        raw = _safe_text(resp) or None
                        if raw:
                            break
                    except Exception as _ve:
                        _ves = str(_ve)
                        if _is_model_gone_error(_ve):
                            _mark_model_dead(_vmodel)
                        if any(x in _ves for x in ['503', '429', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED', '404', 'too large', 'Request payload']):
                            last_vision_err = _ve
                            continue
                        raise
                if raw:
                    break
            if raw:
                break

        if not raw:
            raise Exception(f'Vision Mode failed after {len(_frame_attempts)} frame reduction attempts: {last_vision_err}')

        # Parse timestamps from response
        import json as _jv, re as _rev
        try:
            # Strip ALL markdown fences aggressively
            _clean = raw.strip()
            _clean = _rev.sub(r'^```(?:json)?\s*', '', _clean, flags=_rev.MULTILINE)
            _clean = _rev.sub(r'\s*```\s*$', '', _clean, flags=_rev.MULTILINE)
            _clean = _clean.replace('`', '').strip()
            _s, _e = _clean.find('['), _clean.rfind(']')
            if _s != -1:
                # A truncated response has no closing ']' — keep the tail so the repair below can run
                _clean = _clean[_s:_e+1] if _e > _s else _clean[_s:]
            else:
                # No array found — log what Gemini actually said
                self.log(f'⚠ Vision: Gemini returned non-JSON: {raw[:200]}', YELLOW)
                return None
            vision_hits = _jv.loads(_clean)
        except Exception as _pe:
            # Try bracket-depth repair for truncated responses
            try:
                _depth = 0; _last_obj = -1; _in_str = False; _esc = False
                for _ci, _ch in enumerate(_clean):
                    if _esc: _esc = False; continue
                    if _ch == '\\' and _in_str: _esc = True; continue
                    if _ch == '"': _in_str = not _in_str; continue
                    if _in_str: continue
                    if _ch == '{': _depth += 1
                    elif _ch == '}':
                        _depth -= 1
                        if _depth == 0: _last_obj = _ci
                if _last_obj > 0:
                    _repaired = '[' + _clean[_clean.find('{'):_last_obj+1] + ']'
                    _repaired = _rev.sub(r',\s*\]', ']', _repaired)
                    vision_hits = _jv.loads(_repaired)
                    self.log(f'🎯 Vision: repaired truncated JSON — got {len(vision_hits)} hits', FG2)
                else:
                    self.log(f'⚠ Vision parse failed: {_pe} — raw: {raw[:300]}', YELLOW)
                    return None
            except Exception:
                self.log(f'⚠ Vision parse failed: {raw[:300]}', YELLOW)
                return None

        # Normalise model output: 'M:SS' / 'H:MM:SS' / numeric-string / null timestamps and
        # non-dict items must not crash int()/.get() here or in the caller.
        def _vh_norm(h):
            if not isinstance(h, dict): return None
            try:
                t = sum(float(x) * 60 ** i
                        for i, x in enumerate(reversed(str(h.get('timestamp')).strip().split(':'))))
            except ValueError:
                return None
            if not (0 <= t < 1e9): return None
            h['timestamp'] = t
            return h
        vision_hits = [_h2 for _h2 in map(_vh_norm, vision_hits if isinstance(vision_hits, list) else []) if _h2]

        if not vision_hits:
            self.log('⚠ Vision Mode found no matching moments — try different instructions', YELLOW)
            return None

        # Separate include vs exclude based on EXCLUDE: prefix in reason
        _include_hits = [h for h in vision_hits if not str(h.get('reason','')).upper().startswith('EXCLUDE')]
        _exclude_hits = [h for h in vision_hits if str(h.get('reason','')).upper().startswith('EXCLUDE')]

        self.log(f'🎯 Vision: {len(_include_hits)} to include, {len(_exclude_hits)} to exclude', GREEN)
        for h in _include_hits[:5]:
            ts = h.get('timestamp', 0)
            mm, ss = divmod(int(ts), 60)
            self.log(f'  ✅ {mm}:{ss:02d} — {h.get("reason","?")}', FG2)
        for h in _exclude_hits[:5]:
            ts = h.get('timestamp', 0)
            mm, ss = divmod(int(ts), 60)
            self.log(f'  🚫 {mm}:{ss:02d} — {h.get("reason","?")}', YELLOW)

        return {'include': _include_hits, 'exclude': _exclude_hits}

    def _refine_clips(self, clips, min_sec=60, max_sec=160, ideal_sec=110):
        """Post-process raw AI clip suggestions into cleaner, better clips:
          • snap start/end to real transcript segment boundaries (no mid-word cuts)
          • enforce the 60–160s length rule in code, not just in the prompt
          • merge heavily-overlapping near-duplicates, keeping the higher-scored one
          • rank by score, then by hook/engagement/value/shareability sub-scores

        Safe by construction: if the transcript can't be parsed into segments,
        clips pass through with only length clamping + dedup (no snapping).
        """
        import re as _re_rf
        if not clips:
            return clips

        def _to_secs(t):
            try:
                p = str(t).split(':')
                if len(p) == 3: return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
                if len(p) == 2: return int(p[0]) * 60 + float(p[1])
                return float(t)
            except Exception:
                return None

        def _to_hms(s):
            s = max(0, int(round(s)))
            return f'{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}'

        # ── Parse transcript into ordered (start, end, text) segments ───────────
        # Main clip-finder transcript is "[HH:MM:SS] text" (single stamp); the
        # Auto-Edit path is "[HH:MM:SS -> HH:MM:SS] text". Support both. When a
        # segment has no explicit end, the next segment's start IS the boundary.
        raw = []
        for line in (self.transcript or '').splitlines():
            m2 = _re_rf.match(r'\[([\d:]+)\s*(?:->|[-→])\s*([\d:]+)\]\s*(.*)', line)
            if m2:
                s, e = _to_secs(m2.group(1)), _to_secs(m2.group(2))
                if s is not None:
                    raw.append((s, e, m2.group(3).strip()))
                continue
            m1 = _re_rf.match(r'\[([\d:]+)\]\s*(.*)', line)
            if m1:
                s = _to_secs(m1.group(1))
                if s is not None:
                    raw.append((s, None, m1.group(2).strip()))
        raw.sort(key=lambda x: x[0])
        segs = []
        for i, (s, e, t) in enumerate(raw):
            if e is None or e <= s:
                e = raw[i + 1][0] if i + 1 < len(raw) else s + 5.0
            segs.append((s, e, t))
        starts    = [s for s, _, _ in segs]
        total_end = segs[-1][1] if segs else 0

        def _snap_start(sec):
            best = starts[0]
            for s in starts:
                if s <= sec + 0.5:
                    best = s
                else:
                    break
            return best

        def _snap_end(start_sec, target):
            """Nearest segment boundary to `target`, preferring one right after a
            sentence-ending line so clips don't cut mid-thought."""
            nearest, nearest_gap = target, 1e9
            sentence, sentence_gap = None, 1e9
            for s, e, txt in segs:
                if e <= start_sec + 1:
                    continue
                gap = abs(e - target)
                if gap < nearest_gap:
                    nearest, nearest_gap = e, gap
                if txt.rstrip().endswith(('.', '!', '?', '…', '"')) and gap < sentence_gap:
                    sentence, sentence_gap = e, gap
            if sentence is not None and sentence_gap <= 8:
                return sentence
            return nearest

        def _subscore(c):
            tot = 0
            for k in ('hook', 'engagement', 'value', 'shareability'):
                try: tot += int(c.get(k, 0) or 0)
                except Exception: pass
            return tot

        def _sc(c):
            # model-supplied score may be '8/10', '8.5', None ... — never raise
            try: return int(float(str(c.get('score', 5) or 5).split('/')[0]))
            except Exception: return 5

        # ── Snap + length-enforce each clip ────────────────────────────────────
        refined = []
        for c in clips:
            s = _to_secs(c.get('start'))
            e = _to_secs(c.get('end'))
            if s is None or e is None or e <= s:
                continue
            if segs:
                s = _snap_start(s)
                dur = e - s
                if dur < min_sec:
                    e = min(total_end, s + ideal_sec)   # grow a too-short clip toward ideal
                elif dur > max_sec:
                    e = s + max_sec
                e = _snap_end(s, e)
                if e - s < min_sec:                      # snapping undershot — try again toward ideal
                    e = _snap_end(s, min(total_end, s + ideal_sec))
            if e - s < 45:                               # genuinely can't form a real clip
                continue
            if e - s > max_sec:                          # hard cap
                e = s + max_sec
            c = dict(c)
            c['start'], c['end'] = _to_hms(s), _to_hms(e)
            c['_dur'] = int(e - s)
            refined.append(c)

        # ── Merge heavy overlaps (keep higher score), then rank ────────────────
        refined.sort(key=lambda c: _to_secs(c['start']) or 0)
        kept = []
        for c in refined:
            cs, ce = _to_secs(c['start']), _to_secs(c['end'])
            merged = False
            for i, k in enumerate(kept):
                ks, ke = _to_secs(k['start']), _to_secs(k['end'])
                overlap = max(0, min(ce, ke) - max(cs, ks))
                shorter = min(ce - cs, ke - ks) or 1
                if overlap / shorter > 0.4:
                    better = (_sc(c), _subscore(c)) > (_sc(k), _subscore(k))
                    if better:
                        kept[i] = c
                    merged = True
                    break
            if not merged:
                kept.append(c)

        def _rank(c):
            return (-_sc(c), -_subscore(c))
        kept.sort(key=_rank)
        return kept

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

            # ── Instruction-based transcript pre-filtering ────────────────────
            # Parse instructions for time-based filters like "ignore last hour",
            # "skip first 30 minutes", "only process 1:00:00 to 2:00:00"
            ctx_raw = ''
            if hasattr(self, 'v_context'):
                ctx_raw = self._ctx_text()

            if ctx_raw and lines:
                import re as _re_inst
                _instr_lower = ctx_raw.lower()
                _orig_count = len(lines)

                # Get total video duration from last transcript timestamp
                _last_ts = 0
                for _l in reversed(lines):
                    _tm2 = _re_inst.match(r'\[(\d+):(\d+):(\d+)', _l)
                    if _tm2:
                        _last_ts = int(_tm2.group(1))*3600 + int(_tm2.group(2))*60 + int(_tm2.group(3))
                        break

                _filter_start = 0  # seconds from start to begin including
                _filter_end = _last_ts  # seconds from start to stop including

                # "ignore/skip last N hour(s)/minute(s)"
                # Match 'ignore last hour', 'ignore the last hour', 'ignore last 2 hours'
                _last_match = _re_inst.search(
                    r'(?:ignore|skip|no|exclude|don.t.process|dont.process)\s+(?:the\s+)?last\s+(\d+(?:\.\d+)?)\s*(hour|hr|minute|min)',
                    _instr_lower)
                if not _last_match:
                    # Also match bare 'ignore last hour' (no number = 1)
                    _lm_bare = _re_inst.search(
                        r'(?:ignore|skip)\s+(?:the\s+)?last\s+(hour|hr|minute|min)',
                        _instr_lower)
                    if _lm_bare:
                        _unit_b = _lm_bare.group(1)
                        _filter_end = max(0, _last_ts - (3600 if 'h' in _unit_b else 60))
                        self.log(f'📋 Instruction filter: skipping last 1 {_unit_b} → ends at {int(_filter_end//60)}:{int(_filter_end%60):02d}', FG2)
                if _last_match:
                    _amt = float(_last_match.group(1))
                    _unit = _last_match.group(2)
                    _secs = int(_amt * (3600 if 'h' in _unit else 60))
                    _filter_end = max(0, _last_ts - _secs)
                    self.log(f'📋 Instruction filter: skipping last {_amt} {_unit}(s) → transcript ends at {int(_filter_end//60)}:{int(_filter_end%60):02d}', FG2)

                # "ignore/skip first N hour(s)/minute(s)"
                _first_match = _re_inst.search(r'(?:ignore|skip|no)\s+(?:the\s+)?first\s+(\d+(?:\.\d+)?)\s*(hour|hr|minute|min)', _instr_lower)
                if _first_match:
                    _amt2 = float(_first_match.group(1))
                    _unit2 = _first_match.group(2)
                    _filter_start = int(_amt2 * (3600 if 'h' in _unit2 else 60))
                    self.log(f'📋 Instruction filter: skipping first {_amt2} {_unit2}(s) → transcript starts at {int(_filter_start//60)}:{int(_filter_start%60):02d}', FG2)

                # Apply time filter if any rules matched
                if _filter_start > 0 or _filter_end < _last_ts:
                    _filtered = []
                    for _l in lines:
                        _tm3 = _re_inst.match(r'\[(\d+):(\d+):(\d+)', _l)
                        if _tm3:
                            _lsec2 = int(_tm3.group(1))*3600 + int(_tm3.group(2))*60 + int(_tm3.group(3))
                            if _lsec2 < _filter_start or _lsec2 > _filter_end:
                                continue
                        _filtered.append(_l)
                    lines = _filtered
                    transcript = '\n'.join(lines)
                    self.log(f'📋 Transcript filtered: {_orig_count}→{len(lines)} lines after time filter', GREEN)


            # ── Chunk size based on provider capability ───────────────────────
            # Gemini 3.x/2.5 Flash: 1M token context — can handle entire transcripts
            # Groq gpt-oss (free plan): 8K tokens/min per model — request must stay tiny (~8k chars of transcript)
            # OpenRouter free: 262k-1M context models, but only 50 req/day — big chunks, few calls
            _prov_name = primary
            if 'gemini' in _prov_name.lower():
                CHARS_PER_CHUNK = 120000
            elif 'groq' in _prov_name.lower():
                CHARS_PER_CHUNK = 8000
            else:
                CHARS_PER_CHUNK = 40000
            full_text = transcript  # local copy — may have been time-filtered above (self.transcript stays full)

            # Heatmap mode: if zones are selected, restrict AI to selected transcript only
            _hm_filtered = None
            if (getattr(self, '_heatmap_mode_on', None) and self._heatmap_mode_on.get()
                    and any(z['selected'] for z in getattr(self, '_hm_zones', []))):
                _hm_filtered = self._hm_get_selected_transcript()
                if _hm_filtered:
                    # Keep only the selected-zone lines that survived earlier filters,
                    # and let them drive the chunking/assignments below.
                    _hm_set = set(_hm_filtered.splitlines())
                    _hm_lines = [_l for _l in lines if _l in _hm_set]
                    if _hm_lines:
                        lines = _hm_lines
                        full_text = '\n'.join(lines)
                        n_sel = sum(1 for z in self._hm_zones if z['selected'])
                        self.log(f'🌡 Heatmap: analyzing {n_sel} selected zones only', ACCENT)

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
                return _is_rate_limit_error(e)

            # Use app-level rate-limit tracking (self._rl_provs) so Settings panel
            # reflects live state and marks survive between runs for 5 minutes.
            import time as _time_rl
            _RL_EXPIRY = 300  # seconds before a rate-limit mark auto-clears

            def _mark_rl(prov):
                with self._rl_provs_lock:
                    _pool = [k for k in [self._keys.get(prov,'').strip()] + getattr(self,'_extra_keys',{}).get(prov,[]) if k]
                    if len(_pool) > 1:
                        _cur = getattr(self, '_key_index', {}).get(prov, 0)
                        _next = (_cur + 1) % len(_pool)
                        if not hasattr(self, '_key_index'): self._key_index = {}
                        self._key_index[prov] = _next
                        if _next != 0:
                            return  # still have keys to try
                    self._rl_provs.add(prov)
                    self._rl_since[prov] = _time_rl.time()
                # Refresh Settings panel dot colour immediately
                self.after(0, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)

            def _clear_rl(prov):
                with self._rl_provs_lock:
                    self._rl_provs.discard(prov)
                    self._rl_since.pop(prov, None)
                self.after(0, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)

            def _expire_rl():
                """Auto-clear providers whose rate-limit mark is older than 5 minutes."""
                now = _time_rl.time()
                with self._rl_provs_lock:
                    expired = [p for p, t in self._rl_since.items() if now - t > _RL_EXPIRY]
                    for p in expired:
                        self._rl_provs.discard(p)
                        self._rl_since.pop(p, None)
                if expired:
                    self.after(0, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)

            def _try_chunk(chunk, label, exclude=None, start_prov=None):
                _expire_rl()  # auto-clear stale rate-limit marks before each attempt
                exclude = exclude or set()
                # Start from assigned provider, skip any currently rate-limited
                _order = list(keyed)
                if start_prov and start_prov in _order:
                    idx = _order.index(start_prov)
                    _order = _order[idx:] + _order[:idx]
                # Try non-rate-limited providers first
                _dead = getattr(self, '_dead_models', set())
                _available = [p for p in _order if p not in self._rl_provs and p not in exclude and p not in _dead]
                _fallback  = [p for p in _order if p in self._rl_provs and p not in exclude and p not in _dead]
                _last_err  = None
                _fatal_err = None  # non-recoverable error (bad key, parse fail)
                for prov in _available + _fallback:
                    try:
                        self.log(f'[{label}] → {prov}...')
                        clips = self._call_provider(prov, chunk)
                        _clear_rl(prov)
                        self.log(f'[{label}] {prov} → {len(clips)} clips', GREEN)
                        return clips, prov
                    except Exception as ex:
                        s = str(ex).lower()
                        _last_err = ex
                        if _is_rate_err(ex):
                            _mark_rl(prov)
                            self.log(f'[{label}] {prov} rate-limited, trying next...', YELLOW)
                            continue
                        elif 'all openrouter models unavailable' in s:
                            # All OR models dead for this session — mark provider dead too
                            if not hasattr(self, '_dead_models'):
                                self._dead_models = set()
                            self._dead_models.add(prov)
                            self.after(0, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)
                            self.log(f'[{label}] {prov} all models unavailable — marked dead for session', RED)
                            _fatal_err = ex
                            continue
                        elif ('404' in s or 'no endpoints' in s or 'not found' in s) and '401' not in s:
                            if not hasattr(self, '_dead_models'):
                                self._dead_models = set()
                            self._dead_models.add(prov)
                            self.after(0, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)
                            self.log(f'[{label}] {prov} model unavailable (404) — skipping for session', RED)
                            _fatal_err = ex
                            continue
                        elif ('401' in s or 'invalid api key' in s or 'unauthorized' in s or 'authentication' in s
                              or 'api key not valid' in s or 'api_key_invalid' in s):
                            self.log(f'[{label}] {prov} invalid API key — check Settings', RED)
                            _fatal_err = ex
                            continue
                        elif '403' in s or 'access denied' in s or 'forbidden' in s:
                            self.log(f'[{label}] {prov} access denied — key may lack permissions', RED)
                            _fatal_err = ex
                            continue
                        elif 'no api key' in s or 'no key' in s:
                            self.log(f'[{label}] {prov} has no API key configured', YELLOW)
                            continue
                        elif 'could not parse' in s or 'json' in s:
                            self.log(f'[{label}] {prov} parse error: {str(ex)[:120]}', RED)
                            _fatal_err = ex
                            continue
                        self.log(f'[{label}] {prov} error: {str(ex)[:120]}', RED)
                        continue
                # Surface the most useful error
                _err_to_return = _fatal_err or _last_err
                return [], _err_to_return

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
                    limit = 14000  # keep in sync with CHARS_PER_CHUNK (Groq prompt cap in _call_provider)
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

            def _get_key_slots():
                """Build ordered slot list: one primary per provider first, then extras.
                Extras only used when transcript is long enough to need them.
                Mirrors the enabled/disabled logic in _call_provider exactly."""
                primary_slots = []
                extra_slots   = []
                for prov in keyed:
                    primary  = self._keys.get(prov, '').strip()
                    extras   = getattr(self, '_extra_keys', {}).get(prov, [])
                    enabled  = getattr(self, '_extra_keys_enabled', {}).get(prov, [])
                    enabled_padded = enabled + [True] * max(0, len(extras) - len(enabled))
                    active_extras  = [k for k, en in zip(extras, enabled_padded) if en and k.strip()]
                    if primary:
                        primary_slots.append((prov, 0, prov.split()[0]))
                    for ki, _ in enumerate(active_extras):
                        lbl = f'{prov.split()[0]}[key{ki+2}]'
                        extra_slots.append((prov, ki+1, lbl))
                return primary_slots, extra_slots

            # ── Assign chunks to providers ────────────────────────────────────
            # Strategy:
            # SHORT  (<40 lines):  Race mode — ONE slot per provider (primary only), first wins
            # MEDIUM (40-300):     One slot per provider (primary key), round-robin chunks
            # LONG   (300+ lines): One slot per provider first, then add extra keys if available
            #                      Extras unlock in rounds: primary×N, then primary+extra1×N, etc.
            assignments = []
            _MIN_LINES_TO_SPLIT = 40
            _LONG_THRESHOLD     = 300  # lines before extra keys unlock

            primary_slots, extra_slots = _get_key_slots()
            n_primary = len(primary_slots)

            if n_primary == 0:
                # fallback — shouldn't happen since keyed is non-empty
                for i, ch in enumerate(chunks):
                    assignments.append((ch, keyed[0], f'sec{i+1}/{n_chunks}'))

            elif len(lines) < _MIN_LINES_TO_SPLIT and n_chunks == 1:
                # SHORT: race mode — primary keys only, all get same chunk
                self.log(
                    f'Short transcript ({len(lines)} lines) — racing across '
                    f'{n_primary} provider(s) for fastest response', FG2)
                for prov, ki, lbl in primary_slots:
                    assignments.append((chunks[0], prov, f'{lbl} race'))

            else:
                # MEDIUM/LONG: determine active slots based on transcript length
                # Unlock extra keys in rounds based on how many lines per slot we want
                _lines_per_slot = 150  # target lines per worker
                _slots_needed   = max(n_primary, min(n_primary + len(extra_slots),
                                                      max(n_primary, len(lines) // _lines_per_slot)))
                # Build active slots: primaries first, then extras up to slots_needed
                active_slots = primary_slots + extra_slots[:max(0, _slots_needed - n_primary)]
                n_slots = len(active_slots)

                _prov_summary = ', '.join(
                    f'{p.split()[0]}×{sum(1 for s in active_slots if s[0]==p)}'
                    for p in keyed if any(s[0]==p for s in active_slots))
                self.log(
                    f'Splitting transcript ({len(lines)} lines) across '
                    f'{n_slots} slot(s) ({_prov_summary})', FG2)
                if extra_slots and n_slots > n_primary:
                    self.log(f'  Extra keys unlocked: {n_slots - n_primary} additional slot(s)', FG2)

                section_size = max(1, len(lines) // n_slots)
                for si, (prov, ki, lbl) in enumerate(active_slots):
                    sec_start = si * section_size
                    sec_end   = (si + 1) * section_size if si < n_slots - 1 else len(lines)
                    sec_lines = lines[sec_start:sec_end]
                    if not sec_lines: continue
                    sec_text   = '\n'.join(sec_lines)
                    sub_chunks = _chunks_for_prov(prov, sec_text)
                    for sci, sc in enumerate(sub_chunks):
                        full_lbl = f'{lbl} sec{si+1}'
                        if len(sub_chunks) > 1: full_lbl += f'.{sci+1}'
                        assignments.append((sc, prov, full_lbl))

            total_tasks = len(assignments)
            _mode = 'race' if (len(keyed) > 1 and len(lines) < _MIN_LINES_TO_SPLIT and n_chunks == 1) else 'parallel'
            self.log(
                f'Dispatching {total_tasks} task(s) across {len(keyed)} provider(s) [{_mode}]',
                YELLOW)

            task_results  = [None] * total_tasks
            completed     = [0]
            import threading as _thr, time as _time
            _rl_lock      = _thr.Lock()
            _cooling_down = [False]  # shared flag — all threads wait when True

            def _task_worker(idx, chunk, prov, label):
                # (No start stagger: tasks are dispatched sequentially with a cancel-aware
                # 5s gap in the dispatch loop below.)

                # Check cancel before starting
                if getattr(self, '_cancel_requested', False):
                    return

                # Wait if global cooldown is active
                while _cooling_down[0]:
                    if getattr(self, '_cancel_requested', False):
                        return
                    _time.sleep(2)

                # _try_chunk returns (clips, provider_name) when a provider answered,
                # or (clips, exception) when every provider failed. Only an Exception
                # is a real error — a provider name means it answered (maybe empty).
                clips, _res = _try_chunk(chunk, label, exclude=set(), start_prov=prov)
                last_err = _res if isinstance(_res, Exception) else None
                if not clips and _res is None:
                    # _try_chunk called no provider (all dead / rate-excluded) — not a clean empty
                    last_err = RuntimeError('no AI provider available (all dead or excluded)')

                # Determine if the failure is fatal (no point retrying)
                def _is_fatal(err):
                    if err is None: return False
                    s = str(err).lower()
                    return any(x in s for x in [
                        '401', 'invalid api key', 'unauthorized', 'authentication',
                        '403', 'forbidden', 'access denied',
                        'all openrouter models unavailable',
                        'no api key', 'no key configured',
                        'daily token limit exhausted',  # Groq TPD — fatal for session
                    ])

                # ── Retry policy ──────────────────────────────────────────────
                # Real ERROR (last_err is an Exception): retry on other providers.
                # Clean EMPTY (clips == [] with no Exception): that provider simply
                # found no clip in this section — cross-check with ONE other provider,
                # then accept it. No wasted retries, and an empty section is never
                # reported as an error.
                _retry = 0
                _excluded = {prov}
                _clean_empty = (not clips and last_err is None)
                while not clips and _retry < 3:
                    if getattr(self, '_cancel_requested', False):
                        return
                    if _is_fatal(last_err):
                        self.log(f'[{label}] Fatal error — not retrying: {str(last_err)[:100]}', RED)
                        break
                    # Empty section already cross-checked by a 2nd provider → accept
                    if _clean_empty and _retry >= 1:
                        break
                    _retry += 1
                    clips, _res = _try_chunk(chunk, label, exclude=_excluded, start_prov=None)
                    if isinstance(_res, Exception):
                        last_err = _res
                    elif clips or _res is not None:
                        last_err = None
                    else:            # no provider left to try — keep the earlier error
                        _retry -= 1  # this pass called nothing
                        break
                    _clean_empty = (not clips and last_err is None)
                    _excluded.add(prov)

                if not clips:
                    if last_err:
                        _err_msg = str(last_err)
                        if 'all openrouter models unavailable' in _err_msg.lower():
                            self.log(f'[{label}] OpenRouter: no working free models found. '
                                     'Try adding an OpenRouter API key with credits, or use Gemini/Groq.', RED)
                        elif '401' in _err_msg or 'invalid api key' in _err_msg.lower():
                            self.log(f'[{label}] Invalid API key — open Settings and re-enter your key', RED)
                        elif _is_fatal(last_err):
                            self.log(f'[{label}] Skipped — {_err_msg[:120]}', RED)
                        else:
                            self.log(f'[{label}] Skipped after {_retry} retr{"y" if _retry == 1 else "ies"}: {_err_msg[:100]}', RED)
                    else:
                        # Clean empty result — NOT an error, the section just had no clip
                        self.log(f'[{label}] No clip-worthy moment in this section', FG2)

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

            # Merge all results — in race mode multiple providers return clips for same content
            # Deduplicate by start timestamp, keeping the highest-scored version of each clip
            # (different providers may suggest the same moment with different scores/titles)
            _best_by_start = {}  # start -> best clip seen so far
            for result_list in task_results:
                for clip in (result_list or []):
                    k = clip.get('start', '')
                    if not k:
                        continue
                    existing = _best_by_start.get(k)
                    if existing is None:
                        _best_by_start[k] = clip
                    else:
                        # Keep higher score
                        try:
                            if int(clip.get('score', 5)) > int(existing.get('score', 5)):
                                _best_by_start[k] = clip
                        except (ValueError, TypeError):
                            pass  # keep existing on bad score values

            for k, clip in _best_by_start.items():
                if k not in seen_starts:
                    seen_starts.add(k)
                    all_clips.append(clip)

            if not all_clips:
                if getattr(self, '_cancel_requested', False):
                    return
                # Build a helpful error from what we know about the session
                _dead = getattr(self, '_dead_models', set())
                _rl   = getattr(self, '_rl_provs', set())
                _hint_parts = []
                if _dead:
                    _hint_parts.append(f'Dead/404 models: {", ".join(_dead)}')
                if _rl:
                    _hint_parts.append(f'Rate-limited: {", ".join(_rl)}')
                if not keyed:
                    _hint_parts.append('No API keys configured — add keys in Settings')
                _hint = ' | '.join(_hint_parts) if _hint_parts else 'All providers returned no clips'
                raise Exception(
                    f'No clips found. {_hint}\n\n'
                    'Suggestions:\n'
                    '• Check Settings → AI Provider Status for red/yellow dots\n'
                    '• OpenRouter free tier has very small context — try Gemini (free, huge context)\n'
                    '• If all dots are red/dead, the free model may be unavailable — try again later\n'
                    '• Verify your API key is correct in Settings')

            # ── Refine: snap cuts to sentence boundaries, enforce 60–160s length,
            #    merge overlapping near-duplicates, rank by score + sub-scores ──
            _pre = len(all_clips)
            all_clips = self._refine_clips(all_clips)
            self.log(f'Refined {_pre} → {len(all_clips)} clean, de-duplicated clips', FG2)

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
                    """Collect transcript text spoken within a clip's window.
                    Handles both '[HH:MM:SS] text' and '[HH:MM:SS -> HH:MM:SS] text'."""
                    s = _ts_to_secs(start_t)
                    e = _ts_to_secs(end_t)
                    lines_out = []
                    for line in transcript.splitlines():
                        m = _re_v.match(r'\[([\d:]+)(?:\s*(?:->|[-\u2192])\s*([\d:]+))?\]\s*(.*)', line)
                        if not m:
                            continue
                        ls = _ts_to_secs(m.group(1))
                        le = _ts_to_secs(m.group(2)) if m.group(2) else ls
                        # Include if the segment falls within / overlaps the clip window
                        if ls < e and (le > s or ls >= s):
                            lines_out.append(m.group(3).strip())
                    return ' '.join(lines_out)

                for clip in all_clips:
                    seg_text = _extract_segment_text(
                        clip.get('start','00:00:00'),
                        clip.get('end','00:01:00'),
                        self.transcript
                    )
                    if seg_text and len(seg_text) > 20:
                        # store the true transcript for accuracy checks, but KEEP the
                        # AI's summary/reason \u2014 only fill one in if it's missing
                        clip['_verified_text'] = seg_text
                        if not str(clip.get('reason', '')).strip():
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
            _m = str(sys.exc_info()[1])
            self.after(0, lambda m=_m: messagebox.showerror('AI analysis failed', m[:600]))
        finally:
            self.running = False
            self.after(0, lambda: self.set_busy(False))

    # ── Clip rendering ────────────────────────────────────────────────────────
    def _grab_frame(self, vid, time_str):
        """Extract a frame from a video at given timestamp. Returns PIL Image or None."""
        try:
            _ensure_pkgs_on_path()
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
        # Use stored last video path — v_video may contain placeholder text after tab switch
        vid = self.v_video.get()
        _ph = getattr(self, '_video_placeholder', '')
        if not vid or vid == _ph:
            vid = getattr(self, '_last_transcribed_vid', '') or getattr(self, '_last_dl_path', '') or vid
        # Normalize path and verify exists
        try:
            vid = str(vid).strip()
            if not Path(vid).exists():
                vid = getattr(self, '_last_transcribed_vid', '') or getattr(self, '_last_dl_path', '') or vid
        except Exception:
            vid = getattr(self, '_last_transcribed_vid', '') or vid

        # 2-column grid — wider cards, more readable
        COLS = 2
        for c in range(COLS):
            self.clip_frame.columnconfigure(c, weight=1, uniform='clipcol')

        for i, clip in enumerate(self.clips):
            var = tk.BooleanVar(value=False)  # unchecked by default — user picks what to export
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
            name_var = tk.StringVar(value=clip.get('filename') or re.sub(r'[\\/:*?"<>|]','',clip.get('title','clip'))[:40])
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
            _ensure_pkgs_on_path()
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
            # same fallback as _render_clips (v_video can hold placeholder text after a tab switch)
            vid = getattr(self, '_last_transcribed_vid', '') or getattr(self, '_last_dl_path', '')
        if not vid or not Path(vid).exists():
            messagebox.showerror('No video', 'Select a video file first.')
            return
        if not out.strip():
            messagebox.showerror('No output folder', 'Set an output folder first.')
            return
        self.set_busy(True)
        self.set_progress(f'Censoring {len(sel)} clips...', step=1, total=2)
        def _run():
            _td = None
            try:
                ff = ensure_ffmpeg()
                if not ff:
                    raise RuntimeError('ffmpeg not found')
                import tempfile as _tmp, shutil as _shu
                Path(out).mkdir(parents=True, exist_ok=True)
                _td = _tmp.mkdtemp(prefix='cf_')   # private per-run temp dir (no fixed/shared names)
                _failed = 0
                _used = set()

                def _ff(cmd, outp=None):
                    """Run ffmpeg; raise on non-zero exit or a missing/empty output file."""
                    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[-300:])
                    if outp and not (Path(outp).exists() and Path(outp).stat().st_size > 1000):
                        raise RuntimeError(f'ffmpeg produced no output: {Path(outp).name}')
                    return r

                for i, clip in enumerate(sel):
                    if getattr(self, '_cancel_requested', False):
                        self.log('⛔ Cancelled', YELLOW)
                        return
                    self.set_progress(f'Censoring clip {i+1}/{len(sel)}...', step=1, total=2, pct=int(i/len(sel)*100))
                    tmp_clip = str(Path(_td) / f'cf_censor_clip_{i}.mp4')
                    wav_in = str(Path(_td) / f'cf_cen_wav_{i}.wav')
                    wav_out = str(Path(_td) / f'cf_cen_out_{i}.wav')
                    try:
                        start_t = clip['_sv'].get() if '_sv' in clip else clip.get('start','00:00:00')
                        end_t   = clip['_ev'].get() if '_ev' in clip else clip.get('end','00:01:00')
                        _nv = clip.get('_name_var')
                        _ct = (_nv.get().strip() if _nv else '') or clip.get('title','clip')
                        title = re.sub(r'[\\/:*?"<>|\']', '', _ct).strip()[:45] or 'Clip'
                        if title.lower() in _used:
                            title = f'{title}_{i+1}'
                        _used.add(title.lower())
                        # First export the clip
                        _vcodec, _acodec, _extra = get_encoder(ff)
                        _ff([ff,'-y','-ss',start_t,'-to',end_t,'-i',vid,
                             '-c:v',_vcodec,'-c:a',_acodec]+_extra+[tmp_clip], tmp_clip)
                        # Then censor it
                        _wm = self.v_whisper.get(); _wm = 'base' if _wm == 'auto' else _wm
                        result = _do_transcribe(tmp_clip, _wm,
                                               initial_prompt=self.v_context.get('1.0','end').strip() or None,
                                               ffmpeg_path=ff, use_word_timestamps=True)
                        if result.get('_cancelled') or getattr(self, '_cancel_requested', False):
                            self.log('⛔ Cancelled', YELLOW)
                            return
                        segs = result.get('segments',[])
                        # Use censor tab words, fall back to CENSOR_WORD_LIST if empty
                        _cw = self._censor_words if self._censor_words else list(self.CENSOR_WORD_LIST)
                        words = [w.lower().strip() for w in _cw if w.strip()]
                        # Short roots that are also common inside innocent words (class, pass,
                        # assume, spice, cockpit...) only match as exact word / plural / listed suffix.
                        _AMBIG = {'ass','fag','spic','dick','cock','piss','kike','chink'}
                        _ONLY_PLURAL = {'spic','cock','fag','kike','chink'}
                        _SFX = ('s','es','ed','ing','in','er','ers','head','heads','hole','holes')
                        def _clip_word_match(w):
                            """Simple word match for clip censor."""
                            if len(w) < 2: return False
                            for b in words:
                                b = ''.join(c for c in b if c.isalpha())
                                if not b or len(b) < 3: continue
                                if w == b: return True
                                if b in _AMBIG:
                                    if w == b + 's': return True
                                    if b not in _ONLY_PLURAL and w in {b + x for x in _SFX}: return True
                                    continue
                                if w.startswith(b): return True
                                if len(b) <= 5 and b in w and len(w) <= len(b) + 8: return True
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
                            _ff([ff,'-y','-i',tmp_clip,'-vn','-ar','44100','-ac','2','-f','wav',wav_in], wav_in)
                            import numpy as _np
                            audio, sr = _sf.read(wav_in, dtype='float32')
                            beep = self._censor_make_beep(sr) if style=='beep' else None
                            if style=='mp3' and mp3 and Path(mp3).exists():
                                # let ffmpeg convert the MP3 to the clip's rate/channels (44.1kHz stereo)
                                _mp3_wav = str(Path(_td) / f'cf_cen_mp3_{i}.wav')
                                _ff([ff,'-y','-i',mp3,'-vn','-ar',str(sr),'-ac','2','-f','wav',_mp3_wav], _mp3_wav)
                                beep, _bsr = _sf.read(_mp3_wav, dtype='float32')
                            if style != 'silence' and (beep is None or len(beep) == 0):
                                beep = self._censor_make_beep(sr)   # no usable MP3 -> default beep, never leave it uncensored
                            if beep is not None and beep.ndim == 1 and audio.ndim == 2:
                                beep = _np.repeat(beep[:, None], audio.shape[1], axis=1)   # mono beep -> match audio channels
                            for s_t, e_t, _ in hits:
                                s,e = int(s_t*sr), min(int(e_t*sr), len(audio))
                                if e <= s: continue
                                if style=='silence' or beep is None: audio[s:e] = 0
                                else:
                                    b = beep
                                    if len(b) < e-s: b = _np.tile(b, ((e-s)//len(b)+1,1) if b.ndim==2 else (e-s)//len(b)+1)
                                    audio[s:e] = b[:e-s]
                            _sf.write(wav_out, audio, sr)
                            _crop = getattr(self,'v_crop_mode',None)
                            _crop = _crop.get() if _crop else 'normal'
                            def _mux(inv, wav, outp, vertical=False):
                                if vertical:
                                    _vf = self._get_vertical_vf(inv) or ['-vf','crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                                    _ff([ff,'-y','-i',inv,'-i',wav,'-map','0:v:0','-map','1:a:0']+_vf+
                                        ['-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-shortest',outp], outp)
                                else:
                                    _ff([ff,'-y','-i',inv,'-i',wav,'-map','0:v:0','-map','1:a:0',
                                        '-c:v','copy','-c:a','aac','-b:a','192k','-shortest',outp], outp)
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
                                _shu.copy2(tmp_clip,str(Path(out)/f'{title}.mp4'))
                                self.log(f'[Censor] Clean 16:9: {title}.mp4',GREEN)
                            if _crop in ('vertical','both'):
                                _vf = self._get_vertical_vf(tmp_clip) or ['-vf','crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                                _v916 = str(Path(out)/f'{title}_9x16.mp4')
                                _ff([ff,'-y','-i',tmp_clip]+_vf+['-c:v','libx264','-preset','fast',
                                    '-crf','18','-c:a','aac',_v916], _v916)
                                self.log(f'[Censor] Clean 9:16: {title}_9x16.mp4',GREEN)
                    except Exception as _ce:
                        _failed += 1
                        self.log(f'[Censor] clip {i+1} failed: {_ce}', RED)
                    finally:
                        for _f in (tmp_clip, wav_in, wav_out):
                            try: Path(_f).unlink()
                            except Exception: pass
                self.set_progress('Censor export done!', step=2, total=2, pct=100)
                if _failed:
                    _msg = f'{_failed} of {len(sel)} clips failed (see log). Others saved to {out}'
                    self.after(0, lambda m=_msg: messagebox.showwarning('Censor finished with errors', m))
                else:
                    _msg = f'Censored {len(sel)} clips → {out}'
                    self.after(0, lambda m=_msg: messagebox.showinfo('Done', m))
            except Exception:
                self.log(f'Censor clips error:\n{__import__("traceback").format_exc()}', RED)
            finally:
                if _td:
                    _shu.rmtree(_td, ignore_errors=True)
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
        if not vid or not Path(vid).exists():
            # same fallback as _render_clips (v_video can hold placeholder text after a tab switch)
            vid = getattr(self, '_last_transcribed_vid', '') or getattr(self, '_last_dl_path', '')
        if not vid or not Path(vid).exists():
            messagebox.showerror('No video', 'Select a video file first.')
            return
        self.set_busy(True)
        self.log(f'⚡ Auto Edit: processing {len(sel)} clip(s)...', ACCENT2)

        def _run():
            _td = None
            try:
                import subprocess as _sp, re as _re, tempfile as _tmp, shutil as _shu
                Path(out).mkdir(parents=True, exist_ok=True)
                _td = _tmp.mkdtemp(prefix='cf_')   # private per-run temp dir (no fixed/shared names)
                _failed = 0

                def _ff(cmd, outp=None):
                    """Run ffmpeg; raise on non-zero exit or a missing/empty output file."""
                    r = _sp.run(cmd, stdout=_sp.PIPE, stderr=_sp.PIPE)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[-300:])
                    if outp and not (Path(outp).exists() and Path(outp).stat().st_size > 1000):
                        raise RuntimeError(f'ffmpeg produced no output: {Path(outp).name}')
                    return r

                for i, clip in enumerate(sel):
                    if getattr(self, '_cancel_requested', False):
                        self.log('⛔ Cancelled', YELLOW)
                        return
                    self.set_progress(f'Auto Edit: clip {i+1}/{len(sel)}...', pct=int(i/len(sel)*100))
                    _junk = []   # temp files of this clip, removed in finally
                    try:
                        start_t = clip.get('_sv') and clip['_sv'].get() or clip.get('start','00:00:00')
                        end_t   = clip.get('_ev') and clip['_ev'].get() or clip.get('end','00:01:00')
                        _nv = clip.get('_name_var')
                        _at = (_nv.get().strip() if _nv else '') or clip.get('title','clip')
                        title = re.sub(r'[\\/:*?"<>|]', '', _at).strip()[:45] or 'Clip'

                        # Step 1: Extract raw clip
                        raw = str(Path(_td) / f'ae_raw_{i}.mp4')
                        _junk.append(raw)
                        _vcodec, _acodec, _extra = get_encoder(ff)
                        _ff([ff,'-y','-ss',start_t,'-to',end_t,'-i',vid,
                             '-c:v',_vcodec,'-c:a',_acodec]+_extra+[raw], raw)

                        # Step 2: Detect silence
                        _sil = _sp.run([ff,'-i',raw,'-af','silencedetect=noise=-35dB:d=0.3',
                                        '-f','null','-'], capture_output=True, text=True,
                                       encoding='utf-8', errors='replace')
                        sil_starts = [float(m) for m in _re.findall(r'silence_start: ([\d.]+)', _sil.stderr or '')]
                        sil_ends   = [float(m) for m in _re.findall(r'silence_end: ([\d.]+)', _sil.stderr or '')]

                        if not sil_starts:
                            # No silence — just copy
                            _shu.copy2(raw, str(Path(out) / f'{title} - ClipFinder - Part {i+1}.mp4'))
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
                        _dur = _sp.run([ff,'-i',raw], capture_output=True, text=True,
                                       encoding='utf-8', errors='replace')
                        _dm = _re.search(r'Duration: (\d+):(\d+):([\d.]+)', _dur.stderr or '')
                        if _dm:
                            h,m,s = _dm.groups()
                            total = int(h)*3600+int(m)*60+float(s)
                            if total > prev + 0.1:
                                keeps.append((prev, total))

                        if not keeps:
                            self.log(f'  Clip {i+1}: all silence, skipping', YELLOW)
                            continue

                        # Step 4: Concat non-silent segments. Segments are RE-ENCODED: with
                        # '-c copy' every cut snaps back to the previous keyframe, which
                        # duplicates/desyncs footage. The final concat can stay '-c copy'
                        # because all segments share the same codec parameters.
                        concat_list = str(Path(_td) / f'ae_list_{i}.txt')
                        _junk.append(concat_list)
                        with open(concat_list, 'w', encoding='utf-8') as cf:
                            for j, (ks, ke) in enumerate(keeps):
                                seg = str(Path(_td) / f'ae_seg_{i}_{j}.mp4')
                                _junk.append(seg)
                                _ff([ff,'-y','-ss',str(ks),'-to',str(ke),'-i',raw,
                                     '-c:v','libx264','-preset','veryfast','-crf','18',
                                     '-c:a','aac','-b:a','192k',seg])
                                cf.write("file '" + Path(seg).as_posix().replace("'", "'\\''") + "'\n")

                        out_path = str(Path(out) / f'{title} - ClipFinder - Part {i+1}.mp4')
                        _ff([ff,'-y','-f','concat','-safe','0','-i',concat_list,
                             '-c','copy', out_path], out_path)

                        removed = sum(e-s for s,e in zip(sil_starts, sil_ends))
                        self.log(f'  ✅ Clip {i+1}: removed {removed:.1f}s silence → {out_path.split(chr(92))[-1]}', GREEN)
                    except Exception as _ce:
                        _failed += 1
                        self.log(f'  Clip {i+1} failed: {_ce}', RED)
                    finally:
                        # Cleanup (also on continue / exception paths)
                        for _f in _junk:
                            try: Path(_f).unlink()
                            except Exception: pass

                self.set_progress(f'⚡ Auto Edit done! {len(sel)-_failed}/{len(sel)} clips processed', pct=100)
                if _failed:
                    _msg = f'{_failed} of {len(sel)} clip(s) failed (see log)\nOthers saved to: {out}'
                    self.after(0, lambda m=_msg: messagebox.showwarning('Auto Edit finished with errors', m))
                else:
                    _msg = f'Processed {len(sel)} clip(s)\nSaved to: {out}'
                    self.after(0, lambda m=_msg: messagebox.showinfo('Auto Edit Done', m))
            except Exception:
                import traceback as _tb
                self.log(f'Auto Edit error:\n{_tb.format_exc()}', RED)
            finally:
                if _td:
                    _shu.rmtree(_td, ignore_errors=True)
                self.set_busy(False)

        threading.Thread(target=_run, daemon=True).start()

    def _export_or_censor(self):
        """Export selected clips — with censoring if censor toggle is on."""
        if getattr(self, 'censor_toggle', None) and self.censor_toggle.get():
            self._censor_selected_clips()
        else:
            self._export_selected()

    def _resolve_export_video(self):
        """Source video for export: the Video field, else the last transcribed/downloaded file."""
        v = (self.v_video.get() or '').strip()
        if not v or v == getattr(self, '_video_placeholder', '') or not Path(v).is_file():
            v = (getattr(self, '_last_transcribed_vid', '') or getattr(self, '_last_dl_path', '') or '').strip()
        return v if v and Path(v).is_file() else ''

    def _run_ff(self, cmd, stdout=None, stderr=None):
        """subprocess.run for export/queue ffmpeg jobs; the process is tracked so Cancel can kill it."""
        p = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        with self._ff_lock:
            self._ff_procs.append(p)
        try:
            out, err = p.communicate()
        finally:
            with self._ff_lock:
                if p in self._ff_procs: self._ff_procs.remove(p)
        return subprocess.CompletedProcess(cmd, p.returncode, out, err)

    def _export_selected(self):
        if getattr(self, '_export_running', False):
            return
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Check at least one clip.')
            return
        if not self._resolve_export_video() or not self.v_outdir.get().strip():
            messagebox.showwarning('Missing', 'Set a valid video file and output folder first.')
            return
        self._export_running = True
        self.set_busy(True)
        threading.Thread(target=self._do_export, args=(sel,), daemon=True).start()

    def _autocut(self):
        if getattr(self, '_export_running', False):
            return
        if not self.clips:
            messagebox.showwarning('No clips', 'Run FIND CLIPS first.')
            return
        # Sort by score desc and take top 3 — not just first 3 chronologically
        def _score(c):
            try: return -int(c.get('score', 5))
            except: return -5
        best3 = sorted(self.clips, key=_score)[:3]
        if not self._resolve_export_video() or not self.v_outdir.get().strip():
            messagebox.showwarning('Missing', 'Set a valid video file and output folder first.')
            return
        self._export_running = True
        self.set_busy(True)
        threading.Thread(target=self._do_export, args=(best3,), daemon=True).start()



    def _run_export_queue(self):
        if getattr(self, '_export_running', False):
            return
        if not hasattr(self, '_export_queue') or not self._export_queue:
            messagebox.showwarning('Empty Queue', 'Add clips to queue first.')
            return
        self._export_running = True
        self.set_busy(True)
        jobs = list(self._export_queue)
        self._export_queue.clear()
        try:
            self.queue_lb.delete(0, 'end')
            self._queue_strip.pack_forget()
        except: pass
        threading.Thread(target=self._process_queue, args=(jobs,), daemon=True).start()

    def _add_to_queue(self):
        """Add currently selected clips to the export queue."""
        sel = [self.clips[i] for i, v in enumerate(self.clip_vars) if v.get()]
        if not sel:
            messagebox.showwarning('Nothing selected', 'Select clips first.')
            return
        vid = self._resolve_export_video()
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
        try:
            self.queue_lb.insert('end', label)
            self._queue_strip.pack(fill='x', padx=8, pady=(0,2), before=self.clip_canvas.master)
        except Exception: pass
        self.log(f'Added to queue: {label}', GREEN)

    def _clear_queue(self):
        self._export_queue.clear()
        try:
            self.queue_lb.delete(0, 'end')
            self._queue_strip.pack_forget()
        except Exception: pass
        self.log('Queue cleared.')

    def _run_queue(self):
        if not self._export_queue:
            messagebox.showwarning('Empty', 'Queue is empty. Add clips first.')
            return
        self.set_busy(True)
        threading.Thread(target=self._process_queue, daemon=True).start()

    def _process_queue(self, jobs=None):
        try:
            self._process_queue_inner(jobs)
        except Exception:
            _qe = traceback.format_exc()
            self.log(f'Queue error:\n{_qe}', RED)
            self.after(0, lambda: self.set_busy(False))
        finally:
            self._export_running = False

    def _process_queue_inner(self, jobs=None):
        import shutil as _shq
        queue = jobs or self._export_queue or []
        total_ok = 0; total_clips = 0
        ff = find_ffmpeg()
        if not ff or (not _shq.which(ff) and not Path(ff).exists()):
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
                r = self._run_ff([ff,'-y','-ss',start,'-to',end,'-i',vid,
                                  '-c:v',_vcodec,'-c:a',_acodec]+_extra+[dest],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if r.returncode != 0 and getattr(self, '_cancel_requested', False):
                    try: Path(dest).unlink()
                    except OSError: pass
                    return
                if r.returncode == 0:
                    total_ok += 1
                    self.log(f'  ✅ {fname}', GREEN)
                else:
                    self.log(f'  ❌ Export failed for {fname}', RED)
                total_clips += 1
        self.log(f'Queue done: {total_ok}/{total_clips} clips exported.', GREEN)
        self.set_progress(f'✅ Queue done: {total_ok}/{total_clips} clips exported', pct=100)
        self.after(0, lambda: self.set_busy(False))
        if jobs is None:
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
        import time as _t
        _tdir = Path(_tmp_prev.gettempdir())
        for _old in _tdir.glob('cf_preview_*.mp4'):
            try:
                if _t.time() - _old.stat().st_mtime > 3600: _old.unlink()
            except OSError: pass          # locked by an open player - skip
        tmp = _tdir / f'cf_preview_{int(_t.time()*1000)}.mp4'
        self.log(f'Cutting preview: {start} → {end}', FG2)
        self.set_progress('Cutting preview...', pct=50)

        def _cut_and_open():
            try:
                r = subprocess.run(
                    [ff, '-y', '-ss', start, '-to', end, '-i', vid,
                     '-c', 'copy', str(tmp)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Stream copy can produce tiny/broken files on some containers
                _size = tmp.stat().st_size if tmp.exists() else 0
                if r.returncode != 0 or _size < 10240:
                    self.after(0, lambda: self.log('Preview stream-copy failed — re-encoding...', FG2))
                    r = subprocess.run(
                        [ff, '-y', '-ss', start, '-to', end, '-i', vid,
                         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                         '-c:a', 'aac', '-b:a', '128k', str(tmp)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 10240:
                    import os as _os
                    _os.startfile(str(tmp))
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
        import math as _snap_math

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
                return ts(_snap_math.ceil(min(segs[target_idx]['end'] + 0.3, segs[-1]['end'])))

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

            return ts(_snap_math.ceil(min(best_end + 0.3, segs[-1]['end'])))

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

    def _save_session(self):
        """Save current clips + video path to session file so they can be restored later."""
        if not self.clips:
            import tkinter.messagebox as _mb
            _mb.showwarning('Nothing to save', 'Find some clips first, then save the session.')
            return
        session = {
            'video': self.v_video.get(),
            'outdir': self.v_outdir.get(),
            'clips': [
                {
                    'title':       c.get('title',''),
                    'start':       c['_sv'].get() if '_sv' in c else c.get('start',''),
                    'end':         c['_ev'].get() if '_ev' in c else c.get('end',''),
                    'filename':    c['_name_var'].get() if '_name_var' in c else c.get('title',''),
                    'score':       c.get('score',''),
                    'reason':      c.get('reason',''),
                    'summary':     c.get('summary',''),
                    'speaker':     c.get('speaker',''),
                    'hook':        c.get('hook',''),
                    'engagement':  c.get('engagement',''),
                    'shareability':c.get('shareability',''),
                    'value':       c.get('value',''),
                }
                for c in self.clips
            ],
        }
        try:
            SESSION_FILE.write_text(json.dumps(session, indent=2))
            self.log(f'Session saved — {len(self.clips)} clips ({SESSION_FILE.name})', GREEN)
        except Exception as ex:
            self.log(f'Session save failed: {ex}', RED)

    def _load_session(self):
        """Restore a previously saved session (clips + video path)."""
        import tkinter.messagebox as _mb
        if not SESSION_FILE.exists():
            _mb.showinfo('No session', 'No saved session found.\nUse 💾 Save Session after finding clips.')
            return
        try:
            session = json.loads(SESSION_FILE.read_text())
        except Exception as ex:
            _mb.showerror('Load failed', f'Could not read session file:\n{ex}')
            return
        saved_vid = session.get('video','')
        clips_raw = session.get('clips', [])
        if not clips_raw:
            _mb.showinfo('Empty session', 'Session file has no clips.')
            return
        # Warn if video path changed
        current_vid = self.v_video.get().strip()
        if current_vid == getattr(self, '_video_placeholder', ''):
            current_vid = ''
        if saved_vid and current_vid and saved_vid != current_vid:
            if not _mb.askyesno('Different video',
                f'Session was saved for:\n{Path(saved_vid).name}\n\n'
                f'Currently loaded:\n{Path(current_vid).name}\n\n'
                'Load anyway?'):
                return
        # Restore the video path if current is empty
        if not current_vid and saved_vid and Path(saved_vid).exists():
            self.v_video.set(saved_vid)
            try: self._video_entry.config(fg=FG)
            except Exception: pass
        if session.get('outdir'):
            self.v_outdir.set(session['outdir'])
        self.clips = clips_raw
        self._render_clips()
        self._switch_nb('clips')
        self.log(f'Session loaded — {len(clips_raw)} clips restored', GREEN)

    def _do_export(self, clips):
        try:
            self._do_export_inner(clips)
        except Exception:
            _xe = traceback.format_exc()
            self.log(f'Export error:\n{_xe}', RED)
            self.after(0, lambda: (self.set_busy(False),
                                   messagebox.showerror('Export failed', 'See the log for details.')))
        finally:
            self._export_running = False

    def _do_export_inner(self, clips):
        vid = self._resolve_export_video()
        out = self.v_outdir.get()
        base = Path(vid).stem
        ff = find_ffmpeg()
        ok = 0
        Path(out).mkdir(parents=True, exist_ok=True)
        _vf_cache = {}
        def _to_sec(t):
            try:
                p = [float(x) for x in str(t).strip().split(':')]
                return sum(v*60**k for k, v in enumerate(reversed(p)))
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
                _hw_args = ['-hwaccel', 'cuda']
            elif _vcodec == 'h264_qsv':
                _hw_args = ['-hwaccel', 'qsv']
            _crop_mode = getattr(self, 'v_crop_mode', None)
            _crop_mode = _crop_mode.get() if _crop_mode else 'normal'
            _base_cmd = [ff, '-y'] + _hw_args + ['-ss', start, '-to', end, '-i', vid]

            def _run_fmt(out_path, vertical=False, _st=start, _en=end):
                # Build fresh command — always use _st/_en params, never outer closure vars
                if getattr(self, '_cancel_requested', False): return False
                if vertical:
                    _cmd_base = [ff, '-y', '-ss', _st, '-to', _en, '-i', vid]
                    if vid not in _vf_cache:
                        _vf_cache[vid] = self._get_vertical_vf(vid)
                    _vff = _vf_cache[vid]
                    if not _vff:
                        _vff = ['-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920']
                    _cmd = _cmd_base + ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18'] + _vff + ['-c:a', 'aac', '-b:a', '192k', out_path]
                else:
                    _cmd_base_local = [ff, '-y'] + _hw_args + ['-ss', _st, '-to', _en, '-i', vid]
                    _cmd = _cmd_base_local + ['-c:v', _vcodec] + ['-c:a', _acodec] + _extra + [out_path]
                _r = self._run_ff(_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if _r.returncode != 0 and getattr(self, '_cancel_requested', False):
                    try: Path(out_path).unlink()
                    except OSError: pass
                    return False
                _err = _r.stderr.decode(errors='replace') if _r.stderr else ''
                # Guard: returncode==0 but 0-frame encode writes only a header (~1KB)
                _out_size = Path(out_path).stat().st_size if Path(out_path).exists() else 0
                _ok = _r.returncode == 0 and _out_size > 10240
                if not _ok:
                    if _r.returncode != 0:
                        self.log(f'[Export] {"9:16" if vertical else "16:9"} failed → {out_path}\n{_err[-120:]}', RED)
                    else:
                        self.log(f'[Export] {"9:16" if vertical else "16:9"} produced empty file ({_out_size}B) — retrying with libx264', YELLOW)
                    if vertical:
                        _fallback = [ff, '-y', '-ss', _st, '-to', _en, '-i', vid,
                                     '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                                     '-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920',
                                     '-c:a', 'aac', '-b:a', '192k', out_path]
                        _r2 = self._run_ff(_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return _r2.returncode == 0
                    else:
                        self.log(f'[Export] Falling back to libx264 CPU encoder', YELLOW)
                        _cmd_cpu = [ff, '-y', '-ss', _st, '-to', _en, '-i', vid,
                                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                                    '-movflags', '+faststart',
                                    '-c:a', 'aac', '-b:a', '192k', out_path]
                        _r2 = self._run_ff(_cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                        _out_size2 = Path(out_path).stat().st_size if Path(out_path).exists() else 0
                        if _r2.returncode != 0 or _out_size2 <= 10240:
                            _err2 = _r2.stderr.decode(errors='replace')[-200:] if _r2.stderr else ''
                            self.log(f'[Export] libx264 fallback also failed: {_err2[-120:]}', RED)
                            return False
                        return True
                return True

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

    def _sub_segments_for(self, inp):
        """Whisper segments that belong to video `inp` (subtitle-tab transcript, else main-tab one), or []."""
        try:
            _n = os.path.normcase(os.path.abspath(str(inp)))
        except Exception:
            return []
        if getattr(self, '_sub_segments', None) and getattr(self, '_sub_vid', '') == _n:
            return self._sub_segments
        if getattr(self, '_whisper_segments', None) and getattr(self, '_whisper_vid', '') == _n:
            return self._whisper_segments
        return []

    def _transcript_to_ass(self, s, segs):
        """Convert whisper segments to ASS with pause detection and karaoke word highlight."""
        import re as _re

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
        # BG Box: BorderStyle 3 draws an opaque box in OutlineColour, Outline acts as box padding
        _box = bool(s['bg_on']) and s['bg_opacity'] > 0
        oc_style = bc if _box else oc
        _bstyle  = 3 if _box else 1
        _outline = max(s['stroke'], 4) if _box else s['stroke']

        def _ts(t):
            h=int(t//3600); m=int((t%3600)//60); sc=t%60
            return f'{h}:{m:02d}:{sc:05.2f}'

        ass = (
            '[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
            'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, '
            'Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            # \kf sweeps Secondary -> Primary, so for karaoke the highlight must be the Primary colour
            f'Style: Default,{s["font"]},{s["size"]},{hc if karaoke else tc},{tc if karaoke else hc},{oc_style},{bc},'
            f'{"1" if s["bold"] else "0"},{"1" if s["italic"] else "0"},0,0,100,100,0,0,{_bstyle},'
            f'{_outline},0,2,60,60,80,1\n\n'
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
                prev_end = grp[0]['start']
                for w in grp:
                    gap_cs = int((w['start'] - prev_end) * 100)
                    if gap_cs > 0: line += f'{{\\k{gap_cs}}}'
                    dur_cs = max(1, int((w['end'] - w['start']) * 100))
                    line += f'{{\\kf{dur_cs}}}{w["word"]} '
                    prev_end = w['end']
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
                self._sub_segments = segs_raw
                self._sub_result = result
                self._sub_vid = os.path.normcase(os.path.abspath(inp))
                n = len(segs_raw)
                def _done():
                    self.sub_trans_btn.config(state='normal', text='📝 Transcribe')
                    self.sub_trans_lbl.config(text=f'✅ {n} segments ready', fg=GREEN)
                self.after(0, _done)
            except Exception as _ex:
                import traceback as _tb
                _e = _tb.format_exc()
                _msg = str(_ex)
                def _err():
                    self.sub_trans_btn.config(state='normal', text='📝 Transcribe')
                    self.sub_trans_lbl.config(text=f'❌ {_msg}', fg=RED)
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
            tf_png = None
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

                _fd, tf_png = _tf.mkstemp(suffix='.png'); _os.close(_fd)
                _sp.run([_ff, '-ss', str(mid), '-i', inp,
                         '-vframes', '1', '-q:v', '2', '-vf', 'scale=640:360',
                         tf_png, '-y'], capture_output=True)

                if not Path(tf_png).exists() or Path(tf_png).stat().st_size == 0:
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
            finally:
                if tf_png:
                    try: os.unlink(tf_png)
                    except OSError: pass
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
        # Auto-transcribe if no segments for THIS video yet
        segs = self._sub_segments_for(inp)
        if not segs:
            self.sub_status_lbl.config(text='No transcript — transcribing first...', fg=YELLOW)
            self.sub_burn_btn.config(state='disabled', text='⏳ Transcribing...')
            def _then_burn():
                if self._sub_segments_for(inp):
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
                    self._sub_segments = segs_raw
                    self._sub_result = result
                    self._sub_vid = os.path.normcase(os.path.abspath(inp))
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
        try:
            outdir = self.v_sub_outdir.get().strip() or str(Path.home() / 'Downloads')
            Path(outdir).mkdir(parents=True, exist_ok=True)
            stem = Path(inp).stem
            outfile = str(Path(outdir) / f'{stem} - Subtitled - ClipFinder.mp4')
            s = self._get_sub_settings()
            self.cfg['sub_outdir'] = outdir
            save_cfg(self.cfg)
        except Exception as _be:
            self.sub_status_lbl.config(text=f'❌ {_be}', fg=RED)
            return
        self.sub_burn_btn.config(state='disabled', text='⏳ Burning...')
        self.sub_status_lbl.config(text='Starting...', fg=FG2)

        def _run():
            tf_ass = None
            try:
                import subprocess as _sp, tempfile as _tf, os as _os, re as _re_sub
                _ff = ensure_ffmpeg()
                if not _ff:
                    self.after(0, lambda: (
                        self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES'),
                        self.sub_status_lbl.config(text='❌ ffmpeg not found', fg=RED)))
                    return

                # Write ASS file
                ass_content = self._transcript_to_ass(s, segs)
                _fd, tf_ass = _tf.mkstemp(suffix='.ass'); _os.close(_fd)
                with open(tf_ass, 'w', encoding='utf-8') as _f:
                    _f.write(ass_content)

                # Get video duration for progress %
                _dur_r = _sp.run([_ff, '-i', inp], capture_output=True, text=True,
                                 encoding='utf-8', errors='replace')
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

                # Reference the temp .ass by bare file name (cwd = its folder) so a TEMP path
                # containing an apostrophe / drive colon can't break the filtergraph quoting.
                _inp_abs = _os.path.abspath(inp)
                _out_abs = _os.path.abspath(outfile)
                if _os.path.dirname(_ff): _ff = _os.path.abspath(_ff)   # cwd changes below
                _vf = f'ass={_os.path.basename(tf_ass)}'

                self.after(0, lambda: self.set_progress('🔤 Burning subtitles...', pct=1))

                def _burn_once(_a_args):
                    cmd = [_ff, '-i', _inp_abs, '-vf', _vf,
                           '-c:v'] + _vcodec + _a_args + [_out_abs, '-y']
                    proc = _sp.Popen(cmd, cwd=_os.path.dirname(tf_ass), stderr=_sp.PIPE, text=True,
                                     encoding='utf-8', errors='replace')
                    _tail = []
                    for line in proc.stderr:
                        _tail = (_tail + [line.rstrip()])[-15:]
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
                    return proc.returncode, _tail

                _rc, _tail = _burn_once(['-c:a', 'copy'])
                if _rc != 0 and any(('audio' in _l.lower() or 'codec' in _l.lower()) for _l in _tail):
                    # audio stream may not fit in MP4 (e.g. Vorbis) — retry once with AAC audio
                    self.log('Subtitle burn: audio copy failed, retrying with AAC audio...', YELLOW)
                    _rc, _tail = _burn_once(['-c:a', 'aac', '-b:a', '192k'])

                if _rc == 0:
                    def _done():
                        self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES')
                        self.sub_status_lbl.config(text=f'✅ Saved: {Path(outfile).name}', fg=GREEN)
                        self.set_progress(f'✅ Subtitles burned: {Path(outfile).name}', pct=100)
                        self.log(f'✅ Subtitles burned: {outfile}', GREEN)
                    self.after(0, _done)
                else:
                    raise RuntimeError(f'ffmpeg returned code {_rc}\n' + '\n'.join(_tail))
            except Exception as _ex:
                import traceback as _tb
                _err = _tb.format_exc()
                def _err_ui():
                    self.sub_burn_btn.config(state='normal', text='🔤  BURN SUBTITLES')
                    self.sub_status_lbl.config(text='❌ Error — check log', fg=RED)
                    self.set_progress('❌ Subtitle burn failed', pct=0)
                    self.log(f'Subtitle burn error:\n{_err}', RED)
                self.after(0, _err_ui)
            finally:
                if tf_ass:
                    try: os.unlink(tf_ass)
                    except OSError: pass
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


    # ─────────────────────────────────────────────────────────────────────────
    #  POST STUDIO TAB (v2)
    #  Writes TikTok / Instagram / YouTube Shorts / X copy from a transcript or a rough description,
    #  following the master prompt in PS_MASTER_PROMPT. Pure logic (prompt, parsing, rule enforcement)
    #  lives in the post-studio-engine block above `class App`; this is only the UI + AI plumbing.
    # ─────────────────────────────────────────────────────────────────────────

    _PS_TRANS_PH = 'Paste the transcript, or just describe the clip ("Mizkif reacts to...")'
    _PS_ANGLE_PH = 'Optional. Force an angle, e.g. "make it about Dana calling the rumors bullshit"'
    _PS_PEOPLE_PH = 'Who is in THIS clip, e.g. Nick Lee, Ice Poseidon'
    _PS_RULES_PH = 'Standing rules for every clip, e.g. "Always mention SeeEx"'
    _PS_HANDLES = (('x', '𝕏', '@handle'), ('tiktok', '🎵', '@tiktok'),
                   ('instagram', '📸', '@instagram'), ('youtube', '▶', '@youtube'))

    def _ps_val(self, w):
        """Text of a Text/Entry widget with its placeholder treated as empty."""
        try:
            v = w.get('1.0', 'end') if isinstance(w, tk.Text) else w.get()
        except Exception:
            return ''
        v = v.strip()
        return '' if v == getattr(w, '_ps_ph', None) else v

    def _ps_put(self, w, text):
        """Replace a Text/Entry widget's content (placeholder aware)."""
        ph = getattr(w, '_ps_ph', '')
        try:
            _st = str(w.cget('state'))
            w.config(state='normal')
        except Exception:
            _st = 'normal'
        try:
            self._ps_put_inner(w, text, ph)
        finally:
            try: w.config(state=_st)
            except Exception: pass

    def _ps_put_inner(self, w, text, ph):
        if isinstance(w, tk.Text):
            w.delete('1.0', 'end')
            if text:
                w.insert('1.0', text); w.config(fg=FG)
            else:
                w.insert('1.0', ph); w.config(fg=FG3)
        else:
            w.delete(0, 'end')
            if text:
                w.insert(0, text); w.config(fg=FG)
            else:
                w.insert(0, ph); w.config(fg=FG3)

    def _ps_make_ph(self, w, ph):
        """Give a Text/Entry a grey placeholder that disappears on focus."""
        w._ps_ph = ph
        self._ps_put(w, '')
        def _in(_e):
            if self._ps_val(w) == '' and w.cget('fg') == FG3:
                if isinstance(w, tk.Text): w.delete('1.0', 'end')
                else: w.delete(0, 'end')
                w.config(fg=FG)
        def _out(_e):
            if self._ps_val(w) == '':
                self._ps_put(w, '')
        w.bind('<FocusIn>', _in, add='+')
        w.bind('<FocusOut>', _out, add='+')

    def _ps_lbl(self, parent, text, hint=''):
        tk.Label(parent, text=text, font=('Segoe UI', 8, 'bold'), fg=FG2, bg=BG).pack(anchor='w', pady=(8, 1))
        if hint:
            tk.Label(parent, text=hint, font=('Segoe UI', 7), fg=FG3, bg=BG, wraplength=310,
                     justify='left').pack(anchor='w')

    def _ps_mem_path(self):
        return USER_DIR / 'handle_memory.json'

    def _ps_mem_load(self):
        try:
            return json.loads(self._ps_mem_path().read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _ps_mem_key(self, people):
        return (people or '').split(',')[0].strip().lower().replace(' ', '_')

    def _build_post_studio_tab(self, p):
        """Post Studio v2 - captions for TikTok / Instagram / YouTube Shorts / X from the master prompt."""
        self._ps_hist = []          # results of the CURRENT clip, newest last
        self._ps_hist_i = -1
        self._ps_busy = False
        self._ps_cards = {}
        self._ps_seex = tk.StringVar(value=self.cfg.get('ps_seex', 'auto'))
        _saved_plats = self.cfg.get('ps_plats') or [k for k, *_ in PS_PLATFORMS]
        self._ps_plats = {k: tk.BooleanVar(value=(k in _saved_plats)) for k, *_ in PS_PLATFORMS}

        outer = tk.Frame(p, bg=BG); outer.pack(fill='both', expand=True)

        # ── LEFT: inputs (scrolls, the form is tall) ─────────────────────────────
        lwrap = tk.Frame(outer, bg=BG, width=350)
        lwrap.pack(side='left', fill='y', padx=(10, 0), pady=8)
        lwrap.pack_propagate(False)
        lcv = tk.Canvas(lwrap, bg=BG, bd=0, highlightthickness=0)
        _make_scrollbar(lwrap, lcv)
        lcv.pack(side='left', fill='both', expand=True)
        left = tk.Frame(lcv, bg=BG)
        _lwin = lcv.create_window((0, 0), window=left, anchor='nw')
        left.bind('<Configure>', lambda e: lcv.configure(scrollregion=lcv.bbox('all')))
        lcv.bind('<Configure>', lambda e: lcv.itemconfigure(_lwin, width=e.width - 4))
        _bind_mousewheel(lcv, lcv); _bind_mousewheel(left, lcv)
        tk.Frame(outer, bg=BORDER, width=1).pack(side='left', fill='y', padx=(8, 0))
        right = tk.Frame(outer, bg=BG)
        right.pack(side='left', fill='both', expand=True, padx=10, pady=8)

        top = tk.Frame(left, bg=BG); top.pack(fill='x')
        tk.Label(top, text='🚀  POST STUDIO', font=('Segoe UI', 10, 'bold'), fg=ACCENT, bg=BG).pack(side='left')
        tk.Button(top, text='🆕 New clip', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                  padx=8, pady=3, command=self._ps_new_clip).pack(side='right', padx=(0, 6))

        # transcript
        self._ps_lbl(left, 'CLIP TRANSCRIPT / DESCRIPTION')
        tw = tk.Frame(left, bg=BG3); tw.pack(fill='x', pady=(2, 4))
        self._ps_trans = tk.Text(tw, height=7, font=FONT_MONO_S, bg=BG3, fg=FG3, insertbackground=ACCENT,
                                 relief='flat', bd=4, wrap='word')
        self._ps_trans.pack(fill='x')
        self._ps_make_ph(self._ps_trans, self._PS_TRANS_PH)
        _tb = tk.Frame(left, bg=BG); _tb.pack(fill='x')
        tk.Button(_tb, text='⬆ Current transcript', font=FONT_SMALL, bg=ACCENT, fg='#000', relief='flat', bd=0,
                  cursor='hand2', padx=8, pady=4, command=self._ps_use_current).pack(side='left', padx=(0, 4))
        self._ps_clip_btn = tk.Button(_tb, text='🎬 A found clip ▾', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat',
                                      bd=0, cursor='hand2', padx=8, pady=4, command=self._ps_pick_clip)
        self._ps_clip_btn.pack(side='left', padx=(0, 4))
        tk.Button(_tb, text='📂 Video', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                  padx=8, pady=4, command=self._ps_load_video).pack(side='left')

        # who / angle
        self._ps_lbl(left, 'PEOPLE IN THIS CLIP  (optional)', 'Only these people get named (rule: no random extra names).')
        self._ps_people = tk.Entry(left, font=FONT_SMALL, bg=BG3, fg=FG3, insertbackground=ACCENT, relief='flat', bd=4)
        self._ps_people.pack(fill='x', pady=(2, 0))
        self._ps_make_ph(self._ps_people, self._PS_PEOPLE_PH)
        self._ps_people.bind('<FocusOut>', lambda e: self._ps_recall_handles(), add='+')
        self._ps_lbl(left, 'ANGLE OVERRIDE  (optional)', 'Leave empty and it finds the one moment people stop scrolling for.')
        self._ps_angle = tk.Text(left, height=2, font=FONT_SMALL, bg=BG3, fg=FG3, insertbackground=ACCENT,
                                 relief='flat', bd=4, wrap='word')
        self._ps_angle.pack(fill='x', pady=(2, 0))
        self._ps_make_ph(self._ps_angle, self._PS_ANGLE_PH)

        # SeeEx mode + platforms
        self._ps_lbl(left, 'SEEEX', 'Nick Lee\'s event. Auto = only when the clip is clearly from it.')
        _sx = tk.Frame(left, bg=BG); _sx.pack(fill='x')
        for _v, _t in (('auto', 'Auto'), ('always', 'Always mention'), ('never', 'Not SeeEx')):
            tk.Radiobutton(_sx, text=_t, value=_v, variable=self._ps_seex, font=FONT_SMALL, bg=BG, fg=FG,
                           selectcolor=BG3, activebackground=BG, activeforeground=FG, relief='flat',
                           cursor='hand2').pack(side='left', padx=(0, 8))
        self._ps_lbl(left, 'PLATFORMS')
        _pl = tk.Frame(left, bg=BG); _pl.pack(fill='x')
        for i, (k, lbl, col, _f) in enumerate(PS_PLATFORMS):
            tk.Checkbutton(_pl, text=lbl, variable=self._ps_plats[k], font=FONT_SMALL, bg=BG, fg=col, selectcolor=BG3,
                           activebackground=BG, activeforeground=col, relief='flat', cursor='hand2',
                           command=self._ps_refresh_cards).grid(row=i // 2, column=i % 2, sticky='w', padx=(0, 10))

        # handles
        self._ps_lbl(left, 'HANDLES  (optional)', 'Remembered per person. Used for tagging lines.')
        self._ps_handle = {}
        _hg = tk.Frame(left, bg=BG); _hg.pack(fill='x', pady=(2, 0))
        for i, (k, ico, ph) in enumerate(self._PS_HANDLES):
            tk.Label(_hg, text=ico, font=FONT_SMALL, fg=FG2, bg=BG).grid(row=i // 2, column=(i % 2) * 2, sticky='w')
            e = tk.Entry(_hg, font=FONT_SMALL, bg=BG3, fg=FG3, insertbackground=ACCENT, relief='flat', bd=3, width=14)
            e.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky='we', padx=(2, 8), pady=1)
            self._ps_make_ph(e, ph)
            self._ps_handle[k] = e
        _hg.columnconfigure(1, weight=1); _hg.columnconfigure(3, weight=1)
        self._ps_mem_lbl = tk.Label(left, text='', font=('Segoe UI', 7), fg=GREEN, bg=BG)
        self._ps_mem_lbl.pack(anchor='w')

        # standing rules
        self._ps_lbl(left, 'MY STANDING RULES  (saved)', 'Applied to every clip, e.g. corrections you never want to repeat.')
        self._ps_rules = tk.Text(left, height=3, font=FONT_SMALL, bg=BG3, fg=FG3, insertbackground=ACCENT,
                                 relief='flat', bd=4, wrap='word')
        self._ps_rules.pack(fill='x', pady=(2, 0))
        self._ps_make_ph(self._ps_rules, self._PS_RULES_PH)
        self._ps_put(self._ps_rules, self.cfg.get('ps_rules', ''))

        self._ps_gen_btn = tk.Button(left, text='⚡  WRITE THE POSTS', font=('Segoe UI', 10, 'bold'), bg=ACCENT,
                                     fg='#000', relief='flat', bd=0, cursor='hand2', pady=10,
                                     activebackground=ACCENT2, command=lambda: self._ps_generate('new'))
        self._ps_gen_btn.pack(fill='x', pady=(12, 4))
        self._ps_status = tk.Label(left, text='', font=('Segoe UI', 8), fg=FG2, bg=BG, wraplength=320, justify='left')
        self._ps_status.pack(anchor='w', pady=(0, 10))

        # ── RIGHT: iteration bar + results ───────────────────────────────────────
        hdr = tk.Frame(right, bg=BG); hdr.pack(fill='x')
        tk.Label(hdr, text='GENERATED POSTS', font=('Segoe UI', 9, 'bold'), fg=ACCENT, bg=BG).pack(side='left')
        self._ps_nav_lbl = tk.Label(hdr, text='', font=('Segoe UI', 8), fg=FG2, bg=BG)
        self._ps_nav_lbl.pack(side='right')
        self._ps_next_btn = tk.Button(hdr, text='▶', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, width=3,
                                      cursor='hand2', command=lambda: self._ps_nav(1))
        self._ps_next_btn.pack(side='right', padx=(2, 4))
        self._ps_prev_btn = tk.Button(hdr, text='◀', font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, width=3,
                                      cursor='hand2', command=lambda: self._ps_nav(-1))
        self._ps_prev_btn.pack(side='right')
        self._ps_angle_lbl = tk.Label(right, text='', font=('Segoe UI', 8, 'italic'), fg=FG2, bg=BG,
                                      wraplength=640, justify='left')
        self._ps_angle_lbl.pack(anchor='w', pady=(2, 4))

        it = tk.Frame(right, bg=BG); it.pack(fill='x', pady=(0, 4))
        self._ps_iter_btns = []
        for _task, _t in (('retry', '🔄 Try again'), ('funnier', '😂 Funnier'), ('shorter', '✂ Shorten'),
                          ('viral', '🚀 More viral')):
            b = tk.Button(it, text=_t, font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2',
                          padx=10, pady=4, command=lambda t=_task: self._ps_generate(t))
            b.pack(side='left', padx=(0, 4))
            self._ps_iter_btns.append(b)
        fx = tk.Frame(right, bg=BG); fx.pack(fill='x', pady=(0, 6))
        self._ps_fix = tk.Entry(fx, font=FONT_SMALL, bg=BG3, fg=FG3, insertbackground=ACCENT, relief='flat', bd=5)
        self._ps_fix.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self._ps_make_ph(self._ps_fix, 'Correction or instruction, e.g. "it was NIBBLES, not kisses"')
        self._ps_fix.bind('<Return>', lambda e: self._ps_generate('fix'))
        self._ps_fix_btn = tk.Button(fx, text='Apply', font=FONT_SMALL, bg=ACCENT2, fg='#000', relief='flat', bd=0,
                                     cursor='hand2', padx=12, pady=4, command=lambda: self._ps_generate('fix'))
        self._ps_fix_btn.pack(side='right')
        self._ps_iter_btns.append(self._ps_fix_btn)

        rwrap = tk.Frame(right, bg=BG); rwrap.pack(fill='both', expand=True)
        rcv = tk.Canvas(rwrap, bg=BG, bd=0, highlightthickness=0)
        _make_scrollbar(rwrap, rcv)
        rcv.pack(side='left', fill='both', expand=True)
        self._ps_rcv = rcv
        body = tk.Frame(rcv, bg=BG)
        _rwin = rcv.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: rcv.configure(scrollregion=rcv.bbox('all')))
        rcv.bind('<Configure>', lambda e: rcv.itemconfigure(_rwin, width=e.width - 2))
        _bind_mousewheel(rcv, rcv); _bind_mousewheel(body, rcv)
        self._ps_body = body

        self._ps_notes = tk.Frame(body, bg=BG); self._ps_notes.pack(fill='x', pady=(0, 6))
        self._ps_empty = tk.Label(body, text='Paste a transcript (or describe the clip) on the left,\n'
                                             'then hit  ⚡ WRITE THE POSTS.', font=('Segoe UI', 9), fg=FG3, bg=BG,
                                  justify='center')
        self._ps_empty.pack(pady=40)
        for key, lbl, col, fields in PS_PLATFORMS:
            self._ps_build_card(body, key, lbl, col, fields)
        self._ps_recall_handles()
        self._ps_refresh_cards()
        self._ps_set_iter_state(False)
        self._ps_wheel(left, lcv)
        self._ps_wheel(body, rcv)

    def _ps_wheel(self, w, cv):
        """Mouse wheel scrolls the panel from anywhere over it (Tk does not bubble wheel events to parents)."""
        try:
            _bind_mousewheel(w, cv)
            for c in w.winfo_children():
                self._ps_wheel(c, cv)
        except Exception:
            pass

    # ── cards ──────────────────────────────────────────────────────────────────────

    def _ps_build_card(self, parent, key, label, col, fields):
        card = tk.Frame(parent, bg=BG3)
        head = tk.Frame(card, bg=BG4); head.pack(fill='x')
        tk.Frame(head, bg=col, width=3).pack(side='left', fill='y')
        tk.Label(head, text=label, font=('Segoe UI', 9, 'bold'), fg=col, bg=BG4).pack(side='left', padx=8, pady=5)
        info = {'frame': card, 'fields': {}, 'count': None}
        allbtn = tk.Button(head, text='📋 Copy all', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0,
                           cursor='hand2', padx=8, pady=4)
        allbtn.pack(side='right', padx=(0, 4))
        allbtn.config(command=lambda k=key, b=allbtn: self._ps_copy_all(k, b))
        rg = tk.Button(head, text='🔄', font=FONT_SMALL, bg=BG4, fg=FG2, relief='flat', bd=0, cursor='hand2',
                       padx=6, pady=4, command=lambda k=key: self._ps_generate('retry', only=[k]))
        rg.pack(side='right')
        info['regen'] = rg
        if key == 'x':
            info['count'] = tk.Label(head, text='', font=('Segoe UI', 8), fg=FG3, bg=BG4)
            info['count'].pack(side='right', padx=6)
        for f in fields:
            row = tk.Frame(card, bg=BG3); row.pack(fill='x', padx=6, pady=(5, 0))
            tk.Label(row, text=PS_FIELD_LABEL[f], font=('Segoe UI', 7, 'bold'), fg=FG3, bg=BG3).pack(side='left')
            cb = tk.Button(row, text='📋', font=('Segoe UI', 8), bg=BG3, fg=FG2, relief='flat', bd=0,
                           cursor='hand2', padx=4)
            cb.pack(side='right')
            box = tk.Text(card, height=2, font=FONT_SMALL, bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat',
                          bd=4, wrap='word', highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
            box.pack(fill='x', padx=6, pady=(1, 0))
            box.bind('<KeyRelease>', lambda e, k=key, ff=f: self._ps_on_edit(k, ff))
            _bind_mousewheel(box, self._ps_rcv)
            cb.config(command=lambda k=key, ff=f, b=cb: self._ps_copy_field(k, ff, b))
            info['fields'][f] = {'box': box, 'btn': cb}
        tk.Frame(card, bg=BG3, height=6).pack()
        _bind_mousewheel(card, self._ps_rcv)
        self._ps_cards[key] = info

    def _ps_fit(self, box):
        """Grow a Text widget to the number of visual lines it holds."""
        try:
            box.update_idletasks()
            n = box.count('1.0', 'end-1c', 'displaylines')
            n = (n[0] if isinstance(n, (tuple, list)) else n) or 1
        except Exception:
            n = box.get('1.0', 'end').count('\n') + 1
        box.config(height=max(2, min(14, int(n) + 1)))

    def _ps_on_edit(self, key, field):
        info = self._ps_cards.get(key)
        if not info:
            return
        if key == 'x' and info['count'] is not None:
            n = len(info['fields']['post']['box'].get('1.0', 'end-1c'))
            info['count'].config(text=f'{n}/280', fg=(RED if n > 280 else FG3))
        self._ps_fit(info['fields'][field]['box'])

    def _ps_refresh_cards(self):
        """Show a card only if its platform is ticked AND there is a result for it."""
        res = self._ps_current()
        any_shown = False
        for key, *_ in PS_PLATFORMS:
            info = self._ps_cards.get(key)
            if not info:
                continue
            show = bool(res) and key in res and self._ps_plats[key].get()
            if show:
                info['frame'].pack(fill='x', pady=(0, 8)); any_shown = True
            else:
                info['frame'].pack_forget()
        if any_shown:
            self._ps_empty.pack_forget()
        elif not self._ps_empty.winfo_manager():
            self._ps_empty.pack(pady=40)

    def _ps_current(self):
        if 0 <= self._ps_hist_i < len(self._ps_hist):
            return self._ps_hist[self._ps_hist_i]
        return None

    def _ps_copy(self, text, btn, idle='📋'):
        text = (text or '').strip()
        if not text:
            return
        self.clipboard_clear(); self.clipboard_append(text)
        try:
            btn.config(text='✅', fg=GREEN)
            self.after(1200, lambda: btn.winfo_exists() and btn.config(text=idle, fg=FG2))
        except Exception:
            pass

    def _ps_copy_field(self, key, field, btn):
        self._ps_copy(self._ps_cards[key]['fields'][field]['box'].get('1.0', 'end'), btn)

    def _ps_copy_all(self, key, btn):
        info = self._ps_cards[key]
        fields = next(f for k, _l, _c, f in PS_PLATFORMS if k == key)
        parts = []
        for f in fields:
            t = info['fields'][f]['box'].get('1.0', 'end').strip()
            if t:
                parts.append(t if len(fields) == 1 else f'{PS_FIELD_LABEL[f]}\n{t}')
        self._ps_copy('\n\n'.join(parts), btn, idle='📋 Copy all')

    def _ps_show(self, res):
        """Fill the cards + notes from a result dict (edits made in the boxes are per-version, not stored)."""
        self._ps_refresh_cards()      # cards must be mapped before their height can be measured
        for key, _lbl, _col, fields in PS_PLATFORMS:
            info = self._ps_cards[key]
            for f in fields:
                box = info['fields'][f]['box']
                box.delete('1.0', 'end')
                box.insert('1.0', (res.get(key) or {}).get(f, ''))
        self.update_idletasks()
        for key, _lbl, _col, fields in PS_PLATFORMS:
            for f in fields:
                self._ps_on_edit(key, f)
        self._ps_angle_lbl.config(text=('Angle: ' + res['angle']) if res.get('angle') else '')
        for w in self._ps_notes.winfo_children():
            w.destroy()
        fixes, warns, rem = res.get('fixes', []), res.get('warns', []), res.get('reminders', [])
        if fixes or warns or rem:
            tk.Label(self._ps_notes, text=f'RULES CHECK   {len(fixes)} auto-fixed   {len(warns)} to review',
                     font=('Segoe UI', 8, 'bold'), fg=(YELLOW if warns else GREEN), bg=BG).pack(anchor='w')
            for t in fixes:
                tk.Label(self._ps_notes, text='✔ ' + t, font=('Segoe UI', 8), fg=FG3, bg=BG, wraplength=620,
                         justify='left').pack(anchor='w')
            for t in warns:
                tk.Label(self._ps_notes, text='⚠ ' + t, font=('Segoe UI', 8), fg=YELLOW, bg=BG, wraplength=620,
                         justify='left').pack(anchor='w')
            for t in rem:
                tk.Label(self._ps_notes, text='📌 ' + t, font=('Segoe UI', 8), fg=ACCENT2, bg=BG, wraplength=620,
                         justify='left').pack(anchor='w')
        else:
            tk.Label(self._ps_notes, text='✅ RULES CHECK   nothing to fix', font=('Segoe UI', 8, 'bold'),
                     fg=GREEN, bg=BG).pack(anchor='w')
        self._ps_wheel(self._ps_notes, self._ps_rcv)
        n = len(self._ps_hist)
        self._ps_nav_lbl.config(text=f'version {self._ps_hist_i + 1} of {n}')
        self._ps_prev_btn.config(state='normal' if self._ps_hist_i > 0 else 'disabled')
        self._ps_next_btn.config(state='normal' if self._ps_hist_i < n - 1 else 'disabled')
        self._ps_refresh_cards()
        try:
            self._ps_rcv.yview_moveto(0)
        except Exception:
            pass

    def _ps_snapshot(self):
        """The current version INCLUDING any hand edits made in the boxes (stored back into the history)."""
        cur = self._ps_current()
        if not cur:
            return None
        snap = dict(cur)
        for key, _l, _c, fields in PS_PLATFORMS:
            if key in cur:
                vals = {f: self._ps_cards[key]['fields'][f]['box'].get('1.0', 'end').strip() for f in fields}
                snap[key] = {f: v for f, v in vals.items() if v}
        self._ps_hist[self._ps_hist_i] = snap
        return snap

    def _ps_nav(self, d):
        i = self._ps_hist_i + d
        if 0 <= i < len(self._ps_hist):
            self._ps_snapshot()
            self._ps_hist_i = i
            self._ps_show(self._ps_hist[i])

    def _ps_set_iter_state(self, on):
        for b in self._ps_iter_btns:
            try:
                b.config(state='normal' if on else 'disabled')
            except Exception:
                pass
        self._ps_fix.config(state='normal' if on else 'disabled')
        for k, info in self._ps_cards.items():
            info['regen'].config(state='normal' if on else 'disabled')

    def _ps_set_status(self, msg, col=None):
        try:
            self._ps_status.config(text=msg, fg=col or FG2)
        except Exception:
            pass

    # ── inputs ────────────────────────────────────────────────────────────────────

    def _ps_new_clip(self):
        """Rule 29: every clip is its own piece of content - drop the previous clip's text, angle and results."""
        if self._ps_busy:
            return
        self._ps_put(self._ps_trans, ''); self._ps_put(self._ps_angle, ''); self._ps_put(self._ps_people, '')
        self._ps_put(self._ps_fix, '')
        for k, e in self._ps_handle.items():
            self._ps_put(e, '')
        self._ps_mem_lbl.config(text='')
        self._ps_hist = []; self._ps_hist_i = -1
        for key, _l, _c, fields in PS_PLATFORMS:
            for f in fields:
                self._ps_cards[key]['fields'][f]['box'].delete('1.0', 'end')
        for w in self._ps_notes.winfo_children():
            w.destroy()
        self._ps_angle_lbl.config(text=''); self._ps_nav_lbl.config(text='')
        self._ps_prev_btn.config(state='disabled'); self._ps_next_btn.config(state='disabled')
        self._ps_refresh_cards(); self._ps_set_iter_state(False)
        self._ps_set_status('Fresh clip. Nothing carried over from the last one.', FG2)

    def _ps_use_current(self):
        t = (getattr(self, 'transcript', '') or '').strip()
        if not t:
            self._ps_set_status('⚠ No transcript yet. Run Find Clips or Transcribe first.', YELLOW)
            return
        self._ps_put(self._ps_trans, t[:12000])
        self._ps_set_status(f'✅ Loaded the current transcript ({len(t):,} chars). A whole VOD is too much: use '
                            '"A found clip" to load just one clip.', GREEN if len(t) < 12000 else YELLOW)

    def _ps_pick_clip(self):
        """Menu of the clips Find Clips returned -> load only that clip's part of the transcript."""
        clips = list(getattr(self, 'clips', []) or [])
        if not clips:
            self._ps_set_status('⚠ No clips yet. Run Find Clips first.', YELLOW)
            return
        m = tk.Menu(self, tearoff=0, bg=BG3, fg=FG, activebackground=ACCENT, activeforeground='#000', bd=0)
        for i, c in enumerate(clips[:30]):
            m.add_command(label=f'{i + 1}.  {c.get("start", "")} - {c.get("end", "")}   {str(c.get("title", ""))[:46]}',
                          command=lambda c=c: self._ps_load_clip(c))
        try:
            m.tk_popup(self._ps_clip_btn.winfo_rootx(), self._ps_clip_btn.winfo_rooty() + self._ps_clip_btn.winfo_height())
        finally:
            m.grab_release()

    def _ps_load_clip(self, clip):
        def _sec(t):
            try:
                p = str(t).split(':')
                return sum(float(x) * m for x, m in zip(reversed(p), (1, 60, 3600)))
            except Exception:
                return None
        s, e = _sec(clip.get('start')), _sec(clip.get('end'))
        lines = []
        for ln in (getattr(self, 'transcript', '') or '').splitlines():
            m = re.match(r'\[(\d+):(\d+):(\d+)', ln)
            if not m:
                continue
            t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            if s is not None and e is not None and s - 1 <= t <= e + 1:
                lines.append(ln)
        if not lines:
            self._ps_set_status('⚠ Could not find that clip in the transcript.', YELLOW)
            return
        self._ps_put(self._ps_trans, '\n'.join(lines)[:12000])
        self._ps_hist = []; self._ps_hist_i = -1        # new clip -> old results no longer belong to it
        self._ps_set_status(f'✅ Loaded clip {clip.get("start", "")} - {clip.get("end", "")} ({len(lines)} lines).', GREEN)

    def _ps_load_video(self):
        import tkinter.filedialog as _fd
        vp = _fd.askopenfilename(filetypes=[('Video / audio', '*.mp4 *.mkv *.mov *.webm *.avi *.mp3 *.m4a *.wav'), ('All', '*.*')])
        if not vp:
            return
        model = self.v_whisper.get()
        if not model or model == 'auto':
            model = 'base'
        use_gpu = self.v_use_gpu_whisper.get() if hasattr(self, 'v_use_gpu_whisper') else True
        self._ps_set_status(f'🎬 Transcribing {Path(vp).name} [{model}]...', FG2)
        self._ps_gen_btn.config(state='disabled')

        def _run():
            try:
                ff = find_ffmpeg()
                res = _do_transcribe(vid=vp, model_size=model, use_gpu=use_gpu, ffmpeg_path=ff,
                                     log_cb=lambda m, col=FG2: self.after(0, lambda t=str(m)[:90]: self._ps_set_status(t)))
                segs = (res or {}).get('segments') or []
                if not segs:
                    self.after(0, lambda: self._ps_set_status('⚠ No speech found in that file.', YELLOW))
                else:
                    txt = '\n'.join(f'[{ts(s["start"])}] {s["text"].strip()}' for s in segs)
                    def _ok():
                        self._ps_put(self._ps_trans, txt[:12000])
                        self._ps_set_status(f'✅ Transcribed {len(segs)} segments.', GREEN)
                    self.after(0, _ok)
            except Exception as ex:
                _why = str(ex)[:90]
                self.after(0, lambda: self._ps_set_status(f'❌ {_why}', RED))
            finally:
                self.after(0, lambda: self._ps_gen_btn.config(state='normal'))
        threading.Thread(target=_run, daemon=True).start()

    def _ps_recall_handles(self):
        """Fill the handle boxes from memory for the first person named (and undo the previous person's autofill)."""
        prev = getattr(self, '_ps_autofill', {})
        for k, e in self._ps_handle.items():
            if prev.get(k) and self._ps_val(e) == prev[k]:
                self._ps_put(e, '')
        self._ps_autofill = {}
        mem = self._ps_mem_load().get(self._ps_mem_key(self._ps_val(self._ps_people)))
        if mem:
            for k, e in self._ps_handle.items():
                if mem.get(k) and not self._ps_val(e):
                    self._ps_put(e, mem[k]); self._ps_autofill[k] = mem[k]
            self._ps_mem_lbl.config(text='💾 handles remembered')
        else:
            self._ps_mem_lbl.config(text='')

    def _ps_remember_handles(self, people, handles):
        key = self._ps_mem_key(people)
        if not key or not any(handles.values()):
            return
        try:
            mem = self._ps_mem_load()
            mem[key] = {**handles, 'name': people.split(',')[0].strip()}
            self._ps_mem_path().write_text(json.dumps(mem, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _ps_inputs(self):
        return {
            'transcript': self._ps_val(self._ps_trans),
            'angle': self._ps_val(self._ps_angle),
            'people': self._ps_val(self._ps_people),
            'seex': self._ps_seex.get(),
            'platforms': [k for k, *_ in PS_PLATFORMS if self._ps_plats[k].get()],
            'handles': {k: self._ps_val(e) for k, e in self._ps_handle.items()},
            'rules': self._ps_val(self._ps_rules),
            'correction': self._ps_val(self._ps_fix),
        }

    # ── generation ────────────────────────────────────────────────────────────────

    def _ps_generate(self, task='new', only=None):
        if self._ps_busy:
            return
        inp = self._ps_inputs()
        if not inp['transcript'] and not inp['angle']:
            self._ps_set_status('⚠ Paste a transcript or describe the clip first.', YELLOW)
            return
        plats = list(only or inp['platforms'])
        if not plats:
            self._ps_set_status('⚠ Tick at least one platform.', YELLOW)
            return
        previous = self._ps_snapshot() if task != 'new' else None
        if task != 'new' and not previous:
            task = 'new'
        correction = inp['correction'] if task == 'fix' else ''
        if task == 'fix' and not correction:
            self._ps_set_status('⚠ Type the correction first (e.g. "it was NIBBLES, not kisses").', YELLOW)
            return
        # remember the things that should survive between clips
        try:
            self.cfg['ps_seex'] = inp['seex']; self.cfg['ps_rules'] = inp['rules']; self.cfg['ps_plats'] = inp['platforms']
            save_cfg(self.cfg)
        except Exception:
            pass
        self._ps_remember_handles(inp['people'], inp['handles'])
        self._ps_busy = True
        self._ps_gen_btn.config(state='disabled', text='⏳  Writing...')
        self._ps_set_iter_state(False)
        self._ps_set_status('Writing...', FG2)
        threading.Thread(target=self._ps_worker, args=(inp, task, previous, correction, plats), daemon=True).start()

    def _ps_call_ai(self, lib, key, sysm, user, max_tokens):
        if lib == 'gemini':
            return _gemini_complete(key, 'write', sysm + '\n\n' + user, max_tokens, 0.9)
        msgs = [{'role': 'system', 'content': sysm}, {'role': 'user', 'content': user}]
        if lib == 'groq':
            return _groq_complete(key, 'write', msgs, max_tokens, 0.9)
        return _openrouter_complete(key, 'write', msgs, max_tokens, 0.9, timeout=90)

    def _ps_worker(self, inp, task, previous, correction, plats):
        try:
            for _pk, _ck in (('Groq (Free)', 'key_groq'), ('Google Gemini (Free)', 'key_gemini'),
                             ('OpenRouter (Free models)', 'key_openrouter')):
                if not self._keys.get(_pk, '').strip() and self.cfg.get(_ck, '').strip():
                    self._keys[_pk] = self.cfg[_ck].strip()
            pool = ps_key_pool(self._keys, getattr(self, '_extra_keys', {}), getattr(self, '_extra_keys_enabled', {}))
            if not pool:
                raise ValueError('No API key saved. Open Settings and add a free Gemini, OpenRouter or Groq key.')
            parsed, used, last = None, '', None
            for lib, key in pool:
                # Groq's free plan allows ~8K tokens/minute in total: the master prompt alone is ~5K, so give it less
                lim, mx = (2800, 1100) if lib == 'groq' else (12000, 1800)
                sysm, user = ps_build_prompt(inp['transcript'], plats, inp['angle'], inp['people'], inp['handles'],
                                             inp['seex'], inp['rules'], task, previous, correction, lim)
                self.after(0, lambda l=lib: self._ps_set_status(f'Writing with {l.title()}...'))
                try:
                    txt = self._ps_call_ai(lib, key, sysm, user, mx)
                except Exception as ex:
                    last = ex
                    self.log(f'[Post Studio] {lib} failed: {str(ex)[:140]}', YELLOW)
                    continue
                got = ps_parse(txt)
                if not any(k in got for k in plats):
                    last = ValueError('The AI did not follow the output format.')
                    self.log(f'[Post Studio] {lib} gave an unparseable reply: {txt[:120]!r}', YELLOW)
                    continue
                parsed, used = got, lib
                break
            if parsed is None:
                raise last or RuntimeError('No provider answered.')
            merged = {k: v for k, v in (previous or {}).items() if k in ('angle', 'tiktok', 'instagram', 'youtube', 'x')}
            for k, v in parsed.items():
                if k == 'angle' or k in plats:
                    merged[k] = v
            all_plats = [k for k, *_ in PS_PLATFORMS if k in merged]
            fixed, fixes, warns = ps_enforce(merged, all_plats, inp['seex'], inp['people'], inp['transcript'])
            fixed['fixes'], fixed['warns'] = fixes, warns
            fixed['reminders'] = ps_creator_reminders(inp['people'], inp['transcript'], inp['handles'])
            fixed['provider'] = used

            def _done():
                self._ps_hist.append(fixed); self._ps_hist_i = len(self._ps_hist) - 1
                self._ps_show(fixed)
                self._ps_put(self._ps_fix, '')
                self._ps_busy = False
                self._ps_gen_btn.config(state='normal', text='⚡  WRITE THE POSTS')
                self._ps_set_iter_state(True)
                self._ps_set_status(f'✅ Done ({used.title()}).', GREEN)
            self.after(0, _done)
        except Exception as ex:
            _why = str(ex)
            self.log(f'[Post Studio] {traceback.format_exc()}', RED)
            def _fail():
                self._ps_busy = False
                self._ps_gen_btn.config(state='normal', text='⚡  WRITE THE POSTS')
                self._ps_set_iter_state(self._ps_current() is not None)
                self._ps_set_status(f'❌ {_why[:200]}', RED)
            self.after(0, _fail)


    # ═══════════════════════════════════════════════════════════════════════════
    # DOWNLOADER TAB
    # ═══════════════════════════════════════════════════════════════════════════


    def _build_dl_tab(self, p):
        # Mode bar: paste links (default) or browse a Kick / Twitch / YouTube channel
        _mb = tk.Frame(p, bg=BG2); _mb.pack(fill='x')
        self._dl_mode_btns = {}
        for _k, _t in (('download', '⬇  Download links'), ('browse', '📺  Browse channels (Kick · Twitch · YouTube)')):
            _b = tk.Button(_mb, text=_t, font=('Segoe UI', 9), relief='flat', bd=0, cursor='hand2', padx=16, pady=7,
                           command=lambda k=_k: self._dl_set_mode(k))
            _b.pack(side='left', padx=(8 if _k == 'download' else 2, 2), pady=6)
            self._dl_mode_btns[_k] = _b
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')
        self._dl_main = tk.Frame(p, bg=BG); self._dl_main.pack(fill='both', expand=True)
        self._dl_browse = tk.Frame(p, bg=BG)          # built the first time it is shown
        self._br_built = False
        self._dl_mode = 'download'
        p = self._dl_main                              # the rest of this builder fills the "links" page

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
        tk.Label(q_hdr, text='📋  DOWNLOAD LINKS', font=('Segoe UI',9,'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(q_hdr, text='  paste URLs one per line — YouTube · Twitch · Kick · X/Twitter · TikTok',
                 font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self._dl_queue_status = tk.Label(q_hdr, text='', font=FONT_SMALL, fg=FG2, bg=BG)
        self._dl_queue_status.pack(side='right')
        q_frame = tk.Frame(p, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        q_frame.pack(fill='x', padx=20, pady=(0,4))
        self._dl_queue_box = tk.Text(q_frame, height=10, font=FONT_MONO_S,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat',
                 bd=6, wrap='none')
        self._dl_queue_box.pack(side='left', fill='both', expand=True)
        _qs = tk.Scrollbar(q_frame, command=self._dl_queue_box.yview)
        _qs.pack(side='right', fill='y')
        self._dl_queue_box.config(yscrollcommand=_qs.set)

        # Single action row — one download button, cancel, clear, auto-load
        dl_act_row = tk.Frame(p, bg=BG); dl_act_row.pack(fill='x', padx=20, pady=(4,6))
        self._dl_go_btn = tk.Button(dl_act_row, text='⬇  Download All',
                  font=('Segoe UI',9,'bold'), bg=ACCENT, fg='#000',
                  relief='flat', bd=0, cursor='hand2', padx=14, pady=6,
                  activebackground=ACCENT2, command=self._dl_start_queue)
        self._dl_go_btn.pack(side='left')
        self._dl_cancel_btn = tk.Button(dl_act_row, text='✕ Cancel', font=FONT_SMALL,
                  bg=RED, fg='#fff', relief='flat', bd=0, cursor='hand2', padx=10, pady=6,
                  command=self._dl_cancel)
        tk.Button(dl_act_row, text='✕ Clear', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=10, pady=6,
                  command=lambda: self._dl_queue_box.delete('1.0', 'end')
                  ).pack(side='left', padx=6)
        tk.Checkbutton(dl_act_row, text='Auto-load into Clip Finder after download',
                       variable=self.v_auto_load, font=FONT_SMALL, fg=FG2, bg=BG,
                       selectcolor=BG3, activebackground=BG, relief='flat',
                       cursor='hand2').pack(side='left', padx=12)
        # Mutually exclusive with auto-load (ticking one unticks the other)
        tk.Checkbutton(dl_act_row, text='Auto-transcribe after download',
                       variable=self.v_auto_transcribe, font=FONT_SMALL, fg=FG2, bg=BG,
                       selectcolor=BG3, activebackground=BG, relief='flat',
                       cursor='hand2').pack(side='left', padx=(0, 12))
        # Keep _dl_queue_btn as alias so existing code doesn't break
        self._dl_queue_btn = self._dl_go_btn
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
        self._dl_set_mode('download')

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
        _q_ok = [0]
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
                try:
                    folder = self.v_dl_folder.get().strip()
                    Path(folder).mkdir(parents=True, exist_ok=True)
                    self._dl_log_write(f'\n[Queue {i+1}/{len(urls)}] {url}', ACCENT2)
                    self._dl_log_write(f'Starting download...', FG2)
                    self._dl_log_write(f'URL: {url}', FG2)
                    self._dl_run(url, folder)
                    if getattr(self, '_dl_last_ok', False):
                        _q_ok[0] += 1
                except Exception as _qe:
                    self._dl_log_write(f'❌ Queue item {i+1} failed: {_qe}', RED)
                self._in_queue = True  # keep flag set until loop ends
                import time; time.sleep(0.5)
            self._in_queue = False
            self.after(0, lambda: (
                self._dl_queue_btn.config(state='normal', text='⬇  Download Queue'),
                self._dl_queue_status.config(
                    text=(f'✅ {_q_ok[0]}/{len(urls)} done' if _q_ok[0] == len(urls) else f'⚠ {_q_ok[0]}/{len(urls)} downloaded')
                         if not self._dl_queue_cancel else '⛔ Cancelled'),
                self.set_progress('', pct=0),
                self._dl_run_pending_transcribe(),   # auto-transcribe waits until the whole queue is done
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
        self._dl_last_ok = False
        _out_folder = _dl_tmp_id = None       # set once known; used by the cleanup in `finally`
        try:
            try:
                import yt_dlp, shutil as _sh, re as _re, urllib.request as _ur, json as _json
            except PermissionError as _pe:
                raise RuntimeError(
                    'Permission denied accessing yt-dlp files.\n\n'
                    'Fix: Close ClipFinder, right-click the ClipFinder shortcut → '
                    'Properties → Compatibility → uncheck "Run as administrator", '
                    'then relaunch normally.\n\n'
                    'If that doesn\'t work, go to Settings → Update All Packages to repair.'
                )

            # ── VOD detection — manual toggle OR auto-detect ──────────────
            _manual_vod = getattr(self, 'v_vod_mode', None)
            _manual_vod = _manual_vod.get() if _manual_vod else False
            _is_vod_url = _manual_vod or bool(_KICK_VOD_RE.search(url)) or any(p in url.lower() for p in [
                'twitch.tv/videos/',
            ])
            # For YouTube/generic we detect after getting info
            _vod_folder = str(Path(folder) / 'vod')
            _clip_folder = folder

            quality = self.v_dl_quality.get()
            if quality == 'audio':
                fmt = 'bestaudio/best'
                pp  = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
            elif quality == 'best':
                # iOS serves combined streams — bestvideo+bestaudio won't match
                # Include combined stream fallbacks so iOS client works properly
                fmt = ('bestvideo+bestaudio'
                       '/bestvideo[ext=mp4]+bestaudio[ext=m4a]'
                       '/best[ext=mp4][height>=1080]'
                       '/best[ext=mp4][height>=720]'
                       '/best[ext=mp4]'
                       '/best')
                pp  = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'},
                       {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
            else:
                # Specific resolution — combined stream fallbacks for iOS
                fmt = (f'bestvideo[height<={quality}]+bestaudio'
                       f'/bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]'
                       f'/best[height<={quality}][ext=mp4]'
                       f'/best[height<={quality}]'
                       f'/best[ext=mp4]'
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

            # Use timestamp in temp filename so yt-dlp never thinks file exists already
            import time as _dl_time
            _dl_tmp_id = int(_dl_time.time())

            ydl_opts = {
                'format': fmt,
                'outtmpl': str(Path(_out_folder) / f'_cftmp_{_dl_tmp_id}_%(uploader)s - %(title)s.%(ext)s'),
                'postprocessors': pp,
                'merge_output_format': 'mp4',
                'quiet': False,
                'no_warnings': False,
                'noplaylist': True,
                'playlist_items': '1',
                'verbose': False,
                'progress_hooks': [self._dl_progress_hook],
                'concurrent_fragment_downloads': 8,  # parallel fragments = much faster for VODs
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
            }
            if ffmpeg_loc:
                ydl_opts['ffmpeg_location'] = ffmpeg_loc
            if quality != 'audio':
                # keep the video stream, AAC audio (audio-only downloads must NOT get these: they would
                # override the mp3 encoder of FFmpegExtractAudio)
                ydl_opts['postprocessor_args'] = {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']}

            # Kick.com — resolve the VOD/clip to its public stream URL ourselves. yt-dlp's
            # Kick extractor still calls an API that 404s for the new UUIDv7 VOD ids.
            if _KICK_PAGE_RE.match(url):
                _kick_kind = 'clip' if _KICK_CLIP_RE.search(url) else 'VOD'
                _ck_early  = self.v_cookies.get().strip() if hasattr(self, 'v_cookies') else ''
                self._dl_log_write(f'🔧  Kick {_kick_kind} — resolving stream (Chrome impersonation)...', FG2)
                try:
                    _kr = kick_resolve(url, token=_kick_session_token(_ck_early), log=self._dl_log_write)
                except KickError:
                    raise          # message is already user-facing — shown as the download error
                except Exception as _ke:
                    _kr = None
                    self._dl_log_write(f'⚠️  Kick resolver error: {str(_ke)[:120]} — trying yt-dlp directly', YELLOW)
                if _kr:
                    self._dl_log_write('✅  Got Kick stream URL', FG2)
                    if _kr.get('is_live') and _kr['kind'] == 'vod':
                        self._dl_log_write('ℹ️  This VOD belongs to a stream that is still live — you get everything recorded so far', FG2)
                    url = _kr['stream_url']
                    ydl_opts['format'] = 'best'
                    # Clean "<channel> - <title>" file name (emoji and reserved characters removed)
                    _ks = _re.sub(r'[^\w\s\-.,!&@#()\[\]+]', '', _kr.get('channel') or '').strip() or 'Kick'
                    _kt = _re.sub(r'\s+', ' ', _re.sub(r'[^\w\s\-.,!&@#()\[\]+]', '', _kr.get('title') or '')).strip()[:60] \
                          or ('clip' if _kr['kind'] == 'clip' else 'VOD')
                    ydl_opts['outtmpl'] = str(Path(_out_folder) / f'_cftmp_{_dl_tmp_id}_{_ks} - {_kt}.%(ext)s')
                    self._dl_log_write(f'📁  Name: {_ks} - {_kt} - ClipFinder', FG2)
                ydl_opts['http_headers'] = {'Referer': 'https://kick.com/', 'User-Agent': _KICK_UA}

            # Cookies
            cookies = self.v_cookies.get().strip()
            browser = getattr(self, 'v_cookies_browser', None)
            browser = browser.get().strip() if browser else ''
            try:
                from urllib.parse import urlparse as _urlparse
                _host = (_urlparse(url).hostname or '').lower()
            except Exception:
                _host = ''
            def _host_is(*names):
                return any(_host == n or _host.endswith('.' + n) for n in names)
            is_youtube = _host_is('youtube.com', 'youtu.be', 'youtube-nocookie.com')
            is_twitter = _host_is('twitter.com', 'x.com', 't.co')
            is_instagram = _host_is('instagram.com')
            # Convert Rumble embed URLs to regular URLs
            if 'rumble.com/embed/' in url.lower():
                import re as _re_rum
                _rum_id = _re_rum.search(r'rumble\.com/embed/([^/?]+)', url, _re_rum.I)
                if _rum_id:
                    url = f'https://rumble.com/v{_rum_id.group(1)}.html'
                    self._dl_log_write(f'🔄 Rumble embed → {url}', FG2)
            # Rumble needs browser-like headers to bypass Cloudflare
            if 'rumble.com' in url.lower():
                ydl_opts['http_headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Referer': 'https://rumble.com/',
                    'Sec-Fetch-Mode': 'navigate',
                }
                self._dl_log_write('🛡 Using browser headers for Rumble', FG2)
            has_cookies = bool(cookies and Path(cookies).exists())
            has_browser = bool(browser)

            if (is_youtube or is_instagram) and has_browser:
                # Browser cookies unlock YouTube HD / age-gated videos and Instagram private content.
                # yt-dlp reads the browser's cookie database itself; if the browser has it locked the
                # error handler below tells the user to close the browser.
                ydl_opts['cookiesfrombrowser'] = (browser, None, None, None)
                self._dl_log_write(f'🍪  Using {browser} browser cookies', FG2)
            elif has_cookies:
                ydl_opts['cookiefile'] = cookies
                self._dl_log_write('🍪  Using cookies.txt', FG2)
            elif is_twitter:
                self._dl_log_write('⚠️  X/Twitter requires cookies — add cookies.txt in Downloader settings\n'
                                   '    Get it free: browser extension "Get cookies.txt LOCALLY" → export from x.com', YELLOW)
            elif is_youtube:
                self._dl_log_write('⚠️  No browser set — pick your browser in Settings → Cookies for YouTube HD', YELLOW)

            # Try with web+mweb first, fall back to default if it fails
            def _try_dl(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info = None
            last_err = None
            is_twitch  = 'twitch.tv' in url.lower()
            is_tiktok  = any(x in url.lower() for x in ['tiktok.com', 'vm.tiktok.com'])
            client_attempts = []  # defined here so fallback loop never errors

            if is_youtube:
                # yt-dlp solves YouTube's player challenges with a JavaScript runtime (Node >= 22 or Deno)
                # plus the yt-dlp-ejs package. Without one YouTube only offers storyboards/low quality.
                _js = yt_js_runtime_opts(status_cb=lambda m: self._dl_log_write(f'🟢 {m}', FG2))
                if _js:
                    ydl_opts.update(_js)
                else:
                    self._dl_log_write('⚠️  No JavaScript runtime found (Node.js 22+ or Deno) - YouTube may only give low quality', YELLOW)
                if quality == 'audio':
                    client_attempts = [(None, fmt), (None, 'bestaudio/best')]
                else:
                    client_attempts = [
                        (None, fmt),
                        (None, 'bestvideo+bestaudio/best[ext=mp4]/best'),
                        (None, 'best'),
                    ]

            elif is_twitch:
                # Twitch VODs: chunked format is highest quality
                # Clips: just use best
                twitch_fmt = (f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'
                              if quality not in ('best', 'audio')
                              else 'bestvideo+bestaudio/best')
                client_attempts = [
                    (None, twitch_fmt),
                    (None, 'best[ext=mp4]/best'),
                ]
            elif is_tiktok:
                # TikTok: no-watermark format when available, then best
                tiktok_fmt = 'bestvideo[format_id*=bytevc1]+bestaudio/bestvideo+bestaudio/best'
                client_attempts = [
                    (None, tiktok_fmt),
                    (None, 'best[ext=mp4]/best'),
                    (None, 'best'),
                ]
            elif is_twitter:
                # Twitter/X: just grab best available, no client tricks needed
                twitter_fmt = fmt if quality not in ('best',) else 'bestvideo+bestaudio/best[ext=mp4]/best'
                client_attempts = [
                    (None, twitter_fmt),
                    (None, 'best[ext=mp4]/best'),
                ]
            elif is_instagram:
                # Instagram: cookies required for stories/private content
                # Don't use web client — it strips cookies
                client_attempts = [
                    (None, 'best[ext=mp4]/best'),
                    (None, 'best'),
                ]
            else:
                client_attempts = [
                    (None,                 fmt),
                    (None,                 'best[ext=mp4]/best'),
                ]

            # Kick: the resolver above already swapped a kick.com page URL for its public stream
            # URL (stream./clips. CDN hosts are downloaded directly by yt-dlp). If the URL is
            # STILL a kick.com page here, the resolver crashed - give yt-dlp's own extractor a go.
            is_kick = bool(_KICK_PAGE_RE.match(url))
            _kick_direct_ok = False
            if is_kick:
                _kick_token = _kick_session_token(ydl_opts.get('cookiefile', ''))
                if _kick_token:
                    ydl_opts['http_headers'] = {'Authorization': f'Bearer {_kick_token}',
                                                'Referer': 'https://kick.com/'}
                client_attempts = [
                    (None, 'best[ext=mp4]/best'),
                    (None, 'best'),
                ]
            if not (is_youtube and quality != 'audio' and info) and not (is_kick and _kick_direct_ok):
              for _ci, (_clients, _fmt) in enumerate(client_attempts):
                try:
                    _opts = dict(ydl_opts)
                    _opts['format'] = _fmt
                    # YouTube with cookiefile causes issues — browser cookies via cookiesfrombrowser is fine
                    if is_youtube and has_cookies and not has_browser:
                        _opts.pop('cookiefile', None)
                    # Twitch: public VODs download anonymously. A stale or foreign
                    # auth-token in cookies.txt makes Twitch's GQL metadata API return
                    # HTTP 401. Try anonymous first; only fall back to cookies (needed
                    # for subscriber-only VODs) on the later attempt.
                    if is_twitch and _ci == 0:
                        _opts.pop('cookiefile', None)
                        _opts.pop('cookiesfrombrowser', None)
                    client_str = '+'.join(_clients) if _clients else 'default'
                    self._dl_log_write(f'Trying {client_str} [{_fmt[:40]}]...', FG2)
                    info = _try_dl(_opts)
                    if info:
                        # Log what actually got downloaded
                        _res = info.get('height') or info.get('resolution','?')
                        _fmt_id = info.get('format_id','?')
                        self._dl_log_write(f'✅ Got: {_res}p format={_fmt_id}', GREEN)
                        break
                except Exception as _ex:
                    _ex_str = str(_ex)
                    last_err = _ex
                    if 'cancelled by user' in _ex_str.lower() or getattr(self, '_dl_cancel_requested', False):
                        raise                      # do not retry the next format after a Cancel
                    self._dl_log_write(f'  ↳ Failed: {_ex_str[:80]}', YELLOW)
                    _ex_low = _ex_str.lower()
                    if is_twitter and ('authenticat' in _ex_low or 'login' in _ex_low or 'log in' in _ex_low
                                       or _re.search(r'\b(?:401|403)\b', _ex_str)):
                        raise Exception(
                            'X/Twitter download failed — authentication required.\n\n'
                            'Fix: add a cookies.txt file from your logged-in X account.\n'
                            '1. Install browser extension "Get cookies.txt LOCALLY"\n'
                            '2. Log into x.com in your browser\n'
                            '3. Click the extension → Export cookies for x.com\n'
                            '4. In ClipFinder Downloader tab → set the cookies.txt path')
                    if is_instagram and ('log in' in _ex_low or 'login' in _ex_low or 'authenticat' in _ex_low):
                        # yt-dlp can't handle Instagram Stories — try gallery-dl instead
                        self._dl_log_write('⚠ yt-dlp failed for Instagram — trying gallery-dl...', YELLOW)
                        try:
                            _gdl_result = self._dl_instagram_gallery_dl(url, _out_folder, cookies)
                            if _gdl_result:
                                info = {'title': Path(_gdl_result).stem, '_gallery_dl_path': _gdl_result}
                                break
                        except Exception as _gdl_err:
                            self._dl_log_write(f'gallery-dl also failed: {_gdl_err}', RED)
                        raise Exception(
                            'Instagram download failed — Stories require login cookies.\n\n'
                            'Fix:\n'
                            '1. Install "Get cookies.txt LOCALLY" browser extension\n'
                            '2. Log into instagram.com in your browser\n'
                            '3. Click the extension → Export cookies for instagram.com\n'
                            '4. Save the file and set its path in Downloader → Cookies tab\n\n'
                            'Note: Instagram Stories are heavily restricted and may still fail.')
                    if 'could not copy' in _ex_str.lower() and 'cookie database' in _ex_str.lower():
                        raise Exception(
                            'Could not read browser cookies — browser is open and locking the cookie file.\n\n'
                            'Fix: close your browser completely, then try the download again.\n'
                            'Or export a cookies.txt file manually using "Get cookies.txt LOCALLY" extension.')
                    continue
            if not info:
                if is_twitch and last_err and 'does not exist' in str(last_err).lower():
                    raise Exception(
                        'Twitch says this video does not exist.\n\n'
                        'The VOD was deleted or has expired - Twitch only keeps past broadcasts for 14-60 days '
                        'depending on the channel. Check the link, or grab a newer VOD.')
                if is_twitch and last_err and ('401' in str(last_err) or 'unauthorized' in str(last_err).lower()):
                    raise Exception(
                        'Twitch VOD download failed (HTTP 401 Unauthorized).\n\n'
                        'Most common cause: your cookies.txt has an expired Twitch login, which\n'
                        'Twitch rejects. Public VODs need NO login.\n\n'
                        'Fix:\n'
                        '1. Clear the cookies.txt path in Downloader settings (public VODs work without it), OR\n'
                        '2. Export fresh cookies from a logged-in twitch.tv (for subscriber-only VODs).\n'
                        '3. If it still fails, update yt-dlp via Settings → Update All Packages.')
                raise last_err or Exception('All download attempts failed')

            # Post-download processing
            title    = info.get('title', 'video') or 'video'
            uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id', '')
            # Fix NA uploader — extract from URL path
            if not uploader or uploader.strip().upper() == 'NA':
                import re as _re_url
                _url_match = _re_url.search(r'(?:twitch\.tv|kick\.com|youtube\.com/c?|x\.com)/([^/?&#]+)', url)
                uploader = _url_match.group(1) if _url_match else ''
            # Fix generic titles like "master", "index", "playlist"
            if title.lower() in ('master', 'index', 'playlist', 'na', 'video', ''):
                title = info.get('description', '')[:60] or info.get('webpage_url_basename','') or title

            # Find downloaded file path first
            downloaded = None
            try:
                if info.get('_gallery_dl_path'):
                    downloaded = info['_gallery_dl_path']
                else:
                    rds = info.get('requested_downloads', [])
                    if rds and rds[0].get('filepath'):
                        downloaded = rds[0]['filepath']
                        if not Path(downloaded).exists():
                            mp4 = str(Path(downloaded).with_suffix('.mp4'))
                            if Path(mp4).exists():
                                downloaded = mp4
            except Exception:
                pass

            # Rename: strip temp prefix, add ClipFinder, handle duplicates with (1)(2) etc
            if downloaded and Path(downloaded).exists():
                import re as _re_fn
                _safe_up = _re_fn.sub(r'[\\/:*?"<>|]', '', uploader or '').strip()
                _safe_ti = _re_fn.sub(r'[\\/:*?"<>|]', '', title or '').strip()[:60]
                _ext = Path(downloaded).suffix or '.mp4'      # keep .mp3 / .mkv / .jpg etc.
                if _safe_up and _safe_ti:   _new_name = f'{_safe_up} - {_safe_ti} - ClipFinder{_ext}'
                elif _safe_ti:              _new_name = f'{_safe_ti} - ClipFinder{_ext}'
                elif _safe_up:             _new_name = f'{_safe_up} - ClipFinder{_ext}'
                else:                      _new_name = f'ClipFinder_{_dl_tmp_id}{_ext}'
                try:
                    _new_path = Path(downloaded).parent / _new_name
                    # Always add (1)(2) if same name exists — never overwrite or skip
                    if _new_path.exists() and _new_path.resolve() != Path(downloaded).resolve():
                        _stem, _ext = _new_path.stem, _new_path.suffix
                        _n = 1
                        while _new_path.exists():
                            _new_path = Path(downloaded).parent / f'{_stem} ({_n}){_ext}'
                            _n += 1
                    Path(downloaded).rename(_new_path)
                    downloaded = str(_new_path)
                    self._last_dl_path = downloaded
                    self._dl_log_write(f'✏️  Saved as: {_new_path.name}', FG2)
                except Exception as _re:
                    self._dl_log_write(f'⚠ Rename failed: {_re}', YELLOW)
            self._dl_log_write('', FG2)
            self._dl_log_write(f'✅  Done: {title}', GREEN)
            self._dl_log_write(f'📁  Saved to: {folder}', FG2)

            # Fallback: newest media file THIS download produced (never an older file from a previous run)
            try:
                if not downloaded:
                    video_exts = {'.mp4','.mkv','.webm','.mov','.avi','.mp3','.m4a'}
                    for f in sorted(Path(_out_folder).glob('*'),
                                    key=lambda x: x.stat().st_mtime, reverse=True):
                        if f.suffix.lower() in video_exts and f.stat().st_mtime >= _dl_tmp_id - 5:
                            downloaded = str(f); break
            except Exception:
                pass

            if downloaded:
                self._dl_last_ok = True
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
                        # Re-set after tab switch to survive any focus-out resets
                        self.after(50, lambda _p=p: self.v_video.set(_p))
                        self.after(60, lambda: self._video_entry.config(fg=FG) if hasattr(self, '_video_entry') else None)
                        self.log(f'✅ Loaded: {Path(p).name} — hit ▶ FIND CLIPS', GREEN)
                    elif self.v_auto_transcribe.get():
                        self._dl_log_write('📝  Sending to Transcribe...', ACCENT2)
                        self._dl_auto_transcribe(p)
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
            self._load_after_dl = False       # a failed / cancelled download must not arm the next one
            if not self._dl_last_ok and _out_folder and _dl_tmp_id:
                # partial files of a failed or cancelled download (_cftmp_<id>_*.part / .ytdl / .f137.mp4 ...)
                try:
                    for _f in Path(_out_folder).glob(f'_cftmp_{_dl_tmp_id}_*'):
                        try: _f.unlink()
                        except OSError: pass
                except Exception:
                    pass
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


    def _dl_instagram_gallery_dl(self, url, outdir, cookies=None):
        """Use gallery-dl as fallback for Instagram Stories — handles auth better than yt-dlp."""
        import subprocess as _sp_gdl, sys as _sys_gdl

        # Install gallery-dl if not present
        try:
            import gallery_dl as _gdl_check
        except ImportError:
            self._dl_log_write('Installing gallery-dl for Instagram support...', YELLOW)
            _r = _sp_gdl.run([_sys_gdl.executable, '-m', 'pip', 'install', 'gallery-dl',
                              '--target', str(PKGS_DIR), '-q'],
                             capture_output=True, text=True)
            if _r.returncode != 0:
                raise Exception(f'gallery-dl install failed: {_r.stderr[-200:]}')
            _ensure_pkgs_on_path()

        # Build gallery-dl command
        cmd = [_sys_gdl.executable, '-m', 'gallery_dl',
               '--dest', str(outdir),
               '--filename', '{username}_{id}.{extension}']

        if cookies and Path(cookies).exists():
            cmd += ['--cookies', cookies]

        cmd.append(url)

        self._dl_log_write(f'gallery-dl → {url[:60]}', FG2)
        _r = _sp_gdl.run(cmd, capture_output=True, text=True,
                         env={**__import__('os').environ, 'PYTHONPATH': str(PKGS_DIR)})

        if _r.returncode != 0:
            raise Exception(_r.stderr[-300:] or _r.stdout[-300:])

        # Find downloaded file
        import glob as _glob
        _patterns = [str(Path(outdir) / '*.mp4'), str(Path(outdir) / '*.jpg'),
                     str(Path(outdir) / '**' / '*.mp4')]
        for _pat in _patterns:
            _files = sorted(_glob.glob(_pat, recursive=True), key=lambda f: Path(f).stat().st_mtime, reverse=True)
            if _files:
                self._dl_log_write(f'✅ gallery-dl downloaded: {Path(_files[0]).name}', GREEN)
                return _files[0]
        raise Exception('gallery-dl ran but no file found')

    def _dl_auto_load(self):
        if not self._last_dl_path: return
        p = self._last_dl_path
        self.v_video.set(p)
        # Set entry color to normal (not placeholder gray)
        if hasattr(self, '_video_entry'):
            self.after(0, lambda: self._video_entry.config(fg=FG))
        if not self.v_outdir.get():
            self.v_outdir.set(str(Path(p).parent))
        self._switch_nb('clips')
        # Re-set after tab switch in case focus events reset it
        self.after(50, lambda: self.v_video.set(p))
        self.after(60, lambda: self._video_entry.config(fg=FG) if hasattr(self, '_video_entry') else None)
        self.log(f'✅  Loaded into Clip Finder: {Path(p).name}', GREEN)
        self.log('Hit ▶ FIND CLIPS to analyze, or 📝 TRANSCRIBE ONLY for a quick tweet.', FG2)

    def _dl_auto_transcribe(self, path=None):
        """Send a downloaded file to the Transcript page and start transcribing it.

        While a download queue is still running this only remembers the file - the end of
        the queue hands it back (see _dl_run_pending_transcribe), so a transcription never
        competes with the next download. With several URLs the last file wins, the same as
        auto-load."""
        p = path or self._last_dl_path
        if not p or not Path(p).exists():
            return
        if getattr(self, '_in_queue', False):
            self._pending_transcribe = p
            return
        self._pending_transcribe = None
        self._switch_nb('transcript')       # builds the tab on first visit, so v_trans_file exists afterwards
        self.v_trans_file.set(p)
        if self.running:
            self.log('⚠  Another job is running — the file is loaded on the Transcript page; '
                     'click Transcribe when it finishes.', YELLOW)
            return
        self.log(f'📝  Auto-transcribing: {Path(p).name}', ACCENT)
        self.after(200, self._transcribe_standalone)

    def _dl_run_pending_transcribe(self):
        """Called when a download queue ends: transcribe the file that was held back."""
        p, self._pending_transcribe = self._pending_transcribe, None
        if p and self.v_auto_transcribe.get():
            self._dl_auto_transcribe(p)

    def _dl_autosave(self, *_):
        # Merge into self.cfg so nothing else gets lost
        self.cfg.update({
            'dl_folder':    self.v_dl_folder.get(),
            'cookies_file': self.v_cookies.get(),
            'dl_quality':   self.v_dl_quality.get(),
            'auto_load':    self.v_auto_load.get(),
            'auto_transcribe': self.v_auto_transcribe.get(),
        })
        save_cfg(self.cfg)

    def _dl_done_popup(self, filepath):
        # Skip popup when downloading as part of a queue
        if getattr(self, '_in_queue', False):
            self._dl_log_write(f'✅  Saved: {Path(filepath).name}', GREEN)
            return
        # The Toplevel was never created here (NameError on every finished download since v1.3.2)
        dlg = tk.Toplevel(self)
        dlg.title('Download Complete')
        dlg.configure(bg=BG2)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()//2 - 235
        y = self.winfo_y() + self.winfo_height()//2 - 80
        dlg.geometry(f'470x160+{x}+{y}')
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
        tk.Button(br, text='📝  Transcribe', font=FONT_SMALL, bg=BG3, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=5,
                  command=lambda: (dlg.destroy(), self._dl_auto_transcribe(filepath))
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
        tk.Label(left, text='⚠ Thumbnail search is still in beta — results may vary',
                 font=('Segoe UI', 7), fg=YELLOW, bg=BG, anchor='w'
                 ).pack(fill='x', padx=14, pady=(0,2))
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

        self.thumb_unsplash_var = tk.StringVar(value=self._keys.get('_unsplash',''))

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
        sec('QUALITY')
        self.thumb_pref_var = tk.StringVar(value='hd')
        pref_row = tk.Frame(left, bg=BG); pref_row.pack(anchor='w', padx=14)
        for val, lbl_text in [('hd', '📸 HD'), ('sd', '🖼 SD')]:
            tk.Radiobutton(pref_row, text=lbl_text, variable=self.thumb_pref_var, value=val,
                           font=FONT_SMALL, fg=FG, bg=BG, selectcolor=BG3,
                           activebackground=BG, relief='flat', cursor='hand2'
                           ).pack(side='left', padx=(0,16))
        div()

        # Image type
        sec('IMAGE TYPE')
        self.v_thumb_imgtype = tk.StringVar(value='portrait')
        for val, lbl_text in [
            ('portrait',   '🧑 Portrait / solo'),
            ('group',      '👥 Group photo'),
            ('screenshot', '🖥 Stream screenshot'),
            ('any',        '🔀 Any'),
        ]:
            tk.Radiobutton(left, text=lbl_text, variable=self.v_thumb_imgtype, value=val,
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
        self.thumb_go_btn.pack(fill='x', padx=14, pady=(4,2))

        # Stock toggle right below Find button
        self.v_thumb_stock_only = tk.BooleanVar(value=False)
        tk.Checkbutton(left, text='📦 Stock photos only (needs Unsplash key)',
                       variable=self.v_thumb_stock_only,
                       font=('Segoe UI', 7), fg=FG2, bg=BG, selectcolor=BG3,
                       activebackground=BG, relief='flat', cursor='hand2'
                       ).pack(anchor='w', padx=14, pady=(0,6))
        div()

        # Save All HD
        tk.Button(left, text='💾  SAVE ALL HD', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', pady=6,
                  command=self._thumb_save_all).pack(fill='x', padx=14)

        # Key status below Save All HD
        _us_key = self._keys.get('_unsplash','') or self.cfg.get('key_unsplash','')
        _us_has = bool(_us_key.strip())
        _arow = tk.Frame(left, bg=BG); _arow.pack(fill='x', padx=14, pady=(4,0))
        tk.Label(_arow, text='🔍 Image search: DuckDuckGo (no key needed)', font=('Segoe UI',7), fg=GREEN, bg=BG).pack(side='left')
        _arow2 = tk.Frame(left, bg=BG); _arow2.pack(fill='x', padx=14, pady=(2,0))
        tk.Label(_arow2, text='🔑 Unsplash (stock mode only):', font=('Segoe UI',7), fg=FG2, bg=BG).pack(side='left')
        tk.Label(_arow2, text='✅ Set' if _us_has else '○ Not set',
                 font=('Segoe UI',7,'bold'), fg=GREEN if _us_has else FG3, bg=BG).pack(side='left', padx=3)

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
            try:
                from PIL import Image
            except ImportError:
                raise ValueError(
                    'Pillow (image library) is broken or not installed.\n\n'
                    'Fix: go to Settings → Update Modules → Update All Packages, '
                    'then restart ClipFinder.')
            import urllib3; urllib3.disable_warnings()
            import warnings as _warn; _warn.filterwarnings('ignore', category=DeprecationWarning)
            import io, json as _json, re as _re

            query = self.thumb_query_var.get().strip()
            count = self.thumb_count_var.get()
            pref  = self.thumb_pref_var.get()  # 'hd' or 'sd'

            # Clean query — just the name, no extra fluff
            full_query = query

            self._thumb_set_status(f'Searching: "{full_query}"...')
            self.log(f'[Thumbnails] Searching: {full_query}')

            # Use curl_cffi if available (bypasses browser fingerprint blocks)
            # Falls back to requests if not installed
            sess = None
            try:
                from curl_cffi import requests as _cf
                sess = _cf.Session(impersonate='chrome124')
                self.log('[Thumbnails] Using curl_cffi session (browser mode)', FG2)
            except ImportError:
                pass
            if sess is None:
                import requests as _req
                sess = _req.Session()
                sess.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                })

            image_urls = self._thumb_search(sess, full_query, max_results=80)

            if not image_urls:
                raise ValueError(
                    'No images found.\n'
                    'Try a shorter search term e.g. "mizkif" not "mizkif streamer"\n'
                    'For stock photos toggle the checkbox and add an Unsplash key in Settings.')

            self.log(f'[Thumbnails] Got {len(image_urls)} URLs, downloading...')

            # Use a plain requests session for downloading — curl_cffi doesn't support stream well
            import requests as _req_dl
            dl_sess = _req_dl.Session()
            dl_sess.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://duckduckgo.com/',
            })

            scored = []
            ok = 0
            for idx, (img_url, known_w, known_h) in enumerate(image_urls):
                try:
                    self._thumb_set_status(
                        f'Checking image {idx+1}/{len(image_urls)} '
                        f'({ok} good so far)...')
                    resp = dl_sess.get(img_url, timeout=7, verify=False)
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
                    _raw40 = img.resize((40, 40)).convert("RGB").tobytes()
                    pixels = list(zip(_raw40[0::3], _raw40[1::3], _raw40[2::3]))
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

                    scored.append((score, data, img_url, w, h))
                    del img
                    ok += 1
                except Exception:
                    continue

            self.log(f'[Thumbnails] Loaded {len(scored)} images successfully')
            if not scored:
                raise ValueError('Could not load any images. Try a different search term.')

            scored.sort(key=lambda x: -x[0])
            results = []
            for rank, (score, data, url, w, h) in enumerate(scored[:count]):
                img = Image.open(io.BytesIO(data)).convert('RGB')
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

        except Exception as ex:
            err = traceback.format_exc()
            self.log(f'[Thumbnails] Error:\n{err}', RED)
            msg = str(ex).strip() if isinstance(ex, ValueError) else 'Error — check log.'
            self._thumb_set_status(msg, RED)
        finally:
            self._thumb_running = False
            self.after(0, lambda: self.thumb_go_btn.config(
                state='normal', text='🔍  FIND THUMBNAILS'))

    def _thumb_search(self, sess, query, max_results=40):
        """Image search using ddgs (DuckDuckGo) — zero setup, no API key needed.
        Stock mode uses Unsplash (optional free key)."""
        stock_only   = getattr(self, 'v_thumb_stock_only', None)
        stock_only   = stock_only.get() if stock_only else False
        unsplash_key = (self._keys.get('_unsplash','') or self.cfg.get('key_unsplash','')).strip()
        pref         = getattr(self, 'thumb_pref_var', None)
        hd_only      = (pref.get() == 'hd') if pref else True

        # ── STOCK PHOTOS MODE (Unsplash) ──────────────────────────────────────
        if stock_only:
            if not unsplash_key:
                raise ValueError(
                    'Stock photos mode needs an Unsplash API key.\n'
                    'Sign up free at unsplash.com/developers then add the key in Settings.')
            try:
                self.log('[Thumbnails] Stock mode: Unsplash...', FG2)
                r = sess.get('https://api.unsplash.com/search/photos',
                    params={'query': query, 'per_page': max_results, 'order_by': 'relevant'},
                    headers={'Authorization': f'Client-ID {unsplash_key}', 'Accept-Version': 'v1'},
                    timeout=10)
                if r.status_code == 200:
                    results = [(i['urls'].get('full') or i['urls'].get('regular',''),
                                i.get('width',1920), i.get('height',1080))
                               for i in r.json().get('results',[]) if i.get('urls')]
                    results = [x for x in results if x[0]]
                    self.log(f'[Thumbnails] Unsplash: {len(results)} results', FG2)
                    return results[:max_results]
                _http_err = f'Unsplash returned HTTP {r.status_code}: {(r.text or "")[:120]} - check your key/quota in Settings.'
            except Exception as ex:
                self.log(f'[Thumbnails] Unsplash error: {ex}', YELLOW)
                return []
            raise ValueError(_http_err)

        # ── REAL PEOPLE MODE — DuckDuckGo via ddgs library (no key needed) ────
        try:
            from ddgs import DDGS
        except ImportError:
            raise ValueError(
                'The ddgs package is not installed.\n'
                'Go to Settings → Update Modules and click Update All Packages.')

        try:
            self.log('[Thumbnails] Searching DuckDuckGo Images (ddgs)...', FG2)
            size = 'Large' if hd_only else None

            # Build query based on image type preference
            img_type = getattr(self, 'v_thumb_imgtype', None)
            img_type = img_type.get() if img_type else 'portrait'
            type_queries = {
                'portrait':   f'{query} face photo headshot',
                'group':      f'{query} group photo',
                'screenshot': f'{query} stream screenshot twitch',
                'any':        query,
            }
            search_query = type_queries.get(img_type, f'{query} portrait')
            layout = 'Tall' if img_type == 'portrait' else None

            items = DDGS().images(
                search_query,
                region='us-en',
                safesearch='off',
                size=size,
                type_image='photo',
                layout=layout,
                max_results=max_results,
            )
            results = [(i['image'], i.get('width', 1280), i.get('height', 720))
                       for i in items if i.get('image')]
            self.log(f'[Thumbnails] DuckDuckGo: {len(results)} results', FG2)
            return results[:max_results]
        except Exception as ex:
            _es = str(ex)
            if 'ratelimit' in _es.lower() or '403' in _es:
                raise ValueError(
                    'DuckDuckGo temporarily blocked the search.\n'
                    'Wait a few seconds and try again.')
            self.log(f'[Thumbnails] DDG error: {ex}', YELLOW)
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
        q     = re.sub(r'[\\/:*?"<>|]', '', self.thumb_query_var.get().strip())[:40]
        fname = f'{q}_{r["rank"]}.png'
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
        q = re.sub(r'[\\/:*?"<>|]', '', self.thumb_query_var.get().strip())[:40]
        for r in self._thumb_results:
            fname = f'{q}_{r["rank"]}.png'
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
        from PIL import Image, ImageTk
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

    def _build_editor_tab(self, p):
        """🎬 Editor — load any video or URL, mark clips, grab from CDN or local."""
        import threading as _eth

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(p, bg=BG2); hdr.pack(fill='x')
        tk.Label(hdr, text='🎬  CLIP EDITOR', font=('Segoe UI', 10, 'bold'),
                 fg=ACCENT, bg=BG2).pack(side='left', padx=12, pady=8)
        tk.Label(hdr, text='Load any video or URL · Mark In/Out · Grab clips without full download',
                 font=('Segoe UI', 8), fg=FG2, bg=BG2).pack(side='left')
        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Source row ────────────────────────────────────────────────────────
        src_row = tk.Frame(p, bg=BG2); src_row.pack(fill='x', padx=12, pady=(8,4))
        tk.Label(src_row, text='Source:', font=FONT_SMALL, fg=FG2, bg=BG2).pack(side='left')
        _ed_sf = tk.Frame(src_row, bg=BG3); _ed_sf.pack(side='left', fill='x', expand=True, padx=6)
        self._ed_src = tk.StringVar()
        self._ed_entry = tk.Entry(_ed_sf, textvariable=self._ed_src, font=FONT_SMALL,
                                  bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4)
        self._ed_entry.pack(side='left', fill='x', expand=True)
        self._ed_entry.insert(0, 'Paste Kick/Twitch/YouTube URL or browse local file...')
        self._ed_entry.config(fg=FG3)
        def _ed_focus_in(e):
            if self._ed_src.get() == 'Paste Kick/Twitch/YouTube URL or browse local file...':
                self._ed_entry.delete(0, 'end'); self._ed_entry.config(fg=FG)
        def _ed_focus_out(e):
            if not self._ed_src.get().strip():
                self._ed_entry.insert(0, 'Paste Kick/Twitch/YouTube URL or browse local file...')
                self._ed_entry.config(fg=FG3)
        self._ed_entry.bind('<FocusIn>', _ed_focus_in)
        self._ed_entry.bind('<FocusOut>', _ed_focus_out)

        tk.Button(src_row, text='📁 Browse', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._ed_browse_file).pack(side='left', padx=(0,4))
        tk.Button(src_row, text='▶ Load', font=('Segoe UI', 9, 'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=12, pady=4,
                  activebackground=ACCENT2, command=self._ed_load_source).pack(side='left')

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x')

        # ── Main area: player left, queue right ───────────────────────────────
        main = tk.Frame(p, bg=BG); main.pack(fill='both', expand=True)

        # Left — player + controls
        left = tk.Frame(main, bg=BG); left.pack(side='left', fill='both', expand=True)

        # Player area
        player_outer = tk.Frame(left, bg='#000', height=320)
        player_outer.pack(fill='x', padx=8, pady=(8,0))
        player_outer.pack_propagate(False)

        self._ed_player_frame = tk.Frame(player_outer, bg='#000')
        self._ed_player_frame.pack(fill='both', expand=True)

        # VLC check — show player or fallback message
        self._ed_vlc = None
        self._ed_vlc_media = None
        self._ed_vlc_player = None
        self._ed_has_vlc = False
        try:
            import vlc as _vlc_test
            self._ed_vlc_instance = _vlc_test.Instance('--no-xlib', '--quiet')
            if self._ed_vlc_instance is None:
                raise OSError('libvlc init failed')
            self._ed_vlc_player = self._ed_vlc_instance.media_player_new()
            if self._ed_vlc_player is None:
                raise OSError('libvlc player init failed')
            self._ed_has_vlc = True
            self._ed_player_canvas = tk.Canvas(self._ed_player_frame, bg='#000000',
                                               highlightthickness=0)
            self._ed_player_canvas.pack(fill='both', expand=True)
            # Reattach VLC hwnd on resize — keeps video filling the canvas
            def _ed_canvas_resize(e):
                if self._ed_has_vlc and self._ed_vlc_player and self._ed_playing:
                    try:
                        self._ed_vlc_player.set_hwnd(self._ed_player_canvas.winfo_id())
                    except: pass
            self._ed_player_canvas.bind('<Configure>', _ed_canvas_resize)
            tk.Label(self._ed_player_frame, text='VLC ready — load a source above',
                     font=('Segoe UI', 10), fg=FG2, bg='#000000').place(relx=0.5, rely=0.5, anchor='center')
        except (ImportError, OSError, AttributeError, SystemExit):
            self._ed_has_vlc = False
            self._ed_vlc_player = None
            self._ed_no_vlc_lbl = tk.Label(
                self._ed_player_frame,
                text='📺  No inline player available\n\n'
                     'Install python-vlc for embedded playback:\n'
                     'pip install python-vlc\n\n'
                     'Clips can still be marked by timecode\nand grabbed without the player',
                font=('Segoe UI', 10), fg=FG2, bg='#000', justify='center')
            self._ed_no_vlc_lbl.pack(expand=True)

        # Scrubber / position bar
        self._ed_pos_var = tk.DoubleVar(value=0)
        self._ed_scrubber = tk.Scale(
            left, from_=0, to=100, orient='horizontal',
            variable=self._ed_pos_var, bg=BG, fg=FG, troughcolor=BG3,
            activebackground=ACCENT, highlightthickness=0, bd=0,
            sliderrelief='flat', showvalue=False,
            command=self._ed_scrub)
        self._ed_scrubber.pack(fill='x', padx=8, pady=(2,0))

        # Time display
        time_row = tk.Frame(left, bg=BG); time_row.pack(fill='x', padx=12)
        self._ed_time_lbl = tk.Label(time_row, text='00:00:00', font=('Segoe UI', 9),
                                      fg=ACCENT, bg=BG)
        self._ed_time_lbl.pack(side='left')
        self._ed_dur_lbl = tk.Label(time_row, text='/ 00:00:00', font=('Segoe UI', 9),
                                     fg=FG2, bg=BG)
        self._ed_dur_lbl.pack(side='left', padx=(4,0))

        # Playback controls
        pb_row = tk.Frame(left, bg=BG); pb_row.pack(pady=(4,0))
        for txt, cmd in [
            ('⏮', lambda: self._ed_seek_rel(-30)),
            ('⏪', lambda: self._ed_seek_rel(-5)),
            ('▶/⏸', self._ed_play_pause),
            ('⏩', lambda: self._ed_seek_rel(5)),
            ('⏭', lambda: self._ed_seek_rel(30)),
        ]:
            tk.Button(pb_row, text=txt, font=('Segoe UI', 12), bg=BG2, fg=FG,
                      relief='flat', bd=0, cursor='hand2', padx=12, pady=4,
                      activebackground=BG3, command=cmd).pack(side='left', padx=2)

        tk.Frame(left, bg=BORDER, height=1).pack(fill='x', padx=8, pady=6)

        # Mark In / Mark Out controls
        mark_row = tk.Frame(left, bg=BG); mark_row.pack(fill='x', padx=8, pady=(0,4))
        tk.Label(mark_row, text='IN:', font=('Segoe UI', 9, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        self._ed_in_var = tk.StringVar(value='00:00:00')
        _in_e = tk.Entry(mark_row, textvariable=self._ed_in_var, font=('Segoe UI', 9),
                         bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=3, width=9)
        _in_e.pack(side='left', padx=(4,8))
        tk.Button(mark_row, text='◀ Mark In', font=FONT_SMALL,
                  bg=BG3, fg=ACCENT, relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._ed_mark_in).pack(side='left')

        tk.Label(mark_row, text='OUT:', font=('Segoe UI', 9, 'bold'),
                 fg='#ff4444', bg=BG).pack(side='left', padx=(16,0))
        self._ed_out_var = tk.StringVar(value='00:00:00')
        _out_e = tk.Entry(mark_row, textvariable=self._ed_out_var, font=('Segoe UI', 9),
                          bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=3, width=9)
        _out_e.pack(side='left', padx=(4,8))
        tk.Button(mark_row, text='Mark Out ▶', font=FONT_SMALL,
                  bg=BG3, fg='#ff4444', relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._ed_mark_out).pack(side='left')

        tk.Button(mark_row, text='+ Add to Queue', font=('Segoe UI', 9, 'bold'),
                  bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=12, pady=4,
                  activebackground=ACCENT2, command=self._ed_add_to_queue).pack(side='right')

        # Status
        self._ed_status_lbl = tk.Label(left, text='Load a source to begin',
                                        font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self._ed_status_lbl.pack(fill='x', padx=12)

        tk.Frame(left, bg=BORDER, height=1).pack(fill='x', padx=8, pady=(6,0))

        # ── Image Overlay section ──────────────────────────────────────────────
        ov_hdr = tk.Frame(left, bg=BG); ov_hdr.pack(fill='x', padx=8, pady=(4,2))
        tk.Label(ov_hdr, text='🖼  IMAGE OVERLAY', font=('Segoe UI', 8, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(ov_hdr, text='add PNG/JPG/GIF burned into exported clips',
                 font=('Segoe UI', 7), fg=FG2, bg=BG).pack(side='left', padx=(8,0))

        ov_row = tk.Frame(left, bg=BG); ov_row.pack(fill='x', padx=8, pady=(0,4))
        self._ed_overlay_path = tk.StringVar()
        _ov_e = tk.Entry(ov_row, textvariable=self._ed_overlay_path, font=FONT_SMALL,
                         bg=BG3, fg=FG3, insertbackground=ACCENT, relief='flat', bd=3)
        _ov_e.pack(side='left', fill='x', expand=True)
        _ov_e.insert(0, 'No overlay image')
        def _ov_focus_in(e):
            if self._ed_overlay_path.get() == 'No overlay image':
                _ov_e.delete(0, 'end'); _ov_e.config(fg=FG)
        def _ov_focus_out(e):
            if not self._ed_overlay_path.get().strip():
                _ov_e.insert(0, 'No overlay image'); _ov_e.config(fg=FG3)
        _ov_e.bind('<FocusIn>',  _ov_focus_in)
        _ov_e.bind('<FocusOut>', _ov_focus_out)

        tk.Button(ov_row, text='📁', font=FONT_SMALL, bg=BG3, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=6, pady=3,
                  command=self._ed_browse_overlay).pack(side='left', padx=(4,0))
        tk.Button(ov_row, text='✕', font=FONT_SMALL, bg=BG3, fg=RED,
                  relief='flat', bd=0, cursor='hand2', padx=6, pady=3,
                  command=self._ed_clear_overlay).pack(side='left', padx=(2,0))

        # Position controls
        ov_pos = tk.Frame(left, bg=BG); ov_pos.pack(fill='x', padx=8, pady=(0,4))
        tk.Label(ov_pos, text='Position:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left')
        self._ed_ov_pos = tk.StringVar(value='bottom-right')
        for _pos_val, _pos_lbl in [('top-left','↖'), ('top-right','↗'),
                                    ('bottom-left','↙'), ('bottom-right','↘'),
                                    ('center','⊕')]:
            tk.Radiobutton(ov_pos, text=_pos_lbl, variable=self._ed_ov_pos,
                           value=_pos_val, font=('Segoe UI', 10),
                           bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                           cursor='hand2').pack(side='left', padx=4)

        tk.Label(ov_pos, text='Scale:', font=FONT_SMALL, fg=FG2, bg=BG).pack(side='left', padx=(12,0))
        self._ed_ov_scale = tk.IntVar(value=20)
        tk.Scale(ov_pos, from_=5, to=80, orient='horizontal',
                 variable=self._ed_ov_scale, font=('Segoe UI', 7),
                 bg=BG, fg=FG, troughcolor=BG3, activebackground=ACCENT,
                 highlightthickness=0, bd=0, sliderrelief='flat',
                 width=8, length=80, showvalue=True,
                 label='%').pack(side='left')

        # ── Right — clip queue ────────────────────────────────────────────────
        right = tk.Frame(main, bg=BG2, width=300); right.pack(side='right', fill='y')
        right.pack_propagate(False)
        tk.Frame(main, bg=BORDER, width=1).pack(side='right', fill='y')

        tk.Label(right, text='CLIP QUEUE', font=('Segoe UI', 9, 'bold'),
                 fg=ACCENT, bg=BG2).pack(anchor='w', padx=10, pady=(8,4))

        # Queue list
        self._ed_queue_frame = tk.Frame(right, bg=BG2)
        self._ed_queue_frame.pack(fill='both', expand=True, padx=4)

        self._ed_queue_empty_lbl = tk.Label(
            self._ed_queue_frame,
            text='\n  No clips queued yet\n\n  Mark In/Out then\n  click + Add to Queue',
            font=FONT_SMALL, fg=FG2, bg=BG2, justify='left')
        self._ed_queue_empty_lbl.pack(pady=10)

        # Bottom action bar
        tk.Frame(right, bg=BORDER, height=1).pack(fill='x')
        bot_r = tk.Frame(right, bg=BG2); bot_r.pack(fill='x', padx=8, pady=6)
        tk.Button(bot_r, text='🗑 Clear All', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=self._ed_clear_queue).pack(side='left')
        self._ed_grab_btn = tk.Button(
            bot_r, text='⚡ Grab Clips', font=('Segoe UI', 9, 'bold'),
            bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=12, pady=4,
            activebackground=ACCENT2, command=self._ed_grab_clips)
        self._ed_grab_btn.pack(side='right')

        # Internal state
        self._ed_queue        = []
        self._ed_source_url   = ''
        self._ed_is_url       = False
        self._ed_duration     = 0
        self._ed_playing      = False
        self._ed_poll_job     = None
        self._ed_overlay_img  = ''   # path to overlay image

    # ── Editor helper methods ─────────────────────────────────────────────────

    def _ed_browse_overlay(self):
        path = filedialog.askopenfilename(
            title='Select overlay image',
            filetypes=[('Images', '*.png *.jpg *.jpeg *.gif *.bmp *.webp'), ('All files', '*.*')])
        if path:
            self._ed_overlay_path.set(path)
            self._ed_overlay_img = path
            self._ed_status_lbl.config(text=f'Overlay set: {Path(path).name}')

    def _ed_clear_overlay(self):
        self._ed_overlay_path.set('No overlay image')
        self._ed_overlay_img = ''
        self._ed_status_lbl.config(text='Overlay cleared')

    def _ed_browse_file(self):
        path = filedialog.askopenfilename(
            title='Select video file',
            filetypes=[('Video files', '*.mp4 *.mkv *.mov *.avi *.webm *.ts *.flv'), ('All files', '*.*')])
        if path:
            self._ed_entry.delete(0, 'end')
            self._ed_entry.insert(0, path)
            self._ed_entry.config(fg=FG)
            self._ed_load_source()

    def _ed_load_source(self):
        src = self._ed_src.get().strip()
        if not src or src == 'Paste Kick/Twitch/YouTube URL or browse local file...': return
        # A kick.com page is not playable/cuttable — resolve it to the public HLS stream first
        if _KICK_PAGE_RE.match(src) and (_KICK_VOD_RE.search(src) or _KICK_CLIP_RE.search(src)):
            if getattr(self, '_ed_resolving', False):
                return
            self._ed_resolving = True
            self._ed_status_lbl.config(text='Resolving Kick stream...')
            _ck = self.v_cookies.get().strip() if hasattr(self, 'v_cookies') else ''
            def _resolve_kick():
                try:
                    _kr = kick_resolve(src, token=_kick_session_token(_ck))
                    self.after(0, lambda: self._ed_finish_load(_kr['stream_url']))
                except Exception as _e:
                    _msg = str(_e).splitlines()[0][:140] if str(_e) else 'unknown error'
                    self.after(0, lambda: self._ed_status_lbl.config(text=f'Kick: {_msg}'))
                finally:
                    self._ed_resolving = False
            threading.Thread(target=_resolve_kick, daemon=True).start()
            return
        self._ed_finish_load(src)

    def _ed_finish_load(self, src):
        self._ed_source_url = src
        self._ed_is_url = src.startswith('http')
        self._ed_status_lbl.config(text=f'Loading: {Path(src).name if not self._ed_is_url else src[:60]}...')

        if self._ed_has_vlc:
            try:
                import vlc as _vlc2
                _media = self._ed_vlc_instance.media_new(src)
                self._ed_vlc_player.set_media(_media)
                # Clear placeholder label first
                for w in self._ed_player_frame.winfo_children():
                    if isinstance(w, tk.Label): w.destroy()
                # Force canvas to render and get real HWND — must update before winfo_id
                self._ed_player_canvas.update_idletasks()
                self.update_idletasks()
                _hwnd = self._ed_player_canvas.winfo_id()
                self._ed_vlc_player.set_hwnd(_hwnd)
                # Small delay then play — gives Windows time to associate HWND
                def _start_play():
                    self._ed_vlc_player.play()
                    self._ed_playing = True
                    self._ed_status_lbl.config(text='▶ Playing — use Mark In/Out to set clip boundaries')
                    self._ed_start_poll()
                self.after(200, _start_play)
            except Exception as e:
                self._ed_status_lbl.config(text=f'Player error: {e}')
        else:
            self._ed_status_lbl.config(
                text=f'Source set: {Path(src).name if not self._ed_is_url else src[:50]} — set timecodes manually')

    def _ed_start_poll(self):
        """Poll VLC player position to update scrubber and time label."""
        if self._ed_poll_job:
            self.after_cancel(self._ed_poll_job)
        def _poll():
            if not self._ed_has_vlc or not self._ed_vlc_player: return
            try:
                _dur = self._ed_vlc_player.get_length() // 1000  # ms → s
                _pos = self._ed_vlc_player.get_time()  // 1000
                if _dur > 0:
                    self._ed_duration = _dur
                    self._ed_scrubber.config(to=_dur)
                    self._ed_pos_var.set(_pos)
                    self._ed_time_lbl.config(text=self._ed_fmt(_pos))
                    self._ed_dur_lbl.config(text=f'/ {self._ed_fmt(_dur)}')
            except: pass
            self._ed_poll_job = self.after(500, _poll)
        _poll()

    def _ed_fmt(self, s):
        s = int(s)
        return f'{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}'

    def _ed_parse_tc(self, tc, strict=False):
        """Parse HH:MM:SS or MM:SS into seconds. strict=True raises ValueError instead of returning 0."""
        try:
            parts = [float(x) for x in str(tc).strip().split(':')]
            if not 1 <= len(parts) <= 3 or any(p < 0 for p in parts):
                raise ValueError(tc)
            secs = 0
            for p in parts:
                secs = secs*60 + p
            return int(secs)
        except (ValueError, TypeError, OverflowError):
            if strict: raise ValueError(f'bad timecode: {tc!r}')
            return 0

    def _ed_play_pause(self):
        if not self._ed_has_vlc or not self._ed_vlc_player: return
        if self._ed_playing:
            self._ed_vlc_player.pause()
            self._ed_playing = False
        else:
            self._ed_vlc_player.play()
            self._ed_playing = True
            self._ed_start_poll()

    def _ed_scrub(self, val):
        if not self._ed_has_vlc or not self._ed_vlc_player: return
        try: self._ed_vlc_player.set_time(int(float(val)) * 1000)
        except: pass

    def _ed_seek_rel(self, secs):
        if not self._ed_has_vlc or not self._ed_vlc_player: return
        try:
            cur = self._ed_vlc_player.get_time() // 1000
            self._ed_vlc_player.set_time(max(0, cur + secs) * 1000)
        except: pass

    def _ed_mark_in(self):
        if self._ed_has_vlc and self._ed_vlc_player:
            t = max(0, self._ed_vlc_player.get_time() // 1000)
        else:
            t = self._ed_parse_tc(self._ed_in_var.get())
        self._ed_in_var.set(self._ed_fmt(t))
        self._ed_status_lbl.config(text=f'In point set: {self._ed_fmt(t)}')

    def _ed_mark_out(self):
        if self._ed_has_vlc and self._ed_vlc_player:
            t = max(0, self._ed_vlc_player.get_time() // 1000)
        else:
            t = self._ed_parse_tc(self._ed_out_var.get())
        self._ed_out_var.set(self._ed_fmt(t))
        self._ed_status_lbl.config(text=f'Out point set: {self._ed_fmt(t)}')

    def _ed_add_to_queue(self):
        src = self._ed_source_url
        if not src or src == 'Paste Kick/Twitch/YouTube URL or browse local file...':
            messagebox.showwarning('No source', 'Load a video source first.'); return
        t_in  = self._ed_in_var.get().strip()
        t_out = self._ed_out_var.get().strip()
        try:
            s_in  = self._ed_parse_tc(t_in, strict=True)
            s_out = self._ed_parse_tc(t_out, strict=True)
        except ValueError:
            messagebox.showwarning('Invalid timecode', 'Use HH:MM:SS or MM:SS.'); return
        if s_out <= s_in:
            messagebox.showwarning('Invalid range', 'Out point must be after In point.'); return
        dur = s_out - s_in
        if dur > 360:  # 6 min max
            messagebox.showwarning('Too long', f'Max clip length is 6 minutes. This clip is {dur//60}m {dur%60}s.'); return
        if len(self._ed_queue) >= 10:
            messagebox.showwarning('Queue full', 'Max 10 clips in queue.'); return
        t_in  = self._ed_fmt(s_in)
        t_out = self._ed_fmt(s_out)

        n = len(self._ed_queue) + 1
        clip = {'in': t_in, 'out': t_out, 'src': src, 'label': f'Clip {n}',
                'dur': f'{dur//60}m {dur%60}s'}
        self._ed_queue.append(clip)
        self._ed_render_queue()
        self._ed_status_lbl.config(text=f'Added Clip {n}: {t_in} → {t_out} ({clip["dur"]})')

    def _ed_render_queue(self):
        for w in self._ed_queue_frame.winfo_children(): w.destroy()
        if not self._ed_queue:
            tk.Label(self._ed_queue_frame,
                     text='\n  No clips queued yet\n\n  Mark In/Out then\n  click + Add to Queue',
                     font=FONT_SMALL, fg=FG2, bg=BG2, justify='left').pack(pady=10)
            return
        for i, clip in enumerate(self._ed_queue):
            card = tk.Frame(self._ed_queue_frame, bg=BG3)
            card.pack(fill='x', pady=(0,3), padx=2)
            top = tk.Frame(card, bg=BG3); top.pack(fill='x', padx=6, pady=(4,0))
            tk.Label(top, text=clip['label'], font=('Segoe UI', 8, 'bold'),
                     fg=ACCENT, bg=BG3).pack(side='left')
            tk.Label(top, text=clip['dur'], font=FONT_SMALL,
                     fg=FG2, bg=BG3).pack(side='right')
            bot = tk.Frame(card, bg=BG3); bot.pack(fill='x', padx=6, pady=(0,4))
            tk.Label(bot, text=f'{clip["in"]} → {clip["out"]}',
                     font=FONT_SMALL, fg=FG, bg=BG3).pack(side='left')
            tk.Button(bot, text='✕', font=FONT_SMALL, bg=BG3, fg=RED,
                      relief='flat', bd=0, cursor='hand2',
                      command=lambda idx=i: self._ed_remove_clip(idx)).pack(side='right')

    def _ed_remove_clip(self, idx):
        self._ed_queue.pop(idx)
        # Renumber
        for i, c in enumerate(self._ed_queue): c['label'] = f'Clip {i+1}'
        self._ed_render_queue()

    def _ed_clear_queue(self):
        self._ed_queue.clear()
        self._ed_render_queue()

    def _ed_grab_clips(self):
        """Grab all queued clips via ffmpeg — streams from URL or cuts local file."""
        if not self._ed_queue:
            messagebox.showwarning('Empty queue', 'Add clips to the queue first.'); return
        out_dir = self.v_outdir.get().strip() or self.cfg.get('outdir') or str(Path.home() / 'Videos')
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror('Output folder', f'Cannot create {out_dir}: {e}'); return
        ov = self._ed_overlay_path.get().strip().strip('"')
        overlay_img = '' if ov in ('', 'No overlay image') else ov
        if overlay_img and not Path(overlay_img).exists():
            messagebox.showwarning('Overlay not found', f'Overlay image not found:\n{overlay_img}'); return

        self._ed_grab_btn.config(state='disabled', text='⏳ Grabbing...')
        self._ed_status_lbl.config(text=f'Grabbing {len(self._ed_queue)} clip(s)...')

        import threading as _eth2
        queue_copy = list(self._ed_queue)
        _ov_pos_val = self._ed_ov_pos.get()
        _ov_scale_val = self._ed_ov_scale.get()

        def _grab():
            import subprocess as _sp2
            ffmpeg = find_ffmpeg()
            ov_pos_val  = _ov_pos_val
            ov_scale    = _ov_scale_val
            results = []
            for i, clip in enumerate(queue_copy):
                out_name = f'clip_{i+1}_{clip["in"].replace(":","")}-{clip["out"].replace(":","")}.mp4'
                out_path = str(Path(out_dir) / out_name)
                self.after(0, lambda i=i, t=len(queue_copy):
                    self._ed_status_lbl.config(text=f'Grabbing clip {i+1}/{t}...'))

                # Build ffmpeg command
                if overlay_img and Path(overlay_img).exists():
                    # With overlay — need re-encode so filter can be applied
                    # Position map
                    _pos_map = {
                        'top-left':     'overlay=10:10',
                        'top-right':    'overlay=main_w-overlay_w-10:10',
                        'bottom-left':  'overlay=10:main_h-overlay_h-10',
                        'bottom-right': 'overlay=main_w-overlay_w-10:main_h-overlay_h-10',
                        'center':       'overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2',
                    }
                    _ov_filter = _pos_map.get(ov_pos_val, 'overlay=main_w-overlay_w-10:main_h-overlay_h-10')
                    _scale_filter = f'scale=iw*{ov_scale}/100:-1'
                    cmd = [ffmpeg, '-y',
                           '-ss', clip['in'], '-to', clip['out'],
                           '-i', clip['src'],
                           '-i', overlay_img,
                           '-filter_complex',
                           f'[1:v]{_scale_filter}[ov];[0:v][ov]{_ov_filter}',
                           '-c:v', 'libx264', '-crf', '18', '-preset', 'fast',
                           '-c:a', 'aac',
                           '-avoid_negative_ts', 'make_zero',
                           out_path]
                else:
                    # No overlay — stream copy (fastest)
                    cmd = [ffmpeg, '-y',
                           '-ss', clip['in'], '-to', clip['out'],
                           '-i', clip['src'],
                           '-c', 'copy',
                           '-avoid_negative_ts', 'make_zero',
                           out_path]
                try:
                    _pr = _sp2.run(cmd, capture_output=True, timeout=300)
                    if _pr.returncode == 0 and Path(out_path).exists():
                        results.append((clip['label'], out_path, True))
                    else:
                        _tail = (_pr.stderr or b'').decode(errors='ignore').strip().splitlines()[-1:] or ['ffmpeg failed']
                        results.append((clip['label'], _tail[0][:200], False))
                except Exception as e:
                    results.append((clip['label'], str(e), False))

            self.after(0, lambda: self._ed_grab_done(results, out_dir))

        _eth2.Thread(target=_grab, daemon=True).start()

    def _ed_grab_done(self, results, out_dir):
        self._ed_grab_btn.config(state='normal', text='⚡ Grab Clips')
        ok = [r for r in results if r[2]]
        fail = [r for r in results if not r[2]]
        self._ed_status_lbl.config(
            text=f'✅ {len(ok)} clip(s) saved to {out_dir}' +
                 (f' | ⚠ {len(fail)} failed' if fail else ''))
        if len(ok) == 1:
            # Auto-switch to Auto Edit with the clip loaded
            _path = ok[0][1]
            self.log(f'🎬 Editor: 1 clip grabbed — loading into Auto Edit', ACCENT)
            self._switch_nb('clips')
            self.after(100, lambda: self._switch_sub_clips('auto_edit'))
            self.after(200, lambda: self.v_video.set(_path))
        elif ok:
            messagebox.showinfo('Clips grabbed',
                f'{len(ok)} clips saved to:\n{out_dir}' +
                (f'\n\n⚠ {len(fail)} clip(s) failed.' if fail else ''))

    def _switch_sub_clips(self, key):
        """Switch to a sub-tab inside the Clip Finder tab."""
        for k, f in self._clips_sub_frames.items():
            f.pack_forget()
        if key in self._clips_sub_frames:
            self._clips_sub_frames[key].pack(fill='both', expand=True)
        for k, b in self._clips_sub_btns.items():
            b.config(bg=ACCENT if k==key else BG3,
                     fg='#000' if k==key else FG2,
                     font=('Segoe UI',8,'bold') if k==key else ('Segoe UI',8))

    def _ed_load_from_kick(self, url, title=''):
        """Called from the channel browser (any platform) — loads the URL into the Editor tab."""
        self._switch_nb('editor')
        self.after(100, lambda: self._ed_entry.delete(0, 'end'))
        self.after(100, lambda: self._ed_entry.insert(0, url))
        self.after(100, lambda: self._ed_entry.config(fg=FG))
        self.after(150, self._ed_load_source)
        if title:
            self.after(200, lambda: self._ed_status_lbl.config(
                text=f'Loaded: {title}'))

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
        self.move_btn = tk.Button(btn_row, text='📦 MOVE DUPES TO /duplicates',
                  font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0,
                  cursor='hand2', padx=10, pady=6,
                  command=self._studio_move_dupes)
        self.move_btn.pack(side='left')

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
                self.studio_result_lbl.config(text=msg, fg=color or FG2)
            except: pass
        if threading.current_thread() is threading.main_thread(): _do()
        else: self.after(0, _do)

    def _studio_set_busy(self, busy):
        state = 'disabled' if busy else 'normal'
        for b in (getattr(self, 'dup_btn', None), getattr(self, 'up_btn', None), getattr(self, 'move_btn', None)):
            if b is None: continue
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

            # skip the /duplicates quarantine folder that _studio_move_dupes creates
            paths = [p for p in Path(folder).rglob('*') if p.suffix.lower() in img_exts
                     and 'duplicates' not in [x.lower() for x in p.relative_to(folder).parts[:-1]]]
            self.log(f'[Studio] Found {len(paths)} images')

            if not paths:
                self._studio_set_status('No images found in folder.')
                self.after(0, lambda: self._studio_show_empty('No images found in folder.'))
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
            self._studio_dupes_root = folder     # Move Duplicates must use the folder that was scanned
            total_dupes = sum(len(g)-1 for g in groups)
            self.log(f'[Studio] Found {len(groups)} duplicate groups, {total_dupes} files to remove', GREEN)
            self._studio_set_status(f'Done! {len(groups)} groups, {total_dupes} duplicates found.', GREEN)
            self.after(0, lambda: self._studio_render_dupes(groups))

        except Exception as ex:
            err = traceback.format_exc()
            self.log(f'[Studio] Dupe error:\n{err}', RED)
            msg = str(ex).strip() if isinstance(ex, (ImportError, ValueError, RuntimeError)) else 'Error — check log.'
            self._studio_set_status(msg, RED)
            self.after(0, lambda m=msg: self._studio_show_empty(m))
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
        folder = getattr(self, '_studio_dupes_root', '') or self.v_scan_folder.get().strip()
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
                # Go through the update manager: it stages the wheel, import-tests it and swaps it into PKGS_DIR.
                # (A plain `pip install` goes to site-packages, where the PKGS_DIR opencv-python shadows it, and
                # the loaded cv2 .pyd cannot be replaced while the app is running.)
                _ocv = pm_entry('opencv-contrib-python')
                if _ocv is None:
                    raise RuntimeError('opencv-contrib-python is not in the package registry')
                _stg = pm_stage([_ocv], on_line=lambda l: self.log(f'[Studio] {l}', FG2))
                _stg_bad = [r for r in _stg if not r.get('ok')]
                if _stg_bad or not _stg:
                    raise RuntimeError('opencv-contrib-python install failed: ' +
                                       (_stg_bad[0].get('error', 'unknown error') if _stg_bad else 'nothing was staged'))
                if 'cv2' in sys.modules:
                    # a loaded cv2 .pyd cannot be swapped while running: it is applied at the next start
                    raise RuntimeError('opencv-contrib-python was downloaded. Restart ClipFinder, then run Upscale again.')
                pm_apply_staged()
                _cv2 = _fresh_import('cv2')
                if not hasattr(_cv2, 'dnn_superres'):
                    raise RuntimeError('opencv-contrib-python installed but dnn_superres is missing - restart ClipFinder')
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
                 f'https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x{scale}.pb'),
                (f'ESPCN_x{scale}.pb', 'ESPCN', scale,
                 f'https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x{scale}.pb'),
            ]
            model_path = None; model_name_used = None
            for fname, mname, mscale, url in candidates:
                dest = model_dir / fname
                if not dest.exists():
                    self.log(f'[Studio] Downloading {fname}...')
                    self._studio_set_status(f'Downloading {fname} (one time)...')
                    _part = dest.with_name(dest.name + '.part')
                    try:
                        import shutil as _shu
                        with _ur.urlopen(url, timeout=30) as _resp, open(_part, 'wb') as _pf:
                            _clen = int(_resp.headers.get('Content-Length') or 0)
                            _shu.copyfileobj(_resp, _pf)
                        if _clen and _part.stat().st_size != _clen:
                            raise IOError(f'incomplete download ({_part.stat().st_size}/{_clen} bytes)')
                        os.replace(_part, dest)
                    except Exception as ex:
                        self.log(f'[Studio] Download failed: {ex}', YELLOW)
                        try: _part.unlink()
                        except OSError: pass
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
                    # imwrite silently fails (returns False / writes nothing) for non-ASCII paths on Windows,
                    # so encode in memory and write the bytes with Python's own file API
                    _enc_ok, _enc_buf = _cv2.imencode('.png', output)
                    if not _enc_ok:
                        raise RuntimeError('PNG encode failed')
                    Path(out_path).write_bytes(_enc_buf.tobytes())
                    if not Path(out_path).exists():
                        raise RuntimeError(f'Could not write {out_path}')
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

        except Exception as ex:
            err = traceback.format_exc()
            self.log(f'[Studio] Upscale error:\n{err}', RED)
            msg = str(ex).strip() if isinstance(ex, (ImportError, ValueError, RuntimeError)) else 'Error — check log.'
            self._studio_set_status(msg, RED)
            self.after(0, lambda m=msg: self._studio_show_empty(m))
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
            self._whisper_vid = os.path.normcase(os.path.abspath(str(vid)))
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
                return _is_rate_limit_error(e)

            def _is_access_denied(e):
                s = str(e).lower()
                return any(x in s for x in ['403','access denied','forbidden','unauthorized'])

            segments = []
            keyed_provs = [p for p in dict.fromkeys([self.v_provider.get()] +
                           list(PROVIDERS.keys())) if self._keys.get(p,'').strip()]
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
                    elif 'api key not valid' in err_str.lower() or 'api_key_invalid' in err_str.lower():
                        self.log(f'{prov} API key not valid — check Settings', YELLOW)
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
            _ensure_pkgs_on_path()
            try:
                import google.genai as _gg
            except ImportError as _ge2:
                raise ImportError(f'google-genai broken ({_ge2}) — run Update All Packages in Settings.')
            client = _gg.Client(api_key=key)
            # Walks the Gemini list (429/retired ids move to the next model); never returns None
            return _gemini_complete(key, 'extract', prompt, 8192, 0.3, json=True, think='low', client=client)

        elif prov_name == 'Groq (Free)':
            _ensure_pkgs_on_path()
            try:
                from groq import Groq as _G
            except ImportError:
                raise ImportError('groq package broken — go to Settings → Update All Packages')
            client = _G(api_key=key)
            # Whole Groq list with fallback (the old code used models[0] only, which was retired)
            return _groq_complete(key, 'extract', [{'role':'user','content':prompt}], 3000, 0.3, client=client)

        elif prov_name == 'OpenRouter (Free models)':
            # Only use the selected model when OpenRouter is the selected provider
            _m0 = _pick_model(prov_name, self.v_model.get() if self.v_provider.get() == prov_name else '', 'extract')
            return _openrouter_complete(key, 'extract', [{'role':'user','content':prompt}], 4096,
                                        models=[_m0] + [m for m in _ai_models(prov_name, 'extract') if m != _m0],
                                        timeout=60)

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
            ('_unsplash',               'Unsplash',      'Free · stock photos (thumbnail stock mode)', 'https://unsplash.com/oauth/applications'),
            ('Groq (Free)',             'Groq',        'Free · fastest inference',             'https://console.groq.com/keys'),
            ('OpenRouter (Free models)','OpenRouter',  'Free models available',                'https://openrouter.ai/keys'),
        ]

        if not hasattr(self, 'v_unsplash_key'):
            self.v_unsplash_key = tk.StringVar(value=self._keys.get('_unsplash',''))

        _provider_entries = {}
        _extra_key_vars    = {}  # pkey -> list of StringVars for extra keys
        _extra_key_enabled = {}  # pkey -> list of BooleanVars (enabled/disabled)
        _extra_key_frames  = {}  # pkey -> frame containing extra rows

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

            # RIGHT: + button (fixed, before entry) — hide for single-key services
            _plus_holder = tk.Frame(pr, bg=BG3)
            _plus_holder.pack(side='right', padx=(4,0))
            _plus_btn = tk.Button(_plus_holder, text='+ Add Key', font=('Segoe UI',8),
                                 bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8, pady=4)
            if pkey not in ('_unsplash',):
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
            _extra_key_vars[pkey]    = []
            _extra_key_enabled[pkey] = []
            _extra_key_frames[pkey]  = tk.Frame(s1, bg=BG3)
            _extra_key_frames[pkey].pack(fill='x')
            _cfg_map_k = {
                'Google Gemini (Free)':     ('key_gemini_extra',     'key_gemini_extra_enabled'),
                'Groq (Free)':              ('key_groq_extra',       'key_groq_extra_enabled'),
                'OpenRouter (Free models)': ('key_openrouter_extra', 'key_openrouter_extra_enabled'),
                '_unsplash':                ('key_unsplash_extra',   'key_unsplash_extra_enabled'),
            }
            _cfg_extra_k, _cfg_en_k = _cfg_map_k.get(pkey, ('', ''))
            _existing_extras = [k.strip() for k in self.cfg.get(_cfg_extra_k,'').split(',') if k.strip()]
            _existing_en_raw  = [x for x in self.cfg.get(_cfg_en_k,'').split(',') if x in ('0','1')]
            # Pad with 1 (enabled) if no flags stored yet
            _existing_enabled = [bool(int(x)) for x in _existing_en_raw] + [True]*max(0, len(_existing_extras)-len(_existing_en_raw))

            def _add_extra_row(pk=pkey, val='', enabled=True):
                _ev  = tk.StringVar(value=val)
                _ben = tk.BooleanVar(value=enabled)
                _extra_key_vars[pk].append(_ev)
                _extra_key_enabled[pk].append(_ben)
                _kidx = len(_extra_key_vars[pk])

                # Parent is this provider's extra-key container so '+ Add Key' rows stay under their provider
                _erow = tk.Frame(_extra_key_frames[pk], bg=BG3)
                _erow.pack(fill='x', pady=1)

                def _remove_row(r=_erow, v=_ev, b=_ben, pk2=pk):
                    r.destroy()
                    if v in _extra_key_vars[pk2]:    _extra_key_vars[pk2].remove(v)
                    if b in _extra_key_enabled[pk2]: _extra_key_enabled[pk2].remove(b)

                # LEFT: label
                _lbl_var = tk.StringVar(value=f'  ↳ Key {_kidx+1}')
                tk.Label(_erow, textvariable=_lbl_var,
                        font=('Segoe UI',8), fg=ACCENT2, bg=BG3,
                        width=_COL_NAME, anchor='w').pack(side='left', padx=(4,0))

                # RIGHT: ✕ remove button
                tk.Button(_erow, text='✕', font=('Segoe UI',9,'bold'),
                         bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=6,
                         command=_remove_row).pack(side='right', padx=(0,6))
                # Blank spacer
                tk.Label(_erow, text='', bg=BG3, width=_COL_RIGHT).pack(side='right')

                # Enable/disable toggle — packed right of entry
                def _make_toggle(entry, ben, erow_ref):
                    def _toggle():
                        is_on = ben.get()
                        entry.config(state='normal' if is_on else 'disabled',
                                     fg=FG if is_on else FG3)
                        erow_ref._toggle_btn.config(
                            text='● ON' if is_on else '○ OFF',
                            fg=GREEN if is_on else FG3)
                    return _toggle

                # MIDDLE: entry (orange-bordered when enabled, grey when disabled)
                _eef = tk.Frame(_erow, bg=ACCENT if enabled else FG3, padx=1, pady=1)
                _eef.pack(side='left', fill='x', expand=True, padx=6)
                _einn = tk.Frame(_eef, bg=BG4); _einn.pack(fill='both', expand=True)
                _ee = tk.Entry(_einn, textvariable=_ev, font=('Consolas',9),
                              bg=BG4, fg=FG if enabled else FG3,
                              insertbackground=ACCENT, relief='flat', bd=4, show='•',
                              state='normal' if enabled else 'disabled')
                _ee.pack(side='left', fill='x', expand=True)
                tk.Button(_einn, text='👁', font=('Segoe UI',8), bg=BG4, fg=FG2,
                         relief='flat', bd=0, cursor='hand2', padx=4,
                         command=_make_eye_toggle(_ee)).pack(side='right')

                # Toggle button — after entry frame
                _tbtn = tk.Button(_erow,
                    text='● ON' if enabled else '○ OFF',
                    font=('Segoe UI', 8, 'bold'),
                    fg=GREEN if enabled else FG3,
                    bg=BG3, relief='flat', bd=0, cursor='hand2', padx=6)

                def _toggle_key(b=_ben, e=_ee, ef=_eef, btn=_tbtn, pk=pk):
                    b.set(not b.get())
                    is_on = b.get()
                    e.config(state='normal' if is_on else 'disabled',
                             fg=FG if is_on else FG3)
                    ef.config(bg=ACCENT if is_on else FG3)
                    btn.config(text='● ON' if is_on else '○ OFF',
                               fg=GREEN if is_on else FG3)
                    # Immediately sync to app-level state + config so runs see the change
                    # without requiring the user to press Save first
                    _cfg_en_map = {
                        'Google Gemini (Free)':     'key_gemini_extra_enabled',
                        'Groq (Free)':              'key_groq_extra_enabled',
                        'OpenRouter (Free models)': 'key_openrouter_extra_enabled',
                    }
                    if pk in _cfg_en_map:
                        _all_bvars = _extra_key_enabled.get(pk, [])
                        _flags = [bv.get() for bv in _all_bvars]
                        # Also keep the keys list in sync (only enabled keys active)
                        _all_kvars = _extra_key_vars.get(pk, [])
                        _all_keys  = [v.get().strip() for v in _all_kvars]
                        if hasattr(self, '_extra_keys_enabled'):
                            self._extra_keys_enabled[pk] = _flags
                        if hasattr(self, '_extra_keys'):
                            self._extra_keys[pk] = _all_keys  # keep all, _call_provider filters by enabled
                        self.cfg[_cfg_en_map[pk]] = ','.join('1' if f else '0' for f in _flags)
                        save_cfg(self.cfg)
                    self.log(f'Key {"enabled" if is_on else "disabled"} for {pk}', GREEN if is_on else FG3)

                _tbtn.config(command=_toggle_key)
                _tbtn.pack(side='left', padx=(0,4))
                _erow._toggle_btn = _tbtn

            for _ev_val, _ev_en in zip(_existing_extras,
                                        _existing_enabled + [True]*max(0,len(_existing_extras)-len(_existing_enabled))):
                _add_extra_row(pkey, _ev_val, _ev_en)
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
            # Save extra keys + enabled flags
            _cfg_map = {
                'Google Gemini (Free)':     ('key_gemini',     'key_gemini_extra',     'key_gemini_extra_enabled'),
                'Groq (Free)':              ('key_groq',       'key_groq_extra',       'key_groq_extra_enabled'),
                'OpenRouter (Free models)': ('key_openrouter', 'key_openrouter_extra', 'key_openrouter_extra_enabled'),
            }
            for pkey, (cfg_k, cfg_extra_k, cfg_en_k) in _cfg_map.items():
                self.cfg[cfg_k] = self._keys.get(pkey, '')
                # Save all keys (including disabled ones — so they're not lost)
                all_vars    = _extra_key_vars.get(pkey, [])
                all_en_vars = _extra_key_enabled.get(pkey, [])
                # Keep keys that have a value (even if disabled)
                pairs = [(v.get().strip(), (all_en_vars[i].get() if i < len(all_en_vars) else True))
                         for i, v in enumerate(all_vars)]
                saved_pairs   = [(k, en) for k, en in pairs if k]
                extras        = [k  for k, _  in saved_pairs]
                enabled_flags = [en for _, en in saved_pairs]
                self.cfg[cfg_extra_k] = ','.join(extras)
                self.cfg[cfg_en_k]    = ','.join('1' if en else '0' for en in enabled_flags)
                if hasattr(self, '_extra_keys'):
                    self._extra_keys[pkey] = extras
                if hasattr(self, '_extra_keys_enabled'):
                    self._extra_keys_enabled[pkey] = enabled_flags
            save_cfg(self.cfg)
            self._auto_select_provider()
            self.log(f'✅ API keys saved', GREEN)

        # CFKEYS2: PBKDF2-HMAC-SHA256 (salted) -> HMAC-SHA256 counter keystream, encrypt-then-MAC.
        # CFKEYS1 (unsalted sha256 chain, no MAC) is still readable for old bundles.
        def _keys_xor(enc_key, nonce, data):
            import hmac as _hm, hashlib as _hs
            _out = bytearray()
            for _off in range(0, len(data), 32):
                _ks = _hm.new(enc_key, nonce + (_off // 32).to_bytes(8, 'big'), _hs.sha256).digest()
                _out.extend(x ^ y for x, y in zip(data[_off:_off + 32], _ks))
            return bytes(_out)

        def _keys_encrypt(data, pw):
            import hmac as _hm, hashlib as _hs
            _salt, _nonce = os.urandom(16), os.urandom(16)
            _dk = _hs.pbkdf2_hmac('sha256', pw.encode('utf-8'), _salt, 200000, dklen=64)
            _ct = _keys_xor(_dk[:32], _nonce, data)
            _tag = _hm.new(_dk[32:], _salt + _nonce + _ct, _hs.sha256).digest()
            return b'CFKEYS2:' + _salt + _nonce + _tag + _ct

        def _keys_decrypt(blob, pw):
            """blob = bytes after the CFKEYS2: magic. Raises ValueError on a wrong password / tampering."""
            import hmac as _hm, hashlib as _hs
            if len(blob) < 64:
                raise ValueError('truncated bundle')
            _salt, _nonce, _tag, _ct = blob[:16], blob[16:32], blob[32:64], blob[64:]
            _dk = _hs.pbkdf2_hmac('sha256', pw.encode('utf-8'), _salt, 200000, dklen=64)
            if not _hm.compare_digest(_tag, _hm.new(_dk[32:], _salt + _nonce + _ct, _hs.sha256).digest()):
                raise ValueError('wrong password or corrupted file')
            return _keys_xor(_dk[:32], _nonce, _ct)

        def _export_keys():
            import json as _j, base64 as _b64, hashlib as _hs
            from tkinter import simpledialog as _sd, filedialog as _fd
            _save_keys()
            _bundle = {'v': 1, 'keys': {
                'key_gemini':           self._keys.get('Google Gemini (Free)', ''),
                'key_gemini_extra':          self.cfg.get('key_gemini_extra', ''),
                'key_gemini_extra_enabled':  self.cfg.get('key_gemini_extra_enabled', ''),
                'key_groq':             self._keys.get('Groq (Free)', ''),
                'key_groq_extra':            self.cfg.get('key_groq_extra', ''),
                'key_groq_extra_enabled':    self.cfg.get('key_groq_extra_enabled', ''),
                'key_openrouter':       self._keys.get('OpenRouter (Free models)', ''),
                'key_openrouter_extra':       self.cfg.get('key_openrouter_extra', ''),
                'key_openrouter_extra_enabled': self.cfg.get('key_openrouter_extra_enabled', ''),
                'key_unsplash':         self._keys.get('_unsplash', ''),
            }}
            pw = _sd.askstring('Export Keys', 'Set a password to encrypt your keys:', show='*', parent=self)
            if not pw: return
            dest = _fd.asksaveasfilename(title='Save encrypted key bundle',
                defaultextension='.cfkeys', initialfile='clipfinder_keys.cfkeys',
                filetypes=[('ClipFinder Keys', '*.cfkeys'), ('All', '*.*')])
            if not dest: return
            try:
                _data = _j.dumps(_bundle).encode()
                with open(dest, 'wb') as _f:
                    _f.write(_b64.b64encode(_keys_encrypt(_data, pw)))
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
                if _raw.startswith(b'CFKEYS2:'):
                    _plain = _keys_decrypt(_raw[len(b'CFKEYS2:'):], pw)
                elif _raw.startswith(_magic):
                    _cipher = _raw[len(_magic):]
                    _key = _hs.sha256(pw.encode()).digest()
                    _plain = bytearray()
                    _ks = _key
                    for i, b in enumerate(_cipher):
                        if i % 32 == 0 and i > 0: _ks = _hs.sha256(_ks).digest()
                        _plain.append(b ^ _ks[i % 32])
                else:
                    messagebox.showerror('Import failed', 'Not a valid ClipFinder key bundle.'); return
                _bundle = _j.loads(_plain.decode())
                if _bundle.get('v') != 1:
                    messagebox.showerror('Import failed', 'Unknown bundle version.'); return
                _kd = _bundle.get('keys', {})
                self._keys['Google Gemini (Free)']     = _kd.get('key_gemini', '')
                self._keys['Groq (Free)']              = _kd.get('key_groq', '')
                self._keys['OpenRouter (Free models)'] = _kd.get('key_openrouter', '')
                self._keys['_unsplash']                = _kd.get('key_unsplash', '')
                self.cfg.update({k: _kd.get(k, '') for k in [
                    'key_gemini','key_gemini_extra','key_gemini_extra_enabled',
                    'key_groq','key_groq_extra','key_groq_extra_enabled',
                    'key_openrouter','key_openrouter_extra','key_openrouter_extra_enabled',
                    'key_unsplash']})
                save_cfg(self.cfg)
                for _pk, _ck in [('Google Gemini (Free)','key_gemini'),
                                  ('Groq (Free)','key_groq'),
                                  ('OpenRouter (Free models)','key_openrouter')]:
                    if _pk in self.v_keys: self.v_keys[_pk].set(_kd.get(_ck, ''))
                if hasattr(self, 'v_unsplash_key'): self.v_unsplash_key.set(_kd.get('key_unsplash',''))
                # Rebuild the extra-key rows from the bundle so a later Save/Export does not overwrite them
                for _pk, (_ek, _en) in {'Google Gemini (Free)':     ('key_gemini_extra',     'key_gemini_extra_enabled'),
                                        'Groq (Free)':              ('key_groq_extra',       'key_groq_extra_enabled'),
                                        'OpenRouter (Free models)': ('key_openrouter_extra', 'key_openrouter_extra_enabled')}.items():
                    for _r in list(_extra_key_frames[_pk].winfo_children()): _r.destroy()
                    _extra_key_vars[_pk] = []; _extra_key_enabled[_pk] = []
                    _xks = [k.strip() for k in (_kd.get(_ek, '') or '').split(',') if k.strip()]
                    _xfl = [x for x in (_kd.get(_en, '') or '').split(',') if x in ('0', '1')]
                    for _xi, _xk in enumerate(_xks):
                        _add_extra_row(_pk, _xk, (_xfl[_xi] == '1') if _xi < len(_xfl) else True)
                _save_keys()   # recomputes cfg + self._extra_keys / _extra_keys_enabled from the rebuilt rows
                messagebox.showinfo('Imported', 'All keys imported!')
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
        # Manual refresh button
        _prov_refresh_row = tk.Frame(s2, bg=BG3)
        _prov_refresh_row.pack(fill='x', pady=(0,6))
        tk.Button(_prov_refresh_row, text='↺  Refresh Status',
                  font=('Segoe UI', 8), bg=BG4, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=self._refresh_provider_status).pack(side='right')
        _leg = tk.Frame(s2, bg=BG2); _leg.pack(anchor='w', pady=(0,6))
        for _lt, _lc in [('● Ready', GREEN), ('  ● Rate-limited', YELLOW), ('  ● Dead/404', RED), ('  ○ No key', FG3)]:
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

        # GPU toggle row
        gpu_row_s = tk.Frame(s3, bg=BG3); gpu_row_s.pack(fill='x', pady=(6,3))
        gpu_cb_s = tk.Checkbutton(
            gpu_row_s, text='⚡ Use GPU acceleration for transcription  (recommended — on by default)',
            variable=self.v_use_gpu_whisper,
            font=FONT_SMALL, fg=FG, bg=BG3,
            selectcolor=BG4, activebackground=BG3,
            relief='flat', cursor='hand2',
            command=lambda: (
                self.cfg.update({'use_gpu_whisper': self.v_use_gpu_whisper.get()}),
                save_cfg(self.cfg),
                globals().update({'_WHISPER_DEVICE_CACHE': None}),
                self.log(f'GPU transcription: {"ON" if self.v_use_gpu_whisper.get() else "OFF"}', GREEN if self.v_use_gpu_whisper.get() else YELLOW)
            )
        )
        gpu_cb_s.pack(side='left', padx=4)
        gpu_info = tk.Frame(s3, bg=BG3); gpu_info.pack(fill='x', pady=(0,4), padx=4)
        tk.Label(gpu_info,
                 text='Supports: NVIDIA (CUDA)  •  AMD/Intel (Vulkan via whisper.cpp or DirectML)',
                 font=('Segoe UI', 7), fg=FG2, bg=BG3, justify='left').pack(anchor='w', padx=8)

        # ── Cookies ──
        s4 = section('🍪  Cookies (for YouTube HD, Kick, Twitter/X downloads)')
        tk.Label(s4, text='YouTube HD requires cookies from your logged-in browser. Kick and X/Twitter also need cookies.',
                font=FONT_SMALL, fg=FG2, bg=BG2, wraplength=600, justify='left').pack(anchor='w', pady=(0,6))

        # Browser cookies (easiest — no file needed)
        br_row = tk.Frame(s4, bg=BG2); br_row.pack(fill='x', pady=3)
        tk.Label(br_row, text='Extract from browser:', font=FONT_SMALL, fg=FG2, bg=BG2, width=22, anchor='w').pack(side='left')
        if not hasattr(self, 'v_cookies_browser'):
            self.v_cookies_browser = tk.StringVar(value=self.cfg.get('cookies_browser', ''))
        _browsers = ['', 'chrome', 'firefox', 'edge', 'brave', 'opera']   # yt-dlp cannot read Safari cookies on Windows
        _br_menu = tk.OptionMenu(br_row, self.v_cookies_browser, *_browsers)
        _br_menu.config(font=FONT_SMALL, bg=BG3, fg=FG, relief='flat', bd=0,
                        highlightthickness=0, activebackground=BG4)
        _br_menu['menu'].config(font=FONT_SMALL, bg=BG3, fg=FG)
        _br_menu.pack(side='left', padx=(0,8))
        tk.Label(br_row, text='← Pick your browser for YouTube HD (recommended)',
                 font=('Segoe UI',7), fg=ACCENT2, bg=BG2).pack(side='left')
        def _save_browser(*_):
            self.cfg['cookies_browser'] = self.v_cookies_browser.get()
            save_cfg(self.cfg)
        self.v_cookies_browser.trace_add('write', _save_browser)

        # cookies.txt fallback
        cr = tk.Frame(s4, bg=BG2); cr.pack(fill='x', pady=(6,3))
        tk.Label(cr, text='Or cookies.txt file:', font=FONT_SMALL, fg=FG2, bg=BG2, width=22, anchor='w').pack(side='left')
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
        # Vision Mode Reference Images
        _sec_vision = section('🎯 Vision Mode — Reference Images')
        _vref_dir = _app_path('vision_refs')
        _vref_count = len(list(_vref_dir.glob('*.png')) + list(_vref_dir.glob('*.jpg')) + list(_vref_dir.glob('*.jpeg')))
        _vref_info = tk.Frame(_sec_vision, bg=BG3)
        _vref_info.pack(fill='x', pady=(0,6))
        tk.Label(_vref_info,
                 text='Drop screenshots here to teach Vision Mode what to find or avoid.\n'
                      'Example: save a screenshot of a gambling site as "gambling_site.png" — '
                      'Vision Mode will recognize and skip similar content when you say "no gambling".',
                 font=('Segoe UI', 8), fg=FG2, bg=BG3, justify='left').pack(side='left', anchor='w')
        _vref_row = tk.Frame(_sec_vision, bg=BG3)
        _vref_row.pack(fill='x')
        _vref_count_lbl = tk.Label(_vref_row,
                                    text=f'{_vref_count} reference image{"s" if _vref_count != 1 else ""} saved',
                                    font=('Segoe UI', 8), fg=ACCENT if _vref_count else FG3, bg=BG3)
        _vref_count_lbl.pack(side='left', padx=(0,10))
        def _open_vref_folder():
            _vref_dir.mkdir(exist_ok=True)
            os.startfile(str(_vref_dir))
        tk.Button(_vref_row, text='📁  Open Reference Images Folder',
                  font=('Segoe UI', 9, 'bold'), bg=BG4, fg=FG,
                  relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                  command=_open_vref_folder).pack(side='left', padx=(0,8))
        def _scan_and_label():
            """Use Gemini Vision to auto-identify and rename unlabeled reference images."""
            import threading as _sl_thr, base64 as _sl_b64
            def _do_scan():
                _all = list(_vref_dir.glob('*.png')) + list(_vref_dir.glob('*.jpg')) + list(_vref_dir.glob('*.jpeg'))
                if not _all:
                    self.after(0, lambda: self.log('No images found in vision_refs folder', YELLOW))
                    return
                # Only label images that still carry a generic name; keep names the user chose
                _generic = re.compile(r'(?i)^(screenshot|screen[ _-]?shot|screen[ _-]?capture|image|img|clipboard|capture|snip|photo|pasted[ _-]?image|untitled|unnamed|download|new[ _-]?image)?[\s_\-.()\d]*$')
                _unknown = [p for p in _all if _generic.match(p.stem)]
                _skipped = len(_all) - len(_unknown)
                if not _unknown:
                    self.after(0, lambda n=_skipped: self.log(f'All {n} reference image(s) already have names - nothing to label', FG2))
                    return
                self.after(0, lambda: self.log(f'🔍 Scanning {len(_unknown)} image(s) with Gemini Vision ({_skipped} already named, skipped)...', FG2))
                _key = self.cfg.get('key_gemini','').strip()
                if not _key:
                    self.after(0, lambda: self.log('⚠ Need a Gemini key in Settings to scan images', YELLOW))
                    return
                try:
                    from google import genai as _gsc
                    client = _gsc.Client(api_key=_key)
                    for _f in _unknown:
                        try:
                            _b64 = _sl_b64.b64encode(_f.read_bytes()).decode()
                            _mime = 'image/jpeg' if _f.suffix.lower() in ('.jpg','.jpeg') else 'image/png'
                            # vision role list; thinking off/minimal and token headroom handled by _gemini_config
                            _raw = _gemini_complete(
                                _key, 'vision',
                                [
                                    'Look at this image and identify what brand, website, logo, or content it shows. '
                                    'Reply with ONLY a short snake_case filename label (2-4 words, underscores, no extension). '
                                    'Examples: stake_casino, roobet_gambling, rainbet_logo, slot_machine_game, kick_streaming. '
                                    'Just the label, nothing else.',
                                    {'inline_data': {'mime_type': _mime, 'data': _b64}}
                                ],
                                50, 0.1, client=client)
                            if not _raw:
                                self.after(0, lambda n=_f.name: self.log(f'  ⚠ Gemini returned empty for {n} — skipping', YELLOW))
                                continue
                            _label = __import__('re').sub(r'[^a-z0-9_]', '_', _raw.lower()).strip('_')[:40]
                            _label = __import__('re').sub(r'[^a-z0-9_]', '_', _label).strip('_')[:40]
                            if _label:
                                _new_path = _vref_dir / f'{_label}{_f.suffix}'
                                if not _new_path.exists():
                                    _f.rename(_new_path)
                                    self.after(0, lambda l=_label, o=_f.name: self.log(f'  ✏️ {o} → {l}', FG2))
                        except Exception as _se:
                            self.after(0, lambda e=_se, n=_f.name: self.log(f'  ⚠ Could not label {n}: {e}', YELLOW))
                    self.after(0, _refresh_vref_count)
                    self.after(0, lambda: self.log('✅ Scan complete', GREEN))
                except Exception as _e:
                    self.after(0, lambda err=_e: self.log(f'⚠ Scan failed: {err}', YELLOW))
            _sl_thr.Thread(target=_do_scan, daemon=True).start()
        tk.Button(_vref_row, text='🔍  Scan & Label New Images',
                  font=('Segoe UI', 9, 'bold'), bg='#1a2a3a', fg='#88ccff',
                  relief='flat', bd=0, cursor='hand2', padx=10, pady=4,
                  command=_scan_and_label).pack(side='left', padx=(0,8))
        def _refresh_vref_count():
            _n = len(list(_vref_dir.glob('*.png')) + list(_vref_dir.glob('*.jpg')) + list(_vref_dir.glob('*.jpeg')))
            _vref_count_lbl.config(text=f'{_n} reference image{"s" if _n != 1 else ""} saved',
                                   fg=ACCENT if _n else FG3)
        tk.Button(_vref_row, text='↺  Refresh',
                  font=('Segoe UI', 8), bg=BG4, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=8, pady=4,
                  command=_refresh_vref_count).pack(side='left')



        self._build_update_center(section)

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
            for pkg, _dist in [('faster_whisper', 'faster-whisper'), ('yt_dlp', 'yt-dlp'),
                               ('cv2', 'opencv-python'), ('curl_cffi', 'curl-cffi'),
                               ('soundfile', 'soundfile'), ('imagehash', 'imagehash')]:
                # disk-only: importing these on the UI thread took seconds (cv2, ctranslate2, ...)
                statuses[pkg] = _dist_version(_dist) is not None
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
                ('curl_cffi',     'curl-cffi',      'Kick/Cloudflare bypass — v0.10 to 0.16 (what yt-dlp accepts)'),
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
                    # Use the registry's version range (e.g. curl-cffi >=0.10,<0.17) instead of a bare/unpinned name
                    _ent2 = pm_entry(pip_pkg)
                    _req2 = pm_requirement(_ent2) if _ent2 else pip_pkg
                    _cmd2 = _pip_cmd([_req2], ['--no-deps'] if _nodeps2 else [])
                    if _cmd2 is None:
                        self.after(0, lambda: btn_widget.config(text='❌ No Python 3.12', bg=RED, fg=FG, state='normal')); return
                    def _run_pip2(_c):
                        # never let a timeout / decode error kill the worker: the row must always get its result
                        try:
                            return _sp3.run(_c, capture_output=True, text=True, encoding='utf-8',
                                            errors='replace', timeout=1800)
                        except Exception as _pe2:
                            return type('R', (), {'returncode': 1, 'stderr': f'{type(_pe2).__name__}: {_pe2}'})()
                    r2 = _run_pip2(_cmd2)
                    if r2.returncode != 0 and _nodeps2:
                        r2 = _run_pip2(_pip_cmd([_req2]))
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
                global _WCPP_INSTALL_LOCK
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
                    # auto_install_whispercpp only logs on failure - verify the result before reporting success
                    if not (_find_whispercpp() and _find_whispercpp_model('base')):
                        raise RuntimeError('whisper.cpp install did not complete - see the [whisper.cpp] log lines above')
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
                finally:
                    _WCPP_INSTALL_LOCK = None   # the lock only blocks concurrent runs; a retry must be able to run
            import threading; threading.Thread(target=_do, daemon=True).start()

        def _install_model_ui(size):
            def _do():
                try:
                    # Check both possible model locations first
                    _wcpp_model = _app_path('whisper_cpp') / 'models' / f'ggml-{size}.bin'
                    _fw_model_dir = _app_path('whisper_models')
                    # faster-whisper stores as ggml-{size}.bin or in a hash subfolder
                    _fw_model = _fw_model_dir / f'ggml-{size}.bin'
                    if _wcpp_model.exists():
                        self.after(0, lambda: (
                            self.log(f'✅ ggml-{size}.bin already downloaded', GREEN),
                            self.set_progress(f'✅ whisper {size} model ready', pct=100),
                            _refresh_dep_display()
                        ))
                        return
                    if _fw_model.exists():
                        self.after(0, lambda: (
                            self.log(f'✅ ggml-{size}.bin already downloaded', GREEN),
                            self.set_progress(f'✅ whisper {size} model ready', pct=100),
                            _refresh_dep_display()
                        ))
                        return

                    self.log(f'⬇ Downloading ggml-{size} model...', ACCENT2)
                    self.set_progress(f'⬇ Downloading whisper {size} model...', pct=5)
                    try:
                        import importlib as _il
                        _fw = _il.import_module('faster_whisper')
                        # Fetch the CTranslate2 model only (no model load); this is NOT the ggml file
                        _fw.download_model(size, cache_dir=str(_app_path('whisper_models')))
                        self.after(0, lambda: (
                            self.log(f'✅ faster-whisper {size} model ready', GREEN),
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
                    # Download to a side file and only rename to .bin once complete: an interrupted
                    # transfer used to leave a truncated ggml-*.bin that later counted as "already downloaded"
                    _dl_tmp = model_path.with_name(model_path.name + '.dl')
                    _dl_seen = [0, 0]
                    try:
                        _um_download(model_url, _dl_tmp, timeout=60,
                                     on_bytes=lambda got, total: (_dl_seen.__setitem__(0, got), _dl_seen.__setitem__(1, total),
                                                                  _reporthook(got // 8192, 8192, total) if total > 0 else None))
                        if _dl_seen[1] > 0 and _dl_seen[0] < _dl_seen[1]:
                            raise OSError(f'incomplete download ({_dl_seen[0]} of {_dl_seen[1]} bytes)')
                        os.replace(_dl_tmp, model_path)
                    finally:
                        for _junk in (_dl_tmp, Path(str(_dl_tmp) + '.part')):
                            try: _junk.unlink()
                            except OSError: pass
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

        # NVIDIA CUDA row — only show if NVIDIA GPU detected
        def _install_cuda_torch():
            import threading as _thr_cuda
            def _do_cuda():
                self.log('⬇ Installing whisper.cpp CUDA (cuBLAS) for NVIDIA GPU...', YELLOW)
                self.log('Downloading ~460MB binary (cuBLAS 12.4) — this can take several minutes. No CUDA toolkit needed, just NVIDIA driver.', FG2)
                import subprocess as _sp_cuda, sys as _sys_cuda, urllib.request as _ur_cuda, zipfile as _zf_cuda

                _cuda_dir = _app_path('whisper_cpp_cuda')
                _cuda_dir.mkdir(parents=True, exist_ok=True)
                (_cuda_dir / 'models').mkdir(exist_ok=True)

                # Download whisper.cpp cublas binary from official releases
                _cublas_urls = [
                    'https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.4/whisper-cublas-12.4.0-bin-x64.zip',
                    'https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.4/whisper-cublas-11.8.0-bin-x64.zip',
                ]
                _tmp_zip = _app_path('whisper_cuda_tmp.zip')
                _downloaded = False
                _tmp_part = _tmp_zip.with_name(_tmp_zip.name + '.part')
                def _cuda_hook(count, block, total):
                    if total > 0 and count % 200 == 0:
                        _p = min(99, int(count * block / total * 100))
                        self.after(0, lambda p=_p: self.set_progress(f'⬇ Downloading CUDA binary... {p}%', pct=p))
                for _url in _cublas_urls:
                    try:
                        self.log(f'Trying: {_url.split("/")[-1]}', FG2)
                        # .part file: an interrupted download must never be mistaken for a finished zip
                        _ur_cuda.urlretrieve(_url, str(_tmp_part), reporthook=_cuda_hook)
                        if _tmp_part.exists() and _tmp_part.stat().st_size > 1_000_000:
                            os.replace(str(_tmp_part), str(_tmp_zip))
                            _downloaded = True
                            break
                    except Exception as _de:
                        self.log(f'Failed: {_de}', YELLOW)
                        try: _tmp_part.unlink(missing_ok=True)
                        except Exception: pass
                        continue

                if not _downloaded:
                    self.log('❌ Could not download CUDA binary. Check internet connection.', RED)
                    return

                # Extract
                self.log('Extracting CUDA binary...', FG2)
                try:
                    with _zf_cuda.ZipFile(str(_tmp_zip), 'r') as _zf:
                        for _name in _zf.namelist():
                            _bn = Path(_name).name
                            if not _bn or _name.endswith('/'): continue
                            _data = _zf.read(_name)
                            if len(_data) > 0:
                                (_cuda_dir / _bn).write_bytes(_data)
                                self.log(f'  Extracted: {_bn} ({len(_data)//1024}KB)', FG2)
                    _tmp_zip.unlink(missing_ok=True)
                except Exception as _ee:
                    self.log(f'❌ Extract failed: {_ee}', RED)
                    return

                # Rename whisper-cli.exe
                _cli = _cuda_dir / 'whisper-cli.exe'
                _dst = _cuda_dir / 'whisper-whisper-cli.exe'
                if _cli.exists() and not _dst.exists():
                    _cli.rename(_dst)

                # Download a model if none exists
                _models_dir = _cuda_dir / 'models'
                if not list(_models_dir.glob('ggml-*.bin')):
                    self.log('Downloading ggml-base.bin model (~142MB)...', FG2)
                    _mpart = _models_dir / 'ggml-base.bin.part'
                    try:
                        _ur_cuda.urlretrieve(
                            'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin',
                            str(_mpart))
                        os.replace(str(_mpart), str(_models_dir / 'ggml-base.bin'))
                        self.log('✅ Model downloaded!', GREEN)
                    except Exception as _me:
                        self.log(f'Model download failed: {_me} — download manually in Settings', YELLOW)
                        try: _mpart.unlink(missing_ok=True)
                        except Exception: pass

                if _dst.exists():
                    global _WHISPER_DEVICE_CACHE
                    _WHISPER_DEVICE_CACHE = None
                    self.log('✅ NVIDIA CUDA whisper.cpp installed! Restart ClipFinder.', GREEN)
                else:
                    self.log('❌ Install failed — whisper-whisper-cli.exe not found after extraction.', RED)

            _thr_cuda.Thread(target=_do_cuda, daemon=True).start()

        # Detect NVIDIA GPU
        _has_nvidia = False
        try:
            import subprocess as _sp_nv
            _nv = _sp_nv.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                              capture_output=True, text=True, timeout=3)
            _has_nvidia = _nv.returncode == 0 and _nv.stdout.strip()
        except: pass

        r2b = tk.Frame(btn_grid, bg=BG3); r2b.pack(fill='x', pady=2)
        _nvidia_label = f'NVIDIA GPU: {_nv.stdout.strip()[:40]}' if _has_nvidia else 'No NVIDIA GPU detected'
        tk.Button(r2b, text='⬇  Install NVIDIA CUDA Support', font=('Segoe UI', 9, 'bold'),
                 bg=BG4 if not _has_nvidia else '#1a3a1a', fg=FG if not _has_nvidia else '#00ff88',
                 relief='flat', bd=0, cursor='hand2' if _has_nvidia else 'arrow',
                 padx=12, pady=5,
                 command=_install_cuda_torch if _has_nvidia else lambda: None
                 ).pack(side='left', padx=(0,8))
        tk.Label(r2b, text=f'CUDA torch for faster-whisper GPU — ~2.5GB  |  {_nvidia_label}',
                font=('Segoe UI', 7), fg=GREEN if _has_nvidia else FG3, bg=BG3).pack(side='left')

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
        """Show which API providers have keys configured and live rate-limit state."""
        # Debounce — cancel any pending refresh and schedule one 300ms from now
        # This prevents flickering when many key rotations fire rapidly
        if hasattr(self, '_prov_status_after_id'):
            try: self.after_cancel(self._prov_status_after_id)
            except Exception: pass
        self._prov_status_after_id = self.after(300, self._do_refresh_provider_status)

    def _do_refresh_provider_status(self):
        """Actually rebuild the provider status UI."""
        if not hasattr(self, '_prov_status_frame'): return
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
        import time as _t_status
        _RL_EXPIRY = 300
        # Read live from v_keys StringVars (not cached _keys)
        live_keys = {p: v.get().strip() for p, v in self.v_keys.items()}
        for pname, key in live_keys.items():
            if pname.startswith('_'): continue
            has_key = bool(key.strip())
            if has_key: has_any = True
            _all_xk  = getattr(self,'_extra_keys',{}).get(pname,[])
            _all_xen = getattr(self,'_extra_keys_enabled',{}).get(pname,[])
            _all_xen_pad = _all_xen + [True]*max(0,len(_all_xk)-len(_all_xen))
            _extras  = [k for k,en in zip(_all_xk,_all_xen_pad) if k and en]
            # Check how many active (non-cooldown) keys exist
            import time as _rps_t
            _cds = getattr(self,'_key_cooldowns',{})
            _extras_on_cd = [k for k in _extras if _rps_t.time() < _cds.get((pname,k),0)]
            _active_key_count = (1 if key.strip() and _rps_t.time() >= _cds.get((pname,key.strip()),0) else 0) + len([k for k in _extras if _rps_t.time() >= _cds.get((pname,k),0)])
            # Use app-level _rl_provs (self) — reflects live state during runs
            _is_rl = pname in getattr(self, '_rl_provs', set())
            # Check if provider is marked dead (404/no endpoints) this session
            _is_dead = pname in getattr(self, '_dead_models', set())
            # Check Groq daily token limit
            _is_tpd = (pname == 'Groq (Free)' and getattr(self, '_groq_tpd_exhausted', False))
            # Calculate time remaining on rate limit
            _rl_remaining = 0
            if _is_rl:
                _since = getattr(self, '_rl_since', {}).get(pname, 0)
                _rl_remaining = max(0, int(_RL_EXPIRY - (_t_status.time() - _since)))
                if _rl_remaining == 0:
                    # Expired — clean it up
                    with getattr(self, '_rl_provs_lock', __import__('threading').Lock()):
                        getattr(self, '_rl_provs', set()).discard(pname)
                    _is_rl = False
            r = tk.Frame(self._prov_status_frame, bg=BG2)
            r._is_status_row = True
            r.pack(fill='x', pady=2)
            # Dot color: RED=dead model, YELLOW=rate-limited, GREEN=ready, GREY=no key
            if _is_dead or _is_tpd:
                dot_color = RED
            elif _is_rl:
                dot_color = YELLOW
            elif has_key:
                dot_color = GREEN
            else:
                dot_color = FG3
            tk.Label(r, text='●', font=('Segoe UI', 10), fg=dot_color, bg=BG2).pack(side='left')
            display_name = _display.get(pname, pname)
            _key_suffix = f' (+{len(_extras)} more)' if _extras else ''
            tk.Label(r, text=f' {display_name}{_key_suffix}', font=FONT_SMALL,
                    fg=FG if has_key else FG2, bg=BG2).pack(side='left')
            if _is_dead or _is_tpd:
                status = '🔄 Daily token limit — resets tomorrow' if _is_tpd else '❌ Model unavailable (404)'
                status_color = RED
            elif _is_rl:
                _mins, _secs = divmod(_rl_remaining, 60)
                _eta = f'{_mins}m{_secs:02d}s' if _mins else f'{_secs}s'
                status = f'⏳ Rate-limited — clears in {_eta}'
                status_color = YELLOW
            elif has_key and _extras_on_cd:
                # Some extra keys are on auto-cooldown
                _n_active = _active_key_count
                _n_total  = 1 + len(_extras) if key.strip() else len(_extras)
                _soonest_cd = min(_extras_on_cd, key=lambda k: _cds.get((pname,k),0))
                _rem_cd = max(0, int(_cds.get((pname,_soonest_cd),0) - _rps_t.time()))
                _cd_eta = f'{_rem_cd//60}m{_rem_cd%60:02d}s'
                status = f'⏳ {_n_active}/{_n_total} keys active — {len(_extras_on_cd)} paused, resumes {_cd_eta}'
                status_color = YELLOW
            elif _extras:
                status = f'✓ Ready ({1+len(_extras)} keys)'
                status_color = GREEN
            elif has_key:
                status = '✓ Ready'
                status_color = GREEN
            else:
                status = 'No key — add above'
                status_color = YELLOW
            tk.Label(r, text=status, font=FONT_SMALL, fg=status_color, bg=BG2).pack(side='right')
        # Unsplash status row (stock photos mode)
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
        tk.Label(us_r, text='✓ Ready (stock photos)' if us_has else 'No key — optional, only needed for stock mode',
                font=FONT_SMALL, fg=GREEN if us_has else FG3, bg=BG2).pack(side='right')
        if not has_any:
            r = tk.Frame(self._prov_status_frame, bg=BG2)
            r._is_status_row = True
            r.pack(fill='x', pady=4)
            tk.Label(r, text='⚠️  No API keys configured — add at least one above to find clips',
                    font=FONT_SMALL, fg=YELLOW, bg=BG2).pack(anchor='w')
        # Clear key cooldowns button — shown only if any cooldowns are active
        import time as _rps_t2
        _any_cds = any(_rps_t2.time() < v for v in getattr(self,'_key_cooldowns',{}).values())
        if _any_cds:
            _cd_bar = tk.Frame(self._prov_status_frame, bg=BG2)
            _cd_bar._is_status_row = True
            _cd_bar.pack(fill='x', pady=(6,2))
            tk.Label(_cd_bar, text='⏳ Some keys are auto-paused due to rate-limits or auth errors.',
                     font=('Segoe UI',8), fg=YELLOW, bg=BG2).pack(side='left')
            def _clear_cooldowns():
                with self._key_cd_lock:
                    self._key_cooldowns.clear()
                self.log('✅ All key cooldowns cleared — keys re-enabled', GREEN)
                self._refresh_provider_status()
            tk.Button(_cd_bar, text='Clear All Cooldowns',
                      font=('Segoe UI',8,'bold'), fg=BG, bg=GREEN,
                      relief='flat', bd=0, cursor='hand2', padx=8, pady=2,
                      command=_clear_cooldowns).pack(side='right', padx=4)

        # Auto-refresh every 5 minutes — just enough to reflect cooldown expiry
        if getattr(self, '_prov_periodic_id', None):
            try: self.after_cancel(self._prov_periodic_id)
            except Exception: pass
        self._prov_periodic_id = self.after(300000, lambda: self._refresh_provider_status() if hasattr(self,'_prov_status_frame') else None)


    def _auto_select_provider(self):
        """Auto-select best available provider based on configured keys."""
        # Keep the user's chosen provider when it already has a saved key
        cur = self.v_provider.get()
        if self._keys.get(cur, '').strip():
            self.v_key.set(self._keys[cur])
            self._refresh_prov_btns()
            return
        priority = ['Google Gemini (Free)', 'Groq (Free)', 'OpenRouter (Free models)']
        for pname in priority:
            if self._keys.get(pname, '').strip():
                self.v_provider.set(pname)
                self.v_key.set(self._keys[pname])
                self._refresh_prov_btns()
                self.log(f'Auto-selected provider: {pname}', FG2)
                return


    # ── Music Removal (isolated Demucs engine) ────────────────────────────────
    # Demucs/PyTorch run in a SEPARATE Python process from %LOCALAPPDATA%\ClipFinder\envs\demucs, so
    # nothing here imports torch/demucs/torchaudio and it can never collide with the app's packages.
    @staticmethod
    def _mr_clean_path(s):
        """Strip whitespace and ONE matching pair of quotes that Explorer's 'Copy as path' adds."""
        s = (s or '').strip()
        for _ in range(3):
            if len(s) >= 2 and ((s[0] == s[-1] and s[0] in '"\'`') or (s[0] in '“‘' and s[-1] in '”’')):
                s = s[1:-1].strip()
            else:
                break
        return s

    @staticmethod
    def _mr_explain(tail, what='Demucs'):
        """Readable one-liner from the tail of a failed subprocess."""
        lines = [l.strip() for l in (tail or '').splitlines() if l.strip()]
        last = lines[-1][:300] if lines else 'no details were reported'
        low = (tail or '').lower()
        if any(k in low for k in ('no module named', 'modulenotfounderror', 'dll load failed', 'importerror')):
            return (f'{what} could not start - the Music Removal engine looks damaged. '
                    f'Reinstall it from Settings > Update Center.  ({last})')
        if any(k in low for k in ('out of memory', 'memoryerror', "can't allocate", 'not enough memory')):
            return f'{what} ran out of memory - try a shorter video or close other programs.  ({last})'
        if any(k in low for k in ('urlopen error', 'getaddrinfo', 'connection', 'timed out', 'httperror')):
            return f'{what} could not download the separation model (needed once) - check your internet connection.  ({last})'
        return last

    def _mr_say(self, text, color=None):
        """Update the tab's status label from any thread."""
        color = color or ACCENT2
        def _do():
            try:
                self.mr_status_lbl.config(text=text, fg=color)
            except Exception:
                pass
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _mr_cancel_obj(self):
        """Object with .is_set() (what eng_run/_um_run poll) that follows the global Cancel button."""
        import types as _types
        return _types.SimpleNamespace(is_set=lambda: bool(getattr(self, '_cancel_requested', False)))

    def _mr_engine_refresh(self):
        """Header line of the tab: engine installed (version) / not installed + Install button."""
        try:
            st = eng_status('demucs')
        except Exception:
            st = dict(installed=False, version=None, torch=None)
        try:
            if st.get('installed'):
                self.mr_eng_lbl.config(text=f'Engine: ✅ Demucs {st.get("version") or "?"}  +  PyTorch {st.get("torch") or "?"}  (isolated)',
                                       fg=GREEN)
                self.mr_eng_btn.pack_forget()
            else:
                self.mr_eng_lbl.config(text='Engine: ⚠ not installed - one-time download of about 1 GB', fg=YELLOW)
                if not self.mr_eng_btn.winfo_ismapped():
                    self.mr_eng_btn.pack(side='left', padx=(10, 0))
        except Exception:
            pass

    def _mr_install_engine(self, then=None):
        """Ask ONCE, then build the isolated Demucs engine in a worker thread (cancellable, progress in the
        status bar). Calls then() on the Tk thread when it succeeded; on refusal/failure just resets."""
        if getattr(self, '_mr_busy', False) or getattr(self, '_uc_engine_busy', False):
            messagebox.showinfo('Music Removal', 'Something is already running (or the engine is installing).\n'
                                                 'Wait for it to finish first.')
            return
        if not messagebox.askyesno(
                'Install Music Removal engine?',
                'Music Removal needs its own AI engine (Demucs + PyTorch).\n\n'
                '  -  One-time download of about 1 GB (allow ~3 GB of free disk space)\n'
                '  -  It installs into its own folder and never touches your other modules\n'
                '  -  The separation model (100-400 MB) is fetched the first time you run it\n\n'
                'Install it now?'):
            self._mr_say('Music Removal engine not installed - click "Install engine" when you are ready.', YELLOW)
            return
        self._mr_busy = True
        self._uc_engine_busy = True
        cancel = self._mr_cancel_obj()
        self.log('🎵 Installing the Music Removal engine (one-time download)...', ACCENT2)
        self.set_busy(True)                                   # also clears a stale cancel flag
        self.set_progress('🎵 Installing Music Removal engine...', pct=None)
        self._mr_say('⏳ Installing the Music Removal engine - this can take several minutes...')
        try:
            self.mr_go_btn.config(state='disabled')
        except Exception:
            pass

        def _line(l):
            try:
                self.after(0, lambda l=l: self.set_progress(f'🎵 {l[:70]}', pct=None))
            except Exception:
                pass

        def _work():
            res = dict(ok=False, error='unknown error')
            try:
                res = eng_install('demucs', on_line=_line, cancel=cancel)
            except Exception as e:
                res = dict(ok=False, error=str(e))

            def _fin():
                self._mr_busy = False
                self._uc_engine_busy = False
                try:
                    self.mr_go_btn.config(state='normal')
                except Exception:
                    pass
                self.set_busy(False)
                self.set_progress('', pct=0)
                self._mr_engine_refresh()
                try:
                    self._uc_engine_refresh()
                except Exception:
                    pass
                if res.get('ok'):
                    self.log(f'✅ Music Removal engine ready (Demucs {res.get("version")})', GREEN)
                    self._mr_say('✅ Engine installed', GREEN)
                    if then:
                        then()
                elif res.get('error') == 'Cancelled':
                    self.log('⛔ Engine install cancelled', YELLOW)
                    self._mr_say('⛔ Engine install cancelled', YELLOW)
                else:
                    self.log(f'❌ Music Removal engine: {res.get("error")}', RED)
                    self._mr_say('❌ Engine install failed - see the log', RED)
                    messagebox.showerror('Music Removal engine',
                                         f'Could not install the engine:\n\n{res.get("error")}\n\nDetails are in the update log.')
            try:
                self.after(0, _fin)
            except Exception:
                pass
        threading.Thread(target=_work, daemon=True).start()

    def _mr_parse_queue(self):
        """-> (existing files, missing paths). Strips quotes, ignores blanks and duplicates."""
        try:
            raw = self.v_mr_queue_box.get('1.0', 'end').splitlines()
        except Exception:
            raw = []
        if not any(l.strip() for l in raw):
            try:
                raw = [self.v_mr_video.get()]         # legacy single-file field
            except Exception:
                raw = []
        videos, missing, seen = [], [], set()
        for line in raw:
            p = self._mr_clean_path(line)
            if not p:
                continue
            key = os.path.normcase(os.path.abspath(p))
            if key in seen:
                continue
            seen.add(key)
            (videos if os.path.isfile(p) else missing).append(p)
        return videos, missing

    def _run_music_removal(self):
        """Run Demucs (isolated engine) on all queued videos."""
        if getattr(self, '_mr_busy', False):
            messagebox.showinfo('Music Removal', 'Music Removal is already running.')
            return
        videos, missing = self._mr_parse_queue()
        for m in missing:
            self.log(f'⚠ Music Removal: file not found, skipped: {m}', YELLOW)
        if not videos:
            messagebox.showerror('No video', 'Add videos to the queue first.' if not missing else
                                 'None of the queued files exist:\n\n' + '\n'.join(missing[:8]))
            return
        out = self._mr_clean_path(self.v_mr_out.get())
        if not out:
            messagebox.showerror('No output', 'Select an output folder first.')
            return
        model = self.v_mr_model.get()
        keep_vox = bool(self.v_mr_keep_vocals.get())
        keep_other = bool(self.v_mr_keep_other.get())
        if not keep_vox and not keep_other:
            keep_vox = True
            self.log('[Music] Nothing ticked under Keep - keeping vocals only', FG2)
        if missing and not messagebox.askyesno(
                'Some files were not found',
                f'{len(missing)} queued file(s) do not exist and will be skipped:\n\n' + '\n'.join(missing[:6]) +
                f'\n\nContinue with the other {len(videos)}?'):
            return
        try:
            installed = bool(eng_status('demucs').get('installed'))
        except Exception:
            installed = False
        self._mr_engine_refresh()
        if installed:
            self._mr_start(videos, out, model, keep_vox, keep_other)
        else:
            self._mr_install_engine(then=lambda: self._mr_start(videos, out, model, keep_vox, keep_other))

    def _mr_start(self, videos, out, model, keep_vox, keep_other):
        if getattr(self, '_mr_busy', False):
            return
        self._mr_busy = True
        try:
            self.mr_go_btn.config(state='disabled')
        except Exception:
            pass
        self.set_busy(True)                                   # also clears a stale cancel flag
        self._mr_say(f'⏳ Processing {len(videos)} video(s)...')
        self.log(f'🎵 Music Removal: starting {len(videos)} video(s)...', ACCENT2)
        try:
            threading.Thread(target=self._mr_worker, args=(videos, out, model, keep_vox, keep_other),
                             daemon=True).start()
        except Exception as e:
            self._mr_finish([], [], False, f'Could not start the worker: {e}', out, len(videos))

    def _mr_worker(self, videos, out, model, keep_vox, keep_other):
        """Worker thread: ffmpeg lookup, engine sanity check, then one video at a time."""
        done, failed, cancelled, fatal = [], [], False, ''
        cancel = self._mr_cancel_obj()
        try:
            self._mr_say('⏳ Preparing (ffmpeg)...')
            ff = ensure_ffmpeg()                              # may download ffmpeg - never on the Tk thread
            try:                                              # the Demucs subprocess looks ffmpeg up on PATH
                ffdir = os.path.dirname(ff) if os.path.isabs(ff) else ''
                if ffdir and os.path.normcase(ffdir) not in [os.path.normcase(x) for x in os.environ.get('PATH', '').split(os.pathsep)]:
                    os.environ['PATH'] = ffdir + os.pathsep + os.environ.get('PATH', '')
            except Exception:
                pass
            if not pm_python():
                raise RuntimeError('Python 3.12 was not found - the Music Removal engine needs it. Install Python 3.12 and retry.')
            if not eng_status('demucs').get('installed'):
                raise RuntimeError('The Music Removal engine is not installed. Use the "Install engine" button.')
            os.makedirs(out, exist_ok=True)
            n = len(videos)
            for i, vid in enumerate(videos):
                if cancel.is_set():
                    cancelled = True
                    break
                name = os.path.basename(vid)
                self._mr_say(f'⏳ [{i + 1}/{n}] {name}...')
                self.log(f'🎵 [{i + 1}/{n}] Processing: {name}', ACCENT2)
                try:
                    res = self._run_music_removal_single(vid, out, model, keep_vox, keep_other, ff, i, n)
                except Exception as e:
                    import traceback as _tb
                    failed.append((name, str(e) or e.__class__.__name__))
                    self.log(f'❌ [{name}] Failed: {e}', RED)
                    self.log(_tb.format_exc(), RED)
                    continue
                if res is None:                               # cancelled part-way through this video
                    cancelled = True
                    break
                done.append(res)
        except Exception as e:
            import traceback as _tb2
            fatal = str(e) or e.__class__.__name__
            self.log(f'Music Removal error: {_tb2.format_exc()}', RED)
        finally:
            try:
                self.after(0, lambda: self._mr_finish(done, failed, cancelled, fatal, out, len(videos)))
            except Exception:
                self._mr_busy = False

    def _mr_finish(self, done, failed, cancelled, fatal, out, total):
        """Tk thread: reset the busy state (always) and report an accurate summary."""
        self._mr_busy = False
        try:
            self.mr_go_btn.config(state='normal')
        except Exception:
            pass
        try:
            self.set_busy(False)
        except Exception:
            pass
        if fatal:
            text, color, pct = f'❌ {fatal[:160]}', RED, 0
        elif cancelled:
            text, color, pct = f'⛔ Cancelled - {len(done)} of {total} finished', YELLOW, 0
        elif failed and not done:
            text, color, pct = f'❌ Failed: {len(failed)} of {total} video(s)', RED, 0
        elif failed:
            text, color, pct = f'⚠ {len(done)} done, {len(failed)} failed', YELLOW, 100
        else:
            text, color, pct = f'✅ Done: {len(done)} video(s) processed', GREEN, 100
        self._mr_say(text, color)
        try:
            self.set_progress(text, pct=pct)
        except Exception:
            pass
        self.log(text, color)
        detail = '\n'.join(f'  -  {n}: {why[:200]}' for n, why in failed[:6])
        if len(failed) > 6:
            detail += f'\n  ... and {len(failed) - 6} more (see the log)'
        try:
            if fatal:
                messagebox.showerror('Music Removal', fatal)
            elif cancelled:
                pass
            elif failed and not done:
                messagebox.showerror('Music Removal', f'No video could be processed:\n\n{detail}')
            elif failed:
                messagebox.showwarning('Music Removal', f'{len(done)} saved, {len(failed)} failed:\n\n{detail}\n\nSaved to: {out}')
            else:
                messagebox.showinfo('Music Removed', f'Saved {len(done)} video(s) to:\n{out}'
                                    if len(done) != 1 else f'Saved: {os.path.basename(done[0])}\nLocation: {out}')
        except Exception:
            pass

    def _run_music_removal_single(self, vid, out, model, keep_vox, keep_other, ff, vi=0, total=1):
        """Separate one video with the isolated Demucs engine and mux the chosen stems back.
        Runs on a worker thread. Returns the output path, or None if cancelled; raises RuntimeError
        (readable message) on failure. Temp files are always removed.

        Demucs runs with --two-stems=vocals, so it yields exactly two stems:
          vocals     - the speech
          no_vocals  - EVERYTHING else (music, drums, bass, effects)
        keep_vox -> vocals in the result; keep_other -> no_vocals (the background music) in the result.
        Vocals only = music removed. Both ticked = the full original mix."""
        import tempfile as _tempf, shutil as _shu
        cancel = self._mr_cancel_obj()
        name = os.path.basename(vid)
        total = max(1, int(total))

        def prog(frac, text):
            pct = (vi + max(0.0, min(1.0, frac))) / total * 100
            self.set_progress(f'🎵 [{vi + 1}/{total}] {text}' if total > 1 else f'🎵 {text}', pct=pct)
            self._mr_say(f'⏳ {text}')

        def ffrun(cmd, what, timeout=6 * 3600):
            rc, tail, state = _um_run([ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y'] + cmd,
                                      'ffmpeg', timeout=timeout, cancel=cancel)
            if state == 'cancelled':
                return None
            if state == 'timeout':
                raise RuntimeError(f'ffmpeg timed out while {what}.')
            if rc != 0:
                raise RuntimeError(f'ffmpeg failed while {what}: {self._mr_explain(tail, "ffmpeg")}')
            return True

        tmp = _tempf.mkdtemp(prefix='cf_mr_')
        part = None
        try:
            # 1. audio -> 44.1 kHz stereo wav (ASCII path, so the engine never meets odd characters)
            prog(0.02, 'Extracting audio...')
            self.log('Step 1: Extracting audio...', FG2)
            audio = os.path.join(tmp, 'input_audio.wav')
            if not ffrun(['-i', vid, '-vn', '-ar', '44100', '-ac', '2', '-f', 'wav', audio], 'reading the audio', 3600):
                return None
            if not os.path.isfile(audio) or os.path.getsize(audio) < 1024:
                raise RuntimeError(f'"{name}" has no usable audio track.')
            if cancel.is_set():
                return None

            # 2. separate (progress is parsed from demucs' tqdm bars)
            self.log(f'Step 2: Running Demucs [{model}] in the isolated engine...', FG2)
            prog(0.05, f'Separating vocals [{model}]... (this takes a while)')
            sep_out = os.path.join(tmp, 'separated')
            st = {'passes': 1, 'pass': 0, 'last': -1, 'shown': -1}

            def on_line(line):
                m = re.search(r'bag of (\d+) models', line)
                if m:
                    st['passes'] = max(1, int(m.group(1)))
                    return
                m = re.search(r'(\d{1,3})%\|', line)
                if not m:
                    return
                pct = min(100, int(m.group(1)))
                if 'seconds' not in line:                     # a model-download bar, not separation
                    if pct != st['shown']:
                        st['shown'] = pct
                        self._mr_say(f'⏳ Downloading the {model} model (first use only)... {pct}%')
                    return
                if st['last'] >= 0 and pct < st['last'] - 10:  # a bag of models prints one bar per model
                    st['pass'] = min(st['pass'] + 1, st['passes'] - 1)
                st['last'] = pct
                frac = (st['pass'] + pct / 100.0) / st['passes']
                if int(frac * 100) != st['shown']:
                    st['shown'] = int(frac * 100)
                    prog(0.05 + 0.80 * frac, f'Separating vocals [{model}]... {int(frac * 100)}%')

            rc, tail, state = eng_run('demucs', ['-n', model, '--two-stems=vocals', '-o', sep_out, audio],
                                      on_line=on_line, cancel=cancel, cwd=tmp)
            if state == 'cancelled' or cancel.is_set():
                return None
            if state == 'timeout':
                raise RuntimeError('Demucs timed out.')
            if rc != 0:
                raise RuntimeError('Demucs failed: ' + self._mr_explain(tail))

            # 3. pick / mix the stems
            self.log('Step 3: Mixing selected stems...', FG2)
            prog(0.86, 'Mixing stems...')
            stem_dir = os.path.join(sep_out, model, 'input_audio')
            if not os.path.isdir(stem_dir):                   # be tolerant about the folder naming
                cands = [d for d in (os.path.join(sep_out, x, 'input_audio') for x in
                                     (os.listdir(sep_out) if os.path.isdir(sep_out) else [])) if os.path.isdir(d)]
                stem_dir = cands[0] if cands else stem_dir

            def find_stem(nm):
                for ext in ('wav', 'flac', 'mp3'):
                    p = os.path.join(stem_dir, f'{nm}.{ext}')
                    if os.path.isfile(p):
                        return p
                return None
            wanted = (['vocals'] if keep_vox else []) + (['no_vocals'] if keep_other else [])
            if not wanted:
                wanted = ['vocals']
            stems = []
            for nm in wanted:
                p = find_stem(nm)
                if not p:
                    raise RuntimeError(f'Demucs did not produce the "{nm}" stem (looked in {stem_dir}).')
                stems.append(p)
            if len(stems) == 1:
                mixed = stems[0]
            else:
                mixed = os.path.join(tmp, 'mixed.wav')
                inputs = []
                for s in stems:
                    inputs += ['-i', s]
                # amix divides every input by the input count, so scale back up and guard against clipping
                if not ffrun(inputs + ['-filter_complex',
                                       f'amix=inputs={len(stems)}:duration=longest,volume={len(stems)},alimiter=limit=0.95',
                                       mixed], 'mixing the stems', 3600):
                    return None
            if cancel.is_set():
                return None

            # 4. mux the new audio onto the original video
            self.log('Step 4: Merging with original video...', FG2)
            prog(0.92, 'Merging audio + video...')
            os.makedirs(out, exist_ok=True)
            out_path = os.path.join(out, f'{os.path.splitext(name)[0]} - NoMusic - ClipFinder.mp4')
            part = out_path + '.part'
            reencode = os.path.splitext(vid)[1].lower() in ('.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm')
            if reencode:
                vcodec, _ac, extra = get_encoder(ff)
                cv = ['-c:v', vcodec] + list(extra)
            else:
                cv = ['-c:v', 'copy']
            cmd = ['-i', vid, '-i', mixed] + cv + ['-c:a', 'aac', '-b:a', '192k',
                                                   '-map', '0:v:0?', '-map', '1:a:0', '-shortest',
                                                   '-movflags', '+faststart', '-f', 'mp4', part]
            self.log(f'[Music] ffmpeg merge: {"re-encode" if reencode else "stream copy"} -> {os.path.basename(out_path)}', FG2)
            if not ffrun(cmd, 'merging the audio back into the video'):
                return None
            if not os.path.isfile(part) or os.path.getsize(part) == 0:
                raise RuntimeError('ffmpeg produced an empty file.')
            os.replace(part, out_path)
            part = None
            size = os.path.getsize(out_path) / 1024 / 1024
            self.log(f'✅ Done: {os.path.basename(out_path)} ({size:.1f}MB)', GREEN)
            return out_path
        finally:
            if part:
                try:
                    os.remove(part)
                except OSError:
                    pass
            _shu.rmtree(tmp, ignore_errors=True)

    def _build_music_removal_tab(self, p):
        """AI Music Removal using Demucs — strips background music, keeps vocals."""
        tk.Label(p, text='🎵  AI MUSIC REMOVAL', font=('Segoe UI', 10, 'bold'),
                fg=ACCENT, bg=BG).pack(anchor='w', padx=16, pady=(12,2))
        tk.Label(p, text='Strip copyrighted background music. Keeps vocals and speech. Runs locally — no API needed.',
                font=FONT_SMALL, fg=FG2, bg=BG).pack(anchor='w', padx=16, pady=(0,4))

        # Engine status line: Demucs runs in its own isolated environment (see the update manager)
        eng_row = tk.Frame(p, bg=BG); eng_row.pack(fill='x', padx=16, pady=(0,6))
        self.mr_eng_lbl = tk.Label(eng_row, text='', font=FONT_SMALL, fg=FG2, bg=BG, anchor='w')
        self.mr_eng_lbl.pack(side='left')
        self.mr_eng_btn = tk.Button(eng_row, text='⬇  Install engine', font=FONT_SMALL,
                                    bg=ACCENT, fg='#000', relief='flat', bd=0, cursor='hand2', padx=10, pady=2,
                                    command=lambda: self._mr_install_engine())
        self._mr_engine_refresh()
        p.bind('<Map>', lambda e: self._mr_engine_refresh() if e.widget is p else None)   # picks up Settings-side installs

        sec = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        sec.pack(fill='x', padx=16, pady=(0,6))
        inner = tk.Frame(sec, bg=BG2); inner.pack(fill='x', padx=12, pady=(8,4))

        # ── Queue: multi-file text area ───────────────────────────────────────
        q_hdr = tk.Frame(inner, bg=BG2); q_hdr.pack(fill='x', pady=(0,4))
        tk.Label(q_hdr, text='Videos:', font=FONT_SMALL, fg=FG2, bg=BG2, width=10, anchor='w').pack(side='left')
        tk.Label(q_hdr, text='paste paths or use Browse — one per line',
                 font=('Segoe UI',7), fg=FG2, bg=BG2).pack(side='left')

        qf = tk.Frame(inner, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        qf.pack(fill='x', pady=(0,4))
        self.v_mr_queue_box = tk.Text(qf, font=('Segoe UI', 7), bg=BG3, fg=FG,
                                      insertbackground=ACCENT, relief='flat', bd=4,
                                      wrap='none', height=5)
        _mrqs = tk.Scrollbar(qf, command=self.v_mr_queue_box.yview)
        _mrqs.pack(side='right', fill='y')
        self.v_mr_queue_box.pack(fill='both', expand=True)
        self.v_mr_queue_box.config(yscrollcommand=_mrqs.set)

        btn_row_q = tk.Frame(inner, bg=BG2); btn_row_q.pack(fill='x', pady=(0,4))
        def _mr_browse_multi():
            files = filedialog.askopenfilenames(
                title='Select videos',
                filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')])
            for f in files:
                current = self.v_mr_queue_box.get('1.0','end').strip()
                if f not in current:
                    self.v_mr_queue_box.insert('end', f'\n{f}' if current else f)
            _mr_update_count()
        def _mr_add_clipfinder():
            v = self._mr_clean_path(self._real_video())          # '' while the entry only shows its placeholder
            if not v:
                self.mr_status_lbl.config(text='No Clip Finder video loaded yet - pick one on the Clip Finder tab first.', fg=YELLOW)
                return
            current = self.v_mr_queue_box.get('1.0','end').strip()
            if v not in current:
                self.v_mr_queue_box.insert('end', f'\n{v}' if current else v)
            _mr_update_count()
        def _mr_update_count(*_):
            lines = [l.strip() for l in self.v_mr_queue_box.get('1.0','end').splitlines() if l.strip()]
            self.mr_status_lbl.config(text=f'{len(lines)} video(s) queued' if lines else '')
        def _mr_clear():
            self.v_mr_queue_box.delete('1.0','end')
            _mr_update_count()
        self.v_mr_queue_box.bind('<KeyRelease>', _mr_update_count)

        tk.Button(btn_row_q, text='📂 Browse Multiple', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_mr_browse_multi).pack(side='left', padx=(0,4))
        tk.Button(btn_row_q, text='📋 Use Clip Finder Video', font=FONT_SMALL,
                  bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_mr_add_clipfinder).pack(side='left', padx=(0,4))
        tk.Button(btn_row_q, text='🗑 Clear', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_mr_clear).pack(side='left')

        # Keep v_mr_video as StringVar for compatibility with _run_music_removal
        self.v_mr_video = tk.StringVar()

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
        # Demucs runs with --two-stems=vocals: the only two stems are the vocals and "everything else"
        # (the music). So this box keeps the background music - the label now says exactly that.
        tk.Checkbutton(keep_row, text='Background music (no vocals)', variable=self.v_mr_keep_other,
                      font=FONT_SMALL, fg=FG, bg=BG2, selectcolor=BG3,
                      activebackground=BG2, cursor='hand2').pack(side='left', padx=(8,0))
        tk.Label(keep_row, text='Vocals only = music removed  |  both = original mix',
                font=('Segoe UI',7), fg=FG3, bg=BG2).pack(side='left', padx=8)

        btn_row = tk.Frame(p, bg=BG); btn_row.pack(fill='x', padx=16, pady=6)
        self.mr_go_btn = tk.Button(btn_row, text='🎵  REMOVE MUSIC',
                 font=('Segoe UI',10,'bold'), bg=ACCENT, fg='#000',
                 relief='flat', bd=0, cursor='hand2', padx=20, pady=8,
                 command=self._run_music_removal)
        self.mr_go_btn.pack(side='left')
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
        self.censor_video_var = tk.StringVar()  # kept for compat

        # ── Video queue (multi-file, matches Music Removal layout) ────────────
        sec_vid = tk.Frame(top, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        sec_vid.pack(fill='x', padx=8, pady=(8,4))
        sec_inner = tk.Frame(sec_vid, bg=BG2); sec_inner.pack(fill='x', padx=12, pady=(8,4))

        q_hdr2 = tk.Frame(sec_inner, bg=BG2); q_hdr2.pack(fill='x', pady=(0,4))
        tk.Label(q_hdr2, text='Videos:', font=FONT_SMALL, fg=FG2, bg=BG2, width=8, anchor='w').pack(side='left')
        tk.Label(q_hdr2, text='paste paths or use Browse — one per line',
                 font=('Segoe UI',7), fg=FG2, bg=BG2).pack(side='left')

        qvf = tk.Frame(sec_inner, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        qvf.pack(fill='x', pady=(0,4))
        self.censor_queue_box = tk.Text(qvf, font=('Segoe UI', 7), bg=BG3, fg=FG,
                                        insertbackground=ACCENT, relief='flat', bd=4,
                                        wrap='none', height=4)
        _cqs = tk.Scrollbar(qvf, command=self.censor_queue_box.yview)
        _cqs.pack(side='right', fill='y')
        self.censor_queue_box.pack(fill='both', expand=True)
        self.censor_queue_box.config(yscrollcommand=_cqs.set)

        cqb = tk.Frame(sec_inner, bg=BG2); cqb.pack(fill='x', pady=(0,4))
        def _censor_browse_multi2():
            files = filedialog.askopenfilenames(
                title='Select videos to censor',
                filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm'),('All','*.*')])
            for f in files:
                cur = self.censor_queue_box.get('1.0','end').strip()
                if f not in cur:
                    self.censor_queue_box.insert('end', f'\n{f}' if cur else f)
            _censor_q_count()
        def _censor_add_clipfinder2():
            v = self.v_video.get().strip()
            if not v: return
            cur = self.censor_queue_box.get('1.0','end').strip()
            if v not in cur:
                self.censor_queue_box.insert('end', f'\n{v}' if cur else v)
            _censor_q_count()
        def _censor_q_count(*_):
            lines = [l.strip() for l in self.censor_queue_box.get('1.0','end').splitlines() if l.strip()]
            self._censor_set_status(f'{len(lines)} video(s) queued' if lines else 'Queue empty.')
        def _censor_clear_q2():
            self.censor_queue_box.delete('1.0','end')
            _censor_q_count()
        self.censor_queue_box.bind('<KeyRelease>', _censor_q_count)

        tk.Button(cqb, text='📂 Browse Multiple', font=FONT_SMALL,
                  bg=BG3, fg=FG, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_censor_browse_multi2).pack(side='left', padx=(0,4))
        tk.Button(cqb, text='📋 Use Clip Finder Video', font=FONT_SMALL,
                  bg=BG3, fg=ACCENT2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_censor_add_clipfinder2).pack(side='left', padx=(0,4))
        tk.Button(cqb, text='🗑 Clear', font=FONT_SMALL,
                  bg=BG3, fg=FG2, relief='flat', bd=0, cursor='hand2', padx=8, pady=3,
                  command=_censor_clear_q2).pack(side='left')

        # Output folder
        out_row2 = tk.Frame(sec_vid, bg=BG2); out_row2.pack(fill='x', padx=12, pady=(0,8))
        tk.Label(out_row2, text='Output:', font=FONT_SMALL, fg=FG2, bg=BG2, width=8, anchor='w').pack(side='left')
        of2 = tk.Frame(out_row2, bg=BG3); of2.pack(side='left', fill='x', expand=True)
        self.censor_out_var = tk.StringVar(value=self.cfg.get('censor_outdir', str(Path.home()/'Downloads')))
        tk.Entry(of2, textvariable=self.censor_out_var, font=FONT_SMALL,
                 bg=BG3, fg=FG, insertbackground=ACCENT, relief='flat', bd=4
                 ).pack(side='left', fill='x', expand=True)
        tk.Button(of2, text='📁', font=FONT_SMALL, bg=BG3, fg=FG2,
                  relief='flat', bd=0, cursor='hand2', padx=6,
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
        current = self.censor_queue_box.get('1.0','end').strip()
        if vid not in current:
            if current:
                self.censor_queue_box.insert('end', f'\n{vid}')
            else:
                self.censor_queue_box.insert('end', vid)
        lines = [l.strip() for l in self.censor_queue_box.get('1.0','end').splitlines() if l.strip()]
        self._censor_set_status(f'{len(lines)} video(s) in queue.')

    def _censor_clear_queue(self):
        self.censor_queue_box.delete('1.0','end')
        self._censor_set_status('Queue cleared.')

    def _censor_start(self):
        if self._censor_running: return
        # Read from queue box — same as run queue
        # strip surrounding quotes (Explorer "Copy as path" pastes quoted paths)
        lines = [l.strip().strip('"') for l in self.censor_queue_box.get('1.0','end').splitlines() if l.strip().strip('"')]
        _missing = [l for l in lines if not Path(l).exists()]
        if _missing:
            self.log(f'[Censor] ⚠️ Skipping {len(_missing)} path(s) that do not exist: {_missing}', YELLOW)
        videos = [l for l in lines if Path(l).exists()]
        if not videos:
            messagebox.showerror('No videos', 'Add at least one valid video to the queue.')
            return
        self._censor_save_words()
        self._censor_running = True
        self.censor_go_btn.config(state='disabled', text='⏳  Processing...')
        self._censor_set_status(f'Processing {len(videos)} video(s)...')
        threading.Thread(target=self._censor_run, args=(videos,), daemon=True).start()

    def _censor_run_queue(self):
        self._censor_start()  # unified — both buttons do the same thing now

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
            _fwc_cache = {}   # faster-whisper model reused across the queue
            _ok = 0; _clean = 0; _failed = []

            for vi, vid in enumerate(video_list):
                try:
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
                                  not self.censor_deep_var.get() and
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
                            _FW = _fresh_import('faster_whisper').WhisperModel  # fix: was _FWC (typo)
                            # Respect GPU toggle — same as main transcription
                            _cen_use_gpu = getattr(self, 'v_use_gpu_whisper', None)
                            _cen_use_gpu = _cen_use_gpu.get() if _cen_use_gpu else True
                            _cen_dev, _cen_compute, _cen_dev_label = _detect_whisper_device(use_gpu=_cen_use_gpu)
                            self.log(f'[Censor] Device: {_cen_dev_label}')
                            # Load the model once and reuse it for every queued video
                            _fwc_key = (_censor_model, _cen_dev, _cen_compute)
                            if _fwc_cache.get('key') != _fwc_key:
                                _fwc_cache.clear()
                                _fwc_cache['model'] = _FW(_censor_model, device=_cen_dev, compute_type=_cen_compute,
                                                          download_root=str(_app_path('whisper_models')))
                                _fwc_cache['key'] = _fwc_key
                            _fwc = _fwc_cache['model']
                            # Extract audio first
                            import tempfile as _tmpc
                            _fd_w, _wav_tmp = _tmpc.mkstemp(suffix='.wav', prefix='cf_censor_')
                            os.close(_fd_w)
                            try:
                                _rw = subprocess.run([ff, '-y', '-i', vid, '-vn', '-ar', '16000',
                                                     '-ac', '1', '-f', 'wav', _wav_tmp],
                                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                if _rw.returncode != 0:
                                    raise RuntimeError('ffmpeg audio extract failed: ' + (_rw.stderr or b'').decode(errors='replace')[-200:])
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
                            finally:
                                try: os.unlink(_wav_tmp)
                                except OSError: pass
                            self.log(f'[Censor] faster-whisper done: {len(_segs)} segs with word timestamps')
                        except Exception as _fwe:
                            _fwc_cache.clear()  # drop the model so a failed/CUDA-broken one is not reused
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

                        # Innocent words that merely contain a banned substring (spicy, cocktail, assess...)
                        _SAFE_START = ('spice','spicy','spici','susp','desp','ausp','consp','inspic','cockp','cockt','cockr','dickens','dickson','dickinson','assess','scunth')
                        _SAFE_ANY = ('peacock','hancock','woodcock','shuttlecock')
                        if (w_clean.startswith(_SAFE_START) or any(s in w_clean for s in _SAFE_ANY)) and \
                           not any(w_clean == ''.join(c for c in x.lower() if c.isalpha()) for x in banned_list):
                            return None

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
                        _clean += 1
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
                        _rx = subprocess.run([ff,'-y','-i',vid,'-vn','-ar','44100','-ac','2',
                                       '-f','wav',wav_in],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if _rx.returncode != 0:
                            raise RuntimeError('ffmpeg audio extract failed: ' + (_rx.stderr or b'').decode(errors='replace')[-200:])

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
                        if style == 'mp3' and bleep_mono is None:
                            self.log('[Censor] ⚠️ MP3 file missing/invalid — falling back to beep', YELLOW)
                            bleep_mono = self._censor_make_beep(sr)

                        # Apply censoring (patch in place; track max change only on patched slices)
                        audio_patched = audio
                        _maxdiff = 0.0
                        for start_t, end_t, word in hits:
                            s = int(start_t * sr)
                            e = int(end_t   * sr)
                            e = min(e, len(audio_patched))
                            if e <= s:
                                self.log(f'[Censor] ⚠️ Zero-length hit at {start_t:.2f}s, skipping')
                                continue
                            seg_len = e - s
                            self.log(f'[Censor] Censoring "{word}" samples {s}–{e} ({seg_len} samples)')
                            _orig = audio_patched[s:e].copy()
                            if style == 'silence':
                                audio_patched[s:e] = 0.0
                            elif bleep_mono is not None:
                                patch = _make_bleep_stereo(bleep_mono, seg_len, n_ch)
                                audio_patched[s:e] = patch
                            _maxdiff = max(_maxdiff, float(_np2.abs(audio_patched[s:e] - _orig).max()))

                        # Verify patch was applied
                        diff = _maxdiff
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
                            _ok += 1
                        else:
                            self.log(f'[Censor] ❌ Mux failed (rc={r.returncode}): {mux_err[-300:]}', RED)
                            _failed.append(vid_name)
                    finally:
                        import shutil as _sh
                        _sh.rmtree(tmp_dir, ignore_errors=True)
                except Exception as _ve:
                    _failed.append(vid_name)
                    self.log(f'[Censor] ❌ {vid_name} failed: {_ve}', RED)
                    self.log(traceback.format_exc(), RED)
                    continue

            _done = _ok + _clean
            if _failed:
                self._censor_set_status(f'Finished with errors: {len(_failed)} failed', RED)
                self.after(0, lambda d=_done, f=list(_failed): (
                    self.set_progress(f'⚠ {len(f)} video(s) failed', pct=100),
                    messagebox.showwarning('Censor finished',
                                           f'{d} ok, {len(f)} failed:\n' + '\n'.join(f))
                ))
            else:
                self._censor_set_status(f'Done! {_done} video(s) censored → {out}', GREEN)
                # Clear the queue only after a fully successful run (main thread)
                self.after(0, lambda t=_done, o=out: (
                    self.censor_queue_box.delete('1.0', 'end'),
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
            for prov in [p for p in dict.fromkeys([self.v_provider.get()] +
                         list(PROVIDERS.keys())) if self._keys.get(p,'').strip()]:
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
        n = sum(1 for w in self.censor_results_frame.winfo_children() if isinstance(w, tk.Frame))
        self.censor_result_lbl.config(text=f'{n} video(s) processed')

    # ═══════════════════════════════════════════════════════════════════════════
    # END CENSOR TAB
    # ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    def _self_restart(reason=''):
        """Start a fresh copy of ClipFinder and exit this one (used after updates)."""
        import subprocess as _sp_rs, os as _os_rs
        if _os_rs.environ.get('CF_RESTARTED'):                   # never loop
            return False
        try:
            um_release_instance_lock()                          # the new process must be able to take it
            env = dict(_os_rs.environ, CF_RESTARTED='1')
            _sp_rs.Popen(app_relaunch_cmd(__file__), env=env, close_fds=True,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            um_log(f'restarting ClipFinder ({reason})')
            return True
        except Exception as _e:
            um_log(f'restart failed: {_e}')
            return False

    def _prelaunch_install():
        """Install required packages that are missing or outside their allowed version range.

        Shows a small progress window ONLY when there is something to do, so a normal launch has no
        delay at all. It installs only what is needed (the old version wiped and re-downloaded every
        package - including multi-GB torch - after each app update, aborted the whole batch when a
        single pip call timed out, hid pip's errors, and wrote its "done" stamp even on failure)."""
        import threading as _thr, queue as _q, time as _t
        _legacy = USER_DIR / 'pending_update.flag'               # written by older builds of the Update buttons
        try:
            if _legacy.exists():
                _legacy.unlink()
        except Exception:
            pass
        _entries = pm_sync_needs()
        if not _entries or pm_sync_should_skip():
            return False
        try:
            import tkinter as _tk2, tkinter.ttk as _ttk2
            _s = _tk2.Tk()
            _s.title('ClipFinder - updating components')
            _s.configure(bg='#111111')
            _s.resizable(False, False)
            _s.attributes('-topmost', True)
            _sw, _sh = 580, 200
            _s.geometry(f'{_sw}x{_sh}+{(_s.winfo_screenwidth() - _sw) // 2}+{(_s.winfo_screenheight() - _sh) // 2}')
            _brd = _tk2.Frame(_s, bg='#ff8c00', padx=1, pady=1); _brd.pack(fill='both', expand=True, padx=8, pady=8)
            _inn = _tk2.Frame(_brd, bg='#111111'); _inn.pack(fill='both', expand=True)
            _tk2.Label(_inn, text='\u2702  ClipFinder', font=('Segoe UI', 13, 'bold'), fg='#ff8c00', bg='#111111').pack(pady=(10, 0))
            _sv = _tk2.StringVar(value=f'Installing {len(_entries)} component{"s" if len(_entries) != 1 else ""}...')
            _tk2.Label(_inn, textvariable=_sv, font=('Segoe UI', 9, 'bold'), fg='#dddddd', bg='#111111').pack()
            _tk2.Label(_inn, text=', '.join(e['name'] for e in _entries)[:90], font=('Segoe UI', 8), fg='#888888', bg='#111111').pack()
            _pb = _ttk2.Progressbar(_inn, length=480, mode='indeterminate'); _pb.pack(pady=(8, 2)); _pb.start(15)
            _dv = _tk2.StringVar(value='Starting...')
            _tk2.Label(_inn, textvariable=_dv, font=('Consolas', 7), fg='#666666', bg='#111111').pack()
            _cancel = _thr.Event()
            _tk2.Button(_inn, text='Skip - start ClipFinder anyway', font=('Segoe UI', 8), bg='#222222', fg='#aaaaaa',
                        relief='flat', bd=0, padx=10, pady=3, cursor='hand2', command=_cancel.set).pack(pady=(6, 4))
            _s.update()
            _lines, _res = _q.Queue(), {}
            _w = _thr.Thread(target=lambda: _res.update(r=pm_startup_sync(_entries, status_cb=_lines.put, cancel=_cancel)), daemon=True)
            _w.start()
            _t0 = _t.time()
            while _w.is_alive():
                try:
                    while True:
                        _dv.set(str(_lines.get_nowait())[:96])
                except _q.Empty:
                    pass
                _s.update()
                _t.sleep(0.05)
                if _t.time() - _t0 > 45 * 60:                    # never hold the user hostage
                    _cancel.set()
            _r = _res.get('r') or {}
            _pb.stop()
            if _r.get('failed') and not _cancel.is_set():
                _sv.set('Some components could not be installed - ClipFinder will start anyway')
                _dv.set('; '.join(f'{n}: {why}' for n, why in _r['failed'])[:140])
                _pb['mode'] = 'determinate'; _pb['value'] = 100
                _s.update(); _t.sleep(3.5)
            else:
                _sv.set('Done')
                _s.update(); _t.sleep(0.4)
            _s.destroy()
            return bool(_r.get('restart'))
        except Exception as _e:
            um_log(f'pre-launch installer error: {_e}')
            return False

    # A self-update that could not start twice in a row is rolled back automatically.
    if app_startup_guard() == 'rolled_back':
        if _self_restart('rolled back a failed update'):
            sys.exit(0)

    # Install anything required that is missing. If a package that is already loaded in this process was
    # replaced, start again so everything imports cleanly from the new files.
    if _prelaunch_install():
        if _self_restart('components updated'):
            sys.exit(0)

    # -- Bootstrap default reference images (background) ----------------------
    _vr_dir = USER_DIR / 'vision_refs'
    _vr_dir.mkdir(parents=True, exist_ok=True)
    _ref_urls = {
        'stake_casino.png':   'https://raw.githubusercontent.com/thatspeedykid/clipfinder/main/vision_refs/stake_casino.png',
        'roobet_casino.png':  'https://raw.githubusercontent.com/thatspeedykid/clipfinder/main/vision_refs/roobet_casino.png',
        'rainbet_casino.png': 'https://raw.githubusercontent.com/thatspeedykid/clipfinder/main/vision_refs/rainbet_casino.png',
    }
    import threading as _ref_thr
    def _dl_default_refs():
        for _rn, _ru in _ref_urls.items():
            if not (_vr_dir / _rn).exists():
                try:
                    _um_download(_ru, _vr_dir / _rn, timeout=20)
                    print(f'[CF] Downloaded reference image: {_rn}')
                except Exception:
                    pass
    _ref_thr.Thread(target=_dl_default_refs, daemon=True).start()

    app = App()
    app.mainloop()
