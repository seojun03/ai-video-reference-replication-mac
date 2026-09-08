#!/usr/bin/env python3
"""Build a portable local marketplace ZIP. No network or credentials."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

NAME = 'ai-video-reference-replication'
MARKETPLACE = 'video-reference-shared'
ROOT = Path(__file__).resolve().parents[1]

INSTALL = '''#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "package-files.json").read_text(encoding="utf-8"))
import hashlib
for relative, expected in manifest.items():
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("Package integrity failed: " + relative)
import sys
subprocess.run([sys.executable, str(root / "plugins/ai-video-reference-replication/scripts/managed_updater.py"), "--install"], check=True)
'''


def collect(root=ROOT):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are forbidden in the shared payload: ' + str(path))
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(x in {'.git', '__pycache__', '.DS_Store', '.env'} for x in relative.parts) or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.suffix in {'.pem', '.key'} or path.name.startswith('.env.'):
            raise ValueError('Credential-like file is forbidden: ' + str(relative))
        result['plugins/' + NAME + '/' + relative.as_posix()] = path.read_bytes()
    return result


def build(output=None):
    version = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())['version']
    target_dir = output or Path.home() / 'plugins/exports' / NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (NAME + '-' + version + '.zip')
    files = collect()
    files['.agents/plugins/marketplace.json'] = (json.dumps({
        'name': MARKETPLACE, 'interface': {'displayName': '영상 생성 자동화'},
        'plugins': [{'name': NAME, 'source': {'source': 'local', 'path': './plugins/' + NAME},
                     'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]
    }, ensure_ascii=False, indent=2) + '\n').encode()
    files['install.py'] = INSTALL.encode()
    files['INSTALL-MAC.command'] = b'#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\npython3 install.py\n'
    files['READ-ME.txt'] = 'Mac: 압축을 풀고 INSTALL-MAC.command를 실행하세요. Python 3와 Codex CLI가 필요합니다. 설치기는 검증된 최신 GitHub 릴리스를 전용 폴더에 설치하고 로그인할 때와 6시간마다 자동 업데이트합니다. Codex에서 새 작업을 시작하면 갱신된 버전을 사용합니다. 업체 자료와 계정은 별도로 연결합니다.\n'.encode()
    files['package-files.json'] = (json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}, ensure_ascii=False, indent=2) + '\n').encode()
    with tempfile.NamedTemporaryFile(dir=target_dir, suffix='.zip', delete=False) as temporary:
        temp_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
                archive.writestr(info, data)
        if target.exists() and target.read_bytes() != temp_path.read_bytes():
            raise ValueError('Content changed without a version refresh; refusing to overwrite ' + str(target))
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n')
    return {'path': str(target), 'sha256': digest, 'files': len(files), 'version': version}


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
