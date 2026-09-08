#!/usr/bin/env python3
"""Install only plugin Python dependencies in an isolated recipient venv."""
import os
from pathlib import Path
import subprocess
import sys
import venv

if sys.platform != 'darwin':
    raise SystemExit('This runtime setup currently supports macOS only.')
root = Path(__file__).resolve().parents[1]
environment = Path.home() / '.local/share/ai-video-reference-replication/venv'
if not environment.exists():
    venv.EnvBuilder(with_pip=True).create(environment)
python = environment / 'bin/python'
if not python.is_file():
    raise SystemExit('Existing runtime is incomplete; no files were removed: ' + str(environment))
subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
subprocess.run([str(python), str(root / 'scripts/doctor.py')], check=True)
print('Runtime ready: ' + str(python))
