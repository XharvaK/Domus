"""DA4b: social actor and membership, mood names, need cards in game ticks."""
import json
import os
import unittest

from test_ds1_presence import FakeEntry, FakeSim, FakeSimInfoEntry, LabSim, PresenceTests
from test_da4_cards import SCRIPT
from test_e2 import _entry, _load_pure


EVIDENCE = os.path.join(
    os.path.dirname(__file__), "..", "evidence", "DA5_CALIBRATION_2026-10-04",
    "ashley_e1_c964da78-8841-41c4-ab87-3895fb228b2d.jsonl")


def _social_entry(actor_id="sim-b", membership="RUNNING"):
    return {"entry_key": "k", "interaction_id": "9", "affordance_id": "1",
            "affordance_text": "chat", "target_id": "lab", "source_raw": SCRIPT,
            "source_norm": "UNKNOWN", "source_confidence": "UNKNOWN", "present": True,
            "membership": membership, "actor_id": actor_id}


def _need_row(mono_s, ticks, value, entries, speed="NORMAL", paused=False, age=0,
              social=(), schema_version=5):
    return {"schema_version": schema_version, "monotonic_ns": int(mono_s * 1e9),
            "observation_complete": True,
            "interactions": {"observed": [dict(item) for item in entries]},
            "motives": [{"id": "hunger", "value": value, "band": "ok", "age_ticks": age}],
            "game": {"ticks": ticks, "calendar": None, "clock_speed": speed, "paused": paused},
            "social": [dict(item) for item in social],
            "body": {"posture": {}}}


class SocialReadTests(PresenceTests):
    def test_si_state_is_running_and_names_the_actor(self):
        lab = LabSim("lab")
        other = FakeSim("sim-b", si_state=[FakeEntry(1, "aff", lab)], queue=[])
        entry = FakeSimInfoEntry("sim-b", sim=other)
        probe = self.context([entry])
        social, truncated = probe.observers.read_social("lab", lab, [entry])
        self.assertFalse(truncated)
        self.assertEqual(len(social), 1)
        self.assertEqual(social[0]["membership"], "RUNNING")
        self.assertEqual(social[0]["actor_id"], "sim-b")

    def test_queue_and_si_state_collapse_to_one_row(self):
        lab = LabSim("lab")
        shared = FakeEntry(7, "aff", lab)
        other = FakeSim("sim-c", si_state=[shared], queue=[shared])
        entry = FakeSimInfoEntry("sim-c", sim=other)
        probe = self.context([entry])
        social, _truncated = probe.observers.read_social("lab", lab, [entry])
        self.assertEqual(len(social), 1)
        self.assertEqual(social[0]["membership"], "QUEUED_AND_RUNNING")
        self.assertEqual(social[0]["actor_id"], "sim-c")


class MoodNameTests(unittest.TestCase):
    def test_tuning_name_and_mood_name_or_none(self):
        from test_binding import load_probe
        from test_ds1_senses import FakeBuffs, FakeSimInfo, FakeTracker, make_row

        class CryInBed(object):
            def __init__(self):
                self.guid64 = 37
                self.mood_weight = 1

        class HappyMood(object):
            def __init__(self):
                self.guid64 = 5
                self.__name__ = "Happy"

        row = make_row({"ticks": 10}, FakeSimInfo(
            FakeTracker(), FakeBuffs([CryInBed()], mood=HappyMood(), intensity=2)))
        self.assertEqual(row["sim_signals"][0]["tuning_name"], "CryInBed")
        self.assertEqual(row["mood"]["name"], "Happy")
        self.assertIsNone(row["sim_signals"][0]["game_text"])

        class BoomMeta(type):
            @property
            def __name__(self):
                raise RuntimeError("tuning")

        class Boom(object, metaclass=BoomMeta):
            def __init__(self):
                self.guid64 = 3
                self.mood_weight = 1

        class MoodBoom(object):
            @property
            def __name__(self):
                raise RuntimeError("mood")

            def __init__(self):
                self.guid64 = 9

        row = make_row({"ticks": 10}, FakeSimInfo(
            FakeTracker(), FakeBuffs([Boom()], mood=MoodBoom(), intensity=1)))
        self.assertIsNone(row["sim_signals"][0]["tuning_name"])
        self.assertIsNone(row["mood"]["name"])
        _probe, probe, _calls = load_probe()
        self.assertEqual(probe.schema.OBSERVATION_SCHEMA_VERSION, 18)


