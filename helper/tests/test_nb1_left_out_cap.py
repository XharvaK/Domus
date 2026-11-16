"""NB-1: Natalis accepts at most 12 `left_out` lines per object, so the helper's own lines are capped to fit."""
import re

from domus_helper.acts import RefBook, _cap_left_out, options


def _excluded(count, why="PIE_PICKER"):
    return [{"name": "thing_Hidden%02d" % number, "why": why} for number in range(count)]


def _object(excluded):
    return {"object_id": "2", "class": "object_thing_2", "room": "1", "distance_m": 2.0, "same_room": True,
            "acts": [], "excluded": excluded}


def _left_out(excluded):
    result = options({"room": "1", "objects": [_object(excluded)]})
    return result[0]["left_out"]


def _utf16_units(line):
    return len(line.encode("utf-16-le")) // 2


def _acts_accounted_for(lines):
    """Kept lines are one act each; a remainder line names its count."""
    total = 0
    for line in lines:
        fold = re.match(r"^and (\d+) more$", line)
        remainder = re.match(r"^(\d+) more acts: left out: ", line)
        if fold:
            total += int(fold.group(1))
        elif remainder:
            total += int(remainder.group(1))
        else:
            total += 1
    return total


def test_sixteen_excluded_acts_are_capped_at_twelve_lines_with_a_remainder_line():
    left_out = _left_out(_excluded(16))
    assert len(left_out) <= 12
    assert re.match(r"^\d+ more acts: left out: ", left_out[-1])
    assert all(_utf16_units(line) <= 160 for line in left_out)


def test_thirteen_excluded_acts_are_capped_at_twelve_lines():
    assert len(_left_out(_excluded(13))) <= 12


def test_a_phone_menu_with_twelve_excluded_acts_and_a_folded_line_is_capped_at_twelve_lines():
    phone = {"object_id": "11", "class": "object_phone", "phone": True, "distance_m": 0.0, "same_room": True,
             "acts": [{"guid64": "4242", "name": "phone_Read", "text_key": None},
                      {"guid64": "4243", "name": "phone_Read", "text_key": None}]}
    menu = {"menu_rev": 1, "room": "4", "objects": [phone],
            "excluded_phone": [{"name": "phone_Act%02d" % number, "why": "hidden"} for number in range(12)]}
    listed = options(menu, resolve={}.get, refs=RefBook())
    assert len(listed) == 1
    assert len(listed[0]["left_out"]) <= 12


def test_three_excluded_acts_keep_three_lines_unchanged():
    left_out = _left_out(_excluded(3))
    assert left_out == [
        "thing Hidden00: left out: it opens a menu of choices, not an act",
        "thing Hidden01: left out: it opens a menu of choices, not an act",
        "thing Hidden02: left out: it opens a menu of choices, not an act",
    ]


def test_sixteen_distinct_reasons_fold_the_rest_into_one_and_more_line():
    lines = ["act%d: left out: reason %d" % (index, index) for index in range(16)]
    capped = _cap_left_out(lines)
    assert len(capped) <= 12
    assert re.match(r"^and \d+ more$", capped[-1])
    assert _acts_accounted_for(capped) == 16


def test_sixteen_excluded_acts_with_distinct_reasons_fold_the_rest_into_one_and_more_line():
    why_codes = ["PIE_PICKER", "DENY_NAME", "TRAVEL", "NOT_USER_DIRECTED", "MENU_HIDDEN", "SOCIAL", "PICKER",
                 "FOLDED", "CAP", "NO_NAME", "NO_GUID", "PIE_EMPTY", "GAME_REFUSED", "PHONE", "POSTURE_SOURCE",
                 "OTHER_CODE"]
    excluded = [{"name": "thing_Hidden%02d" % index, "why": why} for index, why in enumerate(why_codes)]
    left_out = _left_out(excluded)
    assert len(left_out) <= 12
    assert re.match(r"^and \d+ more$", left_out[-1])
    assert _acts_accounted_for(left_out) == 16

