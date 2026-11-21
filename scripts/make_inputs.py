"""Materialize synthetic inputs for manual converter checks. New directory only."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "baseline"))
from capture import workbook

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=False)
cases = json.loads((ROOT / "baseline/cases.json").read_text(encoding="utf-8"))
workbook(destination / "moe.xlsx", cases["moe_rows"])
(destination / "cedict.u8").write_text(cases["cedict"], encoding="utf-8")
(destination / "engine-source.txt").write_text("".join(f'{v["key"]}\n{v["text"]}\n</>\n' for v in cases["engine_entries"]), encoding="utf-8")
for resource in cases["engine_resources"]:
    path = destination / "resources" / resource["key"].replace("\\", "/").lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(resource["bytes"]))
print(destination)
