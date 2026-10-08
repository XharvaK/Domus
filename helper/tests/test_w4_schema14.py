"""W4 item 0: the helper's telemetry reader accepts schema 14 observation rows (a held dialog window
with its window fields and a pace block) and still accepts schema 13 rows. Invented strings only."""
import pytest

from domus_helper import telemetry
from domus_helper.vendor import schema
from conftest import event, opened, session_file


def _window(**over):
    item = dict(dialog_id="1001", kind="PICKER", owner_id=None, title_key="0x1", text_key=None,
                responses=[], auto_respond=False,
                rows=[dict(option_id="7", name_key=None, enabled=True, price=None)],
                held=True, cause="hers", select=dict(min=1, max=1), counts=None, text_inputs=None)
    item.update(over)
    return item


PACE = dict(need_drain=0.5, motives_modified=3, drain_measured=0.5, slow_time=1.0,
            clock_scale=1.0, clock_foreign=False)


def _observation(seq=1, **payload):
    return event("presence_snapshot", seq, observation_complete=True,
                 dialogs=dict(open=[_window()], closed=[], truncated=False), pace=dict(PACE), **payload)


def test_schema_14_is_accepted_by_the_vendored_validator():
    assert schema.OBSERVATION_SCHEMA_VERSION == 14
    assert 14 in schema.ACCEPTED_SCHEMA_VERSIONS
    assert 13 in schema.ACCEPTED_SCHEMA_VERSIONS


def test_schema_14_presence_row_with_dialog_and_pace_passes_validation(paths):
    row = _observation()
    assert schema.validate_record(row) is row
    path = session_file(paths, [opened(), row])
    rows = list(telemetry.file_rows(path))
    assert rows[1]["schema_version"] == 14
    assert rows[1]["pace"]["need_drain"] == 0.5
    assert rows[1]["dialogs"]["open"][0]["held"] is True


def test_schema_14_row_reads_back_through_the_tail_reader(paths):
    path = session_file(paths, [opened(), _observation(seq=1)])
    tail = telemetry.tail(["presence_snapshot"], 5, paths=paths, session=path)
    assert tail[0]["dialogs"]["open"][0]["cause"] == "hers"


def test_schema_13_observation_row_without_window_or_pace_still_passes(paths):
    row = event("presence_snapshot", 1, observation_complete=True, dialogs=dict(open=[dict(
        dialog_id="1001", kind="PICKER", owner_id=None, title_key="0x1", text_key=None,
        responses=[], auto_respond=False, rows=[])], closed=[], truncated=False))
    row["schema_version"] = 13
    path = session_file(paths, [opened(), row])
    assert len(list(telemetry.file_rows(path))) == 2


@pytest.mark.parametrize("field, value", [("cause", "nobody"), ("held", "yes")])
def test_schema_14_window_fields_are_checked(field, value):
    row = _observation()
    row["dialogs"]["open"][0][field] = value
    with pytest.raises(schema.SchemaError):
        schema.validate_record(row)


def test_schema_14_pace_block_shape_is_checked():
    row = _observation()
    row["pace"] = dict(PACE, extra=1)
    with pytest.raises(schema.SchemaError):
        schema.validate_record(row)
