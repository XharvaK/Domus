"""DS1-1 red-first: schema v4 senses, motive age_ticks, size budget."""
import json
import os
import sys
import types
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    package = types.ModuleType("ashley_e1")
    package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = package

from ashley_e1 import schema


def presence_row(**overrides):
    row = schema.make_record(
        "presence_snapshot",
        telemetry_session_id="00000000-0000-4000-8000-000000000021",
        wall_timestamp_ms=1, monotonic_ns=2, observation_complete=True,
        attestation=schema.attestation("LAB_E1"),
        save={"save_slot_guid": "g", "slot_id": "s"},
        body={"sim_id": "sim", "instantiated": True, "is_selectable": True,
              "is_selected": None, "posture": None},
        interactions={"observed": [], "queue_truncated": False,
                      "running_truncated": False, "observation_complete": True},
    )
    for key, value in overrides.items():
        row[key] = value
    return row


def full_signal(index=0):
    return {"kind": "MOODLET", "tuning_id": "12345678901234567890",
            "tuning_name": None, "game_text": "x" * 160, "magnitude": "w:99",
            "consequences": "UNKNOWN", "native_override": "UNKNOWN",
            "text_key": "4294967295", "mood_type": "Mood_" + "x" * 60, "visible": True,
            "reason_key": "4294967295", "minutes_left": 1440.5}


def full_presence(index=0):
    return {"id": "%064d" % index, "on_lot": True, "active_household": True, "level": 2 ** 30,
            "is_body": False, "household_id": "1" * 64, "name": "n" * 128,
            "position": {"x": 1.25, "y": 0.0, "z": -3.5, "level": 2 ** 30},
            "room": "2" * 64, "posture": "p" * 160, "doing": "d" * 160,
            "doing_target": "3" * 64, "distance_m": 12.3,
            "relationship": {"known": True,
                             "tracks": [{"track": "t" * 128, "value": -100.0}] * 4,
                             "labels": [{"label": "l" * 128, "text_key": "4294967295"}] * 6,
                             "knows": {"traits": [{"trait": "k" * 128,
                                                   "text_key": "4294967295"}] * 6,
                                       "careers": ["c" * 128] * 4,
                                       "relationship_status": True,
                                       "romantic_preference": True,
                                       "net_worth": 2 ** 40},
                             "sentiments": [{"sentiment": "s" * 128,
                                             "text_key": "4294967295"}] * 3},
            "situations": [{"situation": "v" * 128, "role": "r" * 128}] * 3}


def full_self():
    return {"traits": [{"trait": "t" * 128, "text_key": "4294967295",
                        "personality": True}] * 12,
            "skills": [{"skill": "s" * 128, "text_key": "4294967295", "level": 10}] * 12,
            "funds": 2 ** 40,
            "careers": [{"career": "c" * 64, "text_key": "4294967295", "title_key": "4294967295",
                         "level": 10, "at_work": True}] * 4,
            "wants": [{"want": "w" * 128, "text_key": "4294967295", "tip_key": "4294967295", "fear": True,
                       "locked": True, "done": 2 ** 31, "of": 2 ** 31, "until": [23, 59]}] * 8}


