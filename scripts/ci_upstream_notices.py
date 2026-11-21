"""Recover omitted notices from immutable upstream revisions; never guess license text."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

PREFIXES = ('license', 'licence', 'copying', 'copyright', 'notice', 'unlicense')
APPROVED = {
    'github.com/dropbox/rust-alloc-no-stdlib', 'github.com/rodmitry/atoi_simd',
    'github.com/madsmtm/objc2', 'github.com/servo/stylo', 'github.com/tauri-apps/tauri',
    'github.com/wravery/webview2-rs', 'github.com/openbytedev/dlopen2',
    'github.com/tauri-apps/libappindicator-rs', 'github.com/rich-harris/is-reference',
    'gitlab.com/rich-harris/locate-character', 'github.com/evanw/esbuild', 'github.com/rollup/rollup',
}


def repository(value):
    if isinstance(value, dict): value = value.get('url', '')
    value = (value or '').removeprefix('git+').removesuffix('.git').rstrip('/')
    parsed = urlsplit(value)
    parts = parsed.path.strip('/').split('/')
    if parsed.scheme != 'https' or len(parts) != 2 or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Upstream repository is not an approved HTTPS project')
    key = parsed.netloc.lower() + '/' + '/'.join(parts)
    if key.lower() not in APPROVED:
        raise ValueError('Upstream repository is not approved for notice retrieval')
    return parsed.netloc.lower(), '/'.join(parts)


def pinned(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', value):
        raise ValueError('No immutable upstream commit available')
    return value.lower()


def eligible(path, subdir):
    p, sub = PurePosixPath(path), PurePosixPath(subdir or '.')
    if p.is_absolute() or '..' in p.parts or sub.is_absolute() or '..' in sub.parts:
        return False
    parents = {sub, *sub.parents, PurePosixPath('.')}
    return p.parent in parents and p.name.lower().startswith(PREFIXES)


class UpstreamNotices:
    def __init__(self): self.cache = {}

    def request(self, url):
        if url in self.cache: return self.cache[url]
        host = urlsplit(url).hostname
        if host not in ('api.github.com', 'registry.npmjs.org', 'gitlab.com'):
            raise ValueError('Unexpected notice host')
        headers = {'User-Agent':'MdictStudioPro-notice-collector', 'Accept':'application/json'}
        token = os.environ.get('GITHUB_TOKEN')
        if token and host == 'api.github.com': headers['Authorization'] = 'Bearer ' + token
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024: raise ValueError('Upstream notice response too large')
        result = json.loads(data)
        self.cache[url] = result
        return result

    def files(self, repo, commit, subdir=''):
        host, name = repository(repo)
        commit = pinned(commit)
        if host == 'github.com':
            api = 'https://api.github.com/repos/' + name + '/git/'
            tree = self.request(api + 'trees/' + commit + '?recursive=1')
            if tree.get('truncated'): raise ValueError('Upstream source tree was truncated')
            entries = [p for p in tree['tree'] if p['type'] == 'blob' and eligible(p['path'], subdir)]
            if len(entries) > 32: raise ValueError('Unexpectedly many upstream notice files')
            for entry in entries:
                if entry.get('mode') == '120000': continue
                blob = self.request(api + 'blobs/' + entry['sha'])
                if blob.get('encoding') != 'base64': raise ValueError('Unexpected Git blob encoding')
                data = base64.b64decode(blob['content'])
                digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                if digest != entry['sha']: raise ValueError('Upstream Git blob checksum mismatch')
                yield entry['path'], data, {'repository':repo, 'commit':commit, 'git_blob_sha1':digest}
        else:
            project = quote(name, safe='')
            api = 'https://gitlab.com/api/v4/projects/' + project + '/repository/'
            sub = PurePosixPath(subdir or '.')
            if sub.is_absolute() or '..' in sub.parts: raise ValueError('Invalid source subdirectory')
            for parent in [sub, *sub.parents]:
                at = '' if str(parent) == '.' else str(parent)
                tree = self.request(api + 'tree?ref=' + commit + '&per_page=100&path=' + quote(at, safe=''))
                if len(tree) == 100: raise ValueError('Upstream tree needs pagination; review manually')
                for entry in tree:
                    if entry['type'] != 'blob' or not eligible(entry['path'], subdir): continue
                    blob = self.request(api + 'files/' + quote(entry['path'], safe='') + '?ref=' + commit)
                    data = base64.b64decode(blob['content'])
                    if hashlib.sha256(data).hexdigest() != blob['content_sha256']:
                        raise ValueError('GitLab notice checksum mismatch')
                    yield entry['path'], data, {'repository':repo, 'commit':commit, 'content_sha256':blob['content_sha256']}

    def recover(self, directory, metadata, lock_entry=None):
        if metadata['ecosystem'] == 'cargo':
            vcs = json.loads((directory / '.cargo_vcs_info.json').read_text(encoding='utf-8'))
            repo = metadata.get('repository')
            if not repo and (metadata['name'], metadata['version']) == ('libappindicator-sys', '0.9.0'):
                repo = 'https://github.com/tauri-apps/libappindicator-rs'
            return list(self.files(repo, vcs['git']['sha1'], vcs.get('path_in_vcs', '')))
        name, version = metadata['name'], metadata['version']
        published = self.request('https://registry.npmjs.org/' + quote(name, safe='') + '/' + quote(version, safe=''))
        if published.get('name') != name or published.get('version') != version:
            raise ValueError('npm version metadata differs from installed package')
        if not lock_entry or not lock_entry.get('integrity') or published.get('dist', {}).get('integrity') != lock_entry['integrity']:
            raise ValueError('npm upstream metadata does not match locked package integrity')
        details = published.get('repository') or metadata.get('repository')
        subdir = details.get('directory', '') if isinstance(details, dict) else ''
        return list(self.files(details, published.get('gitHead'), subdir))


def save_recovered(output, package, files):
    folder = output / 'dependencies' / hashlib.sha256(package['id'].encode()).hexdigest()[:24] / 'upstream'
    saved = []
    for index, (name, data, provenance) in enumerate(files):
        if len(data) > 2 * 1024 * 1024: raise ValueError('Upstream notice too large')
        text = data.decode('utf-8')
        if '<html' in text[:500].lower() or not text.strip(): raise ValueError('Invalid upstream notice content')
        dest = folder / f'{index:02d}-{PurePosixPath(name).name}'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        saved.append({'path':dest.relative_to(output).as_posix(), 'sha256':hashlib.sha256(data).hexdigest(),
                      'origin':'upstream_at_package_revision', 'upstream_path':name, **provenance})
    package['notice_files'].extend(saved)
    package['license_text_missing'] = not bool(package['notice_files'])
