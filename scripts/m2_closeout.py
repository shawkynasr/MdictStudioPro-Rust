"""Reconcile accepted M2 receipts into a scoped backend completion decision.

Read-only audit: does not run Rust, raise limits, or relabel historical reports.
Run as part of package.py after the existing full evidence validators.
"""
import hashlib
import json
from pathlib import Path
from m2_sizing import ROOT,require
DECISION='docs/evidence/m2-closeout-review/decision.json'
CRITERIA={
 'ordinary_v2_import_lookup': ['m2-v2-import-user-run/m2-v2-import-report.json','m2-import-jobs-user-run/m2-import-jobs-report.json','m2-sessions-user-run/m2-sessions-report.json','m2-real-readers-user-run/m2-real-readers-report.json'],
 'metadata_stylesheet_preservation': ['m2-metadata-user-run/m2-metadata-report.json','m2-metadata-jobs-user-run/m2-metadata-jobs-report.json','m2-metadata-native-user-confirmation/confirmation.json','m2-metadata-jobs-native-user-confirmation/confirmation.json'],
 'bounded_sizing_indexing_resources': ['m2-sizing-user-run/m2-sizing-report.json','m2-index-user-run/m2-index-report.json','m2-stream-extract-user-run/m2-stream-extract-report.json','m2-extraction-jobs-user-run/m2-extraction-jobs-report.json','m2-large-io-user-run/m2-large-io-report.json','m2-publication-runtime-user-run/m2-publication-runtime-report.json','m2-converter-runtime-user-run/m2-converter-runtime-report.json','m2-full-converters-user-run/m2-full-converters-report.json','m2-real-publication-user-run/m2-real-publication-report.json','m2-cc-pack-user-run/m2-cc-pack-report.json'],
 'representative_full_inputs': ['m2-official-converters-user-run/m2-official-converters-report.json','m2-concise-full-user-run/m2-concise-full-report.json','m2-cc-full-user-run/m2-cc-full-report.json','m2-xlsx-spool-user-run/m2-xlsx-spool-report.json','m2-revised-render-user-run/m2-revised-render-report.json','m2-full-converters-user-run/m2-full-converters-report.json','m2-real-readers-user-run/m2-real-readers-report.json','m2-real-publication-user-run/m2-real-publication-report.json','m2-cc-pack-user-run/m2-cc-pack-report.json'],
 'regression_source_integrity_closeout': ['m2-cc-pack-user-run/m2-cc-pack-report.json','m2-real-publication-user-run/m2-real-publication-report.json','m2-full-converters-user-run/m2-full-converters-report.json'],
}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory():
    r=json.loads((ROOT/'docs/evidence/m2-cc-pack-user-run/m2-cc-pack-report.json').read_text());p={**r['protected_source_sha256'],**r['source_sha256']};require(len(p)==324,'Expected 324 accepted source identities')
    for n,h in p.items():
        relative=Path(n);require(not relative.is_absolute() and '..' not in relative.parts,'Unsafe source identity');require(digest(ROOT/relative)==h,'Accepted backend source changed: '+n)
    return p
def build_decision():
    sources=inventory();paths=sorted({n for group in CRITERIA.values() for n in group});receipts={}
    for n in paths:
        path=ROOT/'docs/evidence'/n;value=json.loads(path.read_text());receipts[n]={'sha256':digest(path),'recorded_status':value.get('status'),'kind':'reader_attestation' if n.endswith('confirmation.json') else 'native_gate_receipt'}
    # These reviewers enforce full transcripts, limits and exact dependency edges.
    from check_full_converters_receipt import DIRECTORY as full_dir,review as full_review
    from check_real_publication_receipt import DIRECTORY as real_dir,review as real_review
    from check_cc_pack_receipt import DIRECTORY as cc_dir,review as cc_review
    summaries={'full_converters':full_review(json.loads((full_dir/'m2-full-converters-report.json').read_text())),'real_publication':real_review(json.loads((real_dir/'m2-real-publication-report.json').read_text())),'CC_packing':cc_review(json.loads((cc_dir/'m2-cc-pack-report.json').read_text()))}
    return {'schema':'studio-m2-closeout-v1','review_date':'2026-11-07','decision':'complete_scoped_native_backend_foundation_ready_for_Tauri_integration','M2_complete':True,'scope':'tested bounded native backend profiles on the user Mac; not desktop feature parity or a production release','production_release_ready':False,'Tauri_GUI_integrated':False,'all_formats_or_platforms_qualified':False,'hard_OS_memory_enforcement':False,'M0_capture_complete':False,'historical_native_reports_modified':False,'new_Rust_commands_run_for_closeout':False,'regression_basis':'recent accepted 39-test runtime plus 5-test block-writer suite, unchanged prior sources, full accepted evidence validation and local Python contract suite','criteria':{k:{'status':'accepted_within_documented_profile','receipts':v} for k,v in CRITERIA.items()},'receipt_bindings':receipts,'accepted_source_sha256':sources,'accepted_source_identities':324,'recent_review_summaries':summaries,'runtime_handoff':'m2/cc-pack-runtime: qualified publication/index/reader facade; retain separate bounded metadata and redirect APIs behind deliberate M3 routing','mandatory_M3_boundaries':['keep explicit profile/size selection and typed limit errors','coordinate separate metadata/redirect APIs before exposing concurrent GUI commands','preserve reader close/release and one-transfer job result lifecycle','isolate dictionary HTML/resources from privileged commands','localize Chinese English Arabic and support RTL','keep optional Python plugin protocol separate from ordinary stdout','qualify packaging and each additional platform independently'],'explicit_deferrals':['Tauri GUI and installer/signing/updater integration','complete original GUI/plugin parity and remaining M0 runtime capture','large indexed-session redirect resolution','larger generic export or metadata-edit envelopes beyond qualified caps','hard process-memory enforcement and arbitrary-size input guarantees','power-loss durability crash-orphan recovery and complete crash recovery policy','Windows/Linux native qualification and resource filesystem policies','unqualified legacy encodings LZO/protected inputs and MDX v3 roadmap'],'next_milestone':'Tauri shell and GUI integration with explicit backend profile routing','routine_native_rerun_required':False}
def review(value):
    expected=build_decision();require(value==expected,'Closeout decision differs from validated scope, sources or receipts');return {'M2_complete':True,'production_release_ready':False,'accepted_criteria':len(CRITERIA),'unique_receipt_bindings':len(expected['receipt_bindings']),'accepted_source_identities':324,'new_Rust_commands_run_for_closeout':False,'next_milestone':expected['next_milestone']}
if __name__=='__main__':print(json.dumps(review(json.loads((ROOT/DECISION).read_text())),indent=2))
