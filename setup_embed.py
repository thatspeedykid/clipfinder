"""Downloads and configures the Python 3.12 embeddable package + copies tkinter into it.

The embeddable zip version is taken from the interpreter that RUNS this script - the same
interpreter tkinter and all DLLs\\*.pyd are copied from - so the embedded python312.dll and the
extension modules transplanted onto it can never be different patch releases (they used to be:
embed 3.12.7 + DLLs from the runner's 3.12.10).

python.org publishes Windows embeddable zips only up to 3.12.10 (PEP 693): 3.12.11+ are
source-only releases, so 3.12.10 is the newest embed that can exist for 3.12.
"""
import hashlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    sys.exit(f'ERROR: setup_embed.py must run under Python 3.12 (this is {sys.version.split()[0]}); '
             'the embedded python312.dll and the copied extension modules must match.')

HERE = Path(__file__).parent.resolve()
dest_zip = HERE / 'ClipFinder_dist' / '_py_embed.zip'
dest_dir = HERE / 'ClipFinder_dist' / 'python'

PY_VER = '.'.join(str(x) for x in sys.version_info[:3])          # e.g. 3.12.10
url = f'https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip'
# md5 published by python.org: https://www.python.org/api/v2/downloads/release_file/?release=1007
KNOWN_MD5 = {'3.12.10': 'fe8ef205f2e9c3ba44d0cf9954e1abd3'}


def download(u, dest, tries=4, timeout=60):
    """urlretrieve has no timeout (a stalled socket hangs until the job timeout) and no retry."""
    last = None
    for n in range(1, tries + 1):
        try:
            with urllib.request.urlopen(u, timeout=timeout) as r, open(dest, 'wb') as f:
                shutil.copyfileobj(r, f)
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sys.exit(f'  ERROR: {u} does not exist. python.org has no Windows embeddable zip for '
                         f'{PY_VER} (3.12.10 was the last 3.12 with binaries). Run this with Python 3.12.10.')
            last = e
        except Exception as e:                          # noqa: BLE001 - network errors are all retryable
            last = e
        print(f'  download attempt {n}/{tries} failed: {last}')
        time.sleep(3 * n)
    sys.exit(f'  ERROR: could not download {u}: {last}')


print(f'  Downloading Python {PY_VER} embeddable (~11MB)...')
download(url, dest_zip)
got = hashlib.md5(dest_zip.read_bytes(), usedforsecurity=False).hexdigest()
want = KNOWN_MD5.get(PY_VER)
if want and got != want:
    sys.exit(f'  ERROR: md5 mismatch for {url}: got {got}, expected {want}')
if not want:
    print(f'  WARNING: no pinned checksum for {PY_VER} (md5 {got}) - add it to KNOWN_MD5')
print('  Extracting...')
with zipfile.ZipFile(dest_zip) as z:
    z.extractall(dest_dir)
dest_zip.unlink()

# Enable site-packages
for pth in dest_dir.glob('python*._pth'):
    txt = pth.read_text().replace('#import site', 'import site')
    pth.write_text(txt)
    print(f'  Enabled site-packages in {pth.name}')

# -- Copy tkinter from THIS interpreter's installation (same version as the embed, see PY_VER) --
# sys.base_prefix (not sys.prefix) so it is also right when run from inside a venv.
src = Path(sys.base_prefix)
print(f'  Copying tkinter from {src}...')
if not (src / 'Lib' / 'tkinter').is_dir() or not (src / 'DLLs' / '_tkinter.pyd').is_file():
    sys.exit(f'  ERROR: {src} has no tkinter (Lib\\tkinter / DLLs\\_tkinter.pyd) - install Python with tcl/tk')

# Copy ALL DLLs (tkinter needs _tkinter.pyd + tcl/tk dlls + dependencies)
for f in (src / 'DLLs').iterdir():
    if f.suffix.lower() in ('.pyd', '.dll'):
        try:
            shutil.copy2(f, dest_dir / f.name)
        except OSError as e:
            print(f'  WARNING: could not copy {f.name}: {e}')   # a missing one is caught by the import check below

# Copy tkinter package
lib_dst = dest_dir / 'Lib'
lib_dst.mkdir(exist_ok=True)
tk_dst = lib_dst / 'tkinter'
if tk_dst.exists():
    shutil.rmtree(tk_dst)
shutil.copytree(src / 'Lib' / 'tkinter', tk_dst)
print('  Copied tkinter package')

# Copy tcl/tk data dirs
for d in src.iterdir():
    if d.is_dir() and any(d.name.lower().startswith(x) for x in ('tcl', 'tk')):
        dst = dest_dir / d.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(d, dst)
        print(f'  Copied {d.name}/')

# Update ._pth to include DLLs and Lib paths
for pth in dest_dir.glob('python*._pth'):
    txt = pth.read_text()
    for entry in ['DLLs', 'Lib', 'Lib\\site-packages']:
        if entry not in txt:
            txt += f'\n{entry}'
    pth.write_text(txt)
    print(f'  Updated {pth.name}')

# Verify: the C extension must at least load (fatal). Creating a Tk window needs a desktop, so that stays a warning.
r1 = subprocess.run([str(dest_dir / 'python.exe'), '-c',
                     'import _tkinter, tkinter; print("_tkinter OK", _tkinter.TK_VERSION)'],
                    capture_output=True, text=True)
if r1.returncode != 0:
    sys.exit(f'  ERROR: embedded python cannot import _tkinter: {r1.stderr.strip()[:300]}')
print(f'  {r1.stdout.strip()}')
r2 = subprocess.run(
    [str(dest_dir / 'python.exe'), '-c',
     'import tkinter; root=tkinter.Tk(); root.destroy(); print("tkinter OK")'],
    capture_output=True, text=True)
if r2.returncode == 0:
    print(f'  {r2.stdout.strip()}')
else:
    print(f'  WARNING: {r2.stderr.strip()[:200]}')

print('  Embedded Python ready.')
