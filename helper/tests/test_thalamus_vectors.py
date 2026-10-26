"""Central golden vectors (a copy of the Ashley-side fixtures). The peripheral vectors tested the thalamus's
decide(), which D2 removed; the central copy only checks that its bytes and manifest still agree."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "domus_helper" / "thalamus" / "vectors"
CENTRAL = (
    "habituation-recovery.json",
    "dishabituation.json",
    "exact-threshold.json",
    "refractory.json",
    "clock-rollback.json",
    "duplicate-out-of-order.json",
    "coalescing.json",
    "README.md",
)


def test_central_manifest_and_schema():
    folder = ROOT / "central"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    assert sorted(manifest) == sorted(CENTRAL)
    for name, digest in manifest.items():
        blob = (folder / name).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == digest
        if name.endswith(".json"):
            assert json.loads(blob)["schemaVersion"] == 1


def test_central_bytes_match_sibling_checkout():
    # helper/tests/<file> -> parents[2] is the worktree; sibling repo is ../Ashley.
    ashley = Path(__file__).resolve().parents[2] / ".." / "Ashley"
    source = ashley / "apps" / "agent-service" / "src" / "core" / "cognitive-v021" / "thalamus" / "vectors"
    if not source.is_dir():
        pytest.skip("sibling Ashley checkout is not present")
    folder = ROOT / "central"
    for name in CENTRAL:
        assert (folder / name).read_bytes() == (source / name).read_bytes()
