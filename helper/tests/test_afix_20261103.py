"""AU_DOMUS_FULL_2026-11-03 fixes: one regression test per audit item."""
import json

from domus_helper.acts import ActCourier
from domus_helper.spool import Spool

PROBE = "2.41.7"


# N-2: every act (act, cancel, answer) is recorded and saved before its command goes out, so a helper that dies
# before tick's save and gets the same act again after a restart never pushes it twice.
def _one_push_across_a_restart(tmp_path, act):
    pushes = []

    def publish(command, args):
        pushes.append((command, args["act_id"]))
        return "%032x" % len(pushes)
    ActCourier(Spool(tmp_path / "spool.db"), publish)._receive({"acts": [act]}, 1000, True, PROBE)
    ActCourier(Spool(tmp_path / "spool.db"), publish)._receive({"acts": [act]}, 2000, True, PROBE)
    return pushes


def test_an_act_is_pushed_once_across_a_restart(tmp_path):
    act = {"act_id": "a" * 32, "object_id": "123", "guid64": "456"}
    assert _one_push_across_a_restart(tmp_path, act) == [("act", "a" * 32)]


def test_a_cancel_is_pushed_once_across_a_restart(tmp_path):
    from domus_helper.acts import QUEUE_OBJECT_ID
    act = {"act_id": "c" * 32, "object_id": QUEUE_OBJECT_ID, "guid64": "77"}
    assert _one_push_across_a_restart(tmp_path, act) == [("cancel", "c" * 32)]


def test_an_answer_is_pushed_once_across_a_restart(tmp_path):
    from domus_helper.acts import DIALOG_PREFIX
    act = {"act_id": "d" * 32, "object_id": DIALOG_PREFIX + "9", "guid64": "ok"}
    assert _one_push_across_a_restart(tmp_path, act) == [("answer", "d" * 32)]
