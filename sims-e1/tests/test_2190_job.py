"""2.19.0: her job is part of who she is, and a work event's buttons say what they do."""
import types
import unittest

import test_215_senses as senses


class _Factory(object):
    def __init__(self, key):
        self._string_id = key


class career_Adult_Culinary(object):
    pass


class _Built(object):
    def __init__(self, key):
        self.hash = key


class JobTests(unittest.TestCase):
    def setUp(self):
        senses.SelfTests.setUp(self)

    def test_her_job_title_level_and_shift(self):
        info = senses.SelfTests._sim_info(self)
        career = career_Adult_Culinary()
        career._current_track = types.SimpleNamespace(
            career_name=_Factory(0x7001), career_levels=[types.SimpleNamespace(title=_Factory(0x7101)),
                                                         types.SimpleNamespace(title=_Factory(0x7102))])
        career._level, career._user_level, career._at_work = 1, 2, True
        info.career_tracker = types.SimpleNamespace(_careers={1: career})
        own = self.probe.observers.read_self(info)
        self.assertEqual(own["careers"], [{"career": "career_Adult_Culinary", "text_key": str(0x7001),
                                           "title_key": str(0x7102), "level": 2, "at_work": True}])

    def test_no_job_is_an_empty_list(self):
        info = senses.SelfTests._sim_info(self)
        info.career_tracker = types.SimpleNamespace(_careers={})
        self.assertEqual(self.probe.observers.read_self(info)["careers"], [])

    def test_a_work_event_button_reads_its_text_from_the_closure(self):
        display_name = _Built(0x8001)
        response = types.SimpleNamespace(dialog_response_id=0, text=lambda *_, **__: display_name)
        dialog = types.SimpleNamespace(text_ok=None, ui_responses=(), _additional_responses=[response])
        self.assertEqual(self.probe.observers._dialog_responses(dialog),
                         [{"response": "0", "text_key": str(0x8001)}])

    def test_a_button_with_no_readable_text_stays_none(self):
        response = types.SimpleNamespace(dialog_response_id=1, text=lambda *_: None)
        dialog = types.SimpleNamespace(text_ok=None, ui_responses=(), _additional_responses=[response])
        self.assertEqual(self.probe.observers._dialog_responses(dialog),
                         [{"response": "1", "text_key": None}])


if __name__ == "__main__":
    unittest.main()
