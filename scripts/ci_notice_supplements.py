"""Explicit standard-text supplements for three reviewed package declarations.

These are never described as recovered upstream notices or legal clearance.
The absence of original upstream license files stays visible in the inventory.
"""
import hashlib
import json
from pathlib import Path
import re

BINDINGS = {
    ('cargo','selectors','0.38.0'): ('MPL-2.0','MPL-2.0.txt','https://www.mozilla.org/MPL/2.0/'),
    ('npm','is-reference','3.0.3'): ('MIT','MIT-standard.txt','https://opensource.org/license/mit'),
    ('npm','locate-character','3.0.0'): ('MIT','MIT-standard.txt','https://opensource.org/license/mit'),
}


def supplement(root, output, directory, package):
    binding = BINDINGS.get((package['ecosystem'],package['name'],package['version']))
    if not binding or not package['license_text_missing']:
        return False
    license_id, filename, origin = binding
    if package.get('license') != license_id:
        raise ValueError('Reviewed supplemental license declaration changed')
    standard = root / 'LICENSES' / filename
    data = standard.read_bytes()
    folder = output / 'dependencies' / hashlib.sha256(package['id'].encode()).hexdigest()[:24] / 'supplement'
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(data)
    original = directory / ('package.json' if package['ecosystem']=='npm' else 'Cargo.toml')
    # Retain the exact package declaration; do not infer copyright years/owners.
    (folder / original.name).write_bytes(original.read_bytes())
    headers = {}
    if package['ecosystem'] == 'cargo':
        for source in sorted(directory.rglob('*.rs')):
            if source.is_symlink(): continue
            with source.open('rb') as stream: text=stream.read(8192).decode('utf-8',errors='replace')
            start = re.match(r'\s*(/\*.*?\*/|(?://[^\n]*(?:\n|$))+)',text,re.S)
            if start and any(t in start[0].lower() for t in ('copyright','license','licence')):
                headers[source.relative_to(directory).as_posix()] = start[0]
        (folder / 'SOURCE-NOTICES.json').write_text(json.dumps(headers,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    details = {'component':package['name'],'version':package['version'],'license_declaration':license_id,
               'basis':'explicit_standard_text_for_exact_declared_license',
               'standard_license_reference':origin,'original_upstream_notice_missing':True,
               'authors_as_reported':package.get('authors',[]), 'repository':package.get('repository'),
               'copyright_years_or_holders_invented':False,
               'note':'Standard license text supplied separately from original package declarations/source notices. MIT angle-bracket fields are the standard form, not a component-specific copyright claim.'}
    (folder / 'SUPPLEMENT.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for p in sorted(folder.iterdir()):
        package['notice_files'].append({'path':p.relative_to(output).as_posix(),
                                       'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                       'origin':'explicit_declared_license_supplement'})
    package['license_text_missing'] = False
    package['original_upstream_notice_missing'] = True
    package['license_text_basis'] = details['basis']
    return True
