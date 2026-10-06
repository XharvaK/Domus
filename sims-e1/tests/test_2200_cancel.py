"""2.20.0: she stops one of her own actions, running or queued, the way the client's X does."""
import json
import unittest

import test_2160_act as acts

STOP = "c" * 32


class _Interaction(object):
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.reasons = []

    def cancel_user(self, cancel_reason_msg=None):
        self.reasons.append(cancel_reason_msg)
        return self.allowed


class piano_Play_Song(_Interaction):
    pass


class CancelTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.song = piano_Play_Song()
        self.queue = {313: self.song}
        self.continuations = {}
        self.case.base.sim.find_interaction_by_id = lambda iid: self.queue.get(iid)
        self.case.base.sim.find_continuation_by_id = lambda iid: self.continuations.get(iid)

    def tearDown(self):
        self.case.tearDown()

    def cancel(self, interaction_id="313", act_id=STOP):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "cancel", "args": {"act_id": act_id, "interaction_id": interaction_id}}, connection)
        return ok, connection

    def phases(self):
        return [(e["phase"], e["object_id"], e["code"], e["tuning_name"], e["finishing_type"]) for e in self.case.events()]

    def test_her_running_action_is_stopped_like_the_clients_x(self):
        self.case.ready()
        ok, connection = self.cancel()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.song.reasons, ["Ashley stopped it."])
        self.assertEqual(self.phases(), [("ACCEPTED", "313", None, "piano_Play_Song", None),
                                         ("FINISHED", "313", None, "piano_Play_Song", "STOPPED")])
        for row in self.case.base.rows("act_event"):
            self.probe.schema.validate_record(row)

    def test_a_continuation_is_found_as_the_client_finds_it(self):
        self.case.ready()
        self.continuations[901] = piano_Play_Song()
        ok, _ = self.cancel("901")
        self.assertTrue(ok)
        self.assertEqual(self.continuations[901].reasons, ["Ashley stopped it."])

    def test_the_game_may_refuse_and_a_missing_one_is_refused(self):
        self.case.ready()
        self.song.allowed = False
        ok, connection = self.cancel()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        ok, connection = self.cancel("404", act_id="d" * 32)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_INTERACTION")
        ok, connection = self.cancel("313")
        self.assertEqual(connection.lines[-1], "ACT_REJECT DUPLICATE")

    def test_not_sampling_refuses(self):
        self.case.base.LedgerWriter.records = [self.case.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        ok, connection = self.cancel()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_SAMPLING")
        self.assertEqual(self.song.reasons, [])

    def test_cmdbox_shape(self):
        from ashley_e1 import cmdbox
        base = {"v": 1, "id": "e" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000, "issuer": "helper", "command": "cancel"}

        def check(args):
            return cmdbox.parse(json.dumps(dict(base, args=args)).encode("utf-8"), 1500, set())[1]
        self.assertIsNone(check({"act_id": STOP, "interaction_id": "313"}))
        for bad in ({"act_id": STOP, "interaction_id": "31x"}, {"act_id": "x", "interaction_id": "313"},
                    {"act_id": STOP}, {"act_id": STOP, "interaction_id": "313", "pick": "1"}):
            self.assertEqual(check(bad), "BAD_ARGS", bad)


if __name__ == "__main__":
    unittest.main()
