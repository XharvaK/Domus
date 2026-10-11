"""D7b: the world's memory, hers to ask. The helper finds what the game recorded about an act, a person or an
object, answers once on POST /domus/memory, runs the search off the tick, and never judges what it finds."""
import json
import threading
import urllib.request

import pytest

from domus_helper import memory
from domus_helper.acts import ActCourier
from domus_helper.spool import Spool
from domus_helper.transport import AshleyClient

NOW = 1_800_000_000_000


@pytest.fixture(autouse=True)
def nothing_answered_yet(monkeypatch):
    monkeypatch.setattr(memory, "_HANDLED", set())


def _act(name, start, wall=None, relationships=None, target=None, objects=None, moodlets=None):
    """An outcome record, shaped as outcomes.acts() writes it."""
    return {
        "act_id": "s1:%s:%d" % (name, start),
        "interaction": {"name": name, "target_id": target},
        "origin": "owner",
        "span": {"start": "c", "end": "c", "start_minute": start, "game_minutes": 10},
        "wall_ms": wall,
        "needs": {"delta": {"hunger": 30}, "measured_to": "next_sample"},
        "moodlets": {"gained": list(moodlets or []), "lost": []},
        "reactions": [],
        "relationships": list(relationships or []),
        "objects": objects,
    }


def _changed(object_id, cls):
    return {"created": [], "destroyed": [], "changed": [{"object_id": object_id, "class": cls,
                                                         "state": "clean", "from": "a", "to": "b"}],
            "truncated": False, "baseline": False}


class FakeClient:
    def __init__(self, on_post=None):
        self.posted = []
        self._on_post = on_post

    def post_memory(self, body):
        self.posted.append(body)
        if self._on_post is not None:
            self._on_post()
        return {"status": "ok", "applied": True}


def _now(run):
    run()


def test_an_act_is_found_by_its_tuning_name_in_any_case():
    records = [_act("stove_Cook", 100), _act("piano_Play", 200)]
    facts = memory.facts_for(records, "STOVE_cook")
    assert facts["matched"] == 1
    assert facts["acts"][0]["what"] == "stove_Cook"
    assert memory.facts_for(records, "toaster")["matched"] == 0


def test_an_act_is_found_by_its_humanised_name_in_words():
    records = [_act("bookshelf_ReadBook", 100), _act("stove_Cook", 200)]
    facts = memory.facts_for(records, "read book")
    assert facts["matched"] == 1 and facts["acts"][0]["what"] == "bookshelf_ReadBook"
    assert memory.facts_for(records, "Read")["matched"] == 1


def test_a_person_in_a_relationship_change_is_found_by_name_and_counted_with_her_tracks():
    records = [
        _act("chat", 100, wall=5000, relationships=[{"with": "Mara Quill", "role": "target",
                                                      "tracks": {"Friendly": 5.0}}]),
        _act("cook", 200, wall=6000),
    ]
    facts = memory.facts_for(records, "mara quill")
    assert facts["matched"] == 1 and facts["acts"][0]["what"] == "chat"
    assert facts["people"] == [{"who": "Mara Quill", "acts": 1, "last_at_ms": 5000, "tracks": {"Friendly": 5.0}}]


def test_an_object_is_found_by_the_class_recorded_for_the_act_target_only():
    records = [
        _act("piano_Play", 100, target="77", objects=_changed("77", "Bookshelf")),
        _act("stove_Cook", 200, target="9", objects=_changed("77", "Toaster")),
    ]
    facts = memory.facts_for(records, "bookshelf")
    assert facts["matched"] == 1 and facts["acts"][0]["what"] == "piano_Play"
    assert memory.facts_for(records, "toaster")["matched"] == 0


def test_a_line_carries_the_game_day_and_the_wall_time_it_was_recorded():
    facts = memory.facts_for([_act("cook", 1445, wall=7000)], "cook")
    line = facts["acts"][0]
    assert line["day"] == 1 and line["at_ms"] == 7000
    assert line["act_id"] == "s1:cook:1445" and line["what"] == "cook"


def test_matches_are_newest_first_capped_at_twelve_acts_and_six_people():
    records = [_act("chat", minute, wall=minute * 10,
                    relationships=[{"with": "Person %d" % (minute % 8), "role": "target"}])
               for minute in range(100, 115)]
    facts = memory.facts_for(records, "chat")
    assert facts["matched"] == 15
    assert len(facts["acts"]) == 12
    assert facts["acts"][0]["act_id"] == "s1:chat:114" and facts["acts"][-1]["act_id"] == "s1:chat:103"
    assert len(facts["people"]) == 6
    stamps = [person["last_at_ms"] for person in facts["people"]]
    assert stamps == sorted(stamps, reverse=True)


