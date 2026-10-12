"""D6 (2.36.0, schema 18): her Sim's inner life as senses. Her aspiration and its objectives, her household's
bills, what her Sim carries, the weather and the season, and the game's notices about her. Read only; every
sense is absent (or None) when the game cannot say. Game-shaped fakes, built from the 1.128 bytecode."""
import sys
import types
import unittest

import test_215_senses as senses
import test_ds3_senses as ds3
import test_2260_talk as talk
from test_2210_camera import HER
from test_ds3_senses import _Wrapper


class _Text(object):
    def __init__(self, key):
        self._string_id = key


class _Objective(object):
    def __init__(self, key):
        self.display_text = _Text(key)


class _Milestone(object):
    def __init__(self, objectives):
        self.objectives = objectives


class _Tracker(object):
    def __init__(self, milestone, done=()):
        self._active_aspiration = milestone
        self._done = set(done)

    def objective_completed(self, objective):
        return objective in self._done


class _Track(object):
    def __init__(self, key):
        self.display_text = _Text(key)


class _Bills(object):
    def __init__(self, owed, delivered, late):
        self.current_payment_owed = owed
        self._delivered, self._late = delivered, late

    def mailman_has_delivered_bills(self):
        return self._delivered

    def is_any_utility_delinquent(self):
        return self._late


class _Stack(object):
    def __init__(self, name, count):
        self.definition = types.SimpleNamespace(name=name)
        self._count = count

    def stack_count(self):
        return self._count


class _Inventory(object):
    def __init__(self, items):
        self._items = items

    def __iter__(self):
        return iter(self._items)


class _Named(object):
    def __init__(self, name):
        self.name = name


class _Unreadable(object):
    @property
    def definition(self):
        raise RuntimeError("unreadable object")


def _without(name):
    """Removes a service from the fake services module for one test; put back by the caller."""
    services = sys.modules["services"]
    saved = getattr(services, name, None)
    if hasattr(services, name):
        delattr(services, name)
    return saved


class _Base(unittest.TestCase):
    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        self.observers = self.probe.observers
        self.schema = self.probe.schema
        self.services = sys.modules["services"]
        self.observers._NOTICED.clear()
        self.observers._OWN_NOTICES.clear()
        del self.observers._NOTICES_PENDING[:]
        del self.observers._SHOWN[:]

    def _info(self):
        return senses.SelfTests._sim_info(self)

    def row(self):
        return ds3.PollOnceTests.row(self)


class AspirationTests(_Base):
    def test_track_name_and_the_current_milestones_objectives(self):
        info = self._info()
        info.primary_aspiration = _Track(0x9001)
        info.aspiration_tracker = _Tracker(_Milestone([_Objective(0x9002), _Objective(0x9003)]))
        own = self.observers.read_self(info)
        self.assertEqual(own["aspiration"], {"name_key": str(0x9001), "objectives": [
            {"text_key": str(0x9002), "done": False}, {"text_key": str(0x9003), "done": False}]})

    def test_a_done_objective_is_done(self):
        info = self._info()
        first = _Objective(0x9002)
        info.primary_aspiration = _Track(0x9001)
        info.aspiration_tracker = _Tracker(_Milestone([first, _Objective(0x9003)]), done=[first])
        objectives = self.observers.read_self(info)["aspiration"]["objectives"]
        self.assertEqual([item["done"] for item in objectives], [True, False])

    def test_at_most_six_objectives(self):
        info = self._info()
        info.primary_aspiration = _Track(0x9001)
        info.aspiration_tracker = _Tracker(_Milestone([_Objective(0x9100 + n) for n in range(9)]))
        self.assertEqual(len(self.observers.read_self(info)["aspiration"]["objectives"]), 6)

    def test_no_primary_aspiration_or_no_tracker_is_absent(self):
        info = self._info()
        info.primary_aspiration = None
        self.assertNotIn("aspiration", self.observers.read_self(info))
        info = self._info()
        info.primary_aspiration = _Track(0x9001)
        self.assertEqual(self.observers.read_self(info)["aspiration"],
                         {"name_key": str(0x9001), "objectives": []})

    def test_an_unreadable_tracker_is_absent_not_raised(self):
        info = self._info()
        info.primary_aspiration = _Track(0x9001)
        info.aspiration_tracker = None
        self.assertEqual(self.observers.read_self(info)["aspiration"],
                         {"name_key": str(0x9001), "objectives": []})


