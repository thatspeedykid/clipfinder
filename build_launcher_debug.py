"""Builds DEBUG launcher — shows console so we can see what's failing."""
import subprocess, sys, os
from pathlib import Path

stub = (
    'import subprocess, sys, os, ctypes\n'
    'from pathlib import Path\n'
    '\n'
    'try:\n'
    '    buf = ctypes.create_unicode_buffer(32768)\n'
    '    ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 32768)\n'
    '    app_dir = Path(buf.value).parent\n'
    'except Exception as e:\n'
    '    print("GetModuleFileNameW failed:", e)\n'
    '    app_dir = Path(sys.executable).parent\n'
    '\n'
    'print("app_dir:", app_dir)\n'
    'print("sys.executable:", sys.executable)\n'
    '\n'
    'py     = app_dir / "python" / "python.exe"\n'
    'script = app_dir / "clipfinder.py"\n'
    '\n'
    'print("python.exe:", py, "exists:", py.exists())\n'
    'print("clipfinder.py:", script, "exists:", script.exists())\n'
    '\n'
    'if not py.exists() or not script.exists():\n'
    '    print("MISSING FILES — cannot launch")\n'
    '    input("Press Enter to exit...")\n'
    '    raise SystemExit(1)\n'
    '\n'
    'print("Launching:", py, script)\n'
    'os.chdir(str(app_dir))\n'
    'result = subprocess.run([str(py), str(script)], cwd=str(app_dir))\n'
    'print("Exit code:", result.returncode)\n'
    'input("Press Enter to exit...")\n'
)

with open('_launcher_stub.py', 'w', encoding='utf-8') as f:
    f.write(stub)

ico = str(Path('clipfinder.ico').resolve()) if Path('clipfinder.ico').exists() else None

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '_launcher_stub.py',
    '--onefile',
    '--console',  # show console so we see output
    '--name', 'ClipFinder_debug',
    '--distpath', 'ClipFinder_dist',
    '--workpath', '_launcher_build',
    '--specpath', '_launcher_build',
    '--noconfirm', '--clean', '--log-level', 'WARN',
]
if ico:
    cmd += ['--icon', ico]

r = subprocess.run(cmd)
os.remove('_launcher_stub.py')
import shutil
if os.path.exists('_launcher_build'):
    shutil.rmtree('_launcher_build')
sys.exit(r.returncode)
