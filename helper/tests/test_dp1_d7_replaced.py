"""D7 (Domus perception 1): the helper forwards what a push replaced to Natalis."""
import json

from domus_helper.acts import ActCourier
from domus_helper.spool import Spool


class _Client:
    def __init__(self):
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        return {"status": "ok", "applied": len(body["events"]), "acts": []}


ACT_ID = "a" * 32


def _row(phase, **extra):
    e2 = {"act_id": ACT_ID, "phase": phase, "code": None, "object_id": "11", "guid64": "4242",
          "interaction_id": None, "tuning_name": "bookshelf_ReadBook", "finishing_type": None, "detail": None}
    e2.update(extra)
    return {"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 5000, "e2": e2}


def test_a_pushed_row_forwards_what_it_replaced(tmp_path):
    client = _Client()
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None)
    replaced = [{"name": "fridge_GrabSnack", "autonomous": True, "state": "queued"},
                {"name": "bookshelf_ReadBook", "autonomous": False, "state": "running"}]
    courier.on_row(_row("PUSHED", interaction_id="777", replaced=replaced))
    courier.tick(client, "h", 2000, True)
    sent = client.bodies[-1]["events"]
    assert sent[-1]["phase"] == "pushed"
    assert sent[-1]["detail"]["replaced"] == replaced


def test_a_malformed_replaced_list_is_not_forwarded(tmp_path):
    client = _Client()
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None)
    courier.on_row(_row("PUSHED", interaction_id="777", replaced="fridge_GrabSnack"))
    courier.tick(client, "h", 2000, True)
    assert "replaced" not in client.bodies[-1]["events"][-1]["detail"]
