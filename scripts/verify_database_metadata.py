"""Independently verify a title/description database copy against its source."""
import argparse
import hashlib
import json
from pathlib import Path
from m4_database import APP_ID, framed, readonly


def inspect(path):
    assert path.stat().st_size <= 128*1024*1024, 'Database exceeds 128 MiB'
    connection = readonly(path)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert connection.execute('PRAGMA application_id').fetchone()[0] == APP_ID
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2
        rows = connection.execute('SELECT entry,paraphrase FROM mdx ORDER BY rowid').fetchall()
        assert 0 < len(rows) <= 100000
        decoded = 0
        for key, text in rows:
            assert isinstance(key, str) and isinstance(text, str)
            assert len(key.encode()) <= 4096 and len(text.encode()) <= 1024*1024
            decoded += len(key.encode()) + len(text.encode())
        assert decoded <= 32*1024*1024
        meta = dict(connection.execute('SELECT key,value FROM studio_meta'))
        assert meta['profile'] == 'studio-sqlite-mdx-v1'
        assert meta['rows_sha256'] == framed(rows) and meta['records'] == str(len(rows))
        raw = meta['mdx_header_json']
        assert meta['mdx_header_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
        attrs = json.loads(raw)
        assert isinstance(attrs, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in attrs.items())
        return rows, meta, attrs
    finally:
        connection.close()


def check(source, copy, edits):
    assert edits and set(edits) <= {'title', 'description', 'stylesheet'}
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    old_rows, old_meta, old_attrs = inspect(source)
    rows, meta, attrs = inspect(copy)
    assert rows == old_rows, 'Row order, duplicate multiplicity, keys or definition text changed'
    expected = {**old_attrs, **{{'title':'Title','description':'Description','stylesheet':'StyleSheet'}[name]: value for name, value in edits.items()}}
    assert attrs == expected, 'Unexpected metadata change'
    assert meta['source_sha256'] == before, 'Copy origin does not identify the source database'
    assert meta['text_profile'] == old_meta['text_profile']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, 'Source changed'
    return {'status': 'passed', 'records': len(rows), 'source_sha256': before,
            'copy_sha256': hashlib.sha256(copy.read_bytes()).hexdigest(), 'rows_sha256': framed(rows),
            'title': attrs.get('Title'), 'description': attrs.get('Description'),
            'source_unchanged': True, 'unselected_metadata_preserved': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--copy', type=Path, required=True)
    p.add_argument('--title')
    p.add_argument('--description')
    p.add_argument('--stylesheet-file', type=Path)
    a = p.parse_args()
    edits = {name: getattr(a, name) for name in ['title', 'description'] if getattr(a, name) is not None}
    try:
        if a.stylesheet_file is not None:
            assert a.stylesheet_file.stat().st_size <= 16384, 'Stylesheet exceeds 16 KiB'
            edits['stylesheet'] = a.stylesheet_file.read_bytes().decode('utf-8')
        result = check(a.source, a.copy, edits)
    except Exception as error:
        result = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
