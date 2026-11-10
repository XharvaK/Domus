"""B-1: the helper's observation `excluded` entries match the shared Natalis wire fixture ({text, reason})."""
import json
from pathlib import Path

from domus_helper.acts import options

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "excluded_wire.json"


def test_helper_excluded_matches_the_shared_wire_fixture():
    hidden = {
        "object_id": "2",
        "class": "object_thing_2",
        "room": "1",
        "distance_m": 2.0,
        "same_room": True,
        "acts": [],
        "excluded": [
            {"name": "thing_Clean", "why": "PIE_PICKER"},
            {"name": "thing_Hide", "why": "MENU_HIDDEN"},
            {"name": "thing_Auto", "why": "NOT_USER_DIRECTED"},
        ],
    }
    read = {
        "object_id": "3",
        "class": "object_thing_3",
        "room": "1",
        "distance_m": 3.0,
        "same_room": True,
        "acts": [{"guid64": "1001", "name": "thing_Read", "text_key": None}],
    }
    result = options({"room": "1", "objects": [hidden, read]})
    shown = next(entry for entry in result if entry["object_id"] == "2")
    expected = json.loads(FIXTURE.read_text())
    assert shown["excluded"] == expected
