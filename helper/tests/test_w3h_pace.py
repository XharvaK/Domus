"""W3h in the helper: the pace settings (defaults, invalid values), the decision cost in game
minutes from ticks, the pace sentences for her portrait, and the shedding order. Invented
strings only."""
import json

from domus_helper import pace
from domus_helper.spool import Spool
from domus_helper.thalamus import observation

NOW = 2_000_000
ACT = "d" * 32


def _settings(tmp_path, text=None):
    path = tmp_path / pace.CONFIG
    if text is not None:
        path.write_text(text, encoding="utf-8")
    lines = []
    values = pace.read_config(path, log=lines.append)
    return values, lines


def test_no_settings_file_means_the_defaults_and_no_log_line(tmp_path):
    values, lines = _settings(tmp_path)
    assert values == {"need_drain": 0.5, "slow_time": 1.0}
    assert lines == []


def test_valid_settings_are_read(tmp_path):
    values, lines = _settings(tmp_path, '{"need_drain": 0.25, "slow_time": 0.4}')
    assert values == {"need_drain": 0.25, "slow_time": 0.4}
    assert lines == []


def test_invalid_values_fall_back_per_key_with_one_log_line(tmp_path):
    values, lines = _settings(tmp_path, '{"need_drain": 2, "slow_time": "fast"}')
    assert values == {"need_drain": 0.5, "slow_time": 1.0}
    assert lines == ["pace settings need_drain, slow_time not in [0.25, 1.0]; using the defaults for them"]


def test_booleans_nan_and_low_values_are_refused_but_the_other_key_is_kept(tmp_path):
    values, lines = _settings(tmp_path, '{"need_drain": true, "slow_time": 0.1}')
    assert values == {"need_drain": 0.5, "slow_time": 1.0}
    assert len(lines) == 1
    values, _ = _settings(tmp_path, '{"need_drain": 0.75, "slow_time": NaN}')
    assert values == {"need_drain": 0.75, "slow_time": 1.0}


def test_unreadable_or_non_object_settings_fall_back_with_one_log_line(tmp_path):
    values, lines = _settings(tmp_path, "[1, 2]")
    assert values == {"need_drain": 0.5, "slow_time": 1.0}
    assert len(lines) == 1
    values, lines = _settings(tmp_path, "{not json")
    assert values == {"need_drain": 0.5, "slow_time": 1.0}
    assert len(lines) == 1


def test_settings_reread_when_the_file_changes(tmp_path):
    lines = []
    settings = pace.PaceSettings(tmp_path, log=lines.append)
    assert settings.refresh() == {"need_drain": 0.5, "slow_time": 1.0}
    (tmp_path / pace.CONFIG).write_text('{"slow_time": 0.5}', encoding="utf-8")
    assert settings.refresh() == {"need_drain": 0.5, "slow_time": 0.5}
    assert settings.refresh() == {"need_drain": 0.5, "slow_time": 0.5}
    assert lines == []


def test_a_game_minute_is_1500_ticks_so_the_cost_counts_ticks_not_clock_scale():
    assert pace.TICKS_PER_GAME_MINUTE == 1500
    assert pace.game_minutes(10_000, 11_500) == 1.0
    assert pace.game_minutes(10_000, 10_300) == 0.2
    assert pace.game_minutes(10_000, 10_000) == 0.0


def test_a_cost_needs_both_ticks_in_order():
    assert pace.game_minutes(None, 11_500) is None
    assert pace.game_minutes(10_000, None) is None
    assert pace.game_minutes(11_500, 10_000) is None
    assert pace.game_minutes(10_000, True) is None


def test_needs_sentence_for_half_and_for_normal_drain():
    assert pace.needs_sentence(0.5) == "your needs drain at half the game's pace, by the User's choice."
    assert pace.needs_sentence(1.0) == "your needs drain at the game's pace."
    assert pace.needs_sentence(0.4) == "your needs drain at 0.4 times the game's pace, by the User's choice."


