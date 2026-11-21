"""Independently compare SQLite physical rows with a row-only UTF-8 JSONL export."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from m4_database import framed, readonly

FILE_CAP = 128 * 1024 * 1024
DECODED_CAP = 32 * 1024 * 1024
BODY_CAP = 1024 * 1024
LINE_CAP = 6 * (BODY_CAP + 4096) + 128


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def validate_row(key, body):
    assert isinstance(key, str) and isinstance(body, str), 'Require string key and text'
    size = len(key.encode('utf-8')) + len(body.encode('utf-8'))
    assert len(key.encode('utf-8')) <= 4096 and len(body.encode('utf-8')) <= BODY_CAP
    return size


def read_jsonl(path):
    assert path.stat().st_size <= FILE_CAP, 'JSONL exceeds 128 MiB'
    result = []
    decoded = 0
    with path.open('rb') as stream:
        while True:
            line = stream.readline(LINE_CAP + 1)
            if not line:
                break
            assert len(line) <= LINE_CAP and line.endswith(b'\n'), 'Missing final LF or oversized JSONL line'
            row = json.loads(line.decode('utf-8'), object_pairs_hook=object_pairs)
            assert isinstance(row, dict) and set(row) == {'key', 'text'}, 'Require exactly key/text fields'
            decoded += validate_row(row['key'], row['text'])
            assert decoded <= DECODED_CAP and len(result) < 100000, 'Decoded row/count cap exceeded'
            result.append((row['key'], row['text']))
    return result


def check(database, jsonl):
    assert database.stat().st_size <= FILE_CAP
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    connection = readonly(database)
    try:
        expected = []
        decoded = 0
        for key, body in connection.execute('SELECT entry,paraphrase FROM mdx ORDER BY rowid'):
            decoded += validate_row(key, body)
            assert decoded <= DECODED_CAP and len(expected) < 100000
            expected.append((key, body))
    finally:
        connection.close()
    assert expected, 'Require a nonempty source dictionary'
    actual = read_jsonl(jsonl)
    assert actual == expected, 'Keys, bodies, physical row order or duplicate multiplicity differ'
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before, 'Input database changed'
    return {'status': 'passed', 'records': len(expected), 'source_sha256': before,
            'rows_sha256': framed(expected), 'bytes': jsonl.stat().st_size,
            'dictionary_metadata_in_jsonl': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--jsonl', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.database, args.jsonl)
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': f'{type(error).__name__}: {error}'}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
