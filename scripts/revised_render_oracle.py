"""Bounded record comparisons; only the accepted Revised set ordering is normalized."""
from itertools import zip_longest
from moe_fixtures import normalized
from large_io_oracle import digest

def records(path):
    with path.open('rb') as stream:
        while key:=stream.readline(4098):
            if len(key)>4097 or not key.endswith(b'\n') or b'\r' in key or b'\0' in key or key in (b'</>\n',b'\n') or key.startswith(b'\xef\xbb\xbf'):raise AssertionError('Invalid canonical headword')
            body=bytearray()
            while True:
                line=stream.readline(1024*1024+2)
                if not line or not line.endswith(b'\n'):raise AssertionError('Missing complete canonical delimiter')
                if line==b'</>\n':break
                if len(body)+len(line)>1024*1024+1:raise AssertionError('Definition cap exceeded')
                body.extend(line)
            if not body.endswith(b'\n'):raise AssertionError('Missing body separator')
            body.pop()
            if b'\r' in body or b'\0' in body:raise AssertionError('Unrepresentable canonical body')
            yield {'key':key[:-1].decode('utf-8'),'text':body.decode('utf-8')}
def normalized_records(path,kind):
    group=[]
    for entry in records(path):
        if kind=='moe_revised' and entry['text'].startswith('@@@LINK='):
            if not group:raise AssertionError('Alias before primary entry')
            group.append(entry)
            if len(group)>16384:raise AssertionError('Alias group exceeds cap')
        else:
            if group:yield from normalized(group,kind)
            group=[entry]
    if group:yield from normalized(group,kind)
def record_summary(path,kind,normalize=False):
    source=normalized_records(path,kind) if normalize else records(path)
    return digest((e['key'],e['text'].encode('utf-8')) for e in source)
def compare_files(actual,expected,kind):
    count=0
    for a,b in zip_longest(normalized_records(actual,kind),normalized_records(expected,kind)):
        if a!=b:raise AssertionError(f'{kind}: record {count} differs beyond the accepted set-order rule')
        count+=1
    return count
