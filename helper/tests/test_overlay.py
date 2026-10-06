import http.client
import json
import re

from domus_helper import inputs, overlay
from domus_helper.overlay_page import PAGE
from domus_helper.spool import Spool

NOW = 1_800_000_000_000


class Feed:
    def __init__(self, items):
        self.items, self.calls = items, 0

    def post_feed(self, body):
        self.calls += 1
        assert body == {"v": 1, "helper_session": "h1"}
        return {"status": "ok", "items": self.items}


def snapshot(**extra):
    row = {"event_kind": "presence_snapshot", "game": {"calendar": "14:05:00.000 day:2 week:1", "paused": False},
           "motives": [{"id": "hunger", "value": 42, "band": "low"}, {"id": "fun", "value": 90, "band": "ok"}],
           "mood": {"name": "Mood_Happy"}, "interactions": {"observed": []}}
    row.update(extra)
    return row


def made(tmp_path, game_only=True):
    spool = Spool(tmp_path / "spool.db")
    if game_only:
        inputs.set_mode(spool, tmp_path, inputs.GAME_ONLY, NOW - 3 * 86_400_000)
    return spool, overlay.Overlay(spool, tmp_path, NOW - overlay.HUMAN_HAND_MS - 1)


def test_nothing_of_hers_while_the_switch_is_off(tmp_path):
    spool, view = made(tmp_path, game_only=False)
    try:
        feed = Feed([{"inputs": "game_only", "line": "Toast smells good."}])
        view.on_row(snapshot(), NOW)
        view.poll(feed, "h1", NOW)
        state = view.publish(NOW, attached=True)
        assert feed.calls == 0
        assert state == {"v": 1, "mode": "off", "card": {"day": None, "time": "Tuesday 14:05", "label": "AI-controlled"}}
    finally:
        spool.close()


def test_a_pass_without_the_stamp_is_refused_and_the_feed_is_paced(tmp_path):
    spool, view = made(tmp_path)
    try:
        feed = Feed([{"inputs": "game_only", "line": "Toast smells good.", "act": {"label": "Cook (Stove)", "state": "pushed"},
                      "plan": [{"label": "Eat (Plate)", "state": "planned"}]},
                     {"line": "No stamp on this one."},
                     {"inputs": "full", "line": "Nor this."},
                     {"inputs": "game_only", "quiet": True}])
        view.on_row(snapshot(), NOW)
        view.poll(feed, "h1", NOW)
        view.poll(feed, "h1", NOW + 1_000)
        assert feed.calls == 1
        state = view.publish(NOW, attached=True)
        assert state["mode"] == "live"
        assert state["passes"] == [
            {"at_ms": None, "line": "Toast smells good.", "act": {"label": "Cook (Stove)", "state": "pushed", "how": None},
             "plan": [{"label": "Eat (Plate)", "state": "planned"}]},
            {"at_ms": None, "quiet": True}]
        assert state["feed"]["refused"] == 2
        assert state["needs"] == [{"need": "hunger", "value": 42, "band": "low"}, {"need": "fun", "value": 90, "band": "ok"}]
        assert state["mood"] == "Happy" and state["card"]["day"] == 2
        view.poll(feed, "h1", NOW + overlay.FEED_EVERY_MS)
        assert feed.calls == 2
        inputs.set_mode(spool, tmp_path, inputs.FULL, NOW + 9_000)
        view.poll(feed, "h1", NOW + 2 * overlay.FEED_EVERY_MS)
        assert view.publish(NOW, attached=True)["mode"] == "off" and view._items == []
    finally:
        spool.close()


def test_the_privacy_list_holds_lines_and_labels(tmp_path):
    spool, view = made(tmp_path)
    try:
        (tmp_path / overlay.PRIVACY_FILE).write_text("# names\nMarrowind\nOld Harbour Street\n", encoding="utf-8")
        feed = Feed([{"inputs": "game_only", "line": "I miss marrowind today."},
                     {"inputs": "game_only", "line": "Walked past old harbour street."},
                     {"inputs": "game_only", "line": "Marrowindy weather.", "act": {"label": "Chat (Marrowind)", "state": "finished"}},
                     {"inputs": "game_only", "line": "Ping @someone_here please."},
                     {"inputs": "game_only", "held": True}])
        view.poll(feed, "h1", NOW)
        passes = view.publish(NOW, attached=True)["passes"]
        assert [item.get("line", "held" if item.get("held") else "") for item in passes] == [
            "held", "held", "Marrowindy weather.", "held", "held"]
        assert passes[2]["act"]["label"] == overlay.HELD
    finally:
        spool.close()


