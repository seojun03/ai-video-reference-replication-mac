#!/usr/bin/env python3
"""Release-only macOS plugin updater; staged validation, locking and rollback."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

NAME = 'ai-video-reference-replication'
MARKETPLACE = 'video-reference-shared'
REPOSITORY = 'seojun03/ai-video-reference-replication-mac'
ASSET = NAME + '-plugin.zip'
LABEL = 'com.incore.video-reference-plugin-update'
MAX_DOWNLOAD = 25 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
DEFAULT_ROOT = Path.home() / 'Library/Application Support/IncoreVideoPlugin'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(payload)
    os.replace(temp, path)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def fetch(url, limit=MAX_DOWNLOAD):
    if not url.startswith(('https://api.github.com/repos/' + REPOSITORY + '/', 'https://github.com/' + REPOSITORY + '/releases/')):
        raise ValueError('Unexpected release URL')
    request = urllib.request.Request(url, headers={'User-Agent': NAME + '-updater', 'Accept': 'application/vnd.github+json' if 'api.github.com' in url else 'application/octet-stream'})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError('Release asset exceeds size limit')
    return payload


def latest_release():
    data = json.loads(fetch('https://api.github.com/repos/' + REPOSITORY + '/releases/latest', 2 * 1024 * 1024))
    if data.get('draft') or data.get('prerelease') or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+-codex\.[0-9]{14}', data.get('tag_name', '')):
        raise ValueError('Invalid stable release')
    assets = {asset['name']: asset for asset in data.get('assets', [])}
    for name in (ASSET, ASSET + '.sha256'):
        if name not in assets:
            raise ValueError('Incomplete release: ' + name)
        url = assets[name]['browser_download_url']
        if not url.startswith('https://github.com/' + REPOSITORY + '/releases/download/' + data['tag_name'] + '/'):
            raise ValueError('Release assets must belong to the same immutable tag')
    return data['tag_name'], assets


def verify_payload(root):
    root = Path(root)
    hashes = read_json(root / 'package-files.json')
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('Missing payload hashes')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(hashes) | {'package-files.json'}:
        raise ValueError('Unlisted or missing payload file')
    for name, digest in hashes.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Unsafe payload path')
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Payload hash mismatch: ' + name)
    manifest = read_json(root / 'plugins' / NAME / '.codex-plugin/plugin.json')
    marketplace = read_json(root / '.agents/plugins/marketplace.json')
    if manifest.get('name') != NAME or not re.fullmatch(r'\d+\.\d+\.\d+\+codex\.\d{14}', manifest.get('version', '')):
        raise ValueError('Unexpected plugin identity or version')
    if marketplace.get('name') != MARKETPLACE or len(marketplace.get('plugins', [])) != 1:
        raise ValueError('Unexpected marketplace')
    entry = marketplace['plugins'][0]
    if entry.get('name') != NAME or entry.get('source') != {'source': 'local', 'path': './plugins/' + NAME}:
        raise ValueError('Unexpected plugin source')
    return manifest['version']


def extract_verified(archive, checksum, destination):
    if hashlib.sha256(archive).hexdigest() != checksum:
        raise ValueError('Release ZIP checksum mismatch')
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(archive)) as bundle:
        entries = bundle.infolist()
        if sum(i.file_size for i in entries) > MAX_EXPANDED or len(entries) > 5000:
            raise ValueError('Expanded archive exceeds limit')
        seen = set()
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if relative.is_absolute() or '..' in relative.parts or '\\' in entry.filename or relative.parts[0] != NAME or stat.S_ISLNK(mode):
                raise ValueError('Unsafe ZIP entry')
            if entry.filename in seen:
                raise ValueError('Duplicate ZIP entry')
            seen.add(entry.filename)
        bundle.extractall(destination)
    root = Path(destination) / NAME
    version = verify_payload(root)
    return root, version


def command(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True, timeout=120)


def find_codex():
    choices = [shutil.which('codex'), '/opt/homebrew/bin/codex', '/usr/local/bin/codex', str(Path.home() / '.local/bin/codex'), '/Applications/Codex.app/Contents/Resources/codex']
    choices.extend(str(p) for p in (Path.home() / '.nvm/versions/node').glob('*/bin/codex'))
    for candidate in dict.fromkeys(x for x in choices if x):
        try:
            command([candidate, 'plugin', '--help'])
            return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    raise RuntimeError('Codex CLI를 찾지 못했습니다. Codex에서 CLI를 설치한 뒤 설치 파일을 다시 실행해주세요.')


def previous_source(cli):
    values = json.loads(command([cli, 'plugin', 'marketplace', 'list', '--json']).stdout)
    for item in values.get('marketplaces', []):
        if item.get('name') == MARKETPLACE:
            source = item.get('marketplaceSource', {})
            if source.get('sourceType', 'local') != 'local':
                raise ValueError('Existing marketplace has a non-local source')
            root = Path(item['root'])
            if not root.is_dir():
                raise ValueError('Previous marketplace is missing; refusing to replace it')
            return root
    return None


def switch_marketplace(cli, root):
    previous = previous_source(cli)
    if previous is not None and previous.resolve() != Path(root).resolve():
        # The CLI cannot replace a source with add alone. Only the source registration
        # changes here; activate retains the old folder and restores it on any failure.
        command([cli, 'plugin', 'marketplace', 'remove', MARKETPLACE])
    command([cli, 'plugin', 'marketplace', 'add', root])


def register(cli, root, version):
    switch_marketplace(cli, root)
    command([cli, 'plugin', 'add', NAME + '@' + MARKETPLACE])
    result = json.loads(command([cli, 'plugin', 'list', '--marketplace', MARKETPLACE, '--json']).stdout)
    match = [p for p in result.get('installed', []) if p.get('pluginId') == NAME + '@' + MARKETPLACE]
    expected = (Path(root) / 'plugins' / NAME).resolve()
    if len(match) != 1 or match[0].get('version') != version or not match[0].get('enabled') or Path(match[0].get('source', {}).get('path', '')).resolve() != expected:
        raise ValueError('Installed version/source verification failed')


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'update.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def activate(root, staged, version, tag, cli, checksum):
    old_source = previous_source(cli)
    old_version = None
    if old_source:
        old_version = read_json(old_source / 'plugins' / NAME / '.codex-plugin/plugin.json')['version']
    destination = root / 'versions' / version
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if verify_payload(destination) != version or read_json(destination / 'package-files.json') != read_json(staged / 'package-files.json'):
            raise ValueError('Version already exists with different content')
    else:
        shutil.move(str(staged), destination)
    previous_files = {name: (root / name).read_bytes() if (root / name).is_file() else None for name in ('update.py', 'state.json')}
    try:
        register(cli, destination, version)
        updater = destination / 'plugins' / NAME / 'scripts/managed_updater.py'
        atomic_bytes(root / 'update.py', updater.read_bytes())
        write_json(root / 'state.json', {'version': version, 'tag': tag, 'sha256': checksum, 'activeRoot': str(destination), 'previousRoot': str(old_source) if old_source else None})
    except Exception as original:
        try:
            for name, payload in previous_files.items():
                if payload is None:
                    (root / name).unlink(missing_ok=True)
                else:
                    atomic_bytes(root / name, payload)
            if old_source:
                register(cli, old_source, old_version)
            else:
                command([cli, 'plugin', 'remove', NAME + '@' + MARKETPLACE])
                command([cli, 'plugin', 'marketplace', 'remove', MARKETPLACE])
        except Exception as recovery:
            raise RuntimeError('Update failed; rollback also failed: ' + str(recovery)) from original
        raise RuntimeError('Update failed; previous marketplace and plugin restored') from original
    return {'status': 'updated', 'version': version}


def update(root=DEFAULT_ROOT, cli=None):
    root = Path(root)
    with locked(root) as acquired:
        if not acquired:
            return {'status': 'already_running'}
        tag, assets = latest_release()
        state = read_json(root / 'state.json') if (root / 'state.json').is_file() else {}
        if state.get('tag') == tag:
            active = Path(state.get('activeRoot', ''))
            if active.is_dir() and verify_payload(active) == state.get('version'):
                return {'status': 'unchanged', 'version': state['version']}
        checksum = fetch(assets[ASSET + '.sha256']['browser_download_url'], 4096).decode().split()[0]
        if not re.fullmatch('[0-9a-f]{64}', checksum):
            raise ValueError('Invalid release checksum')
        archive = fetch(assets[ASSET]['browser_download_url'])
        with tempfile.TemporaryDirectory(prefix='stage-', dir=root) as directory:
            staged, version = extract_verified(archive, checksum, directory)
            if tag != 'v' + version.replace('+', '-'):
                raise ValueError('Release tag differs from plugin version')
            return activate(root, staged, version, tag, cli or find_codex(), checksum)


def schedule(root, python=None):
    root = Path(root)
    plist = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    executable = str(Path(python or sys.executable).resolve())
    payload = {'Label': LABEL, 'ProgramArguments': [executable, str(root / 'update.py'), '--quiet'], 'RunAtLoad': True, 'StartInterval': 21600, 'ProcessType': 'Background', 'EnvironmentVariables': {'PATH': os.environ.get('PATH', '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin')}, 'StandardOutPath': str(root / 'update.log'), 'StandardErrorPath': str(root / 'update-error.log')}
    atomic_bytes(plist, plistlib.dumps(payload))
    # Refresh only this plugin's current-user job.
    subprocess.run(['launchctl', 'bootout', 'gui/' + str(os.getuid()), str(plist)], capture_output=True)
    command(['launchctl', 'bootstrap', 'gui/' + str(os.getuid()), plist])
    command(['launchctl', 'print', 'gui/' + str(os.getuid()) + '/' + LABEL])
    return plist


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('macOS에서 실행해주세요.')
    try:
        result = update()
        if args.install:
            schedule(DEFAULT_ROOT)
            print('설치 완료. 로그인할 때와 6시간마다 새 버전을 자동 확인합니다. Codex에서 새 작업을 시작해주세요.')
        elif not args.quiet or result['status'] == 'updated':
            print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print('영상 플러그인 업데이트 실패: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
