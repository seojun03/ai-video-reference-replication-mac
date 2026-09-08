#!/usr/bin/env python3
"""Read-only recipient preflight. Never reads credential values."""
import importlib.util
import json
import os
import platform
import shutil
from pathlib import Path


def report():
    root = Path(__file__).resolve().parents[1]
    engine = Path(os.environ.get('CAPCUT_AUTOMATION_ROOT', str(Path.home() / 'Documents' / '서준 AI' / '캡컷 자동화'))).expanduser()
    return {
        'plugin': 'ai-video-reference-replication',
        'version': json.loads((root / '.codex-plugin/plugin.json').read_text())['version'],
        'platform': platform.system(),
        'commands': {name: bool(shutil.which(name)) for name in ('codex', 'ffmpeg', 'ffprobe')},
        'pillow': importlib.util.find_spec('PIL') is not None,
        'productLibraryExists': Path(os.environ.get('VIDEO_PRODUCT_LIBRARY_ROOT', str(Path.home() / 'Documents' / '인코어'))).expanduser().is_dir(),
        'capcutSemanticPlatformSupported': platform.system() == 'Darwin',
        'optionalCapcutEngineFound': (engine / 'scripts/build_edit_run_context.py').is_file() and (engine / '.venv/bin/python').is_file(),
        'bundledSkills': sorted(p.name for p in (root / 'skills').iterdir() if (p / 'SKILL.md').is_file()),
        'serviceConnectionStatus': 'Check built-in image_gen, Higgsfield and selected TTS service in the current Codex task; not verified by this local check.',
    }


if __name__ == '__main__':
    print(json.dumps(report(), ensure_ascii=False, indent=2))