class SchemaV4Tests(unittest.TestCase):
    def test_version_is_v4(self):
        self.assertEqual(schema.OBSERVATION_SCHEMA_VERSION, 13)
        self.assertEqual(schema.TELEMETRY_SCHEMA_ID, "e1.telemetry/v13")

    def test_caps(self):
        self.assertEqual(schema.MAX_PRESENCE, 8)
        self.assertEqual(schema.MAX_SOCIAL, 4)

    def test_presence_snapshot_carries_senses(self):
        row = presence_row(
            presence=[{"id": "1", "active_household": True, "level": 2, "is_body": False, "household_id": None, "name": "Bella Goth", "position": {"x": 1.0, "y": 0.0, "z": 2.0, "level": 2}, "room": "5", "posture": "stand", "doing": "sim-chat", "doing_target": "9", "distance_m": 1.5, "relationship": None, "on_lot": True, "situations": None}],
            social=[],
            mood={"type": "123", "intensity": 5, "name": None},
            motives=[{"id": "hunger", "value": 50, "band": "ok",
                       "age_ticks": 100}],
        )
        schema.validate_record(row)

    def test_presence_snapshot_requires_sense_fields(self):
        row = presence_row()
        for key in ("presence", "social", "mood"):
            del row[key]
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_motive_requires_age_ticks(self):
        row = presence_row(
            presence=[], social=[], mood=None,
            motives=[{"id": "hunger", "value": 50, "band": "ok"}],
        )
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_presence_shape_and_caps(self):
        row = presence_row(
            presence=[{"id": "1", "active_household": True}] * 9,
            social=[], mood=None, motives=[],
        )
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)
        row = presence_row(
            presence=[{"id": "1", "active_household": "yes", "level": None}],
            social=[], mood=None, motives=[],
        )
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_social_uses_interaction_shape_and_cap(self):
        entry = {"entry_key": "k", "interaction_id": "1", "affordance_id": "2",
                 "affordance_text": "t", "target_id": "3", "source_raw": "s",
                 "source_norm": "UNKNOWN", "source_confidence": "UNKNOWN",
                 "present": True, "membership": "QUEUED"}
        row = presence_row(presence=[], social=[dict(entry) for _ in range(5)],
                           mood=None, motives=[])
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)
        bad = dict(entry)
        del bad["membership"]
        row = presence_row(presence=[], social=[bad], mood=None, motives=[])
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_mood_shape(self):
        row = presence_row(presence=[], social=[],
                           mood={"type": "1"}, motives=[])
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)
        row = presence_row(presence=[], social=[], mood={"type": "1" * 65,
                                                         "intensity": None},
                           motives=[])
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_non_observation_rows_reject_sense_payloads(self):
        row = schema.make_record(
            "dropped_summary", telemetry_session_id="s",
            wall_timestamp_ms=1, monotonic_ns=2, reason="QUEUE_SATURATION",
            presence=[{"id": "1", "active_household": True, "level": None}],
        )
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_budget_drops_signals_then_presence_and_keeps_social(self):
        """DS3: someone addressing her is the most important fact in the row."""
        from ashley_e1 import snapshot
        entry = {"entry_key": "k", "interaction_id": "1", "affordance_id": "2",
                 "affordance_text": "t", "target_id": "3", "source_raw": "s",
                 "source_norm": "UNKNOWN", "source_confidence": "UNKNOWN",
                 "present": True, "membership": "QUEUED"}
        row = presence_row(
            presence=[full_presence(i) for i in range(8)],
            social=[dict(entry, affordance_text="t" * 160, actor_id="4") for _ in range(4)],
            mood={"type": "1" * 64, "intensity": 1.5, "name": None},
            motives=[{"id": "m" * 64, "value": 50, "band": "ok",
                       "age_ticks": 2 ** 30} for _ in range(12)],
            sim_signals=[full_signal() for _ in range(16)],
            interactions={"observed": [dict(entry, affordance_text="t" * 160)
                                       for _ in range(8)],
                          "queue_truncated": True, "running_truncated": True,
                          "observation_complete": False},
        )
        self.assertGreater(len(json.dumps(row, separators=(",", ":"))), 16 * 1024)
        row = snapshot.apply_size_budget(row)
        schema.validate_record(row)
        payload = schema.serialize_record(row)
        self.assertLessEqual(len(payload), 48 * 1024)
        self.assertEqual(len(row["social"]), 4)
        self.assertEqual(len(row["sim_signals"]), 8)
        self.assertFalse(row["observation_complete"])

    def test_worst_case_fits_after_budget(self):
        from ashley_e1 import snapshot
        entry = {"entry_key": "k", "interaction_id": "1", "affordance_id": "2",
                 "affordance_text": "t", "target_id": "3", "source_raw": "s",
                 "source_norm": "UNKNOWN", "source_confidence": "UNKNOWN",
                 "present": True, "membership": "QUEUED"}
        row = presence_row(
            presence=[full_presence(i) for i in range(8)],
            social=[dict(entry, actor_id="4") for _ in range(4)],
            mood={"type": "12345", "intensity": 7, "name": None},
            motives=[{"id": "m%d" % i, "value": 50, "band": "ok",
                       "age_ticks": 100} for i in range(6)],
            sim_signals=[full_signal() for _ in range(16)],
            interactions={"observed": [dict(entry) for _ in range(8)],
                          "queue_truncated": True, "running_truncated": True,
                          "observation_complete": False},
        )
        row["self"] = full_self()
        row["place"] = {"owner_household_id": "9" * 64, "her_home": False, "venue": "v" * 128}
        key = "4294967295"
        row["dialogs"] = {
            "open": [{"dialog_id": "%064d" % i, "kind": "k" * 128, "owner_id": "8" * 64,
                      "title_key": key, "text_key": key,
                      "responses": [{"response": "r" * 16, "text_key": key}] * 6,
                      "auto_respond": True,
                      "rows": [{"option_id": "9" * 20, "name_key": key, "enabled": True, "price": 99999}] * 40}
                     for i in range(4)],
            "closed": [{"dialog_id": "%064d" % i, "kind": "k" * 128, "title_key": key,
                        "text_key": key, "response": "r" * 16} for i in range(4)],
            "truncated": True}
        row = snapshot.apply_size_budget(row)
        schema.validate_record(row)
        payload = schema.serialize_record(row)
        self.assertLessEqual(len(payload), 48 * 1024)
        self.assertLessEqual(len(row["dialogs"]["open"]), 4)  # 2.18.0 (32 KiB): dialogs keep their rows
        # Rows go before someone addressing her does; the worst case keeps a few.
        self.assertGreaterEqual(len(row["dialogs"]["open"][-1]["rows"]), 5)
        self.assertEqual(len(row["social"]), 4)
        self.assertLessEqual(len(row["sim_signals"]), 16)
        self.assertFalse(row["observation_complete"])


if __name__ == "__main__":
    unittest.main()
