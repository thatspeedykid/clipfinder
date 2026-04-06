"""Builds a tiny launcher EXE — no console window, launches clipfinder.py silently."""
import subprocess, sys, os
from pathlib import Path

stub = '''\
import subprocess, sys, os, ctypes
app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(app_dir)
py = os.path.join(app_dir, 'python', 'python.exe')
# Launch with no console window (CREATE_NO_WINDOW = 0x08000000)
subprocess.Popen([py, os.path.join(app_dir, 'clipfinder.py')],
                 creationflags=0x08000000)
'''

with open('_launcher_stub.py', 'w') as f:
    f.write(stub)

ico = str(Path('clipfinder.ico').resolve()) if Path('clipfinder.ico').exists() else None

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '_launcher_stub.py',
    '--onefile', '--noconsole',
    '--name', 'ClipFinder',
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
if os.path.exists('_launcher_build'): shutil.rmtree('_launcher_build')
sys.exit(r.returncode)
