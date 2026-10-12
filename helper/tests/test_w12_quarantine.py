"""2.39.0 (W12 B4): a failed acts round trip is logged once, an event Mint refuses is quarantined without holding the
others, and unsent events are never trimmed (a round trip sends at most 64). Fakes only; invented ids."""
import json

from domus_helper.acts import ActCourier, EVENTS_PER_SYNC
from domus_helper.spool import Spool
from domus_helper.transport import SyncRefused

ACT_ID = "f" * 32


class _Mint:
    def __init__(self, refuse_phases=()):
        self.bodies = []
        self.down = False
        self.refuse_phases = set(refuse_phases)

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        if self.down:
            return None
        if any(event["phase"] in self.refuse_phases for event in body["events"]):
            return SyncRefused("invalid_body")
        return {"status": "ok", "applied": len(body["events"]), "acts": []}


def _row(phase, at=5000, **extra):
    e2 = {"act_id": ACT_ID, "phase": phase, "code": None, "tuning_name": "bookshelf_ReadBook", "detail": None}
    e2.update(extra)
    return {"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": at, "e2": e2}


def _courier(tmp_path, lines):
    return ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None, log=lines.append)


def test_an_event_mint_refuses_is_quarantined_and_the_rest_of_the_batch_goes_through(tmp_path):
    lines = []
    courier = _courier(tmp_path, lines)
    courier.on_row(_row("ACCEPTED"))
    courier.on_row(_row("WAITING", detail="dialog 555 act " + ACT_ID))
    client = _Mint(refuse_phases={"waiting"})
    courier.tick(client, "h", 1000, True)
    assert [line["trigger"] for line in lines] == ["acts_sync", "acts_quarantined"]
    assert lines[0]["error"] == "refused:invalid_body"
    assert [item["event"]["phase"] for item in courier.quarantined] == ["waiting"]
    assert courier.quarantined[0]["reason"] == "invalid_body"
    assert courier._events == []
    assert courier.sync_ok is True


def test_unsent_events_are_never_trimmed_and_a_round_trip_sends_at_most_64(tmp_path):
    lines = []
    courier = _courier(tmp_path, lines)
    for index in range(100):
        courier.on_row(_row("ACCEPTED", at=5000 + index))
    down = _Mint()
    down.down = True
    courier.tick(down, "h", 1000, True)
    assert len(courier._events) == 100
    sent = []
    for now in (2000, 3000):
        client = _Mint()
        courier.tick(client, "h", now, True)
        sent.append(len(client.bodies[-1]["events"]))
    assert sent == [EVENTS_PER_SYNC, 100 - EVENTS_PER_SYNC]
    assert courier._events == []


def test_a_failed_round_trip_is_one_log_line_and_says_no_reply(tmp_path):
    lines = []
    courier = _courier(tmp_path, lines)
    courier.on_row(_row("ACCEPTED"))
    down = _Mint()
    down.down = True
    courier.tick(down, "h", 1000, True)
    assert lines == [{"wall_ms": 1000, "trigger": "acts_sync", "error": "no_reply", "events": 1}]
    assert courier.sync_ok is False
    courier.tick(_Mint(), "h", 2000, True)
    assert courier.sync_ok is True and len(lines) == 1
