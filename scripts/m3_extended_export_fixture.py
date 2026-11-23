"""Create a synthetic v2 UTF-8 MDX without using the Rust reader or writer."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def block(data):
    return b'\x02\0\0\0' + struct.pack('>I', zlib.adler32(data) & 0xffffffff) + zlib.compress(data)


def fixture(count=145, body_bytes=1024 * 1024):
    if not 1 <= count <= 200 or not 1 <= body_bytes <= 1024 * 1024:
        raise ValueError('Fixture geometry is outside the synthetic test range')
    xml = ('<Dictionary GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" '
           'Encrypted="No" Encoding="UTF-8" Format="Html" KeyCaseSensitive="Yes" '
           'StripKey="No" Compact="No" Compat="Yes" Title="Synthetic export fixture"/>\0').encode('utf-16le')
    keys = [f'entry-{i:03}'.encode('ascii') for i in range(count)]
    key_data = b''.join(struct.pack('>Q', i * (body_bytes + 1)) + key + b'\0' for i, key in enumerate(keys))
    key_block = block(key_data)
    key_info = (struct.pack('>QH', count, len(keys[0])) + keys[0] + b'\0' +
                struct.pack('>H', len(keys[-1])) + keys[-1] + b'\0' +
                struct.pack('>QQ', len(key_block), len(key_data)))
    compressed_info = block(key_info)
    key_header = struct.pack('>5Q', 1, count, len(key_info), len(compressed_info), len(key_block))
    record = b'x' * body_bytes + b'\0'
    compressed_record = block(record)
    record_info = struct.pack('>QQ', len(compressed_record), len(record)) * count
    return (struct.pack('>I', len(xml)) + xml + struct.pack('<I', zlib.adler32(xml) & 0xffffffff) +
            key_header + struct.pack('>I', zlib.adler32(key_header) & 0xffffffff) + compressed_info + key_block +
            struct.pack('>4Q', count, count, len(record_info), len(compressed_record) * count) +
            record_info + compressed_record * count)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = fixture()
    with args.output.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'records': 145, 'payload_bytes': 145 * 1024 * 1024,
                      'file_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}))
