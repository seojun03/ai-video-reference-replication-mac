import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh_publication', ROOT / 'scripts/refresh_plugin.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'publisher.json'
        self.config.write_text(json.dumps({'autoPublish': True, 'repository': 'seojun03/ai-video-reference-replication-mac'}))
        self.enterContext(patch.object(refresh, 'PUBLISHER_CONFIG_PATH', self.config))
        self.enterContext(patch.dict(os.environ))
        os.environ.pop('VIDEO_REFERENCE_SKIP_AUTO_PUBLISH', None)

    def prepare_main(self):
        self.enterContext(patch.object(Path, 'is_file', return_value=True))
        self.enterContext(patch.object(refresh, 'marketplace_name', return_value='personal'))
        self.enterContext(patch.object(refresh, 'cleanup_generated_bytecode'))
        self.enterContext(patch.object(refresh, 'sync_automation_version', return_value={
            'needsCachebuster': False, 'initialized': False, 'contentChanged': False, 'currentVersion': '1.5'}))
        return self.enterContext(patch.object(refresh, 'run'))

    def test_default_refresh_invokes_publication(self):
        run = self.prepare_main()
        self.assertEqual(refresh.main([]), 0)
        self.assertEqual(run.call_args.args[-1], str(ROOT / 'scripts/publish_update.py'))

    def test_publication_failure_cannot_report_success(self):
        run = self.prepare_main()
        def invoke(*args):
            if args[-1] == str(ROOT / 'scripts/publish_update.py'):
                raise subprocess.CalledProcessError(1, args)
        run.side_effect = invoke
        self.assertEqual(refresh.main([]), 1)

    def test_missing_disabled_or_wrong_repository_blocks_before_mutation(self):
        for config in [None, {'autoPublish': False}, {'autoPublish': True, 'repository': 'wrong/repo'}]:
            with self.subTest(config=config), patch.object(refresh, 'run') as run:
                if config is None:
                    self.config.unlink(missing_ok=True)
                else:
                    self.config.write_text(json.dumps(config))
                self.assertEqual(refresh.main([]), 1)
                run.assert_not_called()

    def test_legacy_environment_cannot_silently_skip_publication(self):
        os.environ['VIDEO_REFERENCE_SKIP_AUTO_PUBLISH'] = '1'
        with patch.object(refresh, 'run') as run:
            self.assertEqual(refresh.main([]), 1)
            run.assert_not_called()

    def test_explicit_local_only_does_not_publish(self):
        self.config.unlink()
        run = self.prepare_main()
        self.assertEqual(refresh.main(['--local-only']), 0)
        self.assertFalse(any(call.args[-1] == str(ROOT / 'scripts/publish_update.py') for call in run.call_args_list))


if __name__ == '__main__':
    unittest.main()
