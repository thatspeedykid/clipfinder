"""
ClipFinder — Distribution Builder
Builds ClipFinder_dist/ with embedded Python + all packages.
Run: py -3.12 setup_build.py
"""
import urllib.request, zipfile, subprocess, sys, shutil, os, glob
from pathlib import Path

HERE    = Path(__file__).parent.resolve()
DIST    = HERE / 'ClipFinder_dist'
PYTHON  = DIST / 'python'
SCRIPTS = PYTHON / 'Scripts'

def step(n, msg):
    print(f'\n[{n}] {msg}')

def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print(f'ERROR: {cmd[0]} exited {r.returncode}')
        sys.exit(1)
    return r

# ── Clean ─────────────────────────────────────────────────────────────────────
step(1, 'Cleaning ClipFinder_dist/')
if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir()
PYTHON.mkdir()

# ── Download embedded Python 3.12 ─────────────────────────────────────────────
step(2, 'Downloading Python 3.12 embeddable (~15MB)...')
url  = 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip'
zp   = DIST / '_embed.zip'
urllib.request.urlretrieve(url, zp)
zipfile.ZipFile(zp).extractall(PYTHON)
zp.unlink()
print('  Extracted.')

# Verify pythonw.exe exists (no-console Python launcher)
pythonw = PYTHON / 'pythonw.exe'
if not pythonw.exists():
    # Copy python.exe as pythonw.exe if missing
    import shutil as _sh
    _sh.copy2(PYTHON / 'python.exe', pythonw)
    print('  Created pythonw.exe from python.exe')
else:
    print('  pythonw.exe OK')

# Enable site-packages
for pth in PYTHON.glob('python*._pth'):
    txt = pth.read_text().replace('#import site', 'import site')
    # Also add Lib and DLLs explicitly
    for entry in ['DLLs', 'Lib', 'Lib\\site-packages']:
        if entry not in txt:
            txt += f'\n{entry}'
    pth.write_text(txt)
    print(f'  Updated {pth.name}')

# ── Get pip ────────────────────────────────────────────────────────────────────
step(3, 'Installing pip into embedded Python...')
pip_script = DIST / '_getpip.py'
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', pip_script)
run([str(PYTHON / 'python.exe'), str(pip_script), '--quiet'])
pip_script.unlink()
print('  pip ready.')

# Install setuptools + wheel first — required for building some packages from source
print('  Installing setuptools + wheel...')
subprocess.run([str(PYTHON / 'python.exe'), '-m', 'pip', 'install',
                'setuptools', 'wheel', '--quiet', '--upgrade'], check=False)
print('  setuptools ready.')

# ── Copy tkinter from system Python 3.12 ──────────────────────────────────────
step(4, 'Copying tkinter from system Python 3.12...')
r = subprocess.run(['py', '-3.12', '-c', 'import sys; print(sys.prefix)'],
                   capture_output=True, text=True)
src = Path(r.stdout.strip())
print(f'  Source: {src}')

# All DLLs (tkinter needs _tkinter.pyd + tcl/tk dlls)
for f in (src / 'DLLs').iterdir():
    if f.suffix.lower() in ('.pyd', '.dll'):
        try: shutil.copy2(f, PYTHON / f.name)
        except: pass

# tkinter package
lib_dst = PYTHON / 'Lib'
lib_dst.mkdir(exist_ok=True)
tk_dst = lib_dst / 'tkinter'
if tk_dst.exists(): shutil.rmtree(tk_dst)
shutil.copytree(src / 'Lib' / 'tkinter', tk_dst)
print('  Copied tkinter package.')

# tcl/tk data dirs (init.tcl lives here)
for d in src.iterdir():
    if d.is_dir() and any(d.name.lower().startswith(x) for x in ('tcl', 'tk')):
        dst = PYTHON / d.name
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(d, dst)
        print(f'  Copied {d.name}/')

# Verify tkinter works
r2 = subprocess.run(
    [str(PYTHON / 'python.exe'), '-c',
     'import tkinter; r=tkinter.Tk(); r.destroy(); print("tkinter OK")'],
    capture_output=True, text=True)
if 'OK' in r2.stdout:
    print(f'  {r2.stdout.strip()}')
else:
    print(f'  WARNING: {r2.stderr.strip()[:200]}')

# ── Install all packages ───────────────────────────────────────────────────────
step(5, 'Installing all packages (10-20 min first time)...')
PY  = str(PYTHON / 'python.exe')
PIP = [PY, '-m', 'pip', 'install', '--quiet', '--upgrade',
       '--no-warn-script-location']

pkgs = [
    ('AI providers',   ['google-genai', 'groq', 'openai', 'requests']),
    ('Downloader',     ['yt-dlp', 'curl-cffi']),
    ('Numeric base',   ['numpy', 'scipy']),
    ('Image/audio',    ['Pillow', 'soundfile', 'imagehash']),
    ('Video',          ['opencv-python']),
    ('Whisper',        ['faster-whisper', 'openai-whisper']),
    ('Face tracking',  ['mediapipe']),
]

PIP_BASE = [PY, '-m', 'pip', 'install', '--quiet', '--upgrade', '--no-warn-script-location']

for label, args in pkgs:
    print(f'  {label}...')
    r = subprocess.run(PIP_BASE + args)
    if r.returncode != 0:
        print(f'  WARNING: {label} had errors (may still work)')

# ── Copy app files ─────────────────────────────────────────────────────────────
step(6, 'Copying app files...')
shutil.copy2(HERE / 'clipfinder.py',   DIST / 'clipfinder.py')
if (HERE / 'clipfinder.ico').exists():
    shutil.copy2(HERE / 'clipfinder.ico', DIST / 'clipfinder.ico')
print('  Done.')

# ── Verify ────────────────────────────────────────────────────────────────────
step(7, 'Verifying key packages...')
checks = [
    ('numpy',          'import numpy; print("numpy", numpy.__version__)'),
    ('faster-whisper', 'import faster_whisper; print("faster-whisper OK")'),
    ('cv2',            'import cv2; print("opencv", cv2.__version__)'),
    ('groq',           'import groq; print("groq OK")'),
    ('google-genai',   'from google import genai; print("gemini OK")'),
]
for name, code in checks:
    r = subprocess.run([PY, '-c', code], capture_output=True, text=True)
    status = r.stdout.strip() if r.returncode == 0 else f'FAIL: {r.stderr.strip()[:80]}'
    print(f'  {"OK" if r.returncode==0 else "!!"} {name}: {status}')

# ── Done ──────────────────────────────────────────────────────────────────────
print('\n' + '='*50)
print('  ClipFinder_dist/ is ready.')
print()
print('  To test: double-click ClipFinder_dist/python/python.exe')
print('           then run clipfinder.py')
print()
print('  To build installer: run make_installer.bat')
print('='*50)
