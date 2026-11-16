"""B-1: the helper's observation `excluded` entries match the shared Natalis wire fixture ({text, reason})."""
import json
from pathlib import Path

from domus_helper.acts import _wire_excluded, options

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


def test_excluded_text_and_reason_fit_natalis_utf16_caps():
    shown = _wire_excluded([{"name": "\U0001F600" * 81, "why": "\U0001F600" * 33}])
    assert len(shown) == 1
    text, reason = shown[0]["text"], shown[0]["reason"]
    assert text and reason
    assert len(text.encode("utf-16-le")) // 2 <= 160
    assert len(reason.encode("utf-16-le")) // 2 <= 64
    plain = _wire_excluded([{"name": "a" * 200, "why": "PIE_PICKER"}])
    assert plain == [{"text": "a" * 128, "reason": "PIE_PICKER"}]
