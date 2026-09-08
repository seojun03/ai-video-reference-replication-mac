#!/usr/bin/env python3
"""Dedicated clean macOS CI only: exercise the real Codex CLI transaction."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import build_share_package as builder
import managed_updater as updater

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('This test only runs in an isolated GitHub Actions runner.')
cli = updater.find_codex()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    built = builder.build(root / 'exports')
    data = Path(built['path']).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    old, current_version = updater.extract_verified(data, digest, root / 'old')
    version_path = old / 'plugins' / updater.NAME / '.codex-plugin/plugin.json'
    manifest = updater.read_json(version_path)
    manifest['version'] = '0.0.1+codex.20200101000000'
    updater.write_json(version_path, manifest)
    hashes = updater.read_json(old / 'package-files.json')
    hashes[version_path.relative_to(old).as_posix()] = hashlib.sha256(version_path.read_bytes()).hexdigest()
    (old / 'stale-version-only.txt').write_text('old files must not enter the new install')
    hashes['stale-version-only.txt'] = hashlib.sha256((old / 'stale-version-only.txt').read_bytes()).hexdigest()
    updater.write_json(old / 'package-files.json', hashes)
    updater.register(cli, old, manifest['version'])
    staged, version = updater.extract_verified(data, digest, root / 'new')
    real_register = updater.register
    def fail_new(cli, candidate, version):
        if Path(candidate).resolve() != old.resolve():
            updater.switch_marketplace(cli, candidate)
            raise RuntimeError('Injected registration failure')
        real_register(cli, candidate, version)
    try:
        with patch.object(updater, 'register', side_effect=fail_new):
            updater.activate(root / 'managed', staged, version, 'v' + version.replace('+', '-'), cli, digest)
        raise AssertionError('Failure was not surfaced')
    except RuntimeError as error:
        assert 'previous marketplace and plugin restored' in str(error)
    assert updater.previous_source(cli).resolve() == old.resolve()
    staged, version = updater.extract_verified(data, digest, root / 'retry')
    result = updater.activate(root / 'managed', staged, version, 'v' + version.replace('+', '-'), cli, digest)
    active = Path(updater.read_json(root / 'managed/state.json')['activeRoot'])
    assert result['status'] == 'updated'
    assert old.is_dir() and (old / 'stale-version-only.txt').is_file()
    assert not (active / 'stale-version-only.txt').exists()
    assert updater.previous_source(cli).resolve() == active.resolve()
    updater.command([cli, 'plugin', 'remove', updater.NAME + '@' + updater.MARKETPLACE])
    updater.command([cli, 'plugin', 'marketplace', 'remove', updater.MARKETPLACE])
print('Real Codex installation, rollback, preserved old files, and upgrade verified.')
