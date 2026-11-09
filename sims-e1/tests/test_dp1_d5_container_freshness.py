"""D5 (Domus perception 1): container contents carry freshness in the first view.

A fixture bag holding a spoiled sandwich names Spoiled on the bag in the first menu
payload, and a sandwich listed on its own names its Freshness the same way. Burnt is
included. Names and ids are invented; no game text or real id appears here.
"""
import unittest

from test_binding import load_probe


class Freshness(object):
    __name__ = "Freshness"


class Freshness_Spoiled(object):
    __name__ = "Freshness_Spoiled"


class Freshness_Burnt(object):
    __name__ = "Freshness_Burnt"


class Freshness_Fresh(object):
    __name__ = "Freshness_Fresh"


class Dirtiness(object):
    __name__ = "Dirtiness"


class Dirtiness_Dirty(object):
    __name__ = "Dirtiness_Dirty"


class StateHolder(object):
    def __init__(self, mapping):
        self._states = mapping


class Sandwich(object):
    def __init__(self, value):
        self.state_component = StateHolder({Freshness: value})


class Bag(object):
    def __init__(self, contents, own=None):
        self.state_component = StateHolder(own or {})
        self.inventory_component = list(contents)


class Blank(object):
    pass


class StateWordsTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import act_menu
        self.act_menu = act_menu

    def test_a_spoiled_sandwich_names_spoiled(self):
        self.assertEqual(self.act_menu.state_words(Sandwich(Freshness_Spoiled)), ["Spoiled"])

    def test_a_bag_holding_a_spoiled_sandwich_names_spoiled(self):
        bag = Bag([Sandwich(Freshness_Spoiled)])
        self.assertEqual(self.act_menu.state_words(bag), ["Spoiled"])

    def test_burnt_and_fresh_and_dirty_are_named(self):
        self.assertEqual(self.act_menu.state_words(Sandwich(Freshness_Burnt)), ["Burnt"])
        self.assertEqual(self.act_menu.state_words(Sandwich(Freshness_Fresh)), ["Fresh"])
        dirty = Sandwich(Freshness_Fresh)
        dirty.state_component = StateHolder({Dirtiness: Dirtiness_Dirty})
        self.assertEqual(self.act_menu.state_words(dirty), ["Dirty"])

    def test_an_unreadable_object_names_nothing(self):
        self.assertEqual(self.act_menu.state_words(Blank()), [])


class MenuFreshnessTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import act_menu
        self.act_menu = act_menu

    def _job(self, object_id, obj, name="food_Eat"):
        return {"object_id": object_id, "definition_id": None, "class": "c", "distance_m": 1.0,
                "same_room": True, "room": "4", "on_lot": True, "person": False,
                "guid64": "7", "name": name, "text_key": None, "obj": obj}

    def test_the_first_menu_payload_names_spoiled_on_a_bag_that_holds_a_sandwich(self):
        bag = Bag([Sandwich(Freshness_Spoiled)])
        build = self.act_menu.MenuBuild([self._job("10", bag, "bag_Open")], lambda job: True)
        build.step()
        payload = build.payload(1, "4")
        self.assertEqual(payload["objects"][0]["states"], ["Spoiled"])
        record = self.act_menu.schema.make_record(
            "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload)
        self.act_menu.schema.validate_record(record)

    def test_a_listed_sandwich_names_its_own_spoiled(self):
        build = self.act_menu.MenuBuild(
            [self._job("11", Sandwich(Freshness_Spoiled))], lambda job: True)
        build.step()
        payload = build.payload(1, "4")
        self.assertEqual(payload["objects"][0]["states"], ["Spoiled"])

    def test_states_are_bounded_and_schema_checked(self):
        schema = self.act_menu.schema
        self.assertEqual(schema.MENU_MAX_STATES, 4)
        self.assertEqual(schema.MENU_MAX_STATE_CHARS, 40)
        build = self.act_menu.MenuBuild(
            [dict(self._job("1", Sandwich(Freshness_Spoiled)), states=["Spoiled"])],
            lambda job: True)
        build.step()
        payload = build.payload(1, "4")
        self.assertEqual(payload["objects"][0]["states"], ["Spoiled"])
        for bad in (["x" * 41], ["n%d" % index for index in range(5)]):
            broken = dict(payload, objects=[dict(payload["objects"][0], states=bad)])
            record = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                        monotonic_ns=1, e2=broken)
            with self.assertRaises(schema.SchemaError):
                schema.validate_record(record)


if __name__ == "__main__":
    unittest.main()
