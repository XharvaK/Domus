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


def test_probe_2_41_3_read_faults_in_missingness_reach_her_view():
    row = {"event_kind": "presence_snapshot", "motives": [{"id": "1", "value": 40, "band": "ok"}], "missingness": {
        "sim_signals": {"status": "UNKNOWN", "detail": "senses unavailable: buffs_error"}}}
    assert observation._portrait(row)["senses_unavailable"] == ["moodlets"]
    row = {"event_kind": "presence_snapshot", "motives": [], "missingness": {
        "motives": {"status": "UNKNOWN", "detail": "senses unavailable: no_tracker"},
        "sim_signals": {"status": "UNKNOWN", "detail": "senses unavailable: entry_error"}}}
    assert observation._portrait(row)["senses_unavailable"] == ["needs", "moodlets"]
    # Other missingness (a company list that missed someone) is not a senses fault.
    row = {"event_kind": "presence_snapshot", "motives": [{"id": "1"}], "missingness": {
        "presence": {"status": "MISSING", "detail": "unreadable"}}}
    assert "senses_unavailable" not in observation._portrait(row)


def test_probe_2_41_4_a_partial_moodlets_read_is_not_senses_unavailable():
    row = {"event_kind": "presence_snapshot", "motives": [{"id": "1"}], "missingness": {
        "sim_signals": {"status": "MISSING", "detail": "senses partial: 1 unreadable"}}}
    assert "senses_unavailable" not in observation._portrait(row)


def test_nit_a_partial_read_is_surfaced_as_senses_partial():
    row = {"event_kind": "presence_snapshot", "motives": [{"id": "1"}], "missingness": {
        "sim_signals": {"status": "MISSING", "detail": "senses partial: 2 unreadable"}}}
    portrait = observation._portrait(row)
    assert portrait["senses_partial"] == ["moodlets"]
    assert "senses_unavailable" not in portrait
    assert "senses_partial" not in observation._portrait({"event_kind": "presence_snapshot", "motives": [{"id": "1"}]})