class BillsTests(_Base):
    def test_owed_mail_and_late_from_the_household_bills_manager(self):
        info = self._info()
        info.household = types.SimpleNamespace(
            _funds=types.SimpleNamespace(_funds=500), bills_manager=_Bills(320, True, False))
        self.assertEqual(self.observers.read_self(info)["bills"],
                         {"owed": 320, "delivered": True, "late": False})

    def test_late_when_a_utility_is_delinquent(self):
        info = self._info()
        info.household = types.SimpleNamespace(bills_manager=_Bills(0, False, True))
        self.assertEqual(self.observers.read_self(info)["bills"],
                         {"owed": 0, "delivered": False, "late": True})

    def test_no_bills_manager_is_absent(self):
        info = self._info()
        info.household = types.SimpleNamespace(_funds=types.SimpleNamespace(_funds=500))
        self.assertNotIn("bills", self.observers.read_self(info))

    def test_an_owed_that_is_not_an_int_is_none(self):
        info = self._info()
        info.household = types.SimpleNamespace(bills_manager=_Bills("320", True, False))
        self.assertIsNone(self.observers.read_self(info)["bills"]["owed"])


class InventoryTests(_Base):
    def _with_items(self, items):
        info = self._info()
        sim = types.SimpleNamespace(inventory_component=_Inventory(items))
        info.get_sim_instance = lambda *args, **kwargs: sim
        return info

    def test_stacks_by_name_most_first(self):
        info = self._with_items([_Stack("Pot_Invented", 2), _Stack("Lamp_Invented", 1),
                                 _Stack("Pot_Invented", 3)])
        self.assertEqual(self.observers.read_self(info)["inventory"], [
            {"name": "Pot_Invented", "count": 5}, {"name": "Lamp_Invented", "count": 1}])

    def test_one_unreadable_object_never_drops_the_rest(self):
        info = self._with_items([_Unreadable(), _Stack("Lamp_Invented", 1)])
        self.assertEqual(self.observers.read_self(info)["inventory"],
                         [{"name": "Lamp_Invented", "count": 1}])

    def test_at_most_twenty_four_entries(self):
        info = self._with_items([_Stack("Thing_%02d" % n, 1) for n in range(30)])
        self.assertEqual(len(self.observers.read_self(info)["inventory"]), 24)

    def test_off_the_lot_is_absent(self):
        info = self._info()
        info.get_sim_instance = lambda *args, **kwargs: None
        self.assertNotIn("inventory", self.observers.read_self(info))


class WeatherTests(_Base):
    def _restore_later(self, name):
        saved = _without(name)
        if saved is not None:
            self.addCleanup(setattr, self.services, name, saved)

    def _weather(self, types_now=None, season=None):
        if types_now is not None:
            self.services.weather_service = lambda: types.SimpleNamespace(
                get_current_weather_types=lambda: types_now)
        if season is not None:
            self.services.season_service = lambda: types.SimpleNamespace(season=season)

    def test_weather_types_and_season_as_enum_names(self):
        self._weather({_Named("Rain"), _Named("Cloudy")}, _Named("Summer"))
        self.assertEqual(self.observers.read_weather(), {"types": ["Cloudy", "Rain"], "season": "Summer"})

    def test_at_most_six_types(self):
        self._weather({_Named("Type_%d" % n) for n in range(9)}, _Named("Winter"))
        self.assertEqual(len(self.observers.read_weather()["types"]), 6)

    def test_missing_weather_service_leaves_types_none(self):
        self._restore_later("weather_service")
        self._weather(season=_Named("Autumn"))
        self.assertEqual(self.observers.read_weather(), {"types": None, "season": "Autumn"})

    def test_both_services_missing_is_absent_in_the_row(self):
        self._restore_later("weather_service")
        self._restore_later("season_service")
        self.assertIsNone(self.observers.read_weather())
        self.assertNotIn("weather", self.row())

    def test_the_row_carries_weather_and_validates(self):
        self._weather({_Named("Rain")}, _Named("Summer"))
        row = self.row()
        self.assertEqual(row["weather"], {"types": ["Rain"], "season": "Summer"})
        self.assertEqual(row["schema_version"], 21)

    def row(self):
        return ds3.PollOnceTests.row(self)


