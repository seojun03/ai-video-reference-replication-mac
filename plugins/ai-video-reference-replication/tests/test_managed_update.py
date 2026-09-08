import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManagedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.updater = load('managed_updater')
        self.builder = load('build_share_package')
        self.result = self.builder.build(self.root / 'exports')
        self.archive = Path(self.result['path']).read_bytes()
        self.digest = hashlib.sha256(self.archive).hexdigest()
        self.tag = 'v' + self.result['version'].replace('+', '-')
        self.assets = {name: {'browser_download_url': name} for name in (self.updater.ASSET, self.updater.ASSET + '.sha256')}

    def stage(self, name):
        return self.updater.extract_verified(self.archive, self.digest, self.root / name)

    def test_checksum_failure_has_no_registration(self):
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.updater.extract_verified(self.archive + b'x', self.digest, self.root / 'stage')
        self.assertFalse((self.root / 'stage').exists())

    def test_first_install_then_unchanged_has_no_reinstall(self):
        root = self.root / 'managed'
        fetch = lambda url, limit=None: self.digest.encode() if url.endswith('.sha256') else self.archive
        with patch.object(self.updater, 'latest_release', return_value=(self.tag, self.assets)), patch.object(self.updater, 'fetch', side_effect=fetch), patch.object(self.updater, 'previous_source', return_value=None), patch.object(self.updater, 'register') as register:
            first = self.updater.update(root, cli='fixture-codex')
            again = self.updater.update(root, cli='fixture-codex')
            self.assertEqual(first['status'], 'updated')
            self.assertEqual(again['status'], 'unchanged')
            self.assertEqual(register.call_count, 1)
            self.assertTrue((root / 'update.py').is_file())

    def test_migration_preserves_old_zip_and_rolls_back_failed_registration(self):
        old, version = self.stage('old-download')
        staged, version = self.stage('new-download')
        root = self.root / 'managed'
        root.mkdir()
        (old / 'personal-notes.txt').write_text('keep recipient file')
        calls = []
        def register(cli, source, ver):
            calls.append(Path(source))
            if Path(source) != old:
                raise RuntimeError('Simulated installation failure')
        with patch.object(self.updater, 'previous_source', return_value=old), patch.object(self.updater, 'register', side_effect=register):
            with self.assertRaisesRegex(RuntimeError, 'previous marketplace and plugin restored'):
                self.updater.activate(root, staged, version, self.tag, 'fixture-codex', self.digest)
        self.assertEqual(calls[-1], old)
        self.assertEqual((old / 'personal-notes.txt').read_text(), 'keep recipient file')
        self.assertFalse((root / 'state.json').exists())

    def test_successful_migration_keeps_previous_folder(self):
        old, version = self.stage('old-download')
        staged, version = self.stage('new-download')
        root = self.root / 'managed'
        with patch.object(self.updater, 'previous_source', return_value=old), patch.object(self.updater, 'register'):
            result = self.updater.activate(root, staged, version, self.tag, 'fixture-codex', self.digest)
        self.assertEqual(result['status'], 'updated')
        self.assertTrue(old.is_dir())
        self.assertEqual(json.loads((root / 'state.json').read_text())['previousRoot'], str(old))

    def test_overlapping_check_does_not_fetch_or_mutate(self):
        root = self.root / 'managed'
        with self.updater.locked(root), patch.object(self.updater, 'latest_release') as latest:
            self.assertEqual(self.updater.update(root)['status'], 'already_running')
            latest.assert_not_called()

    def test_source_switch_uses_cli_and_preserves_plugin_until_new_install(self):
        with patch.object(self.updater, 'previous_source', return_value=self.root / 'old'), patch.object(self.updater, 'command') as command:
            self.updater.switch_marketplace('codex', self.root / 'new')
        self.assertEqual(command.call_args_list[0].args[0], ['codex', 'plugin', 'marketplace', 'remove', self.updater.MARKETPLACE])
        self.assertEqual(command.call_args_list[1].args[0], ['codex', 'plugin', 'marketplace', 'add', self.root / 'new'])

    def test_unlisted_file_is_rejected(self):
        staged, version = self.stage('stage')
        (staged / 'extra.py').write_text('pass')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            self.updater.verify_payload(staged)

    def test_schedule_is_current_user_six_hour_job(self):
        import plistlib
        root = self.root / 'managed'
        captured = {}
        def save(path, data):
            captured['path'] = path
            captured['plist'] = plistlib.loads(data)
        with patch.object(self.updater, 'atomic_bytes', side_effect=save), patch.object(self.updater, 'command'), patch.object(self.updater.subprocess, 'run'):
            self.updater.schedule(root, python='/usr/bin/python3')
        self.assertEqual(captured['plist']['StartInterval'], 21600)
        self.assertTrue(captured['plist']['RunAtLoad'])
        self.assertIn('--quiet', captured['plist']['ProgramArguments'])
        self.assertIn('Library/LaunchAgents', str(captured['path']))


if __name__ == '__main__':
    unittest.main()