def test_whose_hand_started_it(tmp_path):
    spool, view = made(tmp_path)
    try:
        view.on_row({"event_kind": "act_event", "e2": {"act_id": "a1", "interaction_id": "501"}}, NOW)
        observed = [
            {"interaction_id": "501", "affordance_text": "<class 'sims4.tuning.instances.stove_Cook'>",
             "source_raw": "InteractionSource.SCRIPT_WITH_USER_INTENT", "membership": "RUNNING"},
            {"interaction_id": "502", "affordance_text": "<class 'sims4.tuning.instances.toilet_Use'>",
             "source_raw": "InteractionSource.AUTONOMY", "membership": "QUEUED"},
            {"interaction_id": "503", "affordance_text": "<class 'sims4.tuning.instances.sim-stand'>",
             "source_raw": "InteractionSource.AUTONOMY", "membership": "RUNNING"},
            {"interaction_id": "504", "affordance_text": "<class 'sims4.tuning.instances.posture_x'>",
             "source_raw": "InteractionSource.POSTURE_GRAPH", "membership": "RUNNING"}]
        view.on_row(snapshot(interactions={"observed": observed}), NOW)
        state = view.publish(NOW, attached=True)
        assert state["doing"] == [{"text": "stove Cook", "by": "her", "queued": False},
                                  {"text": "toilet Use", "by": "body", "queued": True}]
        assert state["human_at_controls"] is False
        observed.append({"interaction_id": "505", "affordance_text": "<class 'sims4.tuning.instances.piano_Play'>",
                         "source_raw": "InteractionSource.PIE_MENU", "membership": "QUEUED"})
        view.on_row(snapshot(interactions={"observed": observed}), NOW + 1)
        state = view.publish(NOW + 1, attached=True)
        assert state["human_at_controls"] is True and state["doing"][-1]["by"] == "human"
        assert view.publish(NOW + overlay.HUMAN_HAND_MS + 2, attached=True)["human_at_controls"] is False
    finally:
        spool.close()


def test_a_pop_up_answered_by_hand_shows_the_human_and_hers_does_not(tmp_path):
    spool, view = made(tmp_path)
    try:
        view.answered = ["77"]
        view.on_row(snapshot(dialogs={"open": [{"dialog_id": "77", "auto_respond": False},
                                               {"dialog_id": "78", "auto_respond": False},
                                               {"dialog_id": "79", "auto_respond": True}], "closed": []}), NOW)
        view.on_row(snapshot(dialogs={"open": [], "closed": [{"dialog_id": "77", "response": 3},
                                                             {"dialog_id": "79", "response": 1}]}), NOW + 1)
        assert view.publish(NOW + 1, attached=True)["human_at_controls"] is False
        view.on_row(snapshot(dialogs={"open": [], "closed": [{"dialog_id": "78", "response": 2}]}), NOW + 2)
        assert view.publish(NOW + 2, attached=True)["human_at_controls"] is True
    finally:
        spool.close()


def test_a_helper_restart_counts_as_a_human_hand(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    try:
        inputs.set_mode(spool, tmp_path, inputs.GAME_ONLY, NOW)
        view = overlay.Overlay(spool, tmp_path, NOW)
        assert view.publish(NOW + 1_000, attached=True)["human_at_controls"] is True
    finally:
        spool.close()


def test_curtain_work_and_detached(tmp_path):
    spool, view = made(tmp_path)
    try:
        view.on_row(snapshot(self={"careers": [{"at_work": True, "title_key": "0x1"}]}), NOW)
        assert view.publish(NOW, attached=True)["mode"] == "work"
        assert view.publish(NOW, attached=False)["mode"] == "curtain"
        spool.put_kv(overlay.CURTAIN_KEY, "on")
        assert view.publish(NOW, attached=True)["mode"] == "curtain"
    finally:
        spool.close()


def test_the_cli_draws_the_curtain(paths, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert overlay.main(["curtain", "on"]) == 0
    assert json.loads(capsys.readouterr().out)["curtain"] == "on"
    assert overlay.main(["curtain", "off"]) == 0
    assert json.loads(capsys.readouterr().out)["curtain"] == "off"


def test_the_pages_are_served_to_this_pc_only(tmp_path):
    spool, view = made(tmp_path)
    try:
        view.publish(NOW, attached=True)
        server = overlay.serve(view, port=0)
        port = server.server_address[1]
        server.RequestHandlerClass.port = port

        def get(path, host):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("GET", path, headers={"Host": host})
            response = connection.getresponse()
            return response.status, response.read()
        try:
            status, body = get("/state.json", "127.0.0.1:%d" % port)
            assert status == 200 and json.loads(body)["mode"] == "live"
            status, body = get("/vertical", "localhost:%d" % port)
            assert status == 200 and b'data-layout="vertical"' in body
            assert get("/state.json", "evil.example:%d" % port)[0] == 403
            assert get("/nope", "127.0.0.1:%d" % port)[0] == 404
        finally:
            server.shutdown()
            server.server_close()
    finally:
        spool.close()


def test_the_page_writes_text_never_markup():
    script = PAGE.split("<script>", 1)[1]
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", script)
