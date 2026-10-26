"""C2 (Owner 2026-10-26): a body sample whose needs could not be read is never shown as a Sim with no needs."""
from domus_helper.thalamus import observation


def test_needs_that_could_not_be_read_reach_her_view_as_senses_unavailable():
    portrait = observation._portrait({"event_kind": "presence_snapshot", "motives": []})
    assert portrait["senses_unavailable"] == ["needs"]
    assert portrait["needs"] == {}


def test_read_needs_and_rows_without_a_body_carry_no_flag():
    read = observation._portrait({"event_kind": "presence_snapshot", "motives": [{"id": "1", "value": 40, "band": "ok"}]})
    assert "senses_unavailable" not in read
    assert "senses_unavailable" not in observation._portrait({"event_kind": "speed_event"})
