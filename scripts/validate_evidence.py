"""Check user-run evidence integrity and compare recorded physical sort orders.

No Rust execution or proof of unrecorded capabilities is implied.
"""
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/macos-user-run"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    provenance = json.loads((EVIDENCE / "provenance.json").read_text(encoding="utf-8"))
    for name, item in provenance["files"].items():
        data = (ROOT / item["path_from_project_root"]).read_bytes()
        require(hashlib.sha256(data).hexdigest() == item["sha256"], f"Evidence changed: {name}")
        print(f"PASS unchanged upload: {name}")
    lock = tomllib.loads((ROOT / "Cargo.lock").read_text(encoding="utf-8"))
    packages = lock["package"]
    engine = [p for p in packages if p["name"] == "mdictlib"]
    require(len(engine) == 1 and engine[0]["version"] == "0.2.8", "Wrong locked engine")
    require("checksum" in engine[0], "Missing engine registry checksum")
    manifest = tomllib.loads((ROOT / "crates/studio-engine-probe/Cargo.toml").read_text(encoding="utf-8"))
    require(manifest["dependencies"]["mdictlib"]["version"] == "=0.2.8", "Manifest no longer matches evidence")
    probe = [p for p in packages if p["name"] == "studio-engine-probe"]
    require(len(probe) == 1, "Missing probe in lockfile")
    require(set(probe[0]["dependencies"]) == set(manifest["dependencies"]), "Root dependencies differ")
    report = json.loads((EVIDENCE / "report.json").read_text(encoding="utf-8"))
    cases = json.loads((ROOT / "baseline/cases.json").read_text(encoding="utf-8"))
    oracle = json.loads((ROOT / "baseline/expected/sort-C-locale.json").read_text(encoding="utf-8"))
    require(report["engine"] == "mdictlib" and report["version"] == "0.2.8", "Wrong report engine")
    require(report["status"] == "synthetic_subset_passed" and report["decision"] == "candidate_only", "Unexpected qualification decision")
    require(report["entries"] == len(cases["engine_entries"]), "Wrong fixture entry count")
    require(report["resources"] == len(cases["engine_resources"]), "Wrong fixture resource count")
    require(len(report["checks"]) == 11 and len(set(report["checks"])) == 11, "Unexpected check inventory")
    require(set(report["sort_probe"]["matches_legacy_C_locale"]) == set(oracle), "Missing sort comparisons")
    for profile, expected in oracle.items():
        kind = profile.split(":")[1]
        actual = report["sort_probe"][kind + "_physical_order"]
        require(sorted(actual) == sorted(cases["sort_keys"]), "Recorded sort keys differ from fixture")
        matches = actual == expected
        require(matches == report["sort_probe"]["matches_legacy_C_locale"][profile], f"Inconsistent recorded comparison: {profile}")
        # Separately show whether all remaining keys retain their order when
        # backslash-bearing keys are excluded. This is evidence, not a waiver.
        projected_matches = [k for k in actual if "\\" not in k] == [k for k in expected if "\\" not in k]
        print(f"{profile}: full_match={matches}, excluding_backslash_keys={projected_matches}")
    print("PASS evidence consistency; no new engine execution performed")
    sort_dir = ROOT / "docs/evidence/legacy-sort-user-run"
    sort_provenance = json.loads((sort_dir / "provenance.json").read_text(encoding="utf-8"))
    for name, expected in sort_provenance["files"].items():
        require(hashlib.sha256((sort_dir/name).read_bytes()).hexdigest()==expected,f"Sort evidence changed: {name}")
    experiment_lock = ROOT / "experiments/legacy-sort/Cargo.lock"
    require(experiment_lock.read_bytes()==(sort_dir/"Cargo.lock").read_bytes(),"Experiment lock differs from uploaded evidence")
    experiment = tomllib.loads(experiment_lock.read_text(encoding="utf-8"))
    patched_engine = [p for p in experiment["package"] if p["name"]=="mdictlib"]
    require(len(patched_engine)==1 and patched_engine[0]["version"]=="0.2.8" and "source" not in patched_engine[0],"Expected patched path dependency")
    require(any(p["name"]=="studio-legacy-sort-experiment" for p in experiment["package"]),"Wrong experiment lockfile")
    sort_report = json.loads((sort_dir/"sort-report.json").read_text(encoding="utf-8"))
    require(sort_report["status"]=="experimental_sort_subset_passed","Sort report did not pass")
    require(sort_report["decision"]=="candidate_only","Evidence must not imply production qualification")
    require(set(sort_report["profiles"])==set(oracle),"Incomplete sort profile evidence")
    for profile, expected_order in oracle.items():
        result=sort_report["profiles"][profile]
        require(result["physical_order"]==expected_order and result["physical_order_matches"] and result["exact_lookups_pass"],f"Sort evidence mismatch: {profile}")
        require(result["key_blocks"]>1,f"No multiblock coverage: {profile}")
    for flag in ["duplicate_ties_and_multiblock_exact_lookups","header_and_reader_normalization_unchanged","upstream_default_order_unchanged"]:
        require(sort_report[flag] is True,f"Missing passing invariant: {flag}")
    safari_dir = ROOT/"docs/evidence/safari-user-run"
    provenance=json.loads((safari_dir/"provenance.json").read_text(encoding="utf-8"))
    for name, expected in provenance["files"].items():
        require(hashlib.sha256((safari_dir/name).read_bytes()).hexdigest()==expected,f"Safari report changed: {name}")
    print("PASS retained sorting report (4 profiles), experiment lock, and Safari report integrity")
    interop_dir=ROOT/"docs/evidence/interop-v1-user-run"
    provenance=json.loads((interop_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((interop_dir/name).read_bytes()).hexdigest()==expected,f"Interop evidence changed: {name}")
    interop=json.loads((interop_dir/"interop-report.json").read_text(encoding="utf-8"))
    require(interop["status"]=="failed" and len(interop["checks"])==14,"Unexpected historical interop result")
    require(sum(v["status"]=="passed" for v in interop["checks"].values())==2,"Historical interop pass count changed")
    print("PASS historical failed interoperability report preserved")
    interop_dir=ROOT/"docs/evidence/interop-v2-user-run"
    provenance=json.loads((interop_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((interop_dir/name).read_bytes()).hexdigest()==expected,f"Interop v2 evidence changed: {name}")
    interop=json.loads((interop_dir/"interop-report.json").read_text(encoding="utf-8"))
    require(interop["status"]=="passed" and len(interop["checks"])==14,"Unexpected revision-2 result")
    require(interop["harness_revision"]==2 and interop["writer_patch_revision"]==2,"Unexpected interop revision")
    require(all(v["status"]=="passed" for v in interop["checks"].values()),"Incomplete interop pass")
    for name in ["Cargo.lock","experiments/legacy-sort/Cargo.lock","patches/studio_legacy_sort.rs"]:
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==interop["source_sha256"][name],f"Current dependency/sort source differs from passing interop: {name}")
    require(interop["source_sha256"]["vendor/mdictlib-0.2.8-studio-sort-v2/src/write/mod.rs"]=="5d599a2de8c7b202a84c4ed0f74cc1dddc328110444dfac968b2f0f6822a4ebc","Passing writer fingerprint changed")
    print("PASS revision-2 interoperability evidence: 14/14")
    codec_dir=ROOT/"docs/evidence/metadata-v1-user-run"
    provenance=json.loads((codec_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((codec_dir/name).read_bytes()).hexdigest()==expected,f"Codec evidence changed: {name}")
    codec=json.loads((codec_dir/"metadata-codec-report.json").read_text(encoding="utf-8"))
    checks=codec["checks"]
    require(codec["status"]=="failed" and len(checks)==111,"Unexpected original codec result")
    require(sum(v["status"]=="passed" for v in checks.values())==77,"Codec pass count changed")
    require(sum(v["status"]=="failed" for v in checks.values())==34,"Codec failure count changed")
    rust=[v for k,v in checks.items() if k.startswith("rust-")]
    require(len(rust)==28 and all(v["status"]=="passed" for v in rust),"Rust codec evidence changed")
    print("PASS original codec evidence retained: 77 passed, 34 failed")
    latest_dir=ROOT/"docs/evidence/v3-user-run"
    provenance=json.loads((latest_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((latest_dir/name).read_bytes()).hexdigest()==expected,f"V3 evidence changed: {name}")
    interop=json.loads((latest_dir/"interop-report.json").read_text(encoding="utf-8"))
    require(interop["status"]=="passed" and interop["writer_patch_revision"]==3 and len(interop["checks"])==14,"Unexpected v3 interop result")
    require(all(v["status"]=="passed" for v in interop["checks"].values()),"Incomplete v3 interoperability evidence")
    codec=json.loads((latest_dir/"metadata-codec-report.json").read_text(encoding="utf-8"))
    require(codec["status"]=="blocked" and not codec["checks"],"Unexpected historical blocked codec result")
    require(codec["setup_error"]=="'tuple' object has no attribute 'writer_revision'","Historical harness failure changed")
    print("PASS v3 reports/logs retained: 14 interop passes; metadata blocked before observations")
    latest_dir=ROOT/"docs/evidence/metadata-v3-completed-user-run"
    provenance=json.loads((latest_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((latest_dir/name).read_bytes()).hexdigest()==expected,f"Completed v3 evidence changed: {name}")
    codec=json.loads((latest_dir/"metadata-codec-report.json").read_text(encoding="utf-8"))
    require(codec["status"]=="failed" and codec["writer_patch_revision"]==3 and codec["harness_revision"]==3,"Unexpected completed codec revision")
    counts={status:sum(v["status"]==status for v in codec["checks"].values()) for status in ["passed","failed","unsupported","blocked"]}
    require(counts==codec["counts"]=={"passed":91,"failed":10,"unsupported":2,"blocked":8},"Completed codec counts changed")
    for key,result in codec["checks"].items():
        if result["status"]=="failed":
            require(key.startswith("forward-") and key.endswith("-xml") and '"StyleSheet"' in result["error"],"New unclassified codec failure")
        if result["status"]=="blocked":
            require(all(codec["checks"][d]["status"]=="unsupported" for d in result["dependencies"]),"Incorrect dependency evidence")
    for style in ["mdict-utils","mdxbuilder"]:
        for suffix in ["write","rust-records","python-records","rust-metadata","xml"]:
            require(codec["checks"][f"reverse-utf16le-{style}-{suffix}"]["status"]=="passed","Reverse UTF-16 evidence differs")
        require(codec["checks"][f"forward-utf16le-{style}-records"]["status"]=="passed","Forward UTF-16 evidence differs")
    print("PASS completed v3 codec evidence: 91 passed, 10 stylesheet differences, 2 unsupported, 8 blocked")
    audit_dir=ROOT/"docs/evidence/real-corpus-local-audit"
    provenance=json.loads((audit_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((audit_dir/name).read_bytes()).hexdigest()==expected,f"Real corpus audit evidence changed: {name}")
    require(hashlib.sha256((ROOT/"scripts/v2_audit.py").read_bytes()).hexdigest()==provenance["auditor_sha256"],"Auditor source differs from local evidence")
    audit=json.loads((audit_dir/"structural-audit.json").read_text(encoding="utf-8"))
    require(audit["native_readers"]==audit["Rust_engine"]==audit["mdict_utils"]=="NOT_RUN","Structural audit must not imply engine/native qualification")
    expected_counts={"CC-CEDICT 092026.mdx":202884,"CC-CEDICT 092026.mdd":17,"almaanyEnAr-ArEn.mdx":82812,"新华成语词典（第2版）.mdx":10414}
    require(len(audit["cases"])==4,"Incomplete real corpus structural evidence")
    for case in audit["cases"]:
        require(case["status"]=="structural_audit_passed" and case["records"]==expected_counts[case["file"]],"Real corpus audit count/status changed")
        require(case["sha256"]==case["sha256_after"]==provenance["input_sha256"][case["file"]],"Input integrity observation changed")
    print("PASS local structural-stage evidence: 296110 MDX records, 17 resources; distinct from engine/native qualification")
    corpus_dir=ROOT/"docs/evidence/real-corpus-user-run"
    provenance=json.loads((corpus_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((corpus_dir/name).read_bytes()).hexdigest()==expected,f"Corpus evidence changed: {name}")
    corpus=json.loads((corpus_dir/"corpus-report.json").read_text(encoding="utf-8"))
    require(corpus["status"]=="passed_reader_comparison_only" and len(corpus["cases"])==4,"Unexpected corpus result")
    lookups=0
    expected_counts={"cc-cedict-mdx":202884,"cc-cedict-mdd":17,"almaany-mdx":82812,"chinese-idioms-mdx":10414}
    for case in corpus["cases"]:
        require(case["status"]=="passed" and case["different_key_payload_counts"]==0 and not case["metadata_differences"],"Corpus comparison failed")
        for result in case["engines"].values():require(result["status"]=="passed" and result["records"]==expected_counts[case["id"]],"Corpus reader count differs")
        require(case["sha256"]==case["sha256_after"],"Corpus input changed")
        require(all(v["status"]=="passed" for v in case["lookups"].values()),"Corpus lookup failed")
        lookups+=len(case["lookups"])
    require(lookups==36,"Corpus sampled lookup count changed")
    print("PASS uploaded Rust/Python corpus evidence: 4 cases, 36 lookups, matching metadata; native rendering remains unrun")
    crash_dir=ROOT/"docs/evidence/native-import-crash"
    provenance=json.loads((crash_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((crash_dir/name).read_bytes()).hexdigest()==expected,f"Native crash evidence changed: {name}")
    report=json.loads((crash_dir/"reader-fixture-report.json").read_text(encoding="utf-8"))
    observation=json.loads((crash_dir/"observation.json").read_text(encoding="utf-8"))
    require(len(report["checks"])==8 and all(v["status"]=="passed" for v in report["checks"].values()),"Automated fixture report changed")
    pair=next(v for v in report["fixtures"] if v["name"]=="reader-utf8-mdict-utils")
    require(pair["mdx_sha256"]==observation["MDX"]["sha256"] and pair["mdd_sha256"]==observation["MDD"]["sha256"],"Crash fixture identity differs")
    require(observation["affected_reader"]=="MDict for macOS 2.2.6 (build 200)" and observation["crash_report_received"] is True,"Confirmed MDict crash evidence differs")
    require(observation["native_pair_result"]=="FAIL_USER_REPORTED_IMPORT_CRASH" and observation["GoldenDict_result"].startswith("NOT_RUN"),"Do not infer a GoldenDict result")
    binary=json.loads((crash_dir/"binary-audit.json").read_text(encoding="utf-8"))
    mdx=next(c for c in binary["cases"] if c["file"].endswith(".mdx"))
    require(mdx["sha256"]==observation["second_pair"]["MDX"]["sha256"] and mdx["records"]==mdx["records_without_terminal_null"]==13,"Actual crashing record-terminator evidence changed")
    require(all(c["status"]=="structural_audit_passed" for c in binary["cases"]),"Crashing pair structural evidence changed")
    print("PASS evidence integrity: automated checks retained alongside native import failure; qualification remains blocked")
    wire_dir=ROOT/"docs/evidence/native-wire-v4-user-run"
    provenance=json.loads((wire_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((wire_dir/name).read_bytes()).hexdigest()==expected,f"V4 wire evidence changed: {name}")
    wire=json.loads((wire_dir/"native-wire-report.json").read_text(encoding="utf-8"))
    require(wire["writer_revision"]==4 and wire["status"]=="offline_checks_passed_native_untested","Unexpected v4 wire result")
    require(wire["native_readers"]=="NOT_RUN_DO_NOT_IMPORT","Do not infer native compatibility")
    require(len(wire["checks"])==16 and sum(k.endswith('.mdx') for k in wire["checks"])==8,"Incomplete v4 checks")
    for name,check in wire["checks"].items():
        require(check["status"]=="passed" and all(check["checks"].values()),f"V4 wire check failed: {name}")
        require(check["sha256"]==check["structural_audit"]["sha256"]==check["structural_audit"]["sha256_after"],"V4 fixture hash differs")
        if name.endswith('.mdx'):
            require(check["structural_audit"]["records_without_terminal_null"]==0,"V4 record terminator missing")
    require(wire["metadata_result"]["status"]=="failed" and wire["metadata_result"]["counts"]=={"passed":91,"failed":10,"unsupported":2,"blocked":8},"V4 unresolved metadata inventory changed")
    require([(s["name"],s["returncode"]) for s in wire["steps"]]==[("prepare",0),("rust-tests",0),("fixture-build",0),("interop",0),("metadata",1)],"V4 step results differ")
    print("PASS uploaded v4 aggregate report: 16 wire checks passed; native and stylesheet gates unresolved")
    minimal_dir=ROOT/"docs/evidence/minimal-controls-user-run"
    provenance=json.loads((minimal_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((minimal_dir/name).read_bytes()).hexdigest()==expected,f"Minimal control evidence changed: {name}")
    minimal=json.loads((minimal_dir/"minimal-controls-report.json").read_text(encoding="utf-8"))
    observation=json.loads((minimal_dir/"native-observations.json").read_text(encoding="utf-8"))
    require(minimal["writer_revision"]==5 and minimal["profile"]=="HeaderLiteralC" and minimal["status"]=="offline_controls_passed_native_untested","Unexpected minimal control report")
    require(minimal["native_readers"]=="NOT_RUN_DO_NOT_IMPORT","Offline report must remain distinct from manual native reports")
    require(len(minimal["checks"])==6 and sum(c["lookups"] for c in minimal["checks"].values())==58,"Incomplete minimal lookup inventory")
    require(set(observation["fixtures"])==set(minimal["checks"]),"Manual fixture inventory differs")
    for name,check in minimal["checks"].items():
        require(check["status"]=="passed" and check["wire"]["status"]=="passed" and all(check["wire"]["checks"].values()),"Minimal offline invariant failed")
        native=observation["fixtures"][name]
        require(native["entry_lookup"]=="PASS_USER_REPORTED_BOTH_READERS" and native["sha256"]==check["wire"]["sha256"],"Manual report fixture identity differs")
    print("PASS minimal evidence: 58 offline lookup checks; six manual native lookup reports kept separate from visual rendering")
    style_dir=ROOT/"docs/evidence/stylesheet-native-user-run"
    provenance=json.loads((style_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance["files"].items():
        require(hashlib.sha256((style_dir/name).read_bytes()).hexdigest()==expected,f"Stylesheet evidence changed: {name}")
    style=json.loads((style_dir/"stylesheet-controls-report.json").read_text(encoding="utf-8"))
    native=json.loads((style_dir/"native-observations.json").read_text(encoding="utf-8"))
    require(style["status"]=="offline_stylesheet_controls_passed_native_untested" and len(style["checks"])==2,"Unexpected offline stylesheet report")
    for check in style["checks"].values():
        require(check["status"]=="passed" and check["raw_stylesheet_preserved"] and check["python_marker_expansion_matches_inline_controls"],"Offline stylesheet check differs")
        require(check["standard_XML_stylesheet_matches_raw"] is False,"Do not hide XML normalization difference")
    require(native["MDict"]["result"]=="FAIL_USER_REPORTED_CRASH_ALONE_AND_GROUP","MDict stylesheet crash must remain recorded")
    require(native["GoldenDict"]["result"]=="FAIL_USER_REPORTED_MARKER_BLUE_PLAIN_BLACK_BOTH_ENCODINGS","Do not infer GoldenDict visual success from entry lookup")
    from reference_builder import verify_kit
    verify_kit(ROOT/"baseline/reference-builder-kit")
    print("PASS stylesheet evidence integrity: offline passes remain distinct from both native failures; reference kit bound to source")
    official_dir=ROOT/"docs/evidence/official-stylesheet-reference"
    provenance=json.loads((official_dir/"provenance.json").read_text(encoding="utf-8"))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((official_dir/name).read_bytes()).hexdigest()==expected,f"Official reference evidence changed: {name}")
    from stylesheet_controls import official_reference_stylesheet, specification, OFFICIAL_SHA256
    style=official_reference_stylesheet()
    require(len(style)==147 and style==specification()['cases'][0]['stylesheet']+'\n',"Native-tested reference stylesheet differs beyond the candidate's final LF")
    native=json.loads((official_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(native['fixture_sha256']==OFFICIAL_SHA256 and len(native['reader_results'])==2 and all(v=='PASS_USER_REPORTED_FIVE_ENTRIES_AND_FORMATTING' for v in native['reader_results'].values()),'Official native observations differ')
    print('PASS official reference identity and native reports; new Rust serialization candidate remains untested natively')
    corrected_dir=ROOT/'docs/evidence/stylesheet-wire-user-run'
    provenance=json.loads((corrected_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((corrected_dir/name).read_bytes()).hexdigest()==expected,f'Corrected stylesheet evidence changed: {name}')
    corrected=json.loads((corrected_dir/'stylesheet-controls-report.json').read_text(encoding='utf-8'))
    native=json.loads((corrected_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(corrected['status']=='offline_stylesheet_controls_passed_native_untested' and corrected['fixture_wrapper_revision']==6 and len(corrected['checks'])==2,'Unexpected corrected stylesheet report')
    for name,check in corrected['checks'].items():
        require(check['status']=='passed' and check['stylesheet_matches_native_tested_official_reference'] and check['definition_text_matches_original_failed_control'],'Corrected stylesheet contract differs')
        require(check['raw_stylesheet_preserved'] is False and check['raw_stylesheet_matches_selected_contract'],'Intentional final LF serialization must stay explicit')
        require(check['structural_audit']['embedded_stylesheet_characters']==147 and native['fixtures'][name]==check['wire']['sha256'],'Native corrected fixture identity differs')
    require(native['result']=='PASS_USER_REPORTED_VISUAL_AND_RESTART_CHECKS_BOTH_READERS_BOTH_ENCODINGS','Corrected native evidence differs')
    from resource_controls import specification as resource_spec, validate_asset_graph
    validate_asset_graph(resource_spec()['cases'][0])
    print('PASS corrected synthetic stylesheet results and MDD fixture graph; native MDD rendering remains pending')
    mdd_dir=ROOT/'docs/evidence/MDD-resources-user-run'
    provenance=json.loads((mdd_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((mdd_dir/name).read_bytes()).hexdigest()==expected,f'MDD native evidence changed: {name}')
    resources=json.loads((mdd_dir/'resource-controls-report.json').read_text(encoding='utf-8'))
    native=json.loads((mdd_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(resources['status']=='offline_MDD_controls_passed_native_untested' and resources['fixture_wrapper_revision']==7,'Unexpected offline MDD report')
    require(len(resources['checks'])==4 and sum(c['lookups'] for c in resources['checks'].values())==22,'Incomplete MDD observation inventory')
    for name,check in resources['checks'].items():
        require(check['status']=='passed' and check['wire']['status']=='passed' and native['fixtures'][name]==check['wire']['sha256'],'MDD fixture result or identity differs')
    require(native['result']=='PASS_USER_REPORTED_CSS_IMAGE_FONT_BOTH_ENCODINGS_BOTH_READERS','MDD native result differs')
    print('PASS synthetic MDD offline and manual native rendering evidence; real rebuild remains untested')
    rebuilt_dir=ROOT/'docs/evidence/real-rebuild-user-run'
    provenance=json.loads((rebuilt_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((rebuilt_dir/name).read_bytes()).hexdigest()==expected,f'Real rebuild evidence changed: {name}')
    rebuilt=json.loads((rebuilt_dir/'real-rebuild-report.json').read_text(encoding='utf-8'))
    require(rebuilt['engine_revision']==6 and rebuilt['status']=='rebuild_records_passed_companions_pending','Unexpected real rebuild status')
    require(len(rebuilt['cases'])==4 and sum(len(c['lookups']) for c in rebuilt['cases'])==36,'Incomplete real rebuild lookup inventory')
    require(sum(c['builder']['records'] for c in rebuilt['cases'] if c['output_name'].endswith('.mdx'))==296110,'Real MDX rebuild count differs')
    require(sum(c['builder']['records'] for c in rebuilt['cases'] if c['output_name'].endswith('.mdd'))==17,'Real MDD rebuild count differs')
    for case in rebuilt['cases']:
        require(case['status']=='passed_rebuild_records_metadata_and_order' and case['different_key_payload_counts']==0,'Real rebuild record comparison differs')
        require(case['structural_audit']['status']=='structural_audit_passed' and case['structural_audit']['sha256']==case['output_sha256'],'Real rebuild structural evidence differs')
        scans=[case[phase][reader] for phase in ['source_scans','rebuilt_scans'] for reader in ['r','p']]
        require(len({s['ordered_key_payload_sha256'] for s in scans})==1 and all(s['attributes']==scans[0]['attributes'] for s in scans),'Real rebuild order/metadata evidence differs')
    pending=[c for c in rebuilt['companions'] if c['status'] not in {'copied_exact_bytes','rebuilt_dictionary_companion'}]
    require(len(pending)==1 and pending[0]['relative_output']=='fonts/amiri-regular.ttf','Unexpected pending rebuild companion')
    require(all(c['before']==c['after'] for c in rebuilt['input_integrity'].values()),'Original input integrity changed')
    print('PASS four real rebuilds and 36 lookups; only Amiri completion and native rebuilt rendering remain pending for this gate')
    finalized_dir=ROOT/'docs/evidence/real-rebuild-finalized-user-run'
    provenance=json.loads((finalized_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((finalized_dir/name).read_bytes()).hexdigest()==expected,f'Finalized real rebuild evidence changed: {name}')
    finalized=json.loads((finalized_dir/'real-rebuild-report.json').read_text(encoding='utf-8'))
    native=json.loads((finalized_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(finalized['status']=='real_rebuild_offline_passed_native_untested' and len(finalized['cases'])==4,'Unexpected finalized rebuild result')
    require(all(c['status'] in {'copied_exact_bytes','rebuilt_dictionary_companion'} for c in finalized['companions']),'A finalized companion remains pending')
    require(all(c['before']==c['after'] for c in finalized['input_integrity'].values()),'Finalized original input integrity differs')
    require(native['result']=='PASS_USER_REPORTED_REAL_REBUILT_RENDERING_BOTH_READERS','Native real rebuild report differs')
    for case in finalized['cases']:require(native['fixtures'][case['output_name']]==case['output_sha256'],'Native rebuilt file identity differs')
    print('PASS finalized real corpus and separate manual native acceptance; bounded stress results remain pending')
    stress_dir=ROOT/'docs/evidence/stress-user-run'
    provenance=json.loads((stress_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((stress_dir/name).read_bytes()).hexdigest()==expected,f'Stress evidence changed: {name}')
    stress=json.loads((stress_dir/'stress-report.json').read_text(encoding='utf-8'))
    require(stress['status']=='standard_stress_subset_passed_M1_open' and stress['profile']=='standard','Unexpected stress result')
    require(stress['build']['entries']==49152 and stress['build']['resources']==128 and stress['mdx_file_bytes']>32*1024*1024,'Standard stress volume differs')
    require(all(p['rss_within_budget'] for p in stress['processes'].values()),'A stress process exceeded its budget')
    require(stress['processes']['stress-build']['peak_rss_bytes']==240140288 and stress['processes']['stress-verify']['peak_rss_bytes']==6078464,'Measured stress RSS changed')
    require(stress['checks']['checksum_policy']['reader_accepted'] is True,'Do not hide diagnostic default checksum acceptance')
    for check in ['write_error_no_publication','overwrite_refused','forced_termination_cleanup','fresh_job_after_failures','prior_rebuild_limit_enforced']:
        require(stress['checks'][check]['status']=='passed',f'Stress failure behavior changed: {check}')
    for original,snapshot in [('experiments/real-rebuild/src/main.rs','qualified-main.rs'),('experiments/real-rebuild/src/stress.rs','qualified-stress.rs')]:
        require(hashlib.sha256((stress_dir/snapshot).read_bytes()).hexdigest()==stress['source_sha256'][original],'Qualified stress source snapshot differs')
    print('PASS bounded standard stress report and matching source snapshots')
    checksum_dir=ROOT/'docs/evidence/checksum-user-run'
    provenance=json.loads((checksum_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((checksum_dir/name).read_bytes()).hexdigest()==expected,f'Checksum evidence changed: {name}')
    checksum=json.loads((checksum_dir/'checksum-report.json').read_text(encoding='utf-8'))
    require(checksum['status']=='strict_checksum_matrix_and_real_scans_passed_M1_open' and checksum['checksum_policy']=='Verify','Unexpected strict checksum result')
    mutations=['xml_checksum','key_header_checksum','key_info_checksum','first_key_checksum','last_key_checksum','first_record_checksum','last_record_checksum','last_record_zlib_trailer']
    for kind in ['mdx','mdd']:
        valid=checksum['checks'][kind+'-valid']
        require(valid['status']=='passed' and valid['verify']['status']=='validated','Valid checksum control differs')
        for mutation in mutations:
            check=checksum['checks'][kind+'-'+mutation]
            require(check['status']=='passed_strict_rejection' and check['verify']['status']=='rejected' and check['independent_error'],'Strict corruption rejection differs')
            expected={'ChecksumMismatch','InvalidData'} if mutation.endswith('zlib_trailer') else {'ChecksumMismatch'}
            require(check['verify']['error_kind'] in expected,'Unexpected checksum error kind')
            if 'record' in mutation:require(check['verify']['phase']=='records','Record corruption was not reached lazily')
        integration=checksum['checks'][kind+'-strict-rebuild-integration']
        require(integration['status']=='passed' and integration['clean_source_and_output_verified'] and integration['corrupted_source_refused_without_publication'],'Strict rebuild integration differs')
    require(len(checksum['real_cases'])==4 and all(c['result']['status']=='validated' and c['result']['checksum_policy']=='Verify' for c in checksum['real_cases']),'Real strict scans incomplete')
    require(sum(c['result']['records'] for c in checksum['real_cases'] if c['id'].endswith('-mdx'))==296110,'Strict MDX count differs')
    require(sum(c['result']['records'] for c in checksum['real_cases'] if c['id'].endswith('-mdd'))==17,'Strict MDD count differs')
    require(all(c['before']==c['after'] for c in checksum['input_integrity'].values()),'Checksum original input changed')
    for original,snapshot in [('experiments/real-rebuild/src/main.rs','qualified-main.rs'),('experiments/real-rebuild/src/strict.rs','qualified-strict.rs'),('scripts/checksum_qualification.py','qualified-checksum_qualification.py')]:
        require(hashlib.sha256((checksum_dir/snapshot).read_bytes()).hexdigest()==checksum['source_sha256'][original],'Qualified checksum source snapshot differs')
    print('PASS strict checksum matrix, rebuild integration and four real scans; fresh TXT/XLSX pack parity remains open')
    fresh_dir=ROOT/'docs/evidence/fresh-pack-user-run'
    provenance=json.loads((fresh_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((fresh_dir/name).read_bytes()).hexdigest()==expected,f'Fresh pack evidence changed: {name}')
    fresh=json.loads((fresh_dir/'fresh-pack-report.json').read_text(encoding='utf-8'))
    require(fresh['status']=='fresh_source_pack_subset_passed_M1_open' and len(fresh['checks'])==14,'Unexpected fresh pack result')
    mdx_count=mdd_count=0
    for name,case in fresh['checks'].items():
        require(case['status']=='passed','Fresh pack case failed')
        for kind,detail in case['detail'].items():
            require(detail['independent_audit']=='passed' and detail['legacy_full_strict_scan']=='passed','Fresh pack inspection incomplete')
            require(detail['metadata_compared']==['Title','Description'],'Do not widen fresh metadata parity claim')
            for key in detail['metadata_compared']:
                require(detail['rust_attributes'][key]==detail['python_attributes'][key],'Fresh compared metadata differs')
            if kind=='mdx':
                mdx_count+=1
                require(detail['rust_attributes']['StripKey']=='No' and detail['python_attributes']['Stripkey']=='Yes','Do not hide fresh header policy mismatch')
            elif kind=='mdd':mdd_count+=1
            else:require(False,'Unexpected fresh output kind')
    require(mdx_count==14 and mdd_count==2,'Fresh output matrix incomplete')
    require(len(fresh['input_integrity'])==7 and all(c['before']==c['after'] for c in fresh['input_integrity'].values()),'Fresh inputs changed')
    for original,snapshot in [('experiments/real-rebuild/src/main.rs','qualified-main.rs'),('experiments/real-rebuild/src/fresh.rs','qualified-fresh.rs'),('scripts/fresh_pack.py','qualified-fresh_pack.py')]:
        require(hashlib.sha256((fresh_dir/snapshot).read_bytes()).hexdigest()==fresh['source_sha256'][original],'Qualified fresh source snapshot differs')
    print('PASS fresh physical-row packing subset; header/lookup policy and Rust XLSX conversion remain open')
    header_dir=ROOT/'docs/evidence/header-lookup-user-run'
    provenance=json.loads((header_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((header_dir/name).read_bytes()).hexdigest()==expected,f'Header lookup evidence changed: {name}')
    header=json.loads((header_dir/'header-lookup-report.json').read_text(encoding='utf-8'))
    require(header['status']=='failed_header_lookup_qualification' and header['error']=='Conflicting flags were not rejected before rows/lookup','Keep original checker failure explicit')
    require(set(header['checks'])=={'literal-utf8','literal-utf16'},'Literal candidate inventory differs')
    for case in header['checks'].values():
        require(case['status']=='passed' and case['records']==77 and case['lookups']==71 and case['duplicate_key_blocks']==12,'Literal lookup result differs')
        require(case['attributes']['StripKey']=='No' and case['attributes']['Format']=='Html','Literal header differs')
    require(set(header['alias_checks'])=={'alias-no','alias-yes'} and all(c['status']=='passed' for c in header['alias_checks'].values()),'Header spelling alias checks differ')
    require(header['flag_only_negative_control']['status']=='passed_mismatch_detected','Flag/order negative control differs')
    from header_lookup import conflict_rejected
    log=(header_dir/'conflicting-aliases.log').read_bytes()
    require(log.startswith(b'\nSTDERR:\n') and conflict_rejected(1,b'',log[len(b'\nSTDERR:\n'):]),'Received conflict log is not the expected upstream refusal')
    # Exit 1 is established by the qualified CLI error branch; the historical
    # log itself contains only stdout/stderr. Resume re-observes the actual exit.
    for original,snapshot in [('scripts/header_lookup.py','qualified-header_lookup.py'),('experiments/real-rebuild/src/policy.rs','qualified-policy.rs'),('experiments/real-rebuild/src/main.rs','qualified-main.rs')]:
        require(hashlib.sha256((header_dir/snapshot).read_bytes()).hexdigest()==header['source_sha256'][original],'Qualified header source snapshot differs')
    print('PASS retained literal/alias results and upstream conflict diagnostic; corrected resume and native checks pending')
    finalized_dir=ROOT/'docs/evidence/header-lookup-finalized-user-run'
    provenance=json.loads((finalized_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((finalized_dir/name).read_bytes()).hexdigest()==expected,f'Final header evidence changed: {name}')
    finalized=json.loads((finalized_dir/'header-lookup-report.json').read_text(encoding='utf-8'))
    native=json.loads((finalized_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(finalized['status']=='literal_header_lookup_offline_passed_legacy_diagnostics_recorded_native_pending','Unexpected finalized header status')
    require(finalized['checks']==header['checks'] and finalized['alias_checks']==header['alias_checks'],'Resume changed previously qualified observations')
    require(finalized['conflicting_aliases']['returncode']==1 and finalized['conflicting_aliases']['stdout_empty'],'Conflict refusal was not re-observed cleanly')
    require(finalized['finalization']['original_report_sha256']==hashlib.sha256((header_dir/'header-lookup-report.json').read_bytes()).hexdigest(),'Finalization refers to another original report')
    require(finalized['finalization']['dictionaries_regenerated'] is False and finalized['finalization']['Rust_full_lookup_matrix_repeated'] is False,'Resume scope differs')
    for original,snapshot in [('scripts/finalize_header_lookup.py','qualified-finalize_header_lookup.py'),('scripts/header_lookup.py','qualified-header_lookup.py')]:
        require(hashlib.sha256((finalized_dir/snapshot).read_bytes()).hexdigest()==finalized['finalization']['source_sha256'][original],'Finalization source snapshot differs')
    require(native['result']=='PASS_USER_REPORTED_NO_MISSING_OR_CRASHES' and native['fixtures']==finalized['native_candidates'],'Native header observations differ')
    for name,case in finalized['checks'].items():require(finalized['native_candidates'][f'07-header-{name}.mdx']==case['sha256'],'Native header fixture hash differs')
    print('PASS finalized header report and separate user native acceptance; broader Unicode qualification pending')
    unicode_dir=ROOT/'docs/evidence/unicode-version-user-run'
    provenance=json.loads((unicode_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((unicode_dir/name).read_bytes()).hexdigest()==expected,f'Unicode evidence changed: {name}')
    unicode=json.loads((unicode_dir/'unicode-profile-report.json').read_text(encoding='utf-8'))
    mapping=unicode['lowercase_mapping']
    require(unicode['status']=='failed_unicode_profile_qualification' and not unicode['checks'],'Do not promote blocked Unicode run')
    require(mapping['scalars_compared']==1112064 and mapping['python_unicode_version']=='16.0.0' and mapping['rust_unicode_version']==[17,0,0],'Unicode version comparison differs')
    require(mapping['python_changed_scalars']==1460 and mapping['rust_changed_scalars']==1488 and len(mapping['differences'])==28,'Unicode delta differs')
    require(all(d['python']==d['input'] and d['rust']!=d['input'] for d in mapping['differences']),'Unicode difference classification differs')
    require(len(unicode['contexts'])==45 and all(c['string_lower']==c['python_string_lower'] and c['scalar_lower']==c['python_scalar_lower'] for c in unicode['contexts']),'Selected Unicode contexts differ')
    for original,snapshot in [('scripts/unicode_profiles.py','qualified-unicode_profiles.py'),('experiments/real-rebuild/src/unicode.rs','qualified-unicode.rs')]:
        require(hashlib.sha256((unicode_dir/snapshot).read_bytes()).hexdigest()==unicode['source_sha256'][original],'Qualified Unicode source snapshot differs')
    print('PASS retained Unicode16/17 difference evidence; versioned candidate qualification pending')
    casing_dir=ROOT/'docs/evidence/casing-policy-user-run'
    provenance=json.loads((casing_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((casing_dir/name).read_bytes()).hexdigest()==expected,f'Casing candidate evidence changed: {name}')
    casing=json.loads((casing_dir/'casing-policy-report.json').read_text(encoding='utf-8'))
    require(casing['status']=='versioned_casing_candidate_passed_engine_integration_pending_M1_open' and casing['engine_integrated'] is False,'Do not broaden original casing scope')
    require(casing['scalar_checks']['scalars_compared']==1112064 and casing['scalar_checks']['legacy16_differences']==0,'Casing scalar result differs')
    require(len(casing['scalar_checks']['modern17_differences'])==28 and casing['context_checks']['words_checked']==2017 and casing['context_checks']['legacy16_differences']==0,'Casing context result differs')
    pinned=ROOT/'baseline/unicode/unicode16-casing.json'
    require(hashlib.sha256(pinned.read_bytes()).hexdigest()==casing['policy']['sha256']==provenance['policy_sha256']=='f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071','Pinned Unicode16 data differs')
    for original,snapshot in [('experiments/real-rebuild/src/casing.rs','qualified-casing.rs'),('scripts/casing_policy.py','qualified-casing_policy.py')]:
        require(hashlib.sha256((casing_dir/snapshot).read_bytes()).hexdigest()==casing['source_sha256'][original],'Qualified casing source snapshot differs')
    print('PASS casing candidate and pinned reviewed data; adapter integration runtime qualification pending')
    integrated_dir=ROOT/'docs/evidence/integrated-casing-user-run'
    provenance=json.loads((integrated_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((integrated_dir/name).read_bytes()).hexdigest()==expected,f'Integrated casing evidence changed: {name}')
    integrated=json.loads((integrated_dir/'integrated-casing-report.json').read_text(encoding='utf-8'))
    require(integrated['status']=='versioned_adapter_sort_lookup_roundtrip_passed_native_and_production_pending_M1_open','Unexpected integrated adapter result')
    require(integrated['adapter_integrated'] is True and integrated['engine_builtin_locator_changed'] is False,'Do not imply built-in locator changed')
    require(len(integrated['checks'])==4 and all(c['status']=='passed' and c['records']==166 and c['queries']==192 and c['reopened_in_separate_process'] and c['physical_and_lookup_order_exact'] for c in integrated['checks'].values()),'Integrated case coverage differs')
    for name,case in integrated['checks'].items():
        require(case['builtin_locator_difference_count']==(31 if name.startswith('unicode16') else 3),'Built-in locator diagnostic differs')
    require(len(integrated['policy_difference_queries'])==28 and len(integrated['negative_checks'])==3 and set(integrated['negative_checks'].values())=={'rejected'},'Integrated policy distinction/refusal checks differ')
    for original,snapshot in [('experiments/real-rebuild/src/main.rs','qualified-main.rs'),('experiments/real-rebuild/src/casing.rs','qualified-casing.rs'),('experiments/real-rebuild/src/integrated.rs','qualified-integrated.rs'),('scripts/integrated_casing.py','qualified-integrated_casing.py')]:
        require(hashlib.sha256((integrated_dir/snapshot).read_bytes()).hexdigest()==integrated['source_sha256'][original],'Qualified integration source snapshot differs')
    print('PASS integrated versioned adapter results; retained report remains historically native-pending')
    native_dir=ROOT/'docs/evidence/native-unicode-user-run'
    provenance=json.loads((native_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((native_dir/name).read_bytes()).hexdigest()==expected,f'Native Unicode evidence changed: {name}')
    staged=json.loads((native_dir/'native-unicode-report.json').read_text(encoding='utf-8'))
    require(staged['status']=='native_unicode_inputs_prepared_native_untested' and staged['native_observations']=='PENDING','Do not relabel original staging result')
    require(staged['source_report_sha256']==hashlib.sha256((integrated_dir/'integrated-casing-report.json').read_bytes()).hexdigest(),'Native source report differs')
    require(len(staged['cases'])==4,'Native fixture inventory differs')
    require({c['sha256'] for c in staged['cases']}=={c['sha256'] for c in integrated['checks'].values()},'Staged native file identities differ')
    observed=json.loads((native_dir/'native-observations.json').read_text(encoding='utf-8'))
    require(observed['result']=='PASS_USER_REPORTED_FOCUSED_NATIVE_UNICODE_AND_RESTART' and observed['files_confirmed']==4 and observed['raw_queries_per_file']==13,'Native confirmation scope differs')
    require(observed['required_stored_markers_accessible'] and observed['all_eight_duplicate_payloads_accessible'] and not observed['crashes_reported'],'Missing native confirmation')
    require(observed['restart_checks']=='passed_user_confirmed' and observed['exhaustive_166_record_native_verification'] is False,'Do not broaden focused native scope')
    print('PASS focused native Unicode and restart: separate user-reported observations; no local native execution')
    closeout_dir=ROOT/'docs/evidence/closeout-first-user-run'
    provenance=json.loads((closeout_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((closeout_dir/name).read_bytes()).hexdigest()==expected,f'Initial closeout evidence changed: {name}')
    closeout=json.loads((closeout_dir/'m1-closeout-report.json').read_text(encoding='utf-8'))
    require(closeout['status']=='regression_failed' and closeout['M1_complete'] is False,'Do not promote initial closeout failure')
    require([s['name'] for s in closeout['steps']]==['evidence','vendor-v2','vendor-v6','baseline','python-contracts'],'Unexpected initial closeout coverage')
    require(all(s['status']=='passed' and s['returncode']==0 for s in closeout['steps'][:4]),'Initial successful gates differ')
    require(closeout['steps'][-1]['status']=='failed' and closeout['steps'][-1]['returncode']==1,'Initial Python failure differs')
    print('PASS retained first closeout failure; original result unchanged')
    final_dir=ROOT/'docs/evidence/closeout-final-user-run'
    provenance=json.loads((final_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((final_dir/name).read_bytes()).hexdigest()==expected,f'Final closeout evidence changed: {name}')
    final=json.loads((final_dir/'m1-closeout-report.json').read_text(encoding='utf-8'))
    require(final['status']=='regression_passed_engine_decision_pending','Final regression did not pass')
    require(final['M1_complete'] is False and final['engine_selected'] is False,'Do not rewrite original decision-pending report')
    expected_steps=['evidence','vendor-v2','vendor-v6','baseline','python-contracts','rust-root','rust-legacy-sort','rust-adapter']
    require([s['name'] for s in final['steps']]==expected_steps,'Final regression inventory differs')
    require(all(s['status']=='passed' and s['returncode']==0 for s in final['steps']),'Final regression contains an unsuccessful step')
    require(final['qualified_source_sha256']==integrated['source_sha256'],'Final report integration identity differs')
    for name,expected in final['lock_sha256'].items():
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,f'Final regression lock differs: {name}')
    status=json.loads((ROOT/'docs/STATUS.json').read_text(encoding='utf-8'))['M1']
    require(status['M1_complete'] is True and status['engine_selected'] is True and status['production_readiness'] is False,'Scoped reviewed decision differs')
    require(status['remaining_gates']==[] and (ROOT/status['engine_decision']).is_file(),'Missing reviewed engine decision')
    print('PASS final user-run eight-gate regression; separate reviewed M1 completion for scoped M2 engine selection')
    foundation_dir=ROOT/'docs/evidence/m2-foundation-user-run'
    provenance=json.loads((foundation_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((foundation_dir/name).read_bytes()).hexdigest()==expected,f'M2 foundation evidence changed: {name}')
    foundation=json.loads((foundation_dir/'m2-foundation-report.json').read_text(encoding='utf-8'))
    require(foundation['status']=='m2_foundation_passed_remaining_M2_work_pending' and foundation['M2_complete'] is False,'Do not broaden M2 foundation result')
    expected_steps=['core-tests','core-smoke']+[f'reopen-utf8-{i}' for i in range(2,6)]+[f'reopen-utf16-{i}' for i in range(6,10)]
    require([s['name'] for s in foundation['steps']]==expected_steps and all(s['returncode']==0 for s in foundation['steps']),'M2 command coverage differs')
    require(len(foundation['checks'])==2 and {c['encoding'] for c in foundation['checks']}=={'utf8','utf16'},'M2 encoding inventory differs')
    require(all(c['records']==15 and c['independent_python_exact_rows']=='passed' and c['wire_audit']=='passed' and c['separate_process_reopen']=='passed' for c in foundation['checks']),'M2 foundation check coverage differs')
    require(provenance['source_snapshots']=={'qualified/'+name:h for name,h in foundation['source_sha256'].items()},'M2 source snapshot bindings differ')
    print('PASS user-run M2 core foundation: ten commands, two 15-record outputs and exact qualified snapshots; M2 remains partial')
    resources_dir=ROOT/'docs/evidence/m2-resources-user-run'
    provenance=json.loads((resources_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((resources_dir/name).read_bytes()).hexdigest()==expected,f'M2 resource evidence changed: {name}')
    resources=json.loads((resources_dir/'m2-resources-report.json').read_text(encoding='utf-8'))
    require(resources['status']=='m2_resources_passed_remaining_M2_work_pending' and resources['M2_complete'] is False,'Do not broaden resource qualification')
    expected_steps=['resource-tests','resource-smoke']+[f'resource-reopen-{i}' for i in range(6)]+['resource-missing','extract-reopen','extract-existing-refused','unsafe-refused','aliases-refused']
    require([s['name'] for s in resources['steps']]==expected_steps,'M2 resource command inventory differs')
    require(all(s['returncode']==0 for s in resources['steps'][:10]),'M2 resource successful commands differ')
    require([(s['returncode'],s['expected_refusal']) for s in resources['steps'][10:]]==[(1,'destination_exists'),(1,'unsafe_path'),(1,'path_collision')],'M2 refusal classifications differ')
    checks=resources['checks']
    require(checks['resources']==6 and len(checks['extraction_inventory'])==6,'M2 resource inventory differs')
    require(all(checks[key]=='passed' for key in ['independent_python_bytes','wire_audit','separate_process_reopen','existing_destination_preserved','unsafe_and_alias_pack_refusals']),'M2 resource result differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in resources['source_sha256'].items()},'M2 resource snapshot bindings differ')
    require(provenance['Linux_runtime_qualified'] is False,'Do not infer Linux runtime acceptance from Mac result')
    print('PASS user-run M2 resources: six exact resources, ten successes, three controlled refusals and exact snapshots; Mac scope only')
    text_dir=ROOT/'docs/evidence/m2-text-user-run'
    provenance=json.loads((text_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((text_dir/name).read_bytes()).hexdigest()==expected,f'M2 text evidence changed: {name}')
    text=json.loads((text_dir/'m2-text-report.json').read_text(encoding='utf-8'))
    require(text['status']=='m2_text_and_cedict_passed_remaining_M2_work_pending' and text['M2_complete'] is False and text['Rust_XLSX_converters_ported'] is False,'Do not broaden TXT/CC-CEDICT scope')
    require(len(text['steps'])==43 and all(s['returncode']==0 for s in text['steps'][:38]),'M2 text successful command inventory differs')
    require([(s['name'],s['returncode'],s['expected_refusal']) for s in text['steps'][38:]]==[
        ('invalid-utf8-refused',1,'invalid_encoding'),('incomplete-refused',1,'malformed_source'),
        ('legacy-no-lf-refused',1,'unrepresentable_source'),('existing-refused',1,'destination_exists'),
        ('nonascii-tone-refused',1,'unsupported_policy')],'M2 text refusal classifications differ')
    checks=text['checks'];goldens=checks['golden_txt'];pipelines=checks['pipelines']
    expected_counts={'cc_cedict':7,'moe_revised':4,'moe_revised_wfg':2,'moe_concise':2,'moe_idioms':2,'moe_mini':2}
    require(len(goldens)==12 and {(g['converter_output'],g['profile']) for g in goldens}=={(n,p) for n in expected_counts for p in ['canonical_v1','legacy_body_span_v1']},'M2 TXT golden/profile coverage differs')
    require(all(g['bytes_exact'] and g['records']==expected_counts[g['converter_output']] for g in goldens),'M2 TXT golden parity differs')
    require(len(pipelines)==4 and {(p['profile'],p['encoding']) for p in pipelines}=={(p,e) for p in ['canonical_v1','legacy_body_span_v1'] for e in ['utf8','utf16']},'M2 TXT pipeline inventory differs')
    require(all(p['records']==13 and p['independent_python_rows']=='passed' and p['wire_audit']=='passed' and p['export_bytes_exact'] for p in pipelines),'M2 TXT pipeline checks differ')
    require([(c['fixture'],c['records']) for c in checks['cedict']]==[('baseline',7),('extended',23)] and all(c['oracle_bytes_exact'] and c['metrics_exact'] for c in checks['cedict']) and checks['pinyin_words']==10,'M2 CC-CEDICT parity differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in text['source_sha256'].items()},'M2 text snapshot bindings differ')
    print('PASS Mac M2 TXT and CC-CEDICT parity: 38 successes, five controlled refusals, exact snapshots; spreadsheet ports remain pending')
    xlsx_dir=ROOT/'docs/evidence/m2-xlsx-user-run'
    provenance=json.loads((xlsx_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((xlsx_dir/name).read_bytes()).hexdigest()==expected,f'XLSX evidence changed: {name}')
    xlsx=json.loads((xlsx_dir/'m2-xlsx-report.json').read_text(encoding='utf-8'))
    require(xlsx['status']=='m2_xlsx_common_cells_passed_MOE_ports_and_date_profile_pending' and xlsx['M2_complete'] is False and xlsx['Rust_MOE_converters_ported'] is False,'Do not broaden XLSX scope')
    require(len(xlsx['steps'])==21 and xlsx['steps'][0]['name']=='reader-lock-resolve' and xlsx['steps'][1]['name']=='xlsx-tests','XLSX run inventory differs')
    require(sum(s['returncode']==0 for s in xlsx['steps'])==14 and sum(s.get('expected_refusal') is not None and s['returncode']==1 for s in xlsx['steps'])==7,'XLSX command results differ')
    require(len(xlsx['checks'])==19 and sum(c['status']=='exact_rows_and_headers' for c in xlsx['checks'])==12,'XLSX common-cell coverage differs')
    expected_refusals={'missing-sheet':'sheet_not_found','date-refused':'unsupported_cell','duration-refused':'unsupported_cell','oversized-rectangle':'limit_exceeded','dimension-required':'unsupported_workbook','external-sheet-refused':'unsupported_workbook','invalid-workbook':'malformed_workbook'}
    require({c['case']:c['code'] for c in xlsx['checks'] if c['status']=='expected_refusal'}==expected_refusals,'XLSX refusal classifications differ')
    counts={c['case']:c.get('rows') for c in xlsx['checks']}
    require(counts['moderate-2000-row-table']==2000 and counts['numeric-lexemes']==142 and counts['captured-MOE-input-rows']==4,'XLSX sample counts differ')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in xlsx['source_sha256'].items()},'XLSX snapshot bindings differ')
    lock_path=xlsx_dir/'qualified/m2/xlsx-reader/Cargo.lock'
    require(lock_path.read_text()==xlsx['dependency_lock_contents'],'Retained XLSX lock differs from receipt')
    packages=tomllib.loads(xlsx['dependency_lock_contents'])['package']
    require(len(packages)==39,'XLSX dependency graph differs')
    for name,version in {'calamine':'0.31.0','quick-xml':'0.38.3','zip':'4.6.1','serde':'1.0.229','serde_json':'1.0.154'}.items():
        require(len([p for p in packages if p['name']==name and p['version']==version and 'checksum' in p])==1,f'XLSX direct pin differs: {name}')
    require(len(xlsx['protected_source_sha256'])==35,'Protected XLSX source inventory differs')
    for name,expected in xlsx['protected_source_sha256'].items():
        if name in text['source_sha256']:require(expected==text['source_sha256'][name],f'XLSX changed qualified dictionary identity: {name}')
    print('PASS Mac XLSX common-cell profile: exact dependency receipt, 12 matching cases and seven controlled refusals; MOE/date work remains pending')
    moe_dir=ROOT/'docs/evidence/m2-moe-first-user-run'
    provenance=json.loads((moe_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((moe_dir/name).read_bytes()).hexdigest()==expected,f'MOE first-run evidence changed: {name}')
    moe=json.loads((moe_dir/'m2-moe-report.json').read_text(encoding='utf-8'))
    require(moe['status']=='m2_moe_failed' and moe['Rust_MOE_ports_runtime_qualified'] is False and moe['checks']==[],'Do not relabel failed MOE compilation as qualified')
    require(moe['steps']==[{'name':'moe-and-reader-tests','returncode':101,'log':'moe-and-reader-tests.log'}],'MOE first-run command inventory differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in moe['source_sha256'].items()},'MOE first-run snapshot bindings differ')
    log=(moe_dir/'moe-and-reader-tests.log').read_text(encoding='utf-8')
    require(log.count('error[E0425]')==4 and 'cannot find value `py_space` in this scope' in log,'MOE compile failure diagnosis differs')
    print('PASS retained MOE first failure: missing import, no converter comparisons reached; corrected runtime still pending')
    moe_dir=ROOT/'docs/evidence/m2-moe-second-user-run'
    provenance=json.loads((moe_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((moe_dir/name).read_bytes()).hexdigest()==expected,f'MOE second-run evidence changed: {name}')
    moe=json.loads((moe_dir/'m2-moe-report.json').read_text(encoding='utf-8'))
    require(moe['status']=='m2_moe_failed' and moe['Rust_MOE_ports_runtime_qualified'] is False and moe['checks']==[],'Do not relabel second MOE attempt as qualified')
    require(len(moe['steps'])==1 and moe['steps'][0]['returncode']==101,'MOE second-run command inventory differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in moe['source_sha256'].items()},'MOE second-run snapshot bindings differ')
    log=moe['steps'][0]['failure_log_tail']
    require('Finished `test` profile' in log and '6 passed; 0 failed' in log and '3 passed; 1 failed' in log and 'assertion `left == right` failed: moe_revised' in log,'MOE second-run result differs')
    print('PASS retained MOE second failure: compiled, reader tests passed, reference-order assertion failed; full conversion matrix still pending')
    moe_dir=ROOT/'docs/evidence/m2-moe-user-run'
    provenance=json.loads((moe_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((moe_dir/name).read_bytes()).hexdigest()==expected,f'MOE accepted evidence changed: {name}')
    moe=json.loads((moe_dir/'m2-moe-report.json').read_text(encoding='utf-8'))
    require(moe['status']=='m2_five_MOE_ports_synthetic_parity_passed_remaining_M2_work_pending' and moe['Rust_MOE_ports_runtime_qualified'] is True and moe['M2_complete'] is False,'Do not broaden MOE qualification scope')
    require(len(moe['steps'])==36 and sum(s['returncode']==0 for s in moe['steps'])==31,'MOE command inventory differs')
    require({s['name']:(s['returncode'],s.get('expected_refusal')) for s in moe['steps'] if s['returncode']!=0}=={
        'no-overwrite':(1,'destination_exists'),'no-headwords':(1,'malformed_source'),'newline-key':(1,'unrepresentable_source'),
        'nonascii-image':(1,'unsupported_policy'),'nonascii-number':(1,'unsupported_policy')},'MOE controlled refusals differ')
    matches=[c for c in moe['checks'] if c['status']=='original_plugin_content_and_TXT_publication_match']
    kinds=['moe_revised','moe_revised_wfg','moe_concise','moe_idioms','moe_mini']
    require(len(moe['checks'])==14 and {c['case'] for c in matches}=={p+'-'+k for p in ['baseline','extended'] for k in kinds},'MOE case inventory differs')
    require(all(c['deterministic_repeat'] for c in matches),'MOE repeatability differs')
    for c in matches:
        baseline=c['case'].startswith('baseline-');revised=c['case'].endswith('-moe_revised')
        primary=2 if baseline else 3;aliases=(2 if baseline else 4) if revised else 0
        require((c['primary_entries'],c['alias_redirects'],c['entries'])==(primary,aliases,primary+aliases),'MOE record metrics differ')
    require({c['case'] for c in matches if not c['raw_python_bytes_equal']}=={'baseline-moe_revised','extended-moe_revised','extended-moe_concise'},'MOE byte-order difference inventory differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in moe['source_sha256'].items()},'MOE accepted snapshot bindings differ')
    lock=tomllib.loads((moe_dir/'qualified/m2/xlsx-reader/Cargo.lock').read_text())['package']
    require([{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in lock]==moe['dependency_packages'],'MOE dependency receipt differs')
    require(moe['qualified_xlsx_lock_unchanged'] and moe['source_sha256']['m2/xlsx-reader/Cargo.lock']==xlsx['source_sha256']['m2/xlsx-reader/Cargo.lock'],'MOE changed XLSX dependency lock')
    require(moe['protected_source_sha256']==xlsx['protected_source_sha256'],'MOE changed qualified core/oracle identities')
    print('PASS Mac five MOE ports: ten synthetic cases, staged TXT publication, deterministic repeats, 31 successes and five controlled refusals; M2 remains partial')
    app_dir=ROOT/'docs/evidence/m2-application-user-run'
    provenance=json.loads((app_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((app_dir/name).read_bytes()).hexdigest()==expected,f'Application evidence changed: {name}')
    app=json.loads((app_dir/'m2-application-report.json').read_text(encoding='utf-8'))
    require(app['status']=='m2_shared_application_conversion_passed_remaining_M2_work_pending' and app['application_runtime_qualified'] is True and app['M2_complete'] is False,'Do not broaden application qualification scope')
    require(len(app['steps'])==49 and sum(s['returncode']==0 for s in app['steps'])==39 and app['steps'][0]['name']=='application-tests','Application command inventory differs')
    refusals={'existing-output':'destination_exists','no-headwords':'malformed_source','newline-key':'unrepresentable_source','nonascii-image':'unsupported_policy','nonascii-number':'unsupported_policy','date-cell':'unsupported_cell','invalid-workbook':'malformed_workbook','missing-sheet':'sheet_not_found','cedict-sheet-option':'invalid_input','unknown-converter':'invalid_input'}
    require({s['name']:(s['returncode'],s.get('expected_refusal')) for s in app['steps'] if s['returncode']!=0}=={n:(1,c) for n,c in refusals.items()},'Application refusal mapping differs')
    checks={c['case']:c for c in app['checks']}
    expected_counts={c['case']:c['entries'] for c in matches};expected_counts.update({'baseline-cc_cedict':7,'extended-cc_cedict':23})
    require(len(app['checks'])==14 and set(checks)==set(expected_counts)|{'active-workbook','named-workbook'},'Application case inventory differs')
    require(all(checks[n]['entries']==count and checks[n]['status']=='original_plugin_content_publication_progress_repeat_passed' for n,count in expected_counts.items()),'Application conversion checks differ')
    require(all(checks[n]['status']=='workbook_boundary_match' for n in ['active-workbook','named-workbook']),'Application workbook boundary differs')
    require({n for n,c in checks.items() if c.get('raw_python_bytes_equal') is False}=={'baseline-moe_revised','extended-moe_revised','extended-moe_concise'},'Application byte-order differences expanded')
    for c in matches:require(checks[c['case']]['output_sha256']==c['output_sha256'],'Facade changed qualified MOE output bytes')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in app['source_sha256'].items()},'Application snapshot bindings differ')
    graph=tomllib.loads((app_dir/'qualified/m2/application/Cargo.lock').read_text())['package']
    require(len(graph)==60 and [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in graph]==app['dependency_packages'],'Application dependency receipt differs')
    registry={(p['name'],p['version'],p.get('checksum')) for p in graph if 'source' in p}
    prior_registry=set()
    for lockpath in [ROOT/'docs/evidence/m2-text-user-run/qualified/m2/Cargo.lock',ROOT/'docs/evidence/m2-xlsx-user-run/qualified/m2/xlsx-reader/Cargo.lock']:
        prior_registry.update((p['name'],p['version'],p.get('checksum')) for p in tomllib.loads(lockpath.read_text())['package'] if 'source' in p)
    require(registry==prior_registry,'Application upgraded or introduced registry dependency identities')
    protected={**xlsx['protected_source_sha256'],**xlsx['source_sha256'],**moe['protected_source_sha256'],**moe['source_sha256']}
    require(len(protected)==81 and app['protected_source_sha256']==protected,'Application changed qualified source identities')
    print('PASS shared application conversion on Mac: 12 converter cases, two workbook boundaries, 39 successes, ten refusals and exact dependency/source receipts; M2 remains partial')
    jobs_dir=ROOT/'docs/evidence/m2-jobs-user-run'
    provenance=json.loads((jobs_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((jobs_dir/name).read_bytes()).hexdigest()==expected,f'Background job evidence changed: {name}')
    jobs=json.loads((jobs_dir/'m2-jobs-report.json').read_text(encoding='utf-8'))
    require(jobs['status']=='m2_background_jobs_passed_remaining_M2_work_pending' and jobs['background_runtime_qualified'] is True and jobs['M2_complete'] is False,'Do not broaden background job qualification scope')
    require(jobs['steps']==[{'name':'background-and-application-tests','returncode':0,'log':'background-and-application-tests.log'},{'name':'background-batch','returncode':0,'log':'background-batch.log'}],'Background command inventory differs')
    good=[c for c in jobs['checks'] if c['status']=='background_content_metrics_and_publication_passed']
    bad=[c for c in jobs['checks'] if c['status']=='expected_failed_job']
    require(len(jobs['checks'])==17 and len(good)==12 and len(bad)==5 and len({c['job_id'] for c in jobs['checks']})==17,'Background job inventory differs')
    require({c['case']:c['code'] for c in bad}=={'no-headwords':'malformed_source','newline-key':'unrepresentable_source','nonascii-image':'unsupported_policy','nonascii-number':'unsupported_policy','existing-output':'destination_exists'},'Background error mapping differs')
    for c in good:
        require(c['case'] in expected_counts and c['entries']==checks[c['case']]['entries'] and c['output_sha256']==checks[c['case']]['output_sha256'],'Background worker changed qualified application output')
    require({c['case'] for c in good}==set(expected_counts),'Background converter matrix differs')
    require({c['case'] for c in good if not c['raw_python_bytes_equal']}=={'baseline-moe_revised','extended-moe_revised','extended-moe_concise'},'Background byte-order differences expanded')
    require(jobs['events_delivered']==50 and provenance['event_transcript_attached'] is False,'Recorded event count/transcript scope differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in jobs['source_sha256'].items()},'Background source snapshot bindings differ')
    name='m2/application/src/lib.rs'
    require((jobs_dir/'qualified'/name).read_bytes()==(app_dir/'qualified'/name).read_bytes()+b'\npub mod runner;\n','Qualified facade changed beyond explicit module export')
    expected={**app['protected_source_sha256'],**app['source_sha256']};expected[name]=jobs['source_sha256'][name]
    require(len(expected)==90 and jobs['protected_source_sha256']==expected,'Background protected identities differ')
    require(jobs['dependency_packages']==app['dependency_packages'] and jobs['source_sha256']['m2/application/Cargo.lock']==app['source_sha256']['m2/application/Cargo.lock'],'Background job dependency graph changed')
    print('PASS background jobs on Mac: 12 exact outputs, five expected failures, passing test command, source/dependency receipts; 50 events reported, no separate transcript attached')
    dictionary_dir=ROOT/'docs/evidence/m2-dictionary-jobs-user-run'
    provenance=json.loads((dictionary_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((dictionary_dir/name).read_bytes()).hexdigest()==expected,f'Dictionary job evidence changed: {name}')
    dictionary=json.loads((dictionary_dir/'m2-dictionary-jobs-report.json').read_text(encoding='utf-8'))
    require(dictionary['status']=='m2_dictionary_background_jobs_passed_remaining_M2_work_pending' and dictionary['dictionary_jobs_runtime_qualified'] is True and dictionary['M2_complete'] is False,'Do not broaden dictionary job scope')
    require(dictionary['steps']==[{'name':'dictionary-background-tests','returncode':0,'log':'dictionary-background-tests.log'},{'name':'dictionary-background-batch','returncode':0,'log':'dictionary-background-batch.log'}],'Dictionary command inventory differs')
    passed={c['case']:c for c in dictionary['checks'] if c['status']=='passed'}
    refused={c['case']:c['code'] for c in dictionary['checks'] if c['status']=='expected_failed_job'}
    require(len(dictionary['checks'])==19 and len(passed)==12 and refused=={'existing-mdx':'destination_exists','existing-export':'destination_exists','existing-extract':'destination_exists','unsafe':'unsafe_path','aliases':'path_collision','missing-resource':'io','malformed-txt':'malformed_source'},'Dictionary outcome matrix differs')
    for profile in ['canonical_v1','legacy_body_span_v1']:
        for encoding in ['utf8','utf16']:
            pack=passed[profile+'-'+encoding+'-pack'];export=passed[profile+'-'+encoding+'-export']
            require(pack['operation']=='pack_mdx' and pack['entries']==13 and pack['wire_audit']=='passed' and pack['independent_python']=='passed','Dictionary MDX qualification differs')
            require(export['operation']=='export_mdx' and export['entries']==13 and export['bytes_exact'] is True,'Dictionary TXT export differs')
    require(passed['recovery-pack']['output_sha256']==passed['canonical_v1-utf8-pack']['output_sha256'] and passed['recovery-export']['output_sha256']==passed['canonical_v1-utf8-export']['output_sha256'],'Dictionary worker recovery differs')
    require(passed['resources-pack']['resources']==6 and passed['resources-pack']['wire_audit']=='passed' and passed['resources-pack']['independent_python']=='passed','Dictionary MDD qualification differs')
    payloads={'css/style.css':b'body{color:teal}','data/all.bin':bytes(range(256)),'empty.bin':b'','fonts/probe.ttf':(dictionary_dir/'qualified/baseline/resource-probe/studio-probe.ttf').read_bytes(),'العربية/نص.txt':'أهلاً'.encode(),'字/text.txt':'字典'.encode()}
    inventory=[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(payloads.items())]
    require(passed['resources-extract']['resources']==6 and passed['resources-extract']['inventory']==inventory,'Dictionary extraction inventory differs')
    require(dictionary['events_delivered']==55 and provenance['event_transcript_attached'] is False,'Dictionary observed event count/transcript scope differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in dictionary['source_sha256'].items()},'Dictionary source snapshot bindings differ')
    expected={**jobs['protected_source_sha256'],**jobs['source_sha256']};name='m2/application/src/runner.rs';expected[name]=dictionary['source_sha256'][name]
    require(len(expected)==95 and dictionary['protected_source_sha256']==expected,'Dictionary protected identities differ')
    require(dictionary['dependency_packages']==jobs['dependency_packages'] and dictionary['source_sha256']['m2/application/Cargo.lock']==jobs['source_sha256']['m2/application/Cargo.lock'],'Dictionary job dependencies changed')
    require(provenance['MDX_v3']=='deferred_for_later_user_roadmap_planning','Do not imply v3 implementation or qualification')
    print('PASS Mac dictionary background jobs: 12 successes, seven expected failures, independent v2 audits, exact exports and six extracted resources; v3 deferred')
    import_dir=ROOT/'docs/evidence/m2-v2-import-first-user-run'
    provenance=json.loads((import_dir/'provenance.json').read_text(encoding='utf-8'))
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((import_dir/name).read_bytes()).hexdigest()==expected,f'First v2 import evidence changed: {name}')
    imported=json.loads((import_dir/'m2-v2-import-report.json').read_text(encoding='utf-8'))
    require(imported['status']=='m2_v2_import_failed' and imported['v2_import_runtime_qualified'] is False and imported['checks']==[],'Do not relabel failed v2 import test as qualified')
    require(len(imported['steps'])==1 and imported['steps'][0]['name']=='import-tests' and imported['steps'][0]['returncode']==101,'First v2 import command inventory differs')
    log=imported['steps'][0]['failure_log_tail']
    require('5 passed; 1 failed' in log and 'ordinary_mdd_import_preserves_binary_bytes_and_exact_key_lookup ... FAILED' in log and 'Expected one Dictionary element without children' in log,'First v2 import diagnosis differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in imported['source_sha256'].items()},'First v2 import snapshot bindings differ')
    lock=(import_dir/'qualified/m2/v2-import/Cargo.lock').read_text()
    require(lock==imported['dependency_lock_contents'],'Recovered import lock differs from receipt')
    packages=tomllib.loads(lock)['package']
    require(len(packages)==61 and [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in packages]==imported['dependency_packages'],'First v2 import dependency receipt differs')
    prior={(p['name'],p['version'],p['checksum']) for p in imported['dependency_packages'] if p['checksum']}
    require(prior=={(p['name'],p['version'],p['checksum']) for p in dictionary['dependency_packages'] if p['checksum']},'Import registry identities changed')
    require(imported['protected_source_sha256']=={**dictionary['protected_source_sha256'],**dictionary['source_sha256']},'First v2 import changed qualified sources')
    print('PASS retained first v2 import failure: compiled, five tests passed, MDD root guard failed; corrected profile remains pending')
    second_dir=ROOT/'docs/evidence/m2-v2-import-second-user-run'
    provenance=json.loads((second_dir/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((second_dir/name).read_bytes()).hexdigest()==expected,f'Second v2 import evidence changed: {name}')
    second=json.loads((second_dir/'m2-v2-import-report.json').read_text())
    require(second['status']=='m2_v2_import_failed' and second['v2_import_runtime_qualified'] is False and second['checks']==[],'Do not relabel cached-artifact failure as qualified')
    require(len(second['steps'])==1 and second['steps'][0]['returncode']==101,'Second import command inventory differs')
    log=second['steps'][0]['failure_log_tail'];header=(second_dir/'qualified/m2/v2-import/src/header.rs').read_text()
    old_message='Expected one Dictionary element without children'
    require(old_message in log and old_message not in header and 'format_roots_are_selected_by_kind_and_children_are_still_refused' in header and 'running 0 tests' in log,'Second import stale-artifact evidence differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in second['source_sha256'].items()},'Second import snapshot bindings differ')
    require(second['dependency_packages']==imported['dependency_packages'] and second['protected_source_sha256']==imported['protected_source_sha256'],'Second import changed dependency/protected identities')
    print('PASS retained second v2 import failure: corrected source hashes, obsolete binary diagnostics; targeted package rebuild added, runtime pending')
    for ordinal,error in [('third','IndexError: list index out of range'),('fourth','AssertionError: Legacy writer changed fixture payloads')]:
        directory=ROOT/f'docs/evidence/m2-v2-import-{ordinal}-user-run'
        provenance=json.loads((directory/'provenance.json').read_text())
        for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
            require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'{ordinal} import evidence changed: {name}')
        report=json.loads((directory/'m2-v2-import-report.json').read_text())
        require(report['status']=='m2_v2_import_failed' and not report['v2_import_runtime_qualified'] and report['checks']==[] and report['error']==error,f'{ordinal} failure relabeled or changed')
        require([(step['name'],step['returncode']) for step in report['steps']]==[('refresh-import-artifacts',0),('import-tests',0)],f'{ordinal} Rust command inventory differs')
        require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in report['source_sha256'].items()},f'{ordinal} source snapshot bindings differ')
        require(report['dependency_packages']==imported['dependency_packages'] and report['protected_source_sha256']==imported['protected_source_sha256'],f'{ordinal} protected/dependency identities differ')
        if ordinal=='fourth':require(report['stage']=='fixture_generation' and 'v2_import_fixtures.py' in report['python_traceback'],'Fourth fixture traceback missing')
        print(f'PASS retained {ordinal} v2 import run: Rust command passed, historical Python fixture failure')
    directory=ROOT/'docs/evidence/m2-v2-import-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted v2 import evidence changed: {name}')
    report=json.loads((directory/'m2-v2-import-report.json').read_text())
    require(report['status']=='m2_ordinary_v2_import_lookup_passed_application_routing_pending' and report['v2_import_runtime_qualified'] and not report['M2_complete'],'Accepted v2 import scope differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in report['source_sha256'].items()},'Accepted v2 import snapshot bindings differ')
    require(report['dependency_packages']==imported['dependency_packages'] and report['protected_source_sha256']==imported['protected_source_sha256'],'Accepted import changed prior dependency/protected identities')
    require(report['dependency_lock_contents']==(directory/'qualified/m2/v2-import/Cargo.lock').read_text(),'Accepted lock bytes differ')
    steps=report['steps'];checks=report['checks']
    require(len(steps)==28 and len(checks)==report['generated_cases']==26,'Accepted import command/case count differs')
    require([(s['name'],s['returncode']) for s in steps[:2]]==[('refresh-import-artifacts',0),('import-tests',0)],'Accepted import Rust test command did not pass')
    require(len({c['case'] for c in checks})==26 and [s['name'] for s in steps[2:]]==[c['case'] for c in checks],'Accepted case identity/order differs')
    successes=[c for c in checks if c['status']=='physical_rows_header_queries_and_wire_passed'];refusals=[c for c in checks if c['status']=='expected_refusal']
    require(len(successes)==15 and len(refusals)==11,'Accepted import/refusal inventory differs')
    for step,case in zip(steps[2:],checks):
        expected=case['status']=='expected_refusal'
        require(step['returncode']==int(expected) and (not expected or step['expected_refusal']==case['code']),'Accepted process outcome differs')
    mdx=[c for c in successes if c['case']!='mdd-duplicates']
    require(len(mdx)==14 and all(c['records']==27 and sum(c['query_checks'].values())==30 for c in mdx),'Accepted MDX record/query counts differ')
    require(sum(c['query_checks']['exact_query_result'] for c in mdx)==328 and sum(c['query_checks']['expected_query_error'] for c in mdx)==92,'Accepted query result totals differ')
    require(next(c for c in successes if c['case']=='mdd-duplicates')['records']==4,'Accepted MDD record count differs')
    print('PASS accepted bounded ordinary v2 import: 26 cases, 420 MDX query checks; application/background routing still pending')
    directory=ROOT/'docs/evidence/m2-import-jobs-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Import job evidence changed: {name}')
    jobs=json.loads((directory/'m2-import-jobs-report.json').read_text())
    require(jobs['status']=='m2_import_application_background_jobs_passed_remaining_M2_work_pending' and not jobs['M2_complete'] and jobs['stage']=='complete','Import job qualification scope changed')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in jobs['source_sha256'].items()},'Import job source snapshot bindings differ')
    require(len(jobs['source_sha256'])==15 and len(jobs['protected_source_sha256'])==114,'Import job identity inventory differs')
    require(jobs['dependency_packages']==report['dependency_packages'] and jobs['dependency_lock_contents']==report['dependency_lock_contents'],'Import jobs changed accepted dependency graph or lock')
    prior={**report['protected_source_sha256'],**report['source_sha256']};qualified=jobs['protected_source_sha256'];lib='m2/v2-import/src/lib.rs'
    require(set(prior)==set(qualified) and all(prior[n]==qualified[n] for n in prior if n!=lib),'Import job changed protected identities')
    old=(ROOT/'docs/evidence/m2-v2-import-user-run/qualified'/lib).read_bytes();new=(directory/'qualified'/lib).read_bytes()
    require(new==old+b'\npub mod application;\n' and hashlib.sha256(new).hexdigest()==qualified[lib],'Reader changed beyond application module export')
    require(len(jobs['steps'])==56 and all(s['returncode']==0 for s in jobs['steps']) and len(jobs['checks'])==27,'Import job command/case inventory differs')
    require([s['name'] for s in jobs['steps'][:2]]==['refresh-import-artifacts','import-application-tests'],'Import job Rust command inventory differs')
    checks=jobs['checks'];require(len({c['case'] for c in checks})==27,'Duplicate import job case receipt')
    require([s['name'] for s in jobs['steps'][2:]]==[c['case']+suffix for c in checks for suffix in ['-sync','-background']],'Sync/background case commands differ')
    require(sum(c['status']=='sync_background_oracle_passed' for c in checks)==15 and sum(c['status']=='expected_job_failure' for c in checks)==12,'Import job positive/failure inventory differs')
    require(next(c for c in checks if c['case']=='aggregate-reply-budget')['status']=='expected_job_failure','Aggregate reply cap refusal missing')
    require(sum(c.get('query_checks',{}).get('exact_query_result',0) for c in checks)==328 and sum(c.get('query_checks',{}).get('expected_query_error',0) for c in checks)==92 and sum(c.get('query_checks',{}).get('resource_queries',0) for c in checks)==4,'Import job oracle counts differ')
    print('PASS accepted bounded import application/worker: 56 commands, 27 sync/background cases; M2 metadata and production work remain')
    directory=ROOT/'docs/evidence/m2-metadata-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Metadata first-run evidence changed: {name}')
    metadata=json.loads((directory/'m2-metadata-report.json').read_text())
    require(metadata['status']=='m2_metadata_failed' and metadata['checks']==[] and metadata['error']=='IndexError: list index out of range','Do not relabel partial metadata run as qualified')
    require(metadata['stage']=='metadata-utf8-case0-strip0' and [(s['name'],s['returncode']) for s in metadata['steps']]==[('refresh-metadata-artifacts',0),('metadata-tests',0),('metadata-utf8-case0-strip0',0)],'Metadata first-run command results differ')
    require('lines[i+1]' in metadata['python_traceback'] and 'read_legacy_physical(source,kind)' in metadata['python_traceback'],'Metadata source oracle traceback differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in metadata['source_sha256'].items()} and len(metadata['source_sha256'])==18,'Metadata snapshot bindings differ')
    require(metadata['dependency_packages']==jobs['dependency_packages'] and metadata['dependency_lock_contents']==jobs['dependency_lock_contents'],'Metadata changed accepted dependency graph/lock')
    print('PASS retained metadata first run: Rust tests and first rebuild passed; source-side Python oracle failure, matrix/native pending')
    directory=ROOT/'docs/evidence/m2-metadata-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Metadata offline evidence changed: {name}')
    passed=json.loads((directory/'m2-metadata-report.json').read_text())
    require(passed['status']=='m2_metadata_rebuild_offline_passed_native_checks_pending' and passed['stage']=='complete' and not passed['M2_complete'],'Do not overstate metadata/native qualification')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in passed['source_sha256'].items()} and len(passed['source_sha256'])==18,'Metadata offline snapshot bindings differ')
    require(passed['protected_source_sha256']==metadata['protected_source_sha256'] and passed['dependency_packages']==metadata['dependency_packages'] and passed['dependency_lock_contents']==metadata['dependency_lock_contents'],'Metadata retry changed protected sources/dependencies')
    require(all(passed['source_sha256'][n]==h for n,h in metadata['source_sha256'].items() if n.endswith(('.rs','.toml','.lock'))),'Metadata retry changed Rust/manifest/lock')
    steps=passed['steps'];checks=passed['checks'];positive=[c for c in checks if c['status']=='metadata_sections_records_passed'];negative=[c for c in checks if c['status']=='expected_refusal']
    require(len(steps)==36 and len(checks)==32 and len({c['case'] for c in checks})==32 and len(positive)==14 and len(negative)==18,'Metadata offline command/case count differs')
    require([(s['name'],s['returncode']) for s in steps[:2]]==[('refresh-metadata-artifacts',0),('metadata-tests',0)],'Metadata offline Rust test receipt differs')
    step_map={s['name']:s for s in steps}
    for case in positive:require(step_map[case['case']]['returncode']==0 and all(case[k] for k in ['binary_sections_exact','raw_and_decoded_metadata_exact','standard_XML_non_stylesheet_metadata_exact']),'Metadata successful comparison flags differ')
    for case in negative:require(step_map[case['case']]['returncode']==1 and step_map[case['case']]['expected_refusal']==case['code'],'Metadata refusal receipt differs')
    require(sum(c['code']=='cancelled' for c in negative)==3 and sum(c['code']=='destination_exists' for c in negative)==2,'Metadata cancellation/no-overwrite inventory differs')
    require(len(passed['native_files'])==2 and passed['native_readers']=='NOT_RUN_AWAIT_OFFLINE_REVIEW','Native reader scope changed')
    for encoding in ['utf8','utf16']:
        native=next(c for c in positive if c['case']=='native-'+encoding);file=next(f for f in passed['native_files'] if f['path']=='native/metadata-'+encoding+'.mdx')
        require(native['records']==5 and native['python_marker_expansion_exact'] and native['output_sha256']==file['sha256'] and step_map['seed-'+encoding]['returncode']==0,'Native metadata control identity/expansion differs')
    print('PASS accepted metadata offline batch: 14 rebuilds, 18 expected refusals; two exact native controls remain pending')
    native_dir=ROOT/'docs/evidence/m2-metadata-native-user-confirmation'
    provenance=json.loads((native_dir/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((native_dir/name).read_bytes()).hexdigest()==expected,f'Native metadata confirmation changed: {name}')
    native=json.loads((native_dir/'confirmation.json').read_text())
    require(native['status']=='user_confirmed_requested_native_controls_passed' and native['user_statement']=='Yes, Confirming all five entries work, no crashes','Native metadata attestation differs')
    require(native['requested_files']==passed['native_files'] and native['requested_readers']==['MDict','GoldenDict'],'Native metadata checklist/file bindings differ')
    require('M2 completion' in native['not_qualified'],'Do not turn scoped native confirmation into M2 closeout')
    print('PASS retained scoped user confirmation for metadata native controls; general metadata packing/publication remain open')
    directory=ROOT/'docs/evidence/m2-metadata-jobs-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'First metadata publication evidence changed: {name}')
    first=json.loads((directory/'m2-metadata-jobs-report.json').read_text())
    require(first['status']=='m2_metadata_jobs_failed' and first['checks']==[] and first['stage']=='rust_tests','Do not overstate first publication run')
    require([(s['name'],s['returncode']) for s in first['steps']]==[('refresh-publication-artifacts',0),('metadata-publication-tests',101)],'First publication command receipt differs')
    log=first['steps'][1]['failure_log_tail'];require('E0282' in log and 'E0283' in log and 'tests/publication.rs' in log and 'PartialEq' in log,'Publication assertion compile diagnosis differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in first['source_sha256'].items()} and len(first['source_sha256'])==23,'First publication snapshot bindings differ')
    old=(directory/'qualified/m2/v2-import/tests/publication.rs').read_text();require('assert_eq!(d.resources()[3].bytes,[])' in old,'Original ambiguous assertion evidence missing')
    require(first['dependency_packages']==passed['dependency_packages'] and first['dependency_lock_contents']==passed['dependency_lock_contents'],'Publication attempt changed accepted lock/dependency graph')
    print('PASS retained metadata publication test-compile failure: empty-array assertion only, runtime retry pending')
    directory=ROOT/'docs/evidence/m2-metadata-jobs-second-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Second publication evidence changed: {name}')
    second=json.loads((directory/'m2-metadata-jobs-report.json').read_text())
    require(second['status']=='m2_metadata_jobs_failed' and second['checks']==[] and second['stage']=='rust_tests','Do not overstate second publication run')
    require([(s['name'],s['returncode']) for s in second['steps']]==[('refresh-publication-artifacts',0),('metadata-publication-tests',101)],'Second publication command receipt differs')
    log=second['steps'][1]['failure_log_tail']
    for count in [16,4,6]:require(f'test result: ok. {count} passed;' in log,'Second publication passing regression receipts missing')
    require(log.count('test result: ok. 4 passed;')==2 and '0 passed; 4 failed;' in log and 'header attribute `KeyCaseSensitive` is written by the builder and cannot be overridden' in log,'Second publication shared builder failure differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in second['source_sha256'].items()} and len(second['source_sha256'])==23,'Second publication snapshot bindings differ')
    require(second['protected_source_sha256']==first['protected_source_sha256'] and second['dependency_packages']==first['dependency_packages'] and second['dependency_lock_contents']==first['dependency_lock_contents'],'Second publication changed protected/dependency identities')
    print('PASS retained second publication run: compiled, 30 tests passed, four packing tests hit builder-owned flag override; retry pending')
    directory=ROOT/'docs/evidence/m2-metadata-jobs-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Publication offline evidence changed: {name}')
    publication=json.loads((directory/'m2-metadata-jobs-report.json').read_text())
    require(publication['status']=='m2_metadata_packing_publication_offline_passed_native_checks_pending' and publication['stage']=='complete' and not publication['M2_complete'],'Publication offline/native scope changed')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in publication['source_sha256'].items()} and len(publication['source_sha256'])==23,'Publication offline snapshot bindings differ')
    require(publication['protected_source_sha256']==second['protected_source_sha256'] and publication['dependency_packages']==second['dependency_packages'] and publication['dependency_lock_contents']==second['dependency_lock_contents'],'Publication changed protected sources/dependencies')
    module='m2/v2-import/src/application/metadata/publication.rs'
    require(all(publication['source_sha256'][n]==h for n,h in second['source_sha256'].items() if n!=module),'Publication retry changed more than packing setup')
    require([(s['name'],s['returncode']) for s in publication['steps']]==[('refresh-publication-artifacts',0),('metadata-publication-tests',0),('sync-batch',0),('background-batch',0)],'Publication offline command inventory differs')
    checks=publication['checks'];require(len(checks)==56,'Publication job count differs')
    for mode in ['sync','background']:
        group=[c for c in checks if c['mode']==mode];positive=[c for c in group if c['status']=='publication_oracle_passed'];negative=[c for c in group if c['status']=='expected_refusal']
        require(len(group)==28 and len({c['case'] for c in group})==28 and len(positive)==10 and len(negative)==18,'Publication per-route case inventory differs')
        require(all(c['state']=='succeeded' and c['metadata_records_wire_passed'] for c in positive),'Publication successful oracle flags differ')
        require(sum(c['state']=='rejected' for c in negative)==14 and sum(c['state']=='failed' for c in negative)==4,'Publication refusal/rejection states differ')
        for encoding in ['utf8','utf16']:
            control=next(c for c in positive if c['case']=='native-'+encoding);require(control['records']==5 and control['Python_marker_expansion_passed'],'Publication native control expansion/count differs')
            if mode=='background':require(control['output_sha256']==next(f['sha256'] for f in publication['native_files'] if f['path']=='background/native-'+encoding+'.mdx'),'Publication native output identity differs')
    require(len(publication['native_files'])==2 and publication['native_readers']=='NOT_RUN_AWAIT_OFFLINE_REVIEW','Do not reuse earlier native evidence for freshly packed controls')
    print('PASS metadata packing/publication offline: 20 publications and 36 expected refusals; freshly packed native controls pending')
    directory=ROOT/'docs/evidence/m2-metadata-jobs-native-user-confirmation'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Fresh-packing native confirmation changed: {name}')
    native=json.loads((directory/'confirmation.json').read_text())
    require(native['status']=='user_confirmed_fresh_packing_native_checklist_passed' and native['user_statement']=='All five entries correct, no crashes or missing entries.','Fresh-packing native statement differs')
    require(native['requested_files']==publication['native_files'] and native['requested_readers']==['MDict','GoldenDict'],'Fresh-packing native file/checklist bindings differ')
    require('M2 completion' in native['not_qualified'] and 'production file-size/RSS/index limits' in native['not_qualified'],'Do not expand native-control acceptance into production/M2 qualification')
    print('PASS scoped fresh-packing native user confirmation; metadata profile accepted, production limits and M2 closeout remain')


    directory=ROOT/'docs/evidence/m2-sizing-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'First sizing evidence changed: {name}')
    sizing=json.loads((directory/'m2-sizing-report.json').read_text())
    require(sizing['status']=='m2_sizing_failed' and sizing['stage']=='rust_tests' and not sizing['checks'],'Sizing runtime measurements were not reached')
    require([(s['name'],s['returncode']) for s in sizing['steps']]==[('refresh-bounded-artifacts',0),('bounded-reader-tests',101)],'Sizing command receipt differs')
    log=sizing['steps'][1]['failure_log_tail']
    require('test result: ok. 1 passed;' in log and '2 passed; 3 failed;' in log and 'MDX import supports declared HTML/Text content' in log,'Sizing fixture diagnosis differs')
    require(len(sizing['protected_source_sha256'])==133 and len(sizing['source_sha256'])==9 and len(sizing['dependency_packages'])==62,'Sizing source/graph inventory differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in sizing['source_sha256'].items()},'Sizing snapshots differ')
    for n,h in sizing['protected_source_sha256'].items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Sizing retry changed prior source: {n}')
    for n,h in sizing['source_sha256'].items():
        if not n.endswith(('tests/reader.rs','Cargo.lock')):
            require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Sizing retry changed runtime source: {n}')
    old=(directory/'qualified/m2/bounded-engine/tests/reader.rs').read_text()
    fixed=(ROOT/'m2/bounded-engine/tests/reader.rs').read_text()
    require(fixed.replace('    builder.header_attribute("Format","Html").unwrap();\n','',1)==old,'Sizing retry must only declare the fixture Format')
    print('PASS first sizing failure retained: Rust compiled, MDX fixture Format corrected; measurements pending')

    directory=ROOT/'docs/evidence/m2-sizing-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted sizing evidence changed: {name}')
    sizing=json.loads((directory/'m2-sizing-report.json').read_text())
    require(sizing['status']=='m2_bounded_reader_first_sizing_gate_passed_larger_path_integration_pending' and sizing['stage']=='complete','Sizing acceptance status differs')
    require(not sizing['M2_complete'] and not sizing['production_readiness'] and not sizing['RSS_is_OS_limit'] and sizing['native_readers']=='NOT_REQUESTED','Do not expand sizing qualification')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in sizing['source_sha256'].items()} and len(sizing['source_sha256'])==9,'Accepted sizing snapshots differ')
    for n,h in {**sizing['protected_source_sha256'],**sizing['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from sizing receipt: {n}')
    first=json.loads((ROOT/'docs/evidence/m2-sizing-first-user-run/m2-sizing-report.json').read_text())
    require(sizing['protected_source_sha256']==first['protected_source_sha256'] and sizing['dependency_packages']==first['dependency_packages'] and sizing['dependency_lock_contents']==first['dependency_lock_contents'],'Sizing retry changed protected sources or graph')
    require(len(sizing['steps'])==32 and len(sizing['checks'])==29,'Sizing receipt inventory differs')
    require([(s['name'],s['returncode']) for s in sizing['steps'][:3]]==[('refresh-bounded-artifacts',0),('bounded-reader-tests',0),('build-bounded-reader',0)],'Sizing Rust test/build receipt differs')
    success=[c for c in sizing['checks'] if c['status']=='stream_scan_queries_memory_passed'];refused=[c for c in sizing['checks'] if c['status']=='expected_refusal']
    require(len(success)==8 and len(refused)==21 and len({c['case'] for c in sizing['checks']})==29,'Sizing outcome counts differ')
    steps={s['name']:s for s in sizing['steps']}
    for c in sizing['checks']:
        s=steps[c['case']]
        require(s['peak_RSS_bytes']==c['peak_RSS_bytes'] and 0<c['peak_RSS_bytes']<=sizing['RSS_observation_target_bytes'],'Sizing RSS receipt differs')
    for c in success:
        memory=c['parser_memory'];require(steps[c['case']]['returncode']==0 and memory['locator']==0 and memory['peak']<=memory['budget']==67108864,'Sizing memory/locator budget differs')
    for c in refused:
        require(steps[c['case']]['returncode']==1 and c['error']['code'] in ['limit_exceeded','cancelled','integrity','engine'],'Sizing expected refusal differs')
    require(sum(c['error']['code']=='cancelled' for c in refused)==3 and sum(c['error']['code']=='integrity' for c in refused)==2,'Sizing cancellation/checksum inventory differs')
    large=next(c for c in success if c['case']=='large-utf8')
    require(large['scan']['records']==262144 and large['scan']['payload_bytes']==67108864 and large['peak_RSS_bytes']==4677632,'Largest tested sizing envelope differs')
    require(max(c['peak_RSS_bytes'] for c in sizing['checks'])==4677632,'Maximum observed sizing RSS differs')
    print('PASS accepted first bounded-reader sizing gate: Rust receipts, 8 scan/query successes, 21 expected refusals; M2 partial')

    directory=ROOT/'docs/evidence/m2-index-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted disk-index evidence changed: {name}')
    index=json.loads((directory/'m2-index-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in index['source_sha256'].items()} and len(index['source_sha256'])==11,'Disk-index snapshot inventory differs')
    require(len(index['protected_source_sha256'])==142 and len(index['dependency_packages'])==62,'Disk-index protected source/graph count differs')
    for n,h in {**index['protected_source_sha256'],**index['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted index receipt: {n}')
    require((ROOT/'m2/indexed-engine/Cargo.lock').read_text()==index['dependency_lock_contents'],'Disk-index lock differs from Mac receipt')
    from index_engine_lock import check_lock as check_index_lock
    require(check_index_lock()==index['dependency_packages'],'Disk-index package graph differs from receipt')
    from check_index_receipt import review as review_index_receipt
    summary=review_index_receipt(index)
    require(summary['page_results']==180 and summary['expected_refusals']==23,'Disk-index page/refusal review differs')
    print('PASS accepted disk-index gate: 12 builds, 20 query processes, 180 recomputed pages, 23 expected refusals; M2 partial')

    directory=ROOT/'docs/evidence/m2-sessions-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted session evidence changed: {name}')
    sessions=json.loads((directory/'m2-sessions-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in sessions['source_sha256'].items()} and len(sessions['source_sha256'])==8,'Session snapshot inventory differs')
    require(len(sessions['protected_source_sha256'])==153 and len(sessions['dependency_packages'])==63,'Session source/graph count differs')
    for n,h in {**sessions['protected_source_sha256'],**sessions['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted session receipt: {n}')
    require((ROOT/'m2/sessions/Cargo.lock').read_text()==sessions['dependency_lock_contents'],'Session lock differs from Mac receipt')
    from session_lock import check_lock as check_session_lock
    require(check_session_lock()==sessions['dependency_packages'],'Session dependency graph differs')
    from check_sessions_receipt import review as review_sessions_receipt
    summary=review_sessions_receipt(sessions)
    require(summary['controller_exchanges']==497 and summary['cancelled_jobs']==10,'Session controller review totals differ')
    print('PASS accepted sessions gate: Rust command receipts, 5 scenarios, 37 recomputed pages, 497 exchanges; M2 partial')

    directory=ROOT/'docs/evidence/m2-stream-extract-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'First streaming-extraction evidence changed: {name}')
    attempt=json.loads((directory/'m2-stream-extract-report.json').read_text())
    require(attempt['status']=='m2_stream_extract_failed' and attempt['stage']=='stream-extract-tests' and attempt['checks']==[],'Extraction runtime matrix was not reached')
    require([(s['name'],s['returncode']) for s in attempt['steps']]==[('refresh-extract-artifacts',0),('stream-extract-tests',101)],'Extraction compile receipt differs')
    log=attempt['steps'][1]['failure_log_tail']
    for diagnostic in ['E0308','src/extract.rs:10','expected `studio_v2_import::ErrorCode`, found `studio_core::ErrorCode`']:
        require(diagnostic in log,'Extraction error-type diagnosis differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in attempt['source_sha256'].items()} and len(attempt['source_sha256'])==10,'Extraction snapshot bindings differ')
    require(len(attempt['protected_source_sha256'])==161 and len(attempt['dependency_packages'])==62,'Extraction source/graph inventory differs')
    for n,h in attempt['protected_source_sha256'].items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Extraction retry changed prior source: {n}')
    for n,h in attempt['source_sha256'].items():
        if n not in ['m2/stream-extract/src/extract.rs','m2/stream-extract/Cargo.lock']:
            require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Extraction retry changed unrelated new source: {n}')
    current=(ROOT/'m2/stream-extract/src/extract.rs').read_text()
    require('use studio_core::ErrorCode as C;' in current and 'core_path_adapter_preserves_serialized_codes_and_messages' in current,'Missing explicit boundary conversion/regression')
    print('PASS retained streaming-extractor E0308 failure; explicit core/application conversion fixed, Rust retry pending')

    directory=ROOT/'docs/evidence/m2-stream-extract-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted streaming-extraction evidence changed: {name}')
    extraction=json.loads((directory/'m2-stream-extract-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in extraction['source_sha256'].items()} and len(extraction['source_sha256'])==10,'Accepted extraction snapshot bindings differ')
    require(extraction['protected_source_sha256']==attempt['protected_source_sha256'] and extraction['dependency_packages']==attempt['dependency_packages'] and extraction['dependency_lock_contents']==attempt['dependency_lock_contents'],'Extraction retry changed protected sources or graph')
    for n,h in {**extraction['protected_source_sha256'],**extraction['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted extraction receipt: {n}')
    require((ROOT/'m2/stream-extract/Cargo.lock').read_text()==extraction['dependency_lock_contents'],'Extraction lock differs from Mac receipt')
    from stream_extract_lock import check_lock as check_extraction_lock
    require(check_extraction_lock()==extraction['dependency_packages'],'Extraction package identities differ')
    from check_stream_extract_receipt import review as review_extraction_receipt
    reviewed=review_extraction_receipt(extraction)
    require(reviewed['file_hashes_recomputed']==4105 and reviewed['expected_refusals']==26,'Extraction review totals differ')
    print('PASS accepted streaming-MDD gate: 4 successful extractions, 4105 recomputed file hashes, 26 expected refusals; M2 partial')

    directory=ROOT/'docs/evidence/m2-extraction-jobs-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted extraction-job evidence changed: {name}')
    background=json.loads((directory/'m2-extraction-jobs-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in background['source_sha256'].items()} and len(background['source_sha256'])==9,'Extraction-job snapshot bindings differ')
    require(len(background['protected_source_sha256'])==171 and len(background['dependency_packages'])==65,'Extraction-job source/graph inventory differs')
    for n,h in {**background['protected_source_sha256'],**background['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted extraction-job receipt: {n}')
    require((ROOT/'m2/extraction-jobs/Cargo.lock').read_text()==background['dependency_lock_contents'],'Extraction-job lock differs from Mac receipt')
    from extraction_jobs_lock import check_lock as check_background_lock
    require(check_background_lock()==background['dependency_packages'],'Extraction-job package identities differ')
    from check_extraction_jobs_receipt import review as review_background_receipt
    reviewed=review_background_receipt(background)
    require(reviewed['file_hashes_recomputed']==4101 and reviewed['controller_exchanges']==1166,'Extraction-job review totals differ')
    print('PASS accepted background extraction/shared-admission gate: 3 scenarios, 4101 reported file hashes, 1166 exchanges; M2 partial')

    directory=ROOT/'docs/evidence/m2-large-io-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted large IO evidence changed: {name}')
    large=json.loads((directory/'m2-large-io-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in large['source_sha256'].items()} and len(large['source_sha256'])==10,'Large IO source snapshot bindings differ')
    require(len(large['protected_source_sha256'])==180 and len(large['dependency_packages'])==62,'Large IO source/graph inventory differs')
    for n,h in {**large['protected_source_sha256'],**large['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted large IO receipt: {n}')
    require((ROOT/'m2/large-io/Cargo.lock').read_text()==large['dependency_lock_contents'],'Large IO lock differs from Mac receipt')
    from large_io_lock import check_lock as check_large_io_lock
    require(check_large_io_lock()==large['dependency_packages'],'Large IO dependency identities differ')
    from check_large_io_receipt import review as review_large_io_receipt
    reviewed=review_large_io_receipt(large)
    require(reviewed==provenance['review_summary'] and reviewed['wire_records_recomputed']==327681 and reviewed['expected_refusals']==31,'Large IO review totals differ')
    print('PASS accepted larger packing/export gate: 16 publications, 31 refusals, 327681 reported record fingerprints, 7 recomputed export hashes; M2 partial')

    directory=ROOT/'docs/evidence/m2-publication-runtime-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'First publication-runtime evidence changed: {name}')
    attempt=json.loads((directory/'m2-publication-runtime-report.json').read_text())
    require(attempt['status']=='m2_publication_runtime_failed' and attempt['stage']=='publication-runtime-tests' and attempt['checks']==[],'Publication runtime scenarios were not reached')
    require([(s['name'],s['returncode']) for s in attempt['steps']]==[('refresh-publication-runtime',0),('publication-runtime-tests',101)],'Publication runtime compile receipt differs')
    log=attempt['steps'][1]['failure_log_tail']
    for text in ['E0223','src/tests.rs:47','OpenRequest::Extraction']:
        require(text in log,'Publication runtime constructor diagnosis differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in attempt['source_sha256'].items()} and len(attempt['source_sha256'])==9,'Publication runtime source snapshot inventory differs')
    require(len(attempt['protected_source_sha256'])==190 and len(attempt['dependency_packages'])==66,'Publication runtime protected source/graph inventory differs')
    for n,h in attempt['protected_source_sha256'].items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Retry changed protected source: {n}')
    for n,h in attempt['source_sha256'].items():
        if n!='m2/publication-runtime/src/tests.rs':require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Retry changed unrelated source: {n}')
    before=(directory/'qualified/m2/publication-runtime/src/tests.rs').read_text();after=(ROOT/'m2/publication-runtime/src/tests.rs').read_text()
    require(before.count('OpenRequest::Extraction {')==1 and after==before.replace('OpenRequest::Extraction {','OpenRequest {',1),'Retry must correct only the reader fixture constructor')
    from publication_runtime_lock import check_lock as check_publication_runtime_lock
    require(check_publication_runtime_lock()==attempt['dependency_packages'] and (ROOT/'m2/publication-runtime/Cargo.lock').read_text()==attempt['dependency_lock_contents'],'Retry changed dependency graph or canonical lock')
    print('PASS retained publication-runtime E0223 compile failure; isolated one-line test constructor correction verified')

    directory=ROOT/'docs/evidence/m2-publication-runtime-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted publication-runtime evidence changed: {name}')
    publication=json.loads((directory/'m2-publication-runtime-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in publication['source_sha256'].items()} and len(publication['source_sha256'])==9,'Accepted publication-runtime snapshots differ')
    require(publication['protected_source_sha256']==attempt['protected_source_sha256'] and publication['dependency_packages']==attempt['dependency_packages'] and publication['dependency_lock_contents']==attempt['dependency_lock_contents'],'Runtime retry changed protected sources/graph')
    for n,h in {**publication['protected_source_sha256'],**publication['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted publication runtime: {n}')
    require(check_publication_runtime_lock()==publication['dependency_packages'],'Accepted runtime graph differs')
    from check_publication_runtime_receipt import review as review_publication_runtime_receipt
    reviewed=review_publication_runtime_receipt(publication)
    require(reviewed==provenance['review_summary'] and reviewed['controller_exchanges']==3331 and reviewed['wire_records_recomputed']==196608,'Publication-runtime review totals differ')
    print('PASS accepted shared publication-runtime gate: 9 publications, 3331 reviewed exchanges, 196608 reported record fingerprints; M2 partial')

    directory=ROOT/'docs/evidence/m2-converter-runtime-first-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'First converter-runtime evidence changed: {name}')
    attempt=json.loads((directory/'m2-converter-runtime-report.json').read_text())
    require(attempt['status']=='m2_converter_runtime_failed' and attempt['stage']=='converter-runtime-tests' and attempt['checks']==[],'Converter scenarios were not reached')
    require([(s['name'],s['returncode']) for s in attempt['steps']]==[('refresh-converter-runtime',0),('converter-runtime-tests',101)],'Converter compile receipt differs')
    log=attempt['steps'][1]['failure_log_tail']
    require('E0753' in log and 'src/lib.rs:2' in log and 'expected outer doc comment' in log,'Converter documentation placement diagnosis differs')
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in attempt['source_sha256'].items()} and len(attempt['source_sha256'])==11,'Converter snapshot bindings differ')
    require(len(attempt['protected_source_sha256'])==199 and len(attempt['dependency_packages'])==66,'Converter protected/graph inventory differs')
    for n,h in attempt['protected_source_sha256'].items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Retry changed protected source: {n}')
    for n,h in attempt['source_sha256'].items():
        if n!='m2/converter-runtime/src/lib.rs':require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Retry changed unrelated converter source: {n}')
    before=(directory/'qualified/m2/converter-runtime/src/lib.rs').read_text().splitlines(True);after=(ROOT/'m2/converter-runtime/src/lib.rs').read_text()
    require(before[0]=='pub mod converters;\n' and before[1].startswith('//! ') and after==before[1]+before[0]+''.join(before[2:]),'Retry must only move crate documentation above module declarations')
    from converter_runtime_lock import check_lock as check_converter_runtime_lock
    require(check_converter_runtime_lock()==attempt['dependency_packages'] and (ROOT/'m2/converter-runtime/Cargo.lock').read_text()==attempt['dependency_lock_contents'],'Converter retry changed graph/lock')
    print('PASS retained converter-runtime E0753 compile failure; isolated documentation placement correction verified')

    directory=ROOT/'docs/evidence/m2-converter-runtime-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted converter-runtime evidence changed: {name}')
    conversion=json.loads((directory/'m2-converter-runtime-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in conversion['source_sha256'].items()} and len(conversion['source_sha256'])==11,'Accepted converter snapshots differ')
    require(conversion['protected_source_sha256']==attempt['protected_source_sha256'] and conversion['dependency_packages']==attempt['dependency_packages'] and conversion['dependency_lock_contents']==attempt['dependency_lock_contents'],'Converter retry changed protected graph/sources')
    for n,h in {**conversion['protected_source_sha256'],**conversion['source_sha256'],**conversion['legacy_oracle_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted converter receipt: {n}')
    require(check_converter_runtime_lock()==conversion['dependency_packages'],'Accepted converter graph differs')
    from check_converter_runtime_receipt import review as review_converter_runtime_receipt
    reviewed=review_converter_runtime_receipt(conversion,json.loads((directory/'review-oracles.json').read_text()))
    require(reviewed==provenance['review_summary'] and reviewed['records_recomputed']==68000 and reviewed['controller_exchanges']==2964,'Converter review totals differ')
    print('PASS accepted larger converter gate: 6 converters, 68000 independently recomputed Python records, 2964 exchanges; M2 partial')

    directory=ROOT/'docs/evidence/m2-real-readers-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,f'Accepted real-reader evidence changed: {name}')
    real=json.loads((directory/'m2-real-readers-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in real['source_sha256'].items()} and len(real['source_sha256'])==4,'Real-reader snapshot inventory differs')
    require(len(real['protected_source_sha256'])==210 and len(real['dependency_packages'])==66,'Real-reader source/graph inventory differs')
    for n,h in {**real['protected_source_sha256'],**real['source_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,f'Current source differs from accepted real-reader receipt: {n}')
    require(check_converter_runtime_lock()==real['dependency_packages'] and hashlib.sha256((ROOT/'m2/converter-runtime/Cargo.lock').read_bytes()).hexdigest()==real['dependency_lock_sha256'],'Real-reader dependency identities differ')
    from check_real_readers_receipt import review as review_real_readers_receipt
    reviewed=review_real_readers_receipt(real)
    require(reviewed==provenance['review_summary'] and reviewed['total_records']==296127 and reviewed['lookup_pages_reviewed']==36,'Real-reader review totals differ')
    print('PASS accepted real-reader gate: 296110 MDX entries, 17 resources, 36 raw-exact pages, 346 exchanges; M2 partial')

    directory=ROOT/'docs/evidence/official-converter-input-inspection'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Official source metadata changed: '+name)
    measured=json.loads((directory/'measurements.json').read_text())
    require(not provenance['native_conversion_qualified'] and not provenance['source_data_or_outputs_bundled'],'Inspection is not native qualification')
    require(measured['protected_source_sha256']=={**real['protected_source_sha256'],**real['source_sha256']} and len(measured['protected_source_sha256'])==214,'Official sizing protected sources differ')
    require(measured['legacy_oracle_sha256']==conversion['legacy_oracle_sha256'],'Official sizing oracle code differs')
    for n,h in {**measured['protected_source_sha256'],**measured['legacy_oracle_sha256']}.items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Official sizing source identity differs: '+n)
    from m2_real_converter_inventory import PROFILE
    require(measured['native_profile']==PROFILE and len(measured['archives'])==5 and len(measured['workbooks'])==4,'Official source/profile inventory differs')
    cases={c['converter']:c for c in measured['legacy_output_measurements']}
    expected={'cc_cedict':203362,'moe_mini':4311,'moe_idioms':5489,'moe_concise':44445,'moe_revised':162636,'moe_revised_wfg':161182}
    require({k:c['records'] for k,c in cases.items()}==expected,'Full original output counts differ')
    for kind,c in cases.items():
        require(not c['native_conversion_run'] and c['decoded_key_body_bytes']==c['key_bytes']+c['body_bytes'],'Official output sizing scope differs')
        require(bool(c['native_profile_blockers'])==(kind not in ['moe_mini','moe_idioms']),'Official eligibility differs')
    require(cases['moe_concise']['native_profile_blockers']==['workbook_row_cap','workbook_rectangle_cell_cap'],'Concise rectangle blocker lost')
    for workbook in measured['workbooks']:
        require(workbook['worksheet_scan']=='complete' and all(w['scan_complete'] and w['unsupported_scalar_cells']==0 for w in workbook['worksheets']),'Official workbook scan incomplete')
    print('PASS full official source inspection and six original Python measurements; Mini/Idioms independently measured Python references retained; M2 partial')

    directory=ROOT/'docs/evidence/m2-official-converters-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Official accepted evidence changed: '+name)
    official=json.loads((directory/'m2-official-converters-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in official['source_sha256'].items()} and len(official['source_sha256'])==3,'Official source snapshot bindings differ')
    require(not provenance['M2_complete'] and not provenance['source_data_or_dictionary_outputs_bundled'],'Official evidence scope expanded')
    from check_official_converters_receipt import review as review_official_converters
    reviewed=review_official_converters(official)
    require(reviewed==provenance['review_summary'] and reviewed['records']==9800 and reviewed['controller_exchanges']==732,'Official conversion review differs')
    print('PASS full official Mini/Idioms native gate: 9800 entries, exact Python hashes, 732 reviewed exchanges; M2 partial')

    directory=ROOT/'docs/evidence/concise-full-source-reference'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Concise reference evidence changed: '+name)
    reference=json.loads((directory/'reference.json').read_text());repeat=json.loads((directory/'python-hashseed17.json').read_text())
    require(not reference['native_run'] and not repeat['native_run'] and not provenance['native_qualification'],'Python reference metadata must not claim native execution')
    require(reference['expected_entries']==44445 and reference['data_rows']==45178 and reference['rectangle_cells']==677685,'Full Concise shape changed')
    require(reference['normalized_record_digest']==repeat['normalized_record_digest'] and repeat['source_sha256']==reference['archive']['source_sha256'] and repeat['file_bytes']==reference['expected_file_bytes']==25093253,'Independent full Concise Python references differ')
    require(reference['legacy_oracle_sha256']==official['legacy_oracle_sha256'],'Concise oracle identity differs')
    from m2_concise_full import protected_sources as concise_protected
    from concise_runtime_lock import check_lock as check_concise_lock
    require(len(concise_protected())==217 and len(check_concise_lock())==66,'Concise protected sources or graph differ')
    print('PASS independent full Concise Python references and isolated profile graph; scoped Mac gate recorded separately; M2 partial')

    directory=ROOT/'docs/evidence/m2-concise-full-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Accepted full Concise evidence changed: '+name)
    concise=json.loads((directory/'m2-concise-full-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in concise['source_sha256'].items()} and len(concise['source_sha256'])==12,'Accepted Concise source snapshots differ')
    require(not provenance['M2_complete'] and not provenance['source_or_dictionary_outputs_bundled'],'Concise evidence scope expanded')
    from check_concise_full_receipt import review as review_concise_full
    reviewed=review_concise_full(concise)
    require(reviewed==provenance['review_summary'] and reviewed['entries']==44445 and reviewed['controller_exchanges']==893,'Full Concise receipt review differs')
    print('PASS full Concise scoped native gate: 44445 entries, matching normalized Python digest, 893 reviewed exchanges; full-size reader overlap unqualified; M2 partial')

    directory=ROOT/'docs/evidence/cc-full-source-reference'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Full CC reference changed: '+name)
    reference=json.loads((directory/'reference.json').read_text())
    require(not provenance['native_qualification'] and not provenance['source_data_or_dictionary_outputs_bundled'] and not reference['native_run'],'CC reference metadata must not claim native execution')
    require(reference['expected_entries']==203362 and reference['primary_entries']==125369 and reference['traditional_entries']==77993 and reference['expected_file_bytes']==76339785,'Complete CC output shape differs')
    prior=next(c for c in measured['legacy_output_measurements'] if c['converter']=='cc_cedict')
    require(reference['raw_python_output_sha256']==prior['output_sha256'] and reference['record_digest']['records']==203362,'Complete CC raw reference differs')
    require(reference['archive']==next(a for a in measured['archives'] if a['member']=='cedict_ts.u8') and reference['legacy_oracle_sha256']==measured['legacy_oracle_sha256'],'CC reference source identities differ')
    from m2_cc_full import protected_sources as cc_protected
    from cc_runtime_lock import check_lock as check_cc_lock
    require(len(cc_protected())==229 and len(check_cc_lock())==66,'CC protected source or dependency graph differs')
    print('PASS complete CC Python reference and exclusive-profile source/graph isolation; scoped native gate recorded separately; M2 partial')

    directory=ROOT/'docs/evidence/m2-cc-full-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Accepted complete CC evidence changed: '+name)
    cc=json.loads((directory/'m2-cc-full-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in cc['source_sha256'].items()} and len(cc['source_sha256'])==12,'Accepted CC source snapshots differ')
    require(not provenance['M2_complete'] and not provenance['source_data_or_dictionary_outputs_bundled'],'CC qualification scope expanded')
    from check_cc_full_receipt import review as review_cc_full
    reviewed=review_cc_full(cc)
    require(reviewed==provenance['review_summary'] and reviewed['entries']==203362 and reviewed['controller_exchanges']==1440,'Accepted full CC receipt review differs')
    print('PASS full CC exclusive native gate: 203362 exact Python-matching entries, 1440 reviewed exchanges, zero final reservations; Revised/WFG and M2 closeout pending')

    directory=ROOT/'docs/evidence/revised-row-source-reference'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Revised row reference changed: '+name)
    reference=json.loads((directory/'reference.json').read_text());expect=reference['expected']
    require(not provenance['native_qualification'] and not provenance['source_data_or_rows_bundled'] and not reference['native_run'],'Python reference metadata must not claim native execution')
    require(expect['row_digest']['rows']==163909 and expect['row_digest']['pairs']==2950362 and expect['normalized_charge_bytes']==84706498 and len(expect['headers'])==18,'Complete Revised row shape differs')
    for name,h in reference['legacy_normalizer_sha256'].items():require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,'Captured original row normalizer changed')
    require(reference['archive']==next(a for a in measured['archives'] if a['member']=='dict_revised_2015_20260929.xlsx'),'Revised source identity differs')
    from m2_xlsx_spool import protected_sources as row_protected
    from xlsx_spool_lock import check_lock as check_row_lock
    require(len(row_protected())==241 and len(check_row_lock())==52,'Row reader source/dependency subset differs')
    print('PASS complete Revised Python row reference and isolated disk-row source/graph checks; scoped native row gate recorded separately; dictionary rendering unqualified; M2 partial')

    directory=ROOT/'docs/evidence/m2-xlsx-spool-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Accepted row-spool evidence changed: '+name)
    spool=json.loads((directory/'m2-xlsx-spool-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in spool['source_sha256'].items()} and len(spool['source_sha256'])==12,'Row source snapshot bindings differ')
    require(not provenance['M2_complete'] and not provenance['source_data_or_rows_bundled'],'Row evidence scope expanded')
    from check_xlsx_spool_receipt import review as review_row_spool
    reviewed=review_row_spool(spool,json.loads((directory/'review-oracles.json').read_text()))
    require(reviewed==provenance['review_summary'] and reviewed['full_normalized_rows']==163909 and reviewed['process_cases']==27,'Accepted row-spool review differs')
    print('PASS full Revised disk-row native gate: 163909 rows, 27 reviewed process cases, independently recomputed file extents; rendering/integration unqualified; M2 partial')

    directory=ROOT/'docs/evidence/revised-render-source-reference'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['files'].items():require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Revised/WFG reference changed: '+name)
    reference=json.loads((directory/'reference.json').read_text());repeat=json.loads((directory/'python-repeat.json').read_text())
    require(not provenance['native_qualification'] and not provenance['source_data_or_dictionary_outputs_bundled'] and not reference['native_run'] and not repeat['native_run'],'Original Python reference must not claim native execution')
    require(reference['cases']['moe_revised']['entries']==162636 and reference['cases']['moe_revised_wfg']['entries']==161182 and reference['cases']['moe_revised']['alias_redirects']==1454,'Full render count reference differs')
    require(reference['cases']['moe_revised']['normalized_record_digest']==repeat['normalized_record_digest'] and reference['archive']['source_sha256']==repeat['source_sha256'],'Repeated complete Revised Python reference differs')
    for name,h in reference['legacy_oracle_sha256'].items():require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,'Original renderer Python source changed')
    from m2_revised_render import protected_sources as render_protected
    from revised_render_lock import check_lock as check_render_lock
    require(len(render_protected())==253 and len(check_render_lock())==53,'Grouped render source/dependency graph differs')
    print('PASS complete Revised/WFG Python references and isolated group-render source/graph checks; scoped standalone native gate recorded separately; M2 partial')

    directory=ROOT/'docs/evidence/m2-revised-render-user-run'
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in {**provenance['files'],**provenance['source_snapshots']}.items():
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,'Accepted grouped-render evidence changed: '+name)
    grouped=json.loads((directory/'m2-revised-render-report.json').read_text())
    require(provenance['source_snapshots']=={'qualified/'+n:h for n,h in grouped['source_sha256'].items()} and len(grouped['source_sha256'])==12,'Grouped source snapshot bindings differ')
    require(not provenance['M2_complete'] and not provenance['source_data_or_dictionary_outputs_bundled'],'Grouped evidence scope expanded')
    from check_revised_render_receipt import review as review_grouped_render
    reviewed=review_grouped_render(grouped,json.loads((directory/'review-oracles.json').read_text()))
    require(reviewed==provenance['review_summary'] and reviewed['full_Revised_entries']==162636 and reviewed['full_WFG_entries']==161182 and reviewed['process_cases']==30,'Accepted grouped-render review differs')
    print('PASS full Revised/WFG standalone TXT gates: 162636/161182 entries, 30 reviewed process cases; background/admission integration and M2 closeout pending')
    from m2_full_converters import protected_sources as full_protected, check_reference, REFERENCE
    from full_converter_runtime_lock import check_lock as full_lock
    require(len(full_protected())==265 and len(full_lock())==68,'Full converter composition source/graph changed')
    check_reference(json.loads((ROOT/REFERENCE).read_text()))
    from check_full_converters_attempt import DIRECTORY as attempt_dir, review as review_attempt
    attempt_provenance=json.loads((attempt_dir/'provenance.json').read_text())
    for n,h in attempt_provenance['files'].items():
        require(hashlib.sha256((attempt_dir/n).read_bytes()).hexdigest()==h,'Incomplete integration evidence changed: '+n)
    require(review_attempt(json.loads((attempt_dir/'m2-full-converters-report.json').read_text()))==attempt_provenance['review_summary'],'Incomplete integration review differs')
    print('PASS incomplete first integration attempt reviewed: 31 native tests, 3 full cases, 415 exchanges; Concise RSS failed, grouped cases not reached; chunked Concise retry prepared, native retry pending')

    test_retry_dir=ROOT/'docs/evidence/m2-full-converters-test-retry'
    test_retry_provenance=json.loads((test_retry_dir/'provenance.json').read_text())
    for n,h in test_retry_provenance['files'].items():
        require(hashlib.sha256((test_retry_dir/n).read_bytes()).hexdigest()==h,'Test retry evidence changed: '+n)
    test_retry=json.loads((test_retry_dir/'m2-full-converters-report.json').read_text())
    require(test_retry['status']=='m2_full_converters_failed' and test_retry['stage']=='native-tests' and test_retry['checks']==[],'Test retry scope changed')
    require(len(test_retry['source_sha256'])==13 and len(test_retry['protected_source_sha256'])==265 and len(test_retry['steps'])==1 and test_retry['steps'][0]['returncode']==101,'Test retry source/command inventory differs')
    for n,h in test_retry['source_sha256'].items():
        require(hashlib.sha256((test_retry_dir/'attempted'/n).read_bytes()).hexdigest()==h,'Test retry snapshot binding differs: '+n)
    for n,h in test_retry['protected_source_sha256'].items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Test retry protected source changed: '+n)
    require('31 passed; 1 failed' in test_retry['steps'][0]['log_tail'] and 'MOE conversion budget exceeded' in test_retry['steps'][0]['log_tail'],'Test retry failure binding differs')
    print('PASS second integration attempt retained: 31 native tests passed, reference setup failed before full datasets; test-only profile correction pending Mac retest')

    from check_full_converters_memory import DIRECTORY as memory_attempt_dir, review as review_memory_attempt
    memory_provenance=json.loads((memory_attempt_dir/'provenance.json').read_text())
    for n,h in memory_provenance['files'].items():
        require(hashlib.sha256((memory_attempt_dir/n).read_bytes()).hexdigest()==h,'Measured memory attempt evidence changed: '+n)
    require(review_memory_attempt(json.loads((memory_attempt_dir/'m2-full-converters-report.json').read_text()))==memory_provenance['review_summary'],'Measured memory attempt review differs')
    from m2_full_converters import CONCISE_ROWS
    concise_rows=json.loads((ROOT/CONCISE_ROWS).read_text())
    require(concise_rows['source_sha256']=='af2e9ba3655799080e0f7214646bde11ca5cc5e16226bca1e9a461285e05eec6' and concise_rows['row_digest']=={'rows':45178,'pairs':677670,'key_bytes':9487380,'value_bytes':8470752,'framed_rows_sha256':'98ab6f54f1a6500a3de22953b53af034ac3c0448675f0eed241347a4cb5de0a0'},'Independent complete Concise row reference differs')
    print('PASS measured Concise memory failure reviewed: 32 native tests passed, 400.74 MiB exceeds target, 624 exchanges reviewed; new disk-backed Concise implementation/native qualification pending')

    disk_compile_dir=ROOT/'docs/evidence/m2-full-converters-disk-compile'
    disk_compile_provenance=json.loads((disk_compile_dir/'provenance.json').read_text())
    for n,h in disk_compile_provenance['files'].items():
        require(hashlib.sha256((disk_compile_dir/n).read_bytes()).hexdigest()==h,'Disk compile evidence changed: '+n)
    disk_compile=json.loads((disk_compile_dir/'m2-full-converters-report.json').read_text())
    require(disk_compile['status']=='m2_full_converters_failed' and disk_compile['stage']=='native-tests' and disk_compile['checks']==[] and len(disk_compile['steps'])==1 and disk_compile['steps'][0]['returncode']==101,'Disk compile failure scope differs')
    require('unresolved import `crate::py_space`' in disk_compile['steps'][0]['log_tail'] and 'could not compile' in disk_compile['steps'][0]['log_tail'],'Disk compile error binding differs')
    require(len(disk_compile['source_sha256'])==disk_compile_provenance['attempted_sources'] and len(disk_compile['protected_source_sha256'])==265,'Disk compile identity inventory differs')
    for n,h in disk_compile['source_sha256'].items():
        require(hashlib.sha256((disk_compile_dir/'attempted'/n).read_bytes()).hexdigest()==h,'Disk compile snapshot binding differs: '+n)
    for n,h in disk_compile['protected_source_sha256'].items():
        require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Disk compile protected source changed: '+n)
    print('PASS disk-Concise compile failure retained; helper now binds to renderer module; native compilation and full qualification pending')

    from check_full_converters_receipt import DIRECTORY as full_converter_dir, review as review_full_converters
    full_converter_provenance=json.loads((full_converter_dir/'provenance.json').read_text())
    for n,h in {**full_converter_provenance['files'],**full_converter_provenance['source_snapshots']}.items():
        require(hashlib.sha256((full_converter_dir/n).read_bytes()).hexdigest()==h,'Accepted full converter evidence changed: '+n)
    full_converter_report=json.loads((full_converter_dir/'m2-full-converters-report.json').read_text())
    require(full_converter_provenance['source_snapshots']=={'qualified/'+n:h for n,h in full_converter_report['source_sha256'].items()},'Full converter snapshot bindings differ')
    require(not full_converter_provenance['M2_complete'] and not full_converter_provenance['source_data_or_dictionary_outputs_bundled'],'Full converter evidence scope expanded')
    require(review_full_converters(full_converter_report)==full_converter_provenance['review_summary'],'Accepted full converter review differs')
    print('PASS all six full converter background profiles: 33 native tests, 2726 exchanges, 282 source identities, independent Concise rows; peak 256.29 MiB, Concise 69.99 MiB; real packing/index-build admission and M2 closeout remain')

    from m2_real_publication import protected_sources as real_publication_protected, REFERENCE as real_publication_reference
    from real_publication_lock import check_lock as real_publication_graph
    require(len(real_publication_protected())==282 and len(real_publication_graph())==68,'Real publication preparation source/graph changed')
    preflight=json.loads((ROOT/real_publication_reference).read_text())
    previous_real=json.loads((ROOT/'docs/evidence/m2-real-readers-user-run/m2-real-readers-report.json').read_text())
    require(set(preflight)=={c['case'] for c in previous_real['checks']},'Real publication source selection differs')
    for c in previous_real['checks']:
        info=preflight[c['case']]
        require(info['source_sha256']==c['source_sha256'] and info['records']==c['independent_scan']['records'] and info['key_bytes']==c['independent_scan']['key_bytes'] and info['decoded_bytes']==info['key_bytes']+c['independent_scan']['payload_bytes'],'Real publication source preflight differs')
    require([n for n,c in preflight.items() if c['packing_blockers']]==['cc-cedict-mdx'],'Packing eligibility scope differs')
    print('PASS real publication preparation: full independent inventory of four dictionaries, three within existing packing caps; exclusive index-build adapter prepared; native qualification pending')

    from check_real_publication_receipt import DIRECTORY as real_publication_dir, review as review_real_publication
    real_publication_provenance=json.loads((real_publication_dir/'provenance.json').read_text())
    for n,h in {**real_publication_provenance['files'],**real_publication_provenance['source_snapshots']}.items():
        require(hashlib.sha256((real_publication_dir/n).read_bytes()).hexdigest()==h,'Accepted real publication evidence changed: '+n)
    real_publication_report=json.loads((real_publication_dir/'m2-real-publication-report.json').read_text())
    require(real_publication_provenance['source_snapshots']=={'qualified/'+n:h for n,h in real_publication_report['source_sha256'].items()},'Real publication snapshot bindings differ')
    require(not real_publication_provenance['M2_complete'] and not real_publication_provenance['source_data_or_dictionary_outputs_bundled'],'Real publication scope expanded')
    require(review_real_publication(real_publication_report)==real_publication_provenance['review_summary'],'Accepted real publication review differs')
    print('PASS bounded real publication/index admission: 36 native tests, 5 complete packed outputs, 4 complete original indexes, 925 exchanges, 300 source identities; full CC packing remains outside caps; M2 partial')

    from m2_cc_pack import protected_sources as cc_pack_protected, REFERENCE as cc_pack_reference
    from cc_pack_lock import check_lock as cc_pack_graph
    require(len(cc_pack_protected())==300 and len(cc_pack_graph())==69,'Block-spooled pack preparation source/graph differs')
    cc_reference=json.loads((ROOT/cc_pack_reference).read_text())
    accepted_cc=next(c for c in real_publication_report['checks'] if c['case']=='cc-cedict-mdx')
    require(cc_reference['inventory']==accepted_cc['inventory'] and cc_reference['expected_sorted_scan']==accepted_cc['index_verifier_reply']['scan'],'Complete CC source/sorted scan reference differs')
    require(cc_reference['inventory']['records']==202884 and cc_reference['inventory']['decoded_bytes']==75162810 and cc_reference['inventory']['manifest_bytes']==84130038,'Complete CC packing source extent differs')
    print('PASS complete CC packing preparation: isolated block-spooled MDX writer, 300 protected identities, 69-package graph; full native tests, UTF-8/UTF-16 packing and measured RSS pending')

    from check_cc_pack_receipt import DIRECTORY as cc_pack_dir, review as review_cc_pack
    cc_pack_provenance=json.loads((cc_pack_dir/'provenance.json').read_text())
    for n,h in {**cc_pack_provenance['files'],**cc_pack_provenance['source_snapshots']}.items():
        require(hashlib.sha256((cc_pack_dir/n).read_bytes()).hexdigest()==h,'Accepted CC packing evidence changed: '+n)
    cc_pack_report=json.loads((cc_pack_dir/'m2-cc-pack-report.json').read_text())
    require(cc_pack_provenance['source_snapshots']=={'qualified/'+n:h for n,h in cc_pack_report['source_sha256'].items()},'CC packing snapshot bindings differ')
    require(not cc_pack_provenance['M2_complete'] and not cc_pack_provenance['source_data_or_dictionary_outputs_bundled'],'CC packing scope expanded')
    require(review_cc_pack(cc_pack_report)==cc_pack_provenance['review_summary'],'Accepted CC packing review differs')
    print('PASS full CC packing: 202884 entries each UTF-8/UTF-16, 44 native tests, 1273 exchanges, 324 identities; runtime RSS 57.23 MiB; M2 closeout review pending')

    from m2_closeout import DECISION as m2_decision_path, review as review_m2_closeout
    closeout_dir=ROOT/'docs/evidence/m2-closeout-review'
    closeout_provenance=json.loads((closeout_dir/'provenance.json').read_text())
    for n,h in closeout_provenance['files'].items():
        require(hashlib.sha256((closeout_dir/n).read_bytes()).hexdigest()==h,'M2 closeout decision changed without review: '+n)
    require(not closeout_provenance['new_Rust_commands_run'] and not closeout_provenance['historical_native_reports_rewritten'] and not closeout_provenance['private_sources_or_dictionary_outputs_bundled'],'Closeout provenance scope expanded')
    closeout=review_m2_closeout(json.loads((ROOT/m2_decision_path).read_text()))
    require(closeout['M2_complete'] and not closeout['production_release_ready'] and closeout['accepted_criteria']==5 and closeout['accepted_source_identities']==324,'M2 closeout scope differs')
    print('PASS M2 scoped native backend closeout: five criteria, 23 bound receipts, 324 source identities; ready for Tauri integration, not a production desktop release')

if __name__ == "__main__":
    main()
