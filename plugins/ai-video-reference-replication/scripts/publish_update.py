#!/usr/bin/env python3
"""Publish the complete validated source after the exact commit passes macOS CI."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ai-video-reference-replication'
REPO = 'seojun03/ai-video-reference-replication-mac'
DIST = Path.home() / 'plugins/ai-video-reference-replication-distribution'


def run(args, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def build_artifacts(root, output):
    spec = importlib.util.spec_from_file_location('package_builder', root / 'scripts/build_share_package.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    result = builder.build(output)
    source = Path(result['path'])
    archive = output / (NAME + '-plugin.zip')
    shutil.copy2(source, archive)
    archive.with_suffix('.zip.sha256').write_text(result['sha256'] + '  ' + archive.name + '\n')
    # A ZIP preserves executable permission after downloading on macOS.
    command = '#!/bin/sh\nset -eu\nif ! command -v python3 >/dev/null 2>&1; then\n  echo "Python 3 is required. Install Python 3 and run this file again."\n  exit 1\nfi\npython3 - --install <<\'INCORE_UPDATER_PY\'\n' + (root / 'scripts/managed_updater.py').read_text() + '\nINCORE_UPDATER_PY\n'
    launcher = output / 'INSTALL-MAC.command'
    launcher.write_text(command)
    launcher.chmod(0o755)
    run(['sh', '-n', launcher])
    installer_zip = output / 'INSTALL-MAC.zip'
    with zipfile.ZipFile(installer_zip, 'w', zipfile.ZIP_DEFLATED) as bundle:
        info = zipfile.ZipInfo(launcher.name, date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o100755 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        bundle.writestr(info, launcher.read_bytes())
    return [archive, archive.with_suffix('.zip.sha256'), launcher, installer_zip]


def main():
    config_path = Path.home() / '.codex/state' / NAME / 'publisher.json'
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    if config.get('autoPublish') is not True or config.get('repository') != REPO:
        raise SystemExit('Owner publishing configuration is not enabled on this machine.')
    if DIST.resolve() != Path(config['distributionRoot']).resolve():
        raise SystemExit('Distribution root differs from owner configuration.')
    version = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())['version']
    tag = 'v' + version.replace('+', '-')
    python = config.get('testPython', sys.executable)
    print('Testing source before publication...', flush=True)
    run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', ROOT / 'tests', ROOT / 'skills/ai-video-reference-replication/tests'], cwd=ROOT)
    if run(['git', 'remote', 'get-url', 'origin'], DIST) != 'https://github.com/' + REPO + '.git':
        raise SystemExit('Unexpected distribution Git remote.')
    target = DIST / 'plugins' / NAME
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', '.pytest_cache'))
    run(['git', 'add', '--', 'plugins', '.github', 'README.md', '.gitignore'], DIST)
    if run(['git', 'diff', '--cached', '--name-only'], DIST):
        run(['git', 'commit', '-m', 'Release video plugin ' + version], DIST)
    commit = run(['git', 'rev-parse', 'HEAD'], DIST)
    run(['git', 'push', '-u', 'origin', 'main'], DIST)
    print('Waiting for macOS CI at ' + commit, flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        runs = json.loads(run(['gh', 'run', 'list', '--repo', REPO, '--commit', commit, '--workflow', 'macos-install.yml', '--json', 'databaseId,status,conclusion', '--limit', '5']))
        if runs and runs[0]['status'] == 'completed':
            if runs[0]['conclusion'] != 'success':
                raise SystemExit('macOS CI failed: ' + str(runs[0]['databaseId']))
            break
        time.sleep(10)
    else:
        raise SystemExit('macOS CI did not finish; no release published.')
    with tempfile.TemporaryDirectory(prefix='video-release-') as directory:
        output = Path(directory)
        run(['git', 'diff', '--exit-code', 'HEAD', '--', 'plugins'], DIST)
        artifacts = build_artifacts(target, output)
        existing = subprocess.run(['gh', 'release', 'view', tag, '--repo', REPO], capture_output=True)
        if existing.returncode:
            # Draft first, then make the complete asset set visible together.
            run(['gh', 'release', 'create', tag, '--repo', REPO, '--target', commit, '--draft', '--title', '영상 생성 자동화 ' + version, '--notes', 'Mac 자동 업데이트용 검증된 플러그인입니다. INSTALL-MAC.zip을 받아 압축 해제 후 실행하세요.', *artifacts])
            run(['gh', 'release', 'edit', tag, '--repo', REPO, '--draft=false', '--latest'])
        download = output / 'public-readback'
        download.mkdir()
        run(['gh', 'release', 'download', tag, '--repo', REPO, '--dir', download])
        for artifact in artifacts:
            if hashlib.sha256(artifact.read_bytes()).digest() != hashlib.sha256((download / artifact.name).read_bytes()).digest():
                raise SystemExit('Public asset differs from local build: ' + artifact.name)
        record = {'version': version, 'tag': tag, 'commit': commit, 'ci': runs[0], 'publicAssetsVerified': [x.name for x in artifacts], 'installerUrl': 'https://github.com/' + REPO + '/releases/latest/download/INSTALL-MAC.zip'}
        state = config_path.parent / 'last-published.json'
        state.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
