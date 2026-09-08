"""One generated-clean-video library per product and Korean calendar date."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import date, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
import uuid
from zoneinfo import ZoneInfo

SCHEMA = 'daily-generated-clean-library/v1'

def require(value, message):
    if not value:
        raise RuntimeError(message)

def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def within(path, root):
    return path == root or root in path.parents

def korean_name(value):
    value = unicodedata.normalize('NFC', value).strip()
    require(value and len(value) <= 100 and not re.search(r'[/\\\x00-\x1f]', value), '잘못된 한글 이름')
    require(re.search(r'[가-힣]', value), '사용자에게 보이는 이름에는 한글이 필요합니다')
    return value

def day_name(value=None):
    value = value or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    require(date.fromisoformat(value).isoformat() == value, '날짜는 YYYY-MM-DD 형식이어야 합니다')
    return value

def real_root(value):
    root = Path(value).expanduser().resolve(strict=True)
    require(root.is_dir() and root.name == '생성 결과물', '정확한 제품의 생성 결과물 폴더를 지정하세요')
    return root

def hide_compatibility(path):
    """Hide this entry in Finder without hiding the destination of a symlink."""
    path = Path(path)
    path = path.parent.resolve(strict=True) / path.name
    if hasattr(os, 'lchflags'):
        os.lchflags(path, path.lstat().st_flags | stat.UF_HIDDEN)
        require(path.lstat().st_flags & stat.UF_HIDDEN, f'이전 경로 숨김 확인 실패: {path}')

def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.정리기록-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)

@contextmanager
def library_lock(root):
    key = hashlib.sha256(str(root).encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f'codex-daily-results-{key}.lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)

def day_paths(root, value):
    day = root / day_name(value)
    clean, records = day / '생성 클린본', day / '작업 기록'
    for path in (day, clean, records):
        require(not path.is_symlink(), f'날짜별 저장 폴더는 실제 폴더여야 합니다: {path}')
        require(not path.exists() or path.is_dir(), f'폴더 경로가 파일과 충돌합니다: {path}')
    return day, clean, records

def replace_source_with_link(source, target, digest):
    """Use a hard link and an atomic pathname replacement; copy no video bytes."""
    source, target = Path(source), Path(target)
    require(source.is_file() and not source.is_symlink(), f'원본 일반 파일이 필요합니다: {source}')
    require(sha256(source) == digest, f'원본 내용이 변경됐습니다: {source}')
    require(not target.exists() and not target.is_symlink(), f'대상을 덮어쓰지 않습니다: {target}')
    require(source.stat().st_dev == target.parent.stat().st_dev, '같은 파일시스템에서만 이동할 수 있습니다')
    os.link(source, target)
    require(sha256(target) == digest, f'새 위치의 해시가 다릅니다: {target}')
    temporary = source.with_name('.경로연결-' + uuid.uuid4().hex)
    temporary.symlink_to(target)
    require(os.path.samefile(source, target) and sha256(source) == digest,
            f'이동 중 원본 변경: 두 경로를 보존합니다: {source}, {target}')
    os.replace(temporary, source)
    require(source.resolve(strict=True) == target and sha256(source) == digest, f'이전 경로 검증 실패: {source}')

def archive_run(root, run, generation_date, label='생성 작업'):
    root = real_root(root)
    original = Path(run).expanduser().absolute()
    source = original.resolve(strict=True)
    require(within(source, root) and source != root and source.is_dir(), '제품 내부의 작업 폴더만 이동할 수 있습니다')
    _, _, records = day_paths(root, generation_date)
    if within(source, records):
        if original.is_symlink():
            hide_compatibility(original)
        return source
    target = records / korean_name(label)
    require(not within(target, source), '폴더를 자기 내부로 이동할 수 없습니다')
    require(not target.exists() and not target.is_symlink(), f'보존 폴더 이름 충돌: {target}')
    records.mkdir(parents=True, exist_ok=True)
    require(source.stat().st_dev == records.stat().st_dev, '동일 파일시스템 내부에서만 이동합니다')
    # Relative links reaching outside the moved tree would acquire a different
    # parent after relocation. Anchor only those links before changing depth.
    for parent, dirs, files in os.walk(source, followlinks=False):
        for name in dirs + files:
            link = Path(parent) / name
            if link.is_symlink() and link.exists() and not os.path.isabs(os.readlink(link)):
                linked_target = link.resolve(strict=True)
                if not within(linked_target, source):
                    temporary = link.with_name('.경로고정-' + uuid.uuid4().hex)
                    temporary.symlink_to(linked_target, target_is_directory=linked_target.is_dir())
                    os.replace(temporary, link)
    source.rename(target)
    source.symlink_to(target, target_is_directory=True)
    hide_compatibility(source)
    if original.is_symlink():
        hide_compatibility(original)
    require(original.resolve(strict=True) == target, f'작업 폴더 이전 경로 검증 실패: {original}')
    return target

def init_run(output_root, generation_date=None, label='생성 작업'):
    root, generation_date = real_root(output_root), day_name(generation_date)
    label = korean_name(label)
    with library_lock(root):
        day, clean, records = day_paths(root, generation_date)
        clean.mkdir(parents=True, exist_ok=True)
        records.mkdir(exist_ok=True)
        index = 1
        while (records / f'{label} {index:03d}').exists():
            index += 1
        run = records / f'{label} {index:03d}'
        run.mkdir()
    return {'output_root': str(root), 'generation_date': generation_date,
            'day_dir': str(day), 'run_dir': str(run), 'final_clean_clips_dir': str(clean)}

def collect(output_root, generation_date, clips, *, expected_count=None, dry_run=False):
    root, generation_date = real_root(output_root), day_name(generation_date)
    require(clips and (expected_count is None or len(clips) == expected_count), '입력 클린본 수가 예상과 다릅니다')
    with library_lock(root):
        day, clean, records = day_paths(root, generation_date)
        manifest_path = records / '클린본 목록.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
            'schema': SCHEMA, 'generation_date': generation_date, 'clips': []}
        require(manifest.get('schema') == SCHEMA and manifest.get('generation_date') == generation_date,
                '다른 형식의 정리 기록은 덮어쓰지 않습니다')
        known, names = {}, set()
        for item in manifest['clips']:
            target = clean / item['filename']
            require(target.is_file() and not target.is_symlink() and sha256(target) == item['sha256'],
                    f'기존 클린본 변경 또는 누락: {target}')
            known[item['sha256']] = item
            names.add(item['filename'])
        if clean.exists():
            unexpected = {p.name for p in clean.iterdir() if not p.name.startswith('.')} - names
            require(not unexpected, f'목록에 없는 파일은 덮어쓰지 않습니다: {sorted(unexpected)}')
        next_index = max((x['number'] for x in manifest['clips']), default=0) + 1
        planned, new_records = [], []
        for clip in clips:
            original = Path(clip['source']).expanduser().absolute()
            source = original.resolve(strict=True)
            require(within(source, root) and source.is_file() and source.suffix.lower() == '.mp4',
                    f'이번 제품 출력 폴더 내부 MP4만 모을 수 있습니다: {source}')
            require(not any(c in source.parts for c in ('rejected', 'quarantine')),
                    f'실패/격리 영상은 클린본에 포함할 수 없습니다: {source}')
            label, digest = korean_name(clip.get('name', '생성 영상')), sha256(source)
            if digest not in known:
                target = clean / f'{next_index:03d}_{label}.mp4'
                require(not target.exists() and not target.is_symlink(), f'대상을 덮어쓰지 않습니다: {target}')
                record = {'number': next_index, 'filename': target.name, 'path': str(target),
                          'sha256': digest, 'original_paths': [], 'source_notes': []}
                known[digest] = record
                new_records.append(record)
                next_index += 1
                move = True
            else:
                record, move = known[digest], False
                target = clean / record['filename']
            if str(original) not in record['original_paths']:
                record['original_paths'].append(str(original))
            note = clip.get('note', '')
            if note and note not in record['source_notes']:
                record['source_notes'].append(note)
            planned.append({'source': str(original), 'resolved_source': str(source),
                            'target': str(target), 'sha256': digest, 'move': move})
        daily_total = len(manifest['clips']) + len(new_records)
        if not dry_run:
            clean.mkdir(parents=True, exist_ok=True)
            records.mkdir(exist_ok=True)
            for item in planned:
                if item['move']:
                    replace_source_with_link(item['resolved_source'], item['target'], item['sha256'])
                require(sha256(item['source']) == item['sha256'], f"이전 경로 내용 변경: {item['source']}")
            manifest['clips'].extend(new_records)
            manifest['updated_at'] = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
            manifest['total_count'] = daily_total
            write_json(manifest_path, manifest)
            (day / '폴더 안내.md').write_text(
                f'{generation_date} 생성 결과물\n\n생성 클린본 폴더에 사용 클린본 {daily_total}개를 모았습니다.\n'
                '추가 생성도 같은 폴더에 이어서 저장하며, 번호는 날짜 안에서 계속 증가합니다.\n'
                '기획·음성·편집 자료와 생성 원본·검수·이전 버전은 작업 기록에서 보존합니다.\n'
                '새 영상 생성·재인코딩·영상 데이터 중복 복사 없이 기존 경로를 유지합니다.\n', encoding='utf-8')
        return {'status': 'dry_run' if dry_run else 'organized', 'generation_date': generation_date,
                'output_root': str(root), 'day_dir': str(day), 'final_clean_clips_dir': str(clean),
                'final_clean_clips_resolved_dir': str(clean), 'result_folder_manifest': str(manifest_path),
                'expected_count': expected_count or len(clips), 'batch_count': len(clips),
                'new_unique_count': len(new_records), 'daily_total_count': daily_total,
                'verified_cut_files': [Path(x['target']).name for x in planned], 'files': planned,
                'layout_mode': 'date_shared_clean_folder_no_media_copy'}

def directory_link(link, target):
    target = Path(target).expanduser().resolve(strict=True)
    require(target.is_dir(), f'연결할 폴더가 아닙니다: {target}')
    if link.exists() or link.is_symlink():
        require(link.is_symlink() and link.resolve(strict=True) == target, f'연결 이름 충돌: {link}')
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)

def organize(args):
    if args.init_run:
        return init_run(args.output_root, args.date, args.run_label)
    require(args.run_dir, '기록을 보존할 --run-dir이 필요합니다')
    root = real_root(args.output_root)
    run = Path(args.run_dir).expanduser().resolve(strict=True)
    require(within(run, root) and run.is_dir(), '이번 제품 내부 작업 폴더가 필요합니다')
    if args.clips_json:
        clips = json.loads(Path(args.clips_json).read_text())
    else:
        require(args.final_dir and args.expected_count is not None,
                '--clips-json 또는 --final-dir과 --expected-count가 필요합니다')
        source = Path(args.final_dir).expanduser().resolve(strict=True)
        clips = [{'source': str(p), 'name': args.batch_name} for p in sorted(source.glob('cut-*.mp4'))]
    result = collect(root, args.date, clips, expected_count=args.expected_count, dry_run=args.dry_run)
    if args.dry_run:
        return result
    records = Path(result['day_dir']) / '작업 기록'
    target = archive_run(root, run, result['generation_date'], args.run_label) if args.archive_run else run
    result['run_dir'] = str(target)
    if args.raw_dir:
        label = korean_name('생성 원본 ' + (args.raw_label or args.batch_name))
        directory_link(records / label, args.raw_dir)
    if args.capcut_dir:
        directory_link(Path(result['day_dir']) / '편집 자료' / '캡컷 사용 영상', args.capcut_dir)
    for value in args.history_link:
        label, target = value.split('=', 1)
        directory_link(records / '이전 버전' / korean_name(label), target)
    return result

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--date', help='실제 생성 완료일, 한국시간 YYYY-MM-DD. 기본값은 오늘')
    parser.add_argument('--init-run', action='store_true')
    parser.add_argument('--run-dir')
    parser.add_argument('--run-label', default='생성 작업')
    parser.add_argument('--archive-run', action='store_true')
    parser.add_argument('--final-dir')
    parser.add_argument('--expected-count', type=int)
    parser.add_argument('--clips-json', help='이번 사용 클립의 source/name 목록 JSON')
    parser.add_argument('--batch-name', default='생성 영상')
    parser.add_argument('--raw-dir')
    parser.add_argument('--raw-label')
    parser.add_argument('--capcut-dir')
    parser.add_argument('--history-link', action='append', default=[])
    parser.add_argument('--dry-run', action='store_true')
    return parser

def main():
    try:
        result = organize(build_parser().parse_args())
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