class SchemaDualTests(unittest.TestCase):
    def setUp(self):
        _, _, _, self.schema, _ = _load_pure()

    def _base(self):
        return self.schema.make_record(
            "presence_snapshot", telemetry_session_id="00000000-0000-4000-8000-0000000000b4",
            wall_timestamp_ms=1, monotonic_ns=2, observation_complete=True,
            attestation=self.schema.attestation("LAB_E1"),
            save={"save_slot_guid": "g", "slot_id": "s"},
            body={"sim_id": "sim", "instantiated": True, "is_selectable": True,
                  "is_selected": None, "posture": None},
            interactions={"observed": [], "queue_truncated": False,
                          "running_truncated": False, "observation_complete": True},
        )

    def test_schema_4_and_5_validate_and_actor_id_is_required(self):
        current = self._base()
        self.schema.validate_row(current)
        # 2.32.0 (PR10, PR11): the game block of schema 15 has build_mode and fire; older rows never had them.
        before_15 = {key: value for key, value in current["game"].items() if key not in ("build_mode", "fire")}
        legacy = dict(current, schema_version=4, game=before_15)
        self.schema.validate_row(legacy)
        entry = _social_entry()
        with_actor = self._base()
        with_actor["social"] = [entry]
        with_actor["mood"] = {"type": "1", "intensity": 1, "name": "Happy"}
        with_actor["sim_signals"] = [{
            "kind": "MOODLET", "tuning_id": "37", "tuning_name": "CryInBed",
            "game_text": None, "magnitude": "w:1", "consequences": None,
            "native_override": None, "text_key": "123", "mood_type": "Mood_Sad",
            "visible": True, "reason_key": None, "minutes_left": None}]
        self.schema.validate_row(with_actor)
        five = dict(current, schema_version=5, game=before_15)
        self.schema.validate_row(five)
        missing = self._base()
        bare = dict(entry)
        del bare["actor_id"]
        missing["social"] = [bare]
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_row(missing)
        old = dict(legacy)
        old["social"] = [bare]
        old["mood"] = {"type": "1", "intensity": 1}
        self.schema.validate_row(old)

    def test_da5_evidence_rows_still_validate(self):
        self.assertTrue(os.path.isfile(EVIDENCE), EVIDENCE)
        count = 0
        with open(EVIDENCE, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                self.assertEqual(row.get("schema_version"), 4)
                self.schema.validate_row(row)
                count += 1
        self.assertGreater(count, 0)


class NeedTickTests(unittest.TestCase):
    def setUp(self):
        _, _, self.reg, _, _ = _load_pure()
        from ashley_e1 import e2_cards
        self.cards = e2_cards

    def _card(self):
        return {"card_class": "need", "affordance_guid64": None, "object_id": None,
                "signature": None, "motive": "hunger", "direction": 1, "min_net_delta": 5.0}

    def _state(self, rows, started, control):
        return {"interaction_id": "100", "foreign_roots": [], "control_rows": control,
                "pushed_mono_ns": 0, "rows_since_push": rows, "started_ns": started}

    def test_speed_change_flat_control_passes_on_ticks(self):
        ours = _entry("100", SCRIPT, "RUNNING", "meal")
        control = [_need_row(0.1, 0, 10, [], speed="NORMAL"),
                   _need_row(0.2, 20000, 10, [], speed="SPEED3")]
        first = _need_row(1, 30000, 10, [ours], speed="NORMAL")
        mid = _need_row(5, 60000, 40, [ours], speed="SUPER_SPEED3")
        later = _need_row(9, 75000, 40, [ours], speed="SUPER_SPEED3")
        more = _need_row(13, 82000, 40, [ours], speed="SUPER_SPEED3")
        last = _need_row(17, 90000, 40, [ours], speed="SUPER_SPEED3")
        trial = [first, mid, later, more, last]
        effect, reason = self.cards.evaluate_effect(
            self._card(), self._state(trial, first["monotonic_ns"], control), last)
        self.assertEqual((effect, reason), (True, None))
        exp = self.reg.Experiment(
            "e-1", "t" * 16, "meal", "s", "100", 0, None, [],
            card=self._card(), control_rows=control)
        for row in trial:
            exp.observe(row)
        self.assertEqual(exp.ambiguous, [])
        self.assertEqual(exp.close(), self.reg.PASS)

    def test_grace_window_and_paused_and_stale(self):
        ours = _entry("100", SCRIPT, "RUNNING", "meal")
        control = [_need_row(0.1, 0, 10, []), _need_row(0.2, 10000, 10, [])]
        start = _need_row(1, 20000, 10, [ours])
        ended = _need_row(2, 25000, 10, [])
        near = _need_row(3, 30000, 40, [])
        held = [_need_row(7, 32000, 40, []), _need_row(11, 34000, 40, []),
                _need_row(15, 36000, 40, [])]
        far = _need_row(6, 45000, 40, [])
        card = self._card()
        near_rows = [start, ended, near]
        effect, reason = self.cards.evaluate_effect(
            card, self._state(near_rows, start["monotonic_ns"], control), near)
        self.assertEqual((effect, reason), (True, None))
        exp = self.reg.Experiment(
            "e-1", "t" * 16, "meal", "s", "100", 0, None, [],
            card=card, control_rows=control)
        for row in [start, ended, near] + held:
            exp.observe(row)
        self.assertEqual(exp.close(), self.reg.PASS, exp.ambiguous)
        effect, reason = self.cards.evaluate_effect(
            card, self._state([start, ended, far], start["monotonic_ns"], control), far)
        self.assertEqual((effect, reason), (False, None))
        paused_start = _need_row(1, 20000, 10, [ours], paused=True)
        paused_now = _need_row(2, 20000, 40, [ours], paused=True)
        effect, reason = self.cards.evaluate_effect(
            card, self._state([paused_start, paused_now], paused_start["monotonic_ns"], control),
            paused_now)
        self.assertEqual((effect, reason), (False, "paused_only"))
        fresh = _need_row(5, 90000, 40, [ours], age=25000)
        effect, reason = self.cards.evaluate_effect(
            card, self._state([start, fresh], start["monotonic_ns"], control), fresh)
        self.assertNotEqual(reason, "stale_value")
        self.assertEqual((effect, reason), (True, None))
        stale = _need_row(5, 90000, 40, [ours], age=40000)
        effect, reason = self.cards.evaluate_effect(
            card, self._state([start, stale], start["monotonic_ns"], control), stale)
        # D14 (DA6E): a stale cache is no reading for this row, not a trial ambiguity.
        self.assertEqual((effect, reason), (False, None))

    def test_social_card_schema_5_passes_and_schema_4_stays_unobserved(self):
        card = {"card_class": "social", "affordance_guid64": None, "object_id": "sim-b",
                "signature": None, "motive": None, "direction": None, "min_net_delta": 5.0}
        ours = _entry("100", SCRIPT, "RUNNING", "sim-b")
        social = [_social_entry()]
        first = _need_row(1, 1000, 10, [ours], social=social)
        second = _need_row(12, 2000, 10, [ours], social=social)
        effect, reason = self.cards.evaluate_effect(
            card, {"interaction_id": "100", "foreign_roots": []}, first)
        self.assertEqual((effect, reason), (True, None))
        exp = self.reg.Experiment(
            "e-1", "t" * 16, "sim-b", "s", "100", 0, None, [], card=card)
        exp.observe(first)
        exp.observe(second)
        self.assertEqual(exp.ambiguous, [])
        self.assertEqual(exp.close(), self.reg.PASS)
        legacy = dict(first, schema_version=4)
        legacy["social"] = [dict(social[0])]
        del legacy["social"][0]["actor_id"]
        effect, reason = self.cards.evaluate_effect(
            card, {"interaction_id": "100", "foreign_roots": []}, legacy)
        self.assertEqual((effect, reason), (False, "social_target_unobserved"))


if __name__ == "__main__":
    unittest.main()