def test_clock_sentence_only_when_the_scale_is_not_one():
    block = {"need_drain": 0.5, "motives_modified": 6, "drain_measured": 0.5, "slow_time": 0.5,
             "clock_scale": 0.5, "clock_foreign": False}
    assert pace.portrait(block, [])["clock"] == "the game's clock runs at half its normal speed."
    block["clock_scale"] = 1.0
    assert "clock" not in pace.portrait(block, [])
    block["clock_scale"] = None
    assert "clock" not in pace.portrait(block, [])


def test_foreign_clock_is_a_fact_and_no_block_means_no_pace_entry():
    block = {"need_drain": 0.5, "slow_time": 1.0, "clock_scale": 1.0, "clock_foreign": True}
    assert pace.portrait(block, [])["clock_foreign"] == "another mod sets the game's clock; Domus leaves it alone."
    assert pace.portrait(None, []) is None
    assert pace.portrait({"need_drain": 0.5}, []) == {"needs": "your needs drain at half the game's pace, by the User's choice."}


def test_portrait_shows_the_last_three_decision_costs_newest_last():
    costs = [{"interaction": "a", "game_minutes": 1.0}, {"interaction": "b", "game_minutes": 2.0},
             {"interaction": "c", "game_minutes": 3.0}, {"interaction": "d", "game_minutes": 4.0}]
    entry = pace.portrait({"need_drain": 0.5}, costs)
    assert [item["interaction"] for item in entry["decisions"]] == ["b", "c", "d"]
    assert pace.portrait(None, costs[:1]) == {"decisions": [{"interaction": "a", "game_minutes": 1.0}]}


def test_applied_values_are_compared_with_the_wanted_ones():
    wanted = {"need_drain": 0.5, "slow_time": 1.0}
    assert not pace.applied_differs({"need_drain": 0.5, "slow_time": 1.0}, wanted)
    assert pace.applied_differs({"need_drain": 1.0, "slow_time": 1.0}, wanted)
    assert pace.applied_differs({"need_drain": 0.5}, dict(wanted, slow_time=0.5))
    assert not pace.applied_differs(None, wanted)
    # A probe that refused the clock never applies slow_time; that is not a mismatch to resend.
    refused = {"need_drain": 0.5, "slow_time": 1.0, "clock_foreign": True}
    assert not pace.applied_differs(refused, dict(wanted, slow_time=0.5))


def _spool(tmp_path):
    return Spool(tmp_path / "spool.db")


def _act_row(phase, ticks, act_id=ACT, tuning="bookshelf_ReadBook"):
    return {"event_kind": "act_event", "wall_timestamp_ms": NOW, "game": {"ticks": ticks},
            "e2": {"act_id": act_id, "phase": phase, "tuning_name": tuning}}


def test_a_decision_costs_the_game_minutes_from_its_observation_to_the_push(tmp_path):
    log = pace.PaceLog(_spool(tmp_path))
    log.observed(100_000)
    log.received([ACT])
    log.on_row(_act_row("ACCEPTED", 100_500))
    assert log.costs() == []
    log.on_row(_act_row("PUSHED", 103_000))
    assert log.costs() == [{"interaction": "bookshelf_ReadBook", "game_minutes": 2.0}]
    log.on_row(_act_row("PUSHED", 110_000))
    assert len(log.costs()) == 1


def test_the_decision_is_the_newest_observation_sent_before_the_act_came_back(tmp_path):
    spool = _spool(tmp_path)
    log = pace.PaceLog(spool)
    log.observed(100_000)
    log.observed(120_000)
    log.received(["e" * 32])
    log.observed(200_000)
    log.on_row(_act_row("PUSHED", 121_500, act_id="e" * 32))
    assert log.costs() == [{"interaction": "bookshelf_ReadBook", "game_minutes": 1.0}]


