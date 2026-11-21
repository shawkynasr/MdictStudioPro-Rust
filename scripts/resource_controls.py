"""Offline MDX/MDD CSS, image, custom-font and exact binary-byte qualification."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import posixpath
import subprocess
import sys
from patched_interop import ROOT, require, compare, read_python, inspect_header, hash_file, verify_candidate_source
from minimal_reader_controls import validate_case
from check_native_wire import wire_contract
from reader_fixtures import green_png
from v2_audit import audit, Assets, css_urls

FONT_SHA256 = 'bb3f262bf21c6f63eca131f239113797636761a866d39756943ae702a318fb1f'


def specification():
    font = (ROOT/'baseline/resource-probe/studio-probe.ttf').read_bytes()
    require(hashlib.sha256(font).hexdigest() == FONT_SHA256, 'Bundled diagnostic font differs')
    css = ("@font-face{font-family:'Studio MDD Probe';src:url('../fonts/studio-probe.ttf') format('truetype');"
           "font-weight:normal;font-style:normal;}\n"
           ".probe-box{background:#00b446 !important;color:#000 !important;border:3px solid #000;padding:8px;}\n"
           ".probe-font{font-family:'Studio MDD Probe',serif !important;font-size:64px !important;"
           "font-weight:normal !important;font-style:normal !important;}\n").encode('utf-8')
    link = '<link rel="stylesheet" type="text/css" href="/styles/probe.css">'
    image = '<img src="/images/green.png" width="24" height="24" alt="IMAGE_RESOURCE_NOT_LOADED">'
    font_sample = ('<p>Embedded font: <span class="probe-font">ABC</span></p>'
                   '<p>Fallback control: <span style="font-family:serif">ABC</span></p>')
    rows = [('css', link+'<div class="probe-box">MDD_CSS_OK</div>'),
            ('image', '<p>MDD_IMAGE_OK: green square below</p>'+image),
            ('font', link+font_sample),
            ('combined', link+'<div class="probe-box">MDD_COMBINED_OK</div>'+image+font_sample),
            ('plain', '<p>PLAIN_CONTROL_OK</p>')]
    resources = [('\\styles\\probe.css', css), ('\\images\\green.png', green_png()),
                 ('\\fonts\\studio-probe.ttf', font), ('\\data\\sentinel.bin', bytes([0,255,128,0,1,2,0,254,0]))]
    return {'profile':'HeaderLiteralC','cases':[{'name':'06-mdd-resources','stylesheet':'',
        'entries':[{'key':k,'text':v} for k,v in rows], 'queries':[k for k,v in rows]+['missing'],
        'resources':[{'key':k,'bytes':list(v)} for k,v in resources]}]}


def validate_asset_graph(case):
    resources = {r['key'].replace('\\','/').lstrip('/'):bytes(r['bytes']) for r in case['resources']}
    require(len(resources) == len(case['resources']), 'Resource aliases or duplicates')
    references = set()
    for entry in case['entries']:
        assets = Assets(); assets.feed(entry['text']); references.update(assets.paths)
    require(references == {'styles/probe.css','images/green.png'}, 'Unexpected MDX resource graph')
    for path in references: require(path in resources, f'Missing MDX asset: {path}')
    css = resources['styles/probe.css'].decode('utf-8')
    urls = css_urls(css)
    require(urls == ['../fonts/studio-probe.ttf'], 'Unexpected CSS font URL graph')
    resolved = posixpath.normpath(posixpath.join('styles', urls[0]))
    require(not resolved.startswith('../') and resolved in resources, 'CSS font URL does not resolve to an MDD key')
    require(hashlib.sha256(resources[resolved]).hexdigest() == FONT_SHA256, 'Font dependency bytes differ')
    return {'mdx_paths':sorted(references), 'css_font_url':urls[0], 'resolved_font_key':resolved,
            'sidecar_assets_required':False, 'font_expected_glyphs':'A=filled triangle; B=plus; C=diamond'}


def validate_resources(case, result, python_rows):
    expected = sorted(case['resources'], key=lambda r:r['key'].lower())
    expected_rows = [(r['key'],bytes(r['bytes'])) for r in expected]
    compare(expected_rows, [(r['key'],bytes(r['bytes'])) for r in result['rows']], order=True)
    compare(expected_rows, python_rows, order=True)
    require(result['key_blocks'] > 1 and result['record_blocks'] > 1, 'MDD did not cross block boundaries')
    queries = [r['key'] for r in case['resources']]+['\\missing-resource.bin']
    require([q['query'] for q in result['lookups']] == queries, 'MDD query inventory differs')
    for lookup in result['lookups']:
        wanted = [r for r in expected if r['key'] == lookup['query']]
        require(lookup['rows'] == wanted, f"MDD lookup differs: {lookup['query']}")
    return {'status':'passed','resources':len(expected),'lookups':len(queries),
            'key_blocks':result['key_blocks'],'record_blocks':result['record_blocks'],
            'inventory':[{'key':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in expected_rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    report = {'status':'blocked','engine_revision':5,'fixture_wrapper_revision':7,
              'native_readers':'NOT_RUN_DO_NOT_IMPORT','checks':{},'steps':[],
              'not_proven':['native_MDD_discovery','native_CSS_image_font_rendering','all_resource_path_aliases',
                            'real_Arabic_font_rendering','production_limits','M1_completion']}
    def run(name, command):
        result = subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=1800)
        (out/(name+'.log')).write_text(result.stdout+'\nSTDERR:\n'+result.stderr,encoding='utf-8')
        report['steps'].append({'name':name,'returncode':result.returncode,'log':name+'.log'})
        require(result.returncode == 0,f'{name} failed; see log')
        return result.stdout
    try:
        require(importlib.metadata.version('mdict-utils') == '1.3.14','Expected mdict-utils 1.3.14')
        run('prepare',[sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','5','--reuse'])
        vendor = ROOT/'vendor/mdictlib-0.2.8-studio-sort-v5'; verify_candidate_source(vendor,5)
        report['source_sha256'] = {str(p.relative_to(ROOT)):hash_file(p) for p in
            [vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',
             ROOT/'experiments/native-controls/src/main.rs',Path(__file__).resolve(),
             ROOT/'baseline/resource-probe/studio-probe.ttf',ROOT/'experiments/native-controls/Cargo.lock']}
        spec = specification(); case = spec['cases'][0]; report['asset_graph'] = validate_asset_graph(case)
        (out/'resource-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        run('rust-wrapper-tests',['cargo','test','--locked','--manifest-path','experiments/native-controls/Cargo.toml'])
        built = json.loads(run('resource-build',['cargo','run','--locked','--manifest-path',
            'experiments/native-controls/Cargo.toml','--',out/'resource-spec.json',out/'dictionaries']))
        (out/'rust-observations.json').write_text(json.dumps(built,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        expected_files = {f"06-mdd-resources-{enc}.{ext}" for enc in ['utf8','utf16'] for ext in ['mdx','mdd']}
        require(built['profile']=='HeaderLiteralC' and len(built['cases'])==2,'Incomplete build report')
        require({r['file'] for r in built['cases']} == {n for n in expected_files if n.endswith('.mdx')},'Wrong MDX file identities')
        require({p.name for p in (out/'dictionaries').iterdir()} == expected_files,'Unexpected sidecar files')
        for result in built['cases']:
            mdx = out/'dictionaries'/result['file']; mdd_result = result['mdd']
            require(mdd_result['file'] == mdx.with_suffix('.mdd').name,'MDD basename differs from MDX')
            mdd = out/'dictionaries'/mdd_result['file']
            for path in [mdx,mdd]:
                observed = audit(path); wire = wire_contract(path,observed)
                require(wire['status']=='passed',f'Wire check failed: {path.name}')
                if path.suffix == '.mdx':
                    check = validate_case(case,result,read_python(path,'mdx'),inspect_header(path)['attributes'])
                    require(observed['style_markers']==0 and observed['embedded_stylesheet_characters']==0,'Unexpected embedded style dependency')
                else:
                    check = validate_resources(case,mdd_result,read_python(path,'mdd'))
                    require(observed['records']==4,'Independent resource count differs')
                    audit_inventory = {r['path']:(r['bytes'],r['sha256']) for r in observed['resources']}
                    require(audit_inventory == {r['key']:(r['bytes'],r['sha256']) for r in check['inventory']},'Auditor inventory differs')
                report['checks'][path.name] = {**check,'wire':wire,'structural_audit':observed}
        with (out/'reader-results.csv').open('w',newline='',encoding='utf-8') as stream:
            writer = csv.DictWriter(stream,fieldnames=['reader','encoding','mdx_sha256','mdd_sha256','key','expected','result','notes'])
            writer.writeheader()
            tests = {'css':'Green background with black border and MDD_CSS_OK',
                'image':'A green 24x24 square, no broken-image icon',
                'font':'Embedded ABC becomes triangle + diamond; fallback ABC stays letters',
                'combined':'Green box, green image and triangle + diamond together',
                'plain':'PLAIN_CONTROL_OK; no resource formatting inherited', 'missing':'No exact entry',
                'restart':'Reader reopens and resources still render'}
            for encoding in ['utf8','utf16']:
                for reader in ['GoldenDict','MDict']:
                    for key,expected in tests.items():
                        writer.writerow({'reader':reader,'encoding':encoding,
                            'mdx_sha256':report['checks'][f'06-mdd-resources-{encoding}.mdx']['wire']['sha256'],
                            'mdd_sha256':report['checks'][f'06-mdd-resources-{encoding}.mdd']['wire']['sha256'],
                            'key':key,'expected':expected,'result':'NOT_RUN'})
        report['status'] = 'offline_MDD_controls_passed_native_untested'
        report['native_readers'] = 'NOT_RUN_READY_FOR_STAGED_MANUAL_TEST'
    except Exception as error:
        report['error'] = str(error)
    finally:
        (out/'resource-controls-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"{report['status']}: {out/'resource-controls-report.json'}")
    return 0 if report['status']=='offline_MDD_controls_passed_native_untested' else 1


if __name__ == '__main__': raise SystemExit(main())
