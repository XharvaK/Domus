"""Live 2026-10-06: Cook opens the recipe question instead of entering her queue. The probe
called it gone (LEFT_QUEUE), her answers queued trays she could not see behind a piano song,
and she cooked again and again."""
from domus_helper.acts import ActCourier
from domus_helper.spool import Spool
from domus_helper.thalamus import observation


class _Client:
    def __init__(self, acts):
        self.acts = list(acts)
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(body)
        acts, self.acts = self.acts, []
        return {"status": "ok", "applied": len(body["events"]), "acts": acts}


COOK = {"act_id": "c" * 32, "object_id": "21", "guid64": "13395", "expires_at_ms": 99_000}


def _event(phase, at, **extra):
    e2 = {"act_id": "c" * 32, "phase": phase, "object_id": "21", "guid64": "13395",
          "tuning_name": "fridge_Cook", "interaction_id": "606"}
    e2.update(extra)
    return {"event_kind": "act_event", "wall_timestamp_ms": at, "e2": e2}


def _sample(at, open_dialogs):
    return {"event_kind": "sample", "wall_timestamp_ms": at, "dialogs": {"open": open_dialogs, "closed": []}}


def _sent_after_cook(rows, tmp_path):
    client = _Client([COOK])
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None)
    courier.tick(client, "h", 1000, True)
    for row in rows:
        courier.on_sample(row)
        if row["event_kind"] == "act_event":
            courier.on_row(row)
    courier.tick(client, "h", 9000, True)
    return client.bodies[-1]["events"]


def test_an_act_that_opened_the_games_question_finished_as_asked(tmp_path):
    sent = _sent_after_cook([
        _event("ACCEPTED", 2000), _event("PUSHED", 2001),
        _sample(2500, [{"dialog_id": "4", "kind": "UiRecipePicker"}]),
        _event("UNKNOWN", 7000, code="LEFT_QUEUE", detail="never seen in her queue"),
    ], tmp_path)
    last = sent[-1]
    assert last["phase"] == "finished"
    assert last["detail"]["finishing_type"] == "ASKED"
    assert "UiRecipePicker" in last["detail"]["detail"] and "answering it" in last["detail"]["detail"]
    assert "code" not in last["detail"]


def test_an_act_that_left_with_no_question_stays_unknown(tmp_path):
    sent = _sent_after_cook([
        _sample(500, [{"dialog_id": "3", "kind": "UiDialogOkCancel"}]),
        _event("ACCEPTED", 2000), _event("PUSHED", 2001),
        _event("UNKNOWN", 7000, code="LEFT_QUEUE", detail="never seen in her queue"),
    ], tmp_path)
    assert sent[-1]["phase"] == "unknown" and sent[-1]["detail"]["code"] == "LEFT_QUEUE"


def test_the_dialogs_she_was_asked_survive_a_restart(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    first = ActCourier(spool, lambda command, args: None)
    first.on_sample(_sample(2500, [{"dialog_id": "4", "kind": "UiRecipePicker"}]))
    again = ActCourier(spool, lambda command, args: None)
    assert again._asked_after(2001, 7000)["kind"] == "UiRecipePicker"


def test_her_portrait_shows_what_waits_in_her_queue():
    row = {"interactions": {"observed": [
        {"affordance_text": "<class 'sims4.tuning.instances.piano_Play_Song'>", "membership": "QUEUED_AND_RUNNING"},
        {"affordance_text": "<class 'sims4.tuning.instances.fridge_CreateTray'>", "membership": "QUEUED"},
        {"affordance_text": "<class 'sims4.tuning.instances.fridge_CreateTray'>", "membership": "QUEUED"},
        {"affordance_text": "<class 'sims4.tuning.instances.seating_Sit_single'>", "membership": "RUNNING"},
    ]}}
    portrait = observation._portrait(row)
    assert portrait["running"] == ["piano_Play_Song", "seating_Sit_single"]
    assert portrait["queued"] == ["fridge_CreateTray", "fridge_CreateTray"]
