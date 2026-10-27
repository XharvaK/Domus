"""DA4b vendor drift and schema-4 calibration coverage on the DA5 session."""
import ast
import json
from pathlib import Path

from domus_helper import calibration


def test_revendored_files_match_probe():
    root = Path(__file__).resolve().parents[2]
    for module in ("schema", "cmdbox", "e2_cards", "e2_trial", "e2_admission", "e2_lineage"):
        source = root / "sims-e1" / "src" / "ashley_e1" / (module + ".py")
        vendor = root / "helper" / "domus_helper" / "vendor" / (module + ".py")
        assert ast.dump(ast.parse(source.read_text(encoding="utf-8"))) == ast.dump(
            ast.parse(vendor.read_text(encoding="utf-8")))


def test_da5_calibration_coverage_unchanged():
    evidence = (Path(__file__).resolve().parents[2] / "sims-e1" / "tests" / "fixtures" / "evidence"
                / "DA5_CALIBRATION_2026-10-04"
                / "ashley_e1_c964da78-8841-41c4-ab87-3895fb228b2d.jsonl")
    rows = []
    with evidence.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    coverage = calibration.analyze(rows)["coverage"]
    assert coverage["affordances"] == 97
    assert coverage["autonomy_spans"] == 268
    assert coverage["gaps"] == 2
