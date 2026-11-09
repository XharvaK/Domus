"""D2 (Domus perception 1): the view cap never drops what a need requires.

A fixture of forty invented objects (two toilets in two rooms, the rest bookshelves) with the Sim's bladder in
distress keeps both toilets through the probe's object cap. Each toilet's acts name the need they relieve
(serves), the object carries the union, and the cap still counts what it left out.

Names, ids and rooms are invented; no game text or real id appears here."""
import unittest

import test_2160_act as acts
import test_e2
from test_binding import load_probe


class ToiletSitA(object):
    guid64 = 6101
    allow_user_directed = True
    advertised_motives = ("bladder",)


class ToiletSitB(object):
    guid64 = 6102
    allow_user_directed = True
    advertised_motives = ("bladder",)


class ReadThing(object):
    guid64 = 6100
    allow_user_directed = True


class FeltNeedsTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import act_menu
        self.act_menu = act_menu

    def test_felt_needs_are_worst_first_and_unread_values_are_skipped(self):
        motives = [
            {"id": "hunger", "value": 72, "band": "ok"},
            {"id": "bladder", "value": 8, "band": "distress"},
            {"id": None, "value": 1, "band": "distress"},
            {"id": "fun", "value": None, "band": "ok"},
            {"id": "hygiene", "value": 30, "band": "low"},
        ]
        self.assertEqual(self.act_menu.felt_needs(motives), ("bladder", "hygiene", "hunger"))
        self.assertEqual(self.act_menu.felt_needs([]), ())
        self.assertEqual(self.act_menu.felt_needs(None), ())


class ViewCapTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.rooms = {}
        room_of = self.probe.observers._room
        self.addCleanup(setattr, self.probe.observers, "_room", room_of)
        self.probe.observers._room = lambda obj, position: self.rooms.get(getattr(obj, "id", None))
        # Forty objects: two invented toilets farthest away in two rooms, thirty-eight bookshelves between them
        # and her room. Without need ordering the cap would keep the shelves and drop the toilets.
        self.things = [acts._Thing(100 + index, 1.0 + index, [ReadThing]) for index in range(38)]
        self.things += [acts._Thing(200, 39.0, [ToiletSitA]), acts._Thing(201, 40.0, [ToiletSitB])]
        for index in range(38):
            self.rooms[100 + index] = "6"
        self.rooms[200], self.rooms[201] = "4", "5"
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.row = {"event_kind": "presence_snapshot",
                    "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"},
                    "motives": [{"id": "hunger", "value": 72, "band": "ok"},
                                {"id": "bladder", "value": 8, "band": "distress"}]}
        self.cap = self.probe.schema.MENU_MAX_OBJECTS
        self.addCleanup(setattr, self.probe.schema, "MENU_MAX_OBJECTS", self.cap)
        self.probe.schema.MENU_MAX_OBJECTS = 20

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def _jobs(self):
        jobs, room = self.probe._menu_jobs(self.row)
        return jobs, room

    def test_forty_objects_and_bladder_distress_keep_both_toilets_through_the_probe_cap(self):
        jobs, room = self._jobs()
        self.assertEqual(jobs.needs, ("bladder", "hunger"))
        build = self.probe.act_menu.MenuBuild(
            jobs, lambda job: True, budget_ms=1e9, max_per_chunk=10000, needs=jobs.needs)
        build.step()
        payload = build.payload(1, room)
        ids = [item["object_id"] for item in payload["objects"]]
        # The two toilets serve the worst need, so they are listed (and kept first) although they are farthest.
        self.assertEqual(ids[:2], ["200", "201"])
        self.assertIn("200", ids)
        self.assertIn("201", ids)
        by_id = {item["object_id"]: item for item in payload["objects"]}
        self.assertEqual(by_id["200"].get("serves"), ["bladder"])
        self.assertEqual(by_id["201"].get("serves"), ["bladder"])
        self.assertEqual(payload["dropped"]["objects"], 20)
        self.assertEqual(payload["dropped"]["rooms"], ["6"])
        record = self.probe.schema.make_record(
            "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload)
        self.probe.schema.validate_record(record)

    def test_each_toilet_act_names_the_need_it_relieves_before_the_cap(self):
        jobs, _room = self._jobs()
        found = {}
        for job in jobs:
            found.setdefault(job["object_id"], []).append(job)
        self.assertEqual(found["200"][0].get("serves"), ["bladder"])
        self.assertEqual(found["201"][0].get("serves"), ["bladder"])
        self.assertNotIn("serves", found["100"][0])
        self.assertIs(found["200"][0].get("need_relief"), True)

    def test_serves_is_bounded_and_schema_checked(self):
        schema = self.probe.schema
        self.assertEqual(schema.MENU_MAX_SERVES, 8)
        self.assertEqual(schema.MENU_MAX_SERVE_CHARS, 32)
        jobs = [{"object_id": "1", "definition_id": None, "class": "c", "distance_m": 1.0,
                 "same_room": True, "room": "4", "on_lot": True, "person": False,
                 "guid64": "7", "name": "a", "text_key": None, "serves": ["bladder"]}]
        build = self.probe.act_menu.MenuBuild(jobs, lambda job: True)
        build.step()
        payload = build.payload(1, "4")
        self.assertEqual(payload["objects"][0]["acts"][0]["serves"], ["bladder"])
        self.assertEqual(payload["objects"][0]["serves"], ["bladder"])
        for bad in (["x" * 33], ["n%d" % index for index in range(9)]):
            broken = dict(payload, objects=[dict(payload["objects"][0],
                                                 acts=[dict(payload["objects"][0]["acts"][0], serves=bad)],
                                                 serves=bad)])
            record = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                        monotonic_ns=1, e2=broken)
            with self.assertRaises(schema.SchemaError):
                schema.validate_record(record)


if __name__ == "__main__":
    unittest.main()