class NoticeFake(object):
    """A UiDialogNotification as the game builds one: owner, title and text, and a dialog id. A notice normally
    has no responses, so dialog_show never stores it in _active_dialogs; the game distributes it instead."""

    _ids = iter(range(701, 100000))

    def __init__(self, owner, title, text):
        self.dialog_id = next(NoticeFake._ids)
        self._owner = lambda: owner
        self.title = None if title is None else _Wrapper(title)
        self.text = _Wrapper(text)
        self.response = None

    def has_responses(self):
        return False

    def respond(self, response):
        raise AssertionError("the probe never answers a notice")


class UiDialogNotification(NoticeFake):
    pass


class UiDialogOkCancel(object):
    def __init__(self, owner, title, text):
        self._owner = lambda: owner
        self.title, self.text = _Wrapper(title), _Wrapper(text)
        self.text_ok, self.text_cancel = _Wrapper(0x6001), _Wrapper(0x6002)
        self.response = None


class NoticeTests(_Base):
    def setUp(self):
        _Base.setUp(self)
        self.module = sys.modules[type(self.probe._E2).__module__]
        self.service = types.SimpleNamespace(_active_dialogs={}, _auto_respond_alarm_handles={})

        def never(*args, **kwargs):
            raise AssertionError("a notice is never held, cancelled or answered")
        self.service.dialog_respond = never
        self.service.dialog_cancel = never
        self.service.dialog_show = never
        self.services.ui_dialog_service = lambda: self.service

    def shown(self, notice):
        """The game distributes a notice: the notice hook sees it, and the game's own send runs."""
        sent = []
        hook = self.module._notice_hook(lambda dialog, *args, **kwargs: sent.append(dialog))
        hook(notice, "dialog_type", "message")
        return sent

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_a_notice_with_no_responses_is_in_the_next_row_once(self):
        notice = UiDialogNotification(self.lab, 0xA001, 0xA002)
        self.assertFalse(notice.has_responses())
        self.shown(notice)
        self.assertEqual(self.service._active_dialogs, {})  # the game keeps only dialogs with responses
        self.assertEqual(self.row()["notices"], [{"title_key": str(0xA001), "text_key": str(0xA002)}])
        self.assertEqual(self.row()["notices"], [])  # recorded once

    def test_a_notice_about_a_household_member_is_hers(self):
        member = types.SimpleNamespace(id=101, household_id="hh1")
        self.shown(UiDialogNotification(member, None, 0xA002))
        self.assertEqual(self.row()["notices"], [{"title_key": None, "text_key": str(0xA002)}])

    def test_a_notice_with_no_owner_is_recorded(self):
        self.shown(UiDialogNotification(None, 0xA001, 0xA002))
        self.assertEqual(len(self.row()["notices"]), 1)

    def test_a_stranger_is_not_recorded(self):
        self.shown(UiDialogNotification(self.far, 0xA001, 0xA002))
        self.assertEqual(self.row()["notices"], [])

    def test_the_probes_own_line_is_not_recorded(self):
        own = UiDialogNotification(self.lab, 0xA001, 0xA002)
        self.observers.note_own_notice(own)
        self.shown(own)
        self.assertEqual(self.row()["notices"], [])

    def test_a_question_is_not_a_notice(self):
        self.shown(UiDialogOkCancel(self.lab, 0x5001, 0x5002))
        self.assertEqual(self.row()["notices"], [])

    def test_at_most_four_per_row_and_the_rest_wait_for_the_next(self):
        for number in range(6):
            self.shown(UiDialogNotification(self.lab, 0xA100 + number, 0xA200 + number))
        first, second = self.row()["notices"], self.row()["notices"]
        self.assertEqual([item["text_key"] for item in first],
                         [str(0xA200 + n) for n in range(4)])
        self.assertEqual([item["text_key"] for item in second], [str(0xA204), str(0xA205)])

    def test_no_dialog_service_does_not_stop_the_notices(self):
        def no_service():
            raise RuntimeError("no service")
        self.services.ui_dialog_service = no_service
        self.shown(UiDialogNotification(self.lab, 0xA001, 0xA002))
        self.assertEqual(len(self.row()["notices"]), 1)

    def test_the_notice_schema_accepts_the_list_and_rejects_a_bad_one(self):
        self.shown(UiDialogNotification(self.lab, 0xA001, 0xA002))
        row = self.row()
        self.schema.validate_record(row)
        for bad in ([{"title_key": "9" * 65, "text_key": None}], [{"title_key": None}],
                    [{"title_key": None, "text_key": None}] * 5):
            with self.assertRaises(Exception):
                self.schema.validate_record(dict(row, notices=bad))


