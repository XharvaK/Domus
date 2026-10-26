"""S6: outcome records from telemetry rows (synthetic, game-shaped)."""
from domus_helper import outcomes

GRAB, EAT, WASH, SLEEP, NAP = ("generic_food_Grab", "generic_consume_food",
                               "sink_washDish_After_Eat_Counter", "bed_sleep", "bed_Nap")
PIE, INTENT, AUTO, POSTURE = ("InteractionSource.PIE_MENU",
                              "InteractionSource.SCRIPT_WITH_USER_INTENT",
                              "InteractionSource.AUTONOMY", "InteractionSource.POSTURE_GRAPH")


def _cal(minute):
    day, rest = divmod(minute, 1440)
    week, day = divmod(day, 7)
    return "%02d:%02d:00.000 day:%d week:%d" % (rest // 60, rest % 60, day, week)


def _row(index, minute, running, hunger=50, moodlets=None, wall_step=1000):
    observed = [{"interaction_id": str(iid), "affordance_id": str(guid),
                 "affordance_text": "<class 'sims4.tuning.instances.%s'>" % name,
                 "source_raw": source, "membership": "RUNNING", "target_id": None}
                for iid, guid, name, source in running]
    observed.append({"interaction_id": "1", "affordance_text": "<class 'sim-stand'>",
                     "source_raw": POSTURE, "membership": "RUNNING"})
    row = {"event_kind": "presence_snapshot", "schema_version": 6,
           "wall_timestamp_ms": index * wall_step, "game": {"calendar": _cal(minute)},
           "motives": [{"id": "hunger", "value": hunger}],
           "interactions": {"observed": observed}, "presence": [], "sim_signals": []}
    for tuning_id, name in (moodlets or []):
        row["sim_signals"].append({"kind": "MOODLET", "tuning_id": tuning_id,
                                   "tuning_name": name, "text_key": "7", "visible": True})
    return row


def _meal(origin_source=PIE, experiment=False):
    rows = [_row(0, 600, []),
            _row(1, 602, [(10, 13435, GRAB, origin_source)]),
            _row(2, 607, [(11, 13433, EAT, INTENT)], hunger=55),
            _row(3, 620, [(11, 13433, EAT, INTENT)], hunger=90),
            _row(4, 628, [(12, 1, WASH, AUTO)], hunger=90, moodlets=[("26886", "Buff_Full")]),
            _row(5, 640, [], hunger=89, moodlets=[("26886", "Buff_Full")])]
    if experiment:
        rows.insert(1, {"event_kind": "experiment_event",
                        "e2": {"phase": "PUSHED", "experiment_id": "s-1", "interaction_id": "10"}})
        rows.append({"event_kind": "experiment_event",
                     "e2": {"phase": "VERDICT", "experiment_id": "s-1", "code": "PASS"}})
    return rows


def test_a_record_carries_the_wall_time_its_first_sample_was_recorded():
    # D7b: the memory answer says when an act was recorded, in wall time.
    grab = outcomes.acts(_meal(), "abcdef12-0000")[0]
    assert grab["wall_ms"] == 1000


def test_grab_then_eat_is_one_chain_and_posture_is_left_out():
    records = outcomes.acts(_meal(), "abcdef12-0000")
    assert [r["interaction"]["name"] for r in records] == [GRAB, EAT, WASH]
    grab, eat, wash = records
    assert grab["origin"] == "owner" and grab["followed_by"][0]["name"] == EAT
    assert grab["followed_by"][0]["after_minutes"] == 5
    assert eat["origin"] == "owner" and eat["continues"] == grab["act_id"]
    assert eat["needs"]["delta"] == {"hunger": 40} and eat["span"]["game_minutes"] == 13
    assert wash["origin"] == "body"
    assert [m["name"] for m in wash["moodlets"]["gained"]] == ["Buff_Full"]
    assert grab["unknown"] == ["objects", "relationships", "self"]


def test_an_experiments_meal_is_never_credited_to_the_owner():
    grab, eat, _ = outcomes.acts(_meal(experiment=True), "abcdef12-0000")
    assert grab["origin"] == "experiment"
    assert grab["experiment"] == {"experiment_id": "s-1", "verdict": "PASS"}
    assert eat["origin"] == "experiment" and eat["continues"] == grab["act_id"]
    assert grab["followed_by"][0]["origin"] == "experiment"


def test_a_continuation_with_no_owner_or_experiment_before_it_stays_user_intent():
    rows = [_row(0, 600, [(11, 13433, EAT, INTENT)]), _row(1, 610, [])]
    assert outcomes.acts(rows)[0]["origin"] == "user_intent"


def test_sleep_onsets_nights_not_naps_spaced_and_confirmed():
    rows, index = [], 0
    for start, name, length in ((22 * 60, SLEEP, 480),            # night 1
                                (1440 + 14 * 60, NAP, 90),        # nap: never
                                (1440 + 15 * 60, SLEEP, 10),      # pushed and cancelled
                                (1440 + 16 * 60, SLEEP, 60),      # 18 h after night 1: counts
                                (1440 + 23 * 60, SLEEP, 480)):    # 7 h after the last: no
        for minute in range(start, start + length + 1, 10):
            rows.append(_row(index, minute, [(100 + start, 9, name, AUTO)]))
            index += 1
        rows.append(_row(index, start + length + 5, []))
        index += 1
    onsets = outcomes.sleep_onsets(outcomes.acts(rows))
    assert [o["span"]["start_minute"] for o in onsets] == [22 * 60, 1440 + 16 * 60]


def test_a_recording_gap_closes_open_acts():
    rows = [_row(0, 600, [(10, 1, WASH, AUTO)]), _row(1, 601, [(10, 1, WASH, AUTO)]),
            _row(100, 900, [(10, 1, WASH, AUTO)])]
    records = outcomes.acts(rows)
    assert [r["span"]["samples"] for r in records] == [2, 1]


def test_deterministic_and_days_framed():
    first = outcomes.acts(_meal(), "s")
    assert first == outcomes.acts(_meal(), "s")
    frame = outcomes.day_frames(first)[0]
    assert frame["acts"] == 3 and frame["body_on_its_own"] == {WASH: 1}


def test_game_minute():
    assert outcomes.game_minute("02:31:21.960 day:2 week:0") == 2 * 1440 + 151
    assert outcomes.game_minute("00:00:00.000 day:0 week:1") == 7 * 1440
    assert outcomes.game_minute(None) is None