def test_the_answer_fits_16_KiB_by_dropping_the_oldest_acts_and_keeps_the_true_count():
    big = ["Mood_%d_%s" % (number, "x" * 900) for number in range(3)]
    records = [_act("chat", minute, wall=minute, moodlets=big) for minute in range(100, 112)]
    facts = memory.facts_for(records, "chat")
    body = memory.body_for("h1", "a1", facts)
    size = len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert size <= memory.BODY_LIMIT == 16 * 1024
    assert body["facts"]["matched"] == 12
    kept = body["facts"]["acts"]
    assert 0 < len(kept) < 12
    assert kept[0]["act_id"] == "s1:chat:111"


def test_the_wire_body_is_exactly_the_contract():
    facts = memory.facts_for([_act("stove_Cook", 100, wall=50)], "cook")
    assert memory.body_for("h1", "a1", facts) == {
        "v": 1, "helper_session": "h1", "ask_id": "a1",
        "facts": {"matched": 1, "acts": [facts["acts"][0]], "people": []}}


def test_each_ask_is_answered_once_and_an_invalid_ask_is_not_answered():
    client = FakeClient()
    asks = [{"ask_id": "a1", "about": "chat"}, {"ask_id": "a1", "about": "chat"},
            {"ask_id": 5, "about": "chat"}, {"ask_id": "a2", "about": "   "}, "junk"]
    memory.handle_asks_in_background(asks, client, helper_session="h1", world="slot1",
                                     read_records=lambda world: [_act("chat", 100)], start=_now)
    memory.handle_asks_in_background(asks, client, helper_session="h1", world="slot1",
                                     read_records=lambda world: [_act("chat", 100)], start=_now)
    assert [body["ask_id"] for body in client.posted] == ["a1"]


def test_an_unreadable_world_is_answered_with_nothing_and_no_error_text():
    client = FakeClient()

    def unreadable(world):
        raise OSError("telemetry folder could not be read")

    memory.handle_asks_in_background([{"ask_id": "a9", "about": "chat"}], client, helper_session="h1",
                                     world="slot1", read_records=unreadable, start=_now)
    assert client.posted == [{"v": 1, "helper_session": "h1", "ask_id": "a9",
                              "facts": {"matched": 0, "acts": [], "people": []}}]


def test_the_search_runs_off_the_tick_on_its_own_thread():
    gate, done = threading.Event(), threading.Event()

    def slow(world):
        gate.wait(5)
        return [_act("chat", 100)]

    client = FakeClient(on_post=done.set)
    memory.handle_asks_in_background([{"ask_id": "a1", "about": "chat"}], client, helper_session="h1",
                                     world="slot1", read_records=slow)
    assert client.posted == []  # the tick has returned while the search still waits
    gate.set()
    assert done.wait(5)
    assert client.posted[0]["facts"]["matched"] == 1


def test_a_send_that_did_not_arrive_is_tried_once_more_after_a_wait(monkeypatch):
    sent = []
    monkeypatch.setattr(memory, "RETRY_WAIT_S", 0)

    class Flaky:
        def post_memory(self, body):
            sent.append(body["ask_id"])
            return None if len(sent) == 1 else {"status": "ok", "applied": True}

    memory.handle_asks_in_background([{"ask_id": "a4", "about": "chat"}], Flaky(), helper_session="h1",
                                     world="slot1", read_records=lambda world: [], start=_now)
    assert sent == ["a4", "a4"]


def test_the_courier_hands_the_memory_asks_of_a_sync_answer_to_its_callback(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    asked = []

    class Sync:
        def sync_acts(self, body):
            return {"status": "ok", "planned": 0, "acts": [],
                    "memory": [{"ask_id": "a1", "about": "chat"}]}

    try:
        courier = ActCourier(spool, lambda command, args: None,
                             memory=lambda asks, client, session: asked.append((asks, session)))
        courier.tick(Sync(), "h1", NOW, True)
    finally:
        spool.close()
    assert asked == [([{"ask_id": "a1", "about": "chat"}], "h1")]


class _Reply:
    status = 200

    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_post_memory_posts_the_body_to_its_route_with_the_token(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request.full_url, request.get_header("X-domus-token"),
                     json.loads(request.data.decode("utf-8")), timeout))
        return _Reply({"status": "ok", "applied": True})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = AshleyClient("https://example.invalid/", "t" * 40)
    assert client.post_memory({"v": 1, "ask_id": "a1"}) == {"status": "ok", "applied": True}
    assert seen == [("https://example.invalid/domus/memory", "t" * 40, {"v": 1, "ask_id": "a1"}, 10)]
