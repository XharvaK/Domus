"""2.26.0: social talk on the User's screen. Invented phrase fixtures only."""
from domus_helper import lang
from domus_helper.spool import Spool
from domus_helper.talk import FORGET_MS, MIN_GAP_MS, WAITING_MAX, Talk, main, sentences


class _Book:
    def sentence(self, tuning, actors):
        if tuning.startswith("quiet"):
            return None
        return "%s does %s." % (" and ".join(actors), tuning)


def _row(running=("invented_wave",), queued=(), social=("invented_greet",)):
    observed = [{"affordance_text": name, "membership": "RUNNING", "target_id": "2"} for name in running]
    observed += [{"affordance_text": name, "membership": "QUEUED"} for name in queued]
    return {
        "motives": [],
        "body": {"sim_id": "1"},
        "presence": [{"id": "1", "is_body": True, "name": "Ada"},
                     {"id": "2", "is_body": False, "name": "Bea", "distance_m": 1.0}],
        "social": [{"actor_id": "2", "affordance_text": name} for name in social],
        "interactions": {"observed": observed},
    }


def _talk(tmp_path):
    sent = []
    spool = Spool(tmp_path / "spool.db")
    return Talk(spool, lambda command, args: sent.append((command, args))), sent, spool


def test_running_and_addressed_sentences_only(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    found = sentences(_row(running=("invented_wave", "quiet_one"), queued=("invented_later",)))
    assert [(text, sim_id) for _, text, sim_id in found] == [
        ("Ada and Bea does invented_wave.", "1"), ("Bea and Ada does invented_greet.", "2")]


def test_each_new_sentence_shows_once_with_a_gap(monkeypatch, tmp_path):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    talk, sent, spool = _talk(tmp_path)
    talk.on_row(_row(), 1_000, True)
    assert talk.tick(1_000, True) == "Ada and Bea does invented_wave."
    assert talk.tick(1_000 + MIN_GAP_MS - 1, True) is None
    assert talk.tick(1_000 + MIN_GAP_MS, True) == "Bea and Ada does invented_greet."
    talk.on_row(_row(), 5_000, True)
    assert talk.tick(9_000, True) is None
    assert sent == [("talk", {"text": "Ada and Bea does invented_wave.", "sim_id": "1"}),
                    ("talk", {"text": "Bea and Ada does invented_greet.", "sim_id": "2"})]
    spool.close()


def test_shows_again_only_after_it_was_gone(monkeypatch, tmp_path):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    talk, sent, spool = _talk(tmp_path)
    talk.on_row(_row(social=()), 1_000, True)
    talk.tick(1_000, True)
    talk.on_row(_row(running=(), social=()), 1_000 + FORGET_MS // 2, True)
    talk.on_row(_row(social=()), 1_000 + FORGET_MS // 2 + 1, True)
    assert talk.tick(90_000, True) is None
    talk.on_row(_row(running=(), social=()), 200_000, True)
    talk.on_row(_row(social=()), 200_001, True)
    assert talk.tick(200_001, True) == "Ada and Bea does invented_wave."
    assert len(sent) == 2
    spool.close()


def test_newest_kept_and_nothing_while_not_live_or_off(monkeypatch, tmp_path):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    talk, sent, spool = _talk(tmp_path)
    talk.on_row(_row(running=("a1", "a2", "a3", "a4"), social=()), 1_000, True)
    assert talk.tick(1_000, True) == "Ada and Bea does a2."
    talk.on_row(_row(running=("b1",), social=()), 2_000, True)
    assert talk.tick(2_000, False) is None
    talk.on_row(_row(running=("c1",), social=()), 3_000, True)
    spool.put_kv("talk", "off")
    assert talk.tick(9_000, True) is None
    spool.put_kv("talk", "on")
    talk.on_row(_row(running=("d1",), social=()), 10_000, True)
    talk.on_row({"event_kind": "act_event", "e2": {}}, 10_000, False)
    assert talk.tick(10_000, True) == "Ada and Bea does d1."
    assert len(sent) == 2 and WAITING_MAX == 3
    spool.close()


def test_one_printable_line_within_the_probe_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(lang, "phrases", lambda: type("B", (), {
        "sentence": lambda self, tuning, actors: "Ada\nwaves  " + "x" * 300})())
    (_, text, _), = sentences(_row(social=()))
    assert text.startswith("Ada waves x") and len(text) == 240 and "\n" not in text


def test_switch_cli(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert main(["off"]) == 0
    assert '"switch": "off"' in capsys.readouterr().out
    assert main(["show"]) == 0
    assert '"switch": "off"' in capsys.readouterr().out
