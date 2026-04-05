"""Downloads and configures Python 3.12 embeddable package + copies tkinter."""
import urllib.request, zipfile, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
dest_zip = HERE / 'ClipFinder_dist' / '_py_embed.zip'
dest_dir = HERE / 'ClipFinder_dist' / 'python'

url = 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip'
print('  Downloading Python 3.12 embeddable (~15MB)...')
urllib.request.urlretrieve(url, dest_zip)
print('  Extracting...')
zipfile.ZipFile(dest_zip).extractall(dest_dir)
dest_zip.unlink()

# Enable site-packages
for pth in dest_dir.glob('python*._pth'):
    txt = pth.read_text().replace('#import site', 'import site')
    pth.write_text(txt)
    print(f'  Enabled site-packages in {pth.name}')

# ── Copy tkinter from system Python 3.12 ─────────────────────────────────────
r = subprocess.run(['py', '-3.12', '-c', 'import sys; print(sys.prefix)'],
                   capture_output=True, text=True)
if r.returncode != 0:
    print('  ERROR: Cannot find Python 3.12'); sys.exit(1)

src = Path(r.stdout.strip())
print(f'  Copying tkinter from {src}...')

# Copy ALL DLLs (tkinter needs _tkinter.pyd + tcl/tk dlls + dependencies)
for f in (src / 'DLLs').iterdir():
    if f.suffix.lower() in ('.pyd', '.dll'):
        try: shutil.copy2(f, dest_dir / f.name)
        except: pass

# Copy tkinter package
lib_dst = dest_dir / 'Lib'
lib_dst.mkdir(exist_ok=True)
tk_dst = lib_dst / 'tkinter'
if tk_dst.exists(): shutil.rmtree(tk_dst)
shutil.copytree(src / 'Lib' / 'tkinter', tk_dst)
print('  Copied tkinter package')

# Copy tcl/tk data dirs
for d in src.iterdir():
    if d.is_dir() and any(d.name.lower().startswith(x) for x in ('tcl', 'tk')):
        dst = dest_dir / d.name
        if dst.exists(): shutil.rmtree(dst)
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

# Verify tkinter works
r2 = subprocess.run(
    [str(dest_dir / 'python.exe'), '-c',
     'import tkinter; root=tkinter.Tk(); root.destroy(); print("tkinter OK")'],
    capture_output=True, text=True)
if r2.returncode == 0:
    print(f'  {r2.stdout.strip()}')
else:
    print(f'  WARNING: {r2.stderr.strip()[:200]}')

print('  Embedded Python ready.')