def test_decision_costs_survive_a_restart(tmp_path):
    spool = _spool(tmp_path)
    pace.PaceLog(spool).observed(50_000)
    log = pace.PaceLog(spool)
    log.received([ACT])
    log2 = pace.PaceLog(spool)
    log2.on_row(_act_row("PUSHED", 51_500))
    assert pace.PaceLog(spool).costs() == [{"interaction": "bookshelf_ReadBook", "game_minutes": 1.0}]


def test_a_push_with_no_decision_or_no_ticks_records_nothing(tmp_path):
    log = pace.PaceLog(_spool(tmp_path))
    log.received([ACT])
    log.on_row(_act_row("PUSHED", 5_000))
    log.observed(9_000)
    log.received([ACT])
    log.on_row({"event_kind": "act_event", "e2": {"act_id": ACT, "phase": "PUSHED"}})
    assert log.costs() == []


def test_pending_acts_are_kept_to_a_limit(tmp_path):
    spool = _spool(tmp_path)
    log = pace.PaceLog(spool)
    log.observed(1)
    log.received(["%032d" % number for number in range(pace.PENDING_KEPT + 5)])
    assert len(json.loads(spool.get_kv("pace_log"))["pending"]) == pace.PENDING_KEPT


def _body(pace_block=None, windows=None):
    row = {"game": {"calendar": "10:00:00.000 day:1 week:1", "clock_speed": "NORMAL", "paused": False},
           "presence": [{"is_body": True, "id": 1, "name": "Body"}]}
    return observation._portrait(row, windows=windows, pace=pace.portrait(pace_block, []))


def test_the_portrait_carries_the_pace_entry_when_there_is_one():
    portrait = _body({"need_drain": 0.5, "clock_scale": 1.0, "slow_time": 1.0})
    assert portrait["pace"] == {"needs": "your needs drain at half the game's pace, by the User's choice."}
    assert "pace" not in _body(None)


def _row_with_mood(size, running=True):
    row = {"game": {}, "mood": {"name": "m" * size},
           "presence": [{"is_body": True, "id": 1, "name": "Body"}]}
    if running:
        row["interactions"] = {"observed": [{"affordance_text": "<class 'x.bookshelf-ReadBook'>",
                                             "membership": "RUNNING"}]}
    return row


def _size(value):
    return observation._bytes(value)


def test_over_the_limit_the_pace_entry_goes_whole_before_the_running_lists():
    limit = observation._PORTRAIT_LIMIT
    entry = pace.portrait({"need_drain": 0.5}, [{"interaction": "q" * 60, "game_minutes": 1.0}] * 3)
    # A mood name adds exactly its length, so this mood fills the limit without the pace entry.
    base = _size(observation._portrait(_row_with_mood(0)))
    fits = _row_with_mood(limit - base)
    assert _size(observation._portrait(fits)) == limit
    shed = observation._portrait(fits, pace=entry)
    assert "pace" not in shed
    assert shed["running"] == ["bookshelf-ReadBook"]
    assert _size(shed) <= limit


def test_over_the_limit_one_window_at_a_time_goes_before_the_pace_entry():
    limit = observation._PORTRAIT_LIMIT
    entry = pace.portrait({"need_drain": 0.5}, [{"interaction": "q" * 60, "game_minutes": 1.0}] * 3)
    windows = [{"event": "DIALOG_SHOWN", "code": "TIMEOUT" + "t" * 40, "ago_min": n} for n in range(4)]
    base = _size(observation._portrait(_row_with_mood(0), pace=entry))
    one = _size(windows[0]) + 1
    # With the pace entry and two and a half windows over the limit: the oldest windows go, pace stays.
    row = _row_with_mood(limit - base - (5 * one) // 2)
    shed = observation._portrait(row, windows=windows, pace=entry)
    assert shed["pace"] == entry
    assert 1 <= len(shed["windows"]) < len(windows)
    assert shed["windows"] == windows[-len(shed["windows"]):]
    assert _size(shed) <= limit