class NoticeHookTests(_Base):
    """2.36.0: the notice hook observes; it never holds, never answers, and always runs the game's own send."""

    def setUp(self):
        _Base.setUp(self)
        self.module = sys.modules[type(self.probe._E2).__module__]

    def test_the_original_gets_the_same_arguments_and_its_result(self):
        seen = []

        def original(dialog, *args, **kwargs):
            seen.append((dialog, args, kwargs))
            return "sent"
        notice = UiDialogNotification(self.lab, 0xA001, 0xA002)
        result = self.module._notice_hook(original)(notice, "type", "msg", extra=2)
        self.assertEqual(result, "sent")
        self.assertEqual(seen, [(notice, ("type", "msg"), {"extra": 2})])

    def test_the_original_still_runs_when_the_observer_raises(self):
        seen = []
        saved = self.observers.notice_shown

        def broken(dialog):
            raise RuntimeError("the observer broke")
        self.observers.notice_shown = broken
        self.addCleanup(setattr, self.observers, "notice_shown", saved)
        notice = UiDialogNotification(self.lab, 0xA001, 0xA002)
        self.module._notice_hook(lambda dialog, *args, **kwargs: seen.append(dialog))(notice, "type", "msg")
        self.assertEqual(seen, [notice])

    def test_the_hold_controller_is_never_consulted(self):
        class Controller(object):
            def hold_dialog(self, *args, **kwargs):
                raise AssertionError("a notice is never held")
        saved = self.module._HOLD["controller"]
        self.module._HOLD["controller"] = Controller()
        self.addCleanup(self.module._HOLD.__setitem__, "controller", saved)
        seen = []
        self.module._notice_hook(lambda dialog, *args, **kwargs: seen.append(dialog))(
            UiDialogNotification(self.lab, 0xA001, 0xA002), "type", "msg")
        self.assertEqual(len(seen), 1)

    def test_install_observes_the_class_and_restore_gives_the_game_back(self):
        names = ("UiDialogBase", "UiDialogObjectColorPicker", "SimPersonalityAssignmentDialog",
                 "UiMapViewPicker", "UiApartmentPicker", "UiDialogNotification", "Distributor", "Consts_pb2")
        saved = dict((name, getattr(self.module, name)) for name in names)

        def put_back():
            self.module._restore_holds()
            for name, value in saved.items():
                setattr(self.module, name, value)
        self.addCleanup(put_back)

        class Notification(object):
            def distribute_dialog(self, dialog_type, dialog_msg):
                return "game"
        original = Notification.distribute_dialog
        for name in names:
            setattr(self.module, name, None)
        self.module.UiDialogNotification = Notification
        self.module._restore_holds()
        self.assertTrue(self.module._install_holds(object()))
        self.assertIsNot(Notification.distribute_dialog, original)
        self.assertEqual(Notification.distribute_dialog.__qualname__, "_notice_hook.<locals>.distribute_dialog")
        self.module._restore_holds()
        self.assertIs(Notification.distribute_dialog, original)


