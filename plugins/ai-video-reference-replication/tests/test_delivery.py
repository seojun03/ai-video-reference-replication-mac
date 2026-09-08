import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class DeliveryTests(unittest.TestCase):
    def test_changed_content_bumps_once_and_reinstall_keeps_version(self):
        refresh = module('refresh_plugin')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ROOT.name
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            first = refresh.sync_automation_version(root)
            second = refresh.sync_automation_version(root)
            self.assertEqual(first['currentVersion'], second['currentVersion'])
            self.assertFalse(second['contentChanged'])
            (root / 'README.md').write_text((root / 'README.md').read_text() + '\nChange fixture.\n')
            changed = refresh.sync_automation_version(root)
            again = refresh.sync_automation_version(root)
            self.assertTrue(changed['contentChanged'])
            self.assertEqual(changed['currentVersion'], refresh.next_minor_version(second['currentVersion']))
            self.assertEqual(changed['currentVersion'], again['currentVersion'])
            self.assertFalse(again['contentChanged'])

    def test_archive_hashes_and_tamper_blocks_install_before_cli(self):
        builder = module('build_share_package')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = builder.build(root / 'exports')
            with zipfile.ZipFile(result['path']) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(root / 'extracted')
            payload = root / 'extracted' / ROOT.name
            hashes = json.loads((payload / 'package-files.json').read_text())
            for name, expected in hashes.items():
                self.assertEqual(hashlib.sha256((payload / name).read_bytes()).hexdigest(), expected)
                self.assertNotIn('__pycache__', name)
            (payload / 'plugins' / ROOT.name / 'README.md').write_text('tampered')
            check = subprocess.run([sys.executable, str(payload / 'install.py')], capture_output=True, text=True)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn('Package integrity failed', check.stderr)

    def test_package_cannot_contain_links_or_credential_files(self):
        builder = module('build_share_package')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'secret.key').write_text('fixture')
            with self.assertRaisesRegex(ValueError, 'Credential-like'):
                builder.collect(root)
            (root / 'secret.key').unlink()
            (root / 'link').symlink_to(ROOT / 'README.md')
            with self.assertRaisesRegex(ValueError, 'Symlinks'):
                builder.collect(root)


if __name__ == '__main__':
    unittest.main()
