"""R3: the helper's vendored probe modules are byte-identical to the probe's own (the helper must not import the
probe tree, so it carries copies; this keeps them from drifting). __init__.py is the vendor package's own file."""
import hashlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "helper" / "domus_helper" / "vendor"
PROBE = REPO / "sims-e1" / "src" / "ashley_e1"
VENDORED = ("schema.py", "cmdbox.py", "e2_admission.py", "e2_cards.py", "e2_lineage.py", "e2_trial.py")


def test_every_vendored_module_is_listed():
    present = sorted(path.name for path in VENDOR.glob("*.py") if path.name != "__init__.py")
    assert present == sorted(VENDORED)


@pytest.mark.parametrize("name", VENDORED)
def test_vendored_copy_matches_the_probe(name):
    vendored = hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
    probe = hashlib.sha256((PROBE / name).read_bytes()).hexdigest()
    assert vendored == probe, "helper/domus_helper/vendor/%s drifted from sims-e1/src/ashley_e1/%s" % (name, name)
