"""Offline-only revision-4 checks. Never opens or imports a native reader."""
import argparse
import json
import re
from pathlib import Path
import struct
import subprocess
import sys
from patched_interop import ROOT,require,experiment_command,hash_file
from v2_audit import audit


def wire_contract(path,observation):
    checks={}
    with path.open("rb") as stream:
        length=struct.unpack(">I",stream.read(4))[0]
        require(length<=1024*1024,"Oversized diagnostic header")
        xml=stream.read(length).decode("utf-16le")
    attrs=dict(re.findall(r'(\w+)="(.*?)"',xml,re.S))
    checks["structure"]=observation["status"]=="structural_audit_passed"
    checks["explicit_unencrypted_header"]=attrs.get("Encrypted")=="No"
    checks["header_CRLF_then_NUL"]=xml.endswith("\r\n\0")
    if path.suffix.lower()==".mdx":
        checks["all_MDX_records_have_encoded_terminal_NUL"]=observation.get("records_without_terminal_null")==0
    else:
        checks["MDD_has_explicit_empty_encoding"]=attrs.get("Encoding")==""
        checks["MDD_legacy_metadata_present"]=all(k in attrs for k in ["Title","Description","Format","Compact","Compat","CreationDate","RegisterBy","StyleSheet"])
    return {"status":"passed" if all(checks.values()) else "failed","checks":checks,"sha256":hash_file(path)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={"status":"blocked","suite":"native-wire-revision-4","native_readers":"NOT_RUN_DO_NOT_IMPORT","writer_revision":4,"checks":{},"steps":[],"not_proven":["native_crash_fixed","native_sort_and_strip_policy_consistency","generic_XML_stylesheet_semantics","production_writer_qualification"]}
    def run(name,cmd,allow_failure=False):
        result=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
        (out/f"{name}.log").write_text(result.stdout+"\nSTDERR:\n"+result.stderr,encoding="utf-8")
        report["steps"].append({"name":name,"returncode":result.returncode,"log":f"{name}.log"})
        if not allow_failure:require(result.returncode==0,f"{name} failed; see log")
        return result
    try:
        run("prepare",[sys.executable,ROOT/"scripts/prepare_sort_experiment.py","--revision","4","--reuse"])
        # Same workspace/lock, isolated candidate selected explicitly.
        cmd=experiment_command(4)
        run("rust-tests",cmd[:3]+["test","--locked","--manifest-path","experiments/legacy-sort/Cargo.toml"])
        run("fixture-build",[sys.executable,ROOT/"scripts/reader_fixtures.py","--writer-revision","4","--output",out/"fixtures"])
        run("interop",[sys.executable,ROOT/"scripts/patched_interop.py","--writer-revision","4","--output",out/"interop"])
        # Keep the known standard-XML stylesheet disagreements visible.
        run("metadata",[sys.executable,ROOT/"scripts/metadata_codecs.py","--writer-revision","4","--output",out/"metadata"],allow_failure=True)
        metadata=json.loads((out/"metadata/metadata-codec-report.json").read_text(encoding="utf-8"))
        report["metadata_result"]={"status":metadata["status"],"counts":metadata.get("counts"),"report":"metadata/metadata-codec-report.json"}
        require(metadata.get("counts")=={"passed":91,"failed":10,"unsupported":2,"blocked":8},"Metadata observation inventory changed; review before proceeding")
        expected_statuses={}
        for name,result in metadata.get("checks",{}).items():
            if result["status"]=="failed":
                require(name.startswith("forward-") and name.endswith("-xml") and '"StyleSheet"' in result.get("error",""),f"New metadata failure: {name}")
                expected_statuses[name]=result["status"]
            elif result["status"]=="unsupported":require("gb18030" in name,"Unexpected unsupported case")
            elif result["status"]=="blocked":
                require(result.get("dependencies") and all(metadata["checks"][d]["status"]=="unsupported" for d in result["dependencies"]),"Unexpected blocked metadata case")
        require(metadata["status"]=="failed" and len(metadata.get("checks",{}))==111 and len(expected_statuses)==10,"Metadata suite did not reach the expected unresolved stylesheet gate")
        report["unresolved_stylesheet_checks"]=list(expected_statuses)
        files=sorted((out/"fixtures/dictionaries").glob("*"))
        files=[p for p in files if p.suffix.lower() in {".mdx",".mdd"}]
        require(len(files)==16,"Expected eight synthetic MDX/MDD pairs")
        for path in files:
            observed=audit(path)
            check=wire_contract(path,observed)
            report["checks"][path.name]={**check,"structural_audit":observed}
        require(all(c["status"]=="passed" for c in report["checks"].values()),"Revision-4 wire invariant failed")
        report["status"]="offline_checks_passed_native_untested"
    except Exception as error:
        if report["checks"]:report["status"]="failed_offline_wire"
        report["error"]=str(error)
    finally:
        (out/"native-wire-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{report['status']}: {out/'native-wire-report.json'}")
    return 0 if report["status"]=="offline_checks_passed_native_untested" else 1


if __name__=="__main__":raise SystemExit(main())
