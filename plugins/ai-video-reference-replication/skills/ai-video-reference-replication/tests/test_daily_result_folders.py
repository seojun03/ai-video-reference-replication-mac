import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from daily_result_folders import archive_run, collect, init_run, sha256


class DailyLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '제품' / '생성 결과물'
        self.root.mkdir(parents=True)
        self.run = self.root / '20260831-example-v001'
        self.run.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def clip(self, name, content):
        p = self.run / name
        p.write_bytes(content)
        return {'source': str(p), 'name': '피부 표현'}

    def test_same_day_batches_append_and_preserve_original_inode(self):
        first = self.clip('cut-01.mp4', b'first video bytes')
        second = self.clip('cut-02.mp4', b'second video bytes')
        inode = Path(first['source']).stat().st_ino
        a = collect(self.root, '2026-08-31', [first])
        b = collect(self.root, '2026-08-31', [second])
        self.assertEqual(a['final_clean_clips_dir'], b['final_clean_clips_dir'])
        self.assertEqual(b['daily_total_count'], 2)
        self.assertEqual(Path(a['files'][0]['target']).stat().st_ino, inode)
        self.assertTrue(Path(first['source']).is_symlink())
        self.assertEqual(Path(first['source']).read_bytes(), b'first video bytes')
        self.assertEqual(sorted(p.name for p in Path(b['final_clean_clips_dir']).iterdir()),
                         ['001_피부 표현.mp4', '002_피부 표현.mp4'])

    def test_rerun_and_identical_source_do_not_add_another_clip(self):
        first = self.clip('cut-01.mp4', b'same bytes')
        duplicate = self.clip('cut-02.mp4', b'same bytes')
        collect(self.root, '2026-08-31', [first])
        result = collect(self.root, '2026-08-31', [first, duplicate])
        self.assertEqual(result['daily_total_count'], 1)
        self.assertEqual(result['new_unique_count'], 0)
        self.assertTrue(Path(duplicate['source']).is_file())

    def test_archive_keeps_paths_and_hides_only_the_legacy_link(self):
        clip = self.clip('cut-01.mp4', b'preserve')
        collect(self.root, '2026-08-31', [clip])
        target = archive_run(self.root, self.run, '2026-08-31', '레퍼런스 작업')
        self.assertTrue(self.run.is_symlink())
        self.assertEqual(Path(clip['source']).read_bytes(), b'preserve')
        self.assertEqual(self.run.resolve(), target)
        if hasattr(self.run.lstat(), 'st_flags'):
            self.assertTrue(self.run.lstat().st_flags & stat.UF_HIDDEN)
            self.assertFalse(target.lstat().st_flags & stat.UF_HIDDEN)

    def test_other_product_source_and_escaped_symlink_are_rejected(self):
        outside = Path(self.temp.name) / 'other.mp4'
        outside.write_bytes(b'other product')
        link = self.run / 'cut-01.mp4'
        link.symlink_to(outside)
        with self.assertRaises(RuntimeError):
            collect(self.root, '2026-08-31', [{'source': str(link), 'name': '영상'}])
        self.assertEqual(outside.read_bytes(), b'other product')
        self.assertFalse((self.root / '2026-08-31').exists())

    def test_relative_links_outside_moved_run_keep_their_target(self):
        external = self.root / '원본.mp4'
        external.write_bytes(b'root source')
        linked = self.run / 'reference.mp4'
        linked.symlink_to('../원본.mp4')
        archive_run(self.root, self.run, '2026-08-31', '이전 작업')
        self.assertEqual(linked.read_bytes(), b'root source')
        self.assertEqual(linked.resolve(), external.resolve())

    def test_dry_run_and_count_failure_leave_sources_untouched(self):
        first = self.clip('cut-01.mp4', b'keep')
        result = collect(self.root, '2026-08-31', [first], dry_run=True)
        self.assertEqual(result['daily_total_count'], 1)
        self.assertFalse(Path(first['source']).is_symlink())
        self.assertFalse((self.root / '2026-08-31').exists())
        with self.assertRaises(RuntimeError):
            collect(self.root, '2026-08-31', [first], expected_count=2)

    def test_unknown_destination_and_modified_registered_clip_block(self):
        first = self.clip('cut-01.mp4', b'first')
        result = collect(self.root, '2026-08-31', [first])
        clean = Path(result['final_clean_clips_dir'])
        unknown = clean / '사용자 영상.mp4'
        unknown.write_bytes(b'user file')
        with self.assertRaises(RuntimeError):
            collect(self.root, '2026-08-31', [first])
        self.assertEqual(unknown.read_bytes(), b'user file')
        unknown.unlink()
        Path(result['files'][0]['target']).write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            collect(self.root, '2026-08-31', [first])

    def test_new_runs_share_clean_folder_but_keep_distinct_records(self):
        a = init_run(self.root, '2026-08-31', '추가 장면')
        b = init_run(self.root, '2026-08-31', '추가 장면')
        self.assertEqual(a['final_clean_clips_dir'], b['final_clean_clips_dir'])
        self.assertNotEqual(a['run_dir'], b['run_dir'])
        self.assertEqual(Path(a['run_dir']).parent.name, '작업 기록')
        self.assertEqual(Path(b['run_dir']).name, '추가 장면 002')

    def test_dates_separate_and_archive_collision_never_overwrites(self):
        a = collect(self.root, '2026-08-30', [self.clip('cut-01.mp4', b'a')])
        b = collect(self.root, '2026-08-31', [self.clip('cut-02.mp4', b'b')])
        self.assertNotEqual(a['final_clean_clips_dir'], b['final_clean_clips_dir'])
        existing = self.root / '2026-08-31' / '작업 기록' / '기존 작업'
        existing.mkdir()
        marker = existing / '사용자.txt'
        marker.write_text('keep')
        with self.assertRaises(RuntimeError):
            archive_run(self.root, self.run, '2026-08-31', '기존 작업')
        self.assertFalse(self.run.is_symlink())
        self.assertEqual(marker.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