class SchemaEighteenTests(_Base):
    def test_version_and_self_shapes(self):
        self.assertEqual((self.schema.OBSERVATION_SCHEMA_VERSION, self.schema.TELEMETRY_SCHEMA_ID),
                         (21, "e1.telemetry/v21"))
        self.assertEqual(self.schema.PROBE_VERSION, "2.40.0")
        self.assertIn(18, self.schema.ACCEPTED_SCHEMA_VERSIONS)

    def test_the_self_fields_validate_and_bad_ones_are_refused(self):
        info = self._info()
        info.primary_aspiration = _Track(0x9001)
        info.aspiration_tracker = _Tracker(_Milestone([_Objective(0x9002)]))
        info.household = types.SimpleNamespace(bills_manager=_Bills(320, True, False))
        row = self.row()
        base = dict(row["self"], aspiration=self.observers.read_self(info)["aspiration"],
                    bills=self.observers.read_self(info)["bills"], inventory=[{"name": "Pot_Invented", "count": 2}])
        self.schema.validate_record(dict(row, self=base))
        bad_cases = [
            dict(base, aspiration={"name_key": None, "objectives": [{"text_key": None, "done": 1}]}),
            dict(base, aspiration={"name_key": None, "objectives": [{"text_key": None, "done": True}] * 7}),
            dict(base, bills={"owed": "320", "delivered": True, "late": False}),
            dict(base, bills={"owed": 320, "delivered": True}),
            dict(base, inventory=[{"name": "Pot_Invented", "count": -1}]),
            dict(base, inventory=[{"name": 5, "count": 1}]),
        ]
        for bad in bad_cases:
            with self.assertRaises(Exception):
                self.schema.validate_record(dict(row, self=bad))

    def test_the_self_fields_may_be_absent(self):
        row = self.row()
        self.assertNotIn("aspiration", row["self"])
        self.schema.validate_record(row)

    def test_weather_outside_the_row_shape_is_refused(self):
        row = self.row()
        for bad in ({"types": ["a"] * 7, "season": None}, {"types": None}, {"types": None, "season": 4}):
            with self.assertRaises(Exception):
                self.schema.validate_record(dict(row, weather=bad))


class OwnLineTests(unittest.TestCase):
    """2.36.0: the probe's own talk line is marked before it is shown, so the notice hook never records it."""

    def test_the_talk_line_is_marked_before_it_is_shown(self):
        base = talk.TalkTests("test_shows_one_line_and_changes_nothing")
        base.setUp()
        self.addCleanup(base.tearDown)
        module = sys.modules[type(base.probe._E2).__module__]

        class UiDialogNotification(object):
            """The game's class name: the hook looks for it by name."""

            def __init__(self, owner, text):
                self.dialog_id = 701
                self._owner = lambda: owner
                self.title = None
                self.text = None

            def show_dialog(self):
                # the game distributes the line as it shows it
                module._notice_hook(lambda dialog, *args, **kwargs: None)(self, "type", "msg")

        class _Factory(object):
            def TunableFactory(self):
                class _Tunable(object):
                    def default(self, owner, text=None):
                        return UiDialogNotification(owner, text)
                return _Tunable()

        saved = module.UiDialogNotification
        self.addCleanup(setattr, module, "UiDialogNotification", saved)
        module.UiDialogNotification = _Factory()
        base.case.ready()
        ok, connection = base.talk({"text": "Ashley is asking Don about his day.", "sim_id": HER})
        self.assertTrue(ok, connection.lines)
        her = types.SimpleNamespace(id=int(HER), household_id="hh1")
        self.assertEqual(module.observers.read_notices(her), [])
        self.assertEqual(module.observers._OWN_NOTICES, {})  # the mark was used by the hook


if __name__ == "__main__":
    unittest.main()
