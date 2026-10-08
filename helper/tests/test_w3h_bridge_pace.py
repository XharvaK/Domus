"""W3h in the bridge: the pace command goes to the probe when the game attaches, when a setting
changes, and when the probe's rows show other values for three rows in a row; a failed write is
tried again later; her portrait gets the probe's block. The probe inbox is faked. Invented
strings only."""
from domus_helper import bridge as bridge_module
from domus_helper import commands
from domus_helper.bridge import Bridge

NOW = 1_000_000
WANTED = {"need_drain": 0.5, "slow_time": 1.0}


def _bridge(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    sent = []
    monkeypatch.setattr(commands, "publish", lambda command, args, issuer, paths=None: sent.append((command, args)))
    bridge = Bridge(paths, client=None, process=(1, "t"), detected_build="1.128.90.1030", mono=lambda: 0)
    return bridge, sent


def _block(need=0.5, slow=1.0, scale=1.0, foreign=False):
    return {"need_drain": need, "motives_modified": 6, "drain_measured": need, "slow_time": slow,
            "clock_scale": scale, "clock_foreign": foreign}


def test_nothing_is_sent_while_the_game_is_not_attached(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "detached"
    bridge._pace_tick(NOW)
    assert sent == []


def test_the_settings_are_published_once_when_the_game_attaches(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    bridge._pace_tick(NOW + 1_000)
    assert sent == [("pace", WANTED)]


def test_a_changed_setting_is_published_again(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    (tmp_path / "pace.json").write_text('{"slow_time": 0.5}', encoding="utf-8")
    bridge._pace_tick(NOW + 1_000)
    assert sent[-1] == ("pace", {"need_drain": 0.5, "slow_time": 0.5})
    assert len(sent) == 2


def test_a_reattach_publishes_again(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    bridge._state = "detached"
    bridge._pace_tick(NOW + 1_000)
    bridge._state = "attached"
    bridge._pace_tick(NOW + 2_000)
    assert len(sent) == 2


def test_three_rows_in_a_row_that_differ_ask_for_one_resend(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    later = NOW + 120_000
    bridge._pace_observe(_block(need=1.0), later)
    bridge._pace_observe(_block(need=1.0), later)
    bridge._pace_tick(later)
    assert len(sent) == 1
    bridge._pace_observe(_block(need=1.0), later)
    bridge._pace_tick(later)
    assert len(sent) == 2


def test_a_matching_row_restarts_the_count(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    later = NOW + 120_000
    for block in (_block(need=1.0), _block(need=1.0), _block(), _block(need=1.0), _block(need=1.0)):
        bridge._pace_observe(block, later)
    bridge._pace_tick(later)
    assert len(sent) == 1


def test_a_mismatch_within_a_minute_of_the_last_send_does_not_resend(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    for _ in range(3):
        bridge._pace_observe(_block(need=1.0), NOW + 2_000)
    bridge._pace_tick(NOW + 2_000)
    assert len(sent) == 1


def test_a_refused_clock_is_not_asked_again_for_slow_time(paths, tmp_path, monkeypatch):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    (tmp_path / "pace.json").write_text('{"slow_time": 0.5}', encoding="utf-8")
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    later = NOW + 120_000
    for _ in range(4):
        bridge._pace_observe(_block(slow=1.0, foreign=True), later)
    bridge._pace_tick(later)
    assert len(sent) == 1


def test_a_failed_write_is_tried_again_after_thirty_seconds(paths, tmp_path, monkeypatch, capsys):
    bridge, sent = _bridge(paths, tmp_path, monkeypatch)
    attempts = []

    def refuse(command, args, issuer, paths=None):
        attempts.append(command)
        raise ValueError("unknown command")

    monkeypatch.setattr(commands, "publish", refuse)
    bridge._state = "attached"
    bridge._pace_tick(NOW)
    bridge._pace_tick(NOW + 5_000)
    assert len(attempts) == 1
    assert "pace not sent: ValueError" in capsys.readouterr().out
    monkeypatch.setattr(commands, "publish", lambda command, args, issuer, paths=None: sent.append((command, args)))
    bridge._pace_tick(NOW + bridge_module.PACE_RETRY_MS)
    assert sent == [("pace", WANTED)]


def test_her_portrait_context_carries_the_probe_block_and_its_pace_sentences(paths, tmp_path, monkeypatch):
    bridge, _ = _bridge(paths, tmp_path, monkeypatch)
    assert bridge._obs_ctx(NOW)["pace"] is None
    bridge._pace_observe(_block(scale=0.5), NOW)
    entry = bridge._obs_ctx(NOW)["pace"]
    assert entry == {"needs": "your needs drain at half the game's pace, by the User's choice.",
                     "clock": "the game's clock runs at half its normal speed."}


def test_a_decision_sent_to_ashley_is_the_one_its_act_is_measured_from(paths, tmp_path, monkeypatch):
    bridge, _ = _bridge(paths, tmp_path, monkeypatch)
    bridge.client = object()
    bridge._last_row = {"game": {"ticks": 40_000}, "telemetry_session_id": "s"}
    bridge._last_body_row = bridge._last_row
    monkeypatch.setattr(bridge_module, "build", lambda decision, ctx: {"observation_id": "s.1"})
    monkeypatch.setattr(bridge_module, "run_scorer", lambda scorer, obs: None)
    monkeypatch.setattr(bridge.spool, "enqueue_observation", lambda obs, now: None)
    decision = type("D", (), {"fired": True, "percepts": [object()], "reason": "need",
                              "theta": 1.0, "arousal": 0.0, "trace": []})()
    bridge._on_decision(decision, [], NOW, NOW, None)
    bridge._pace_log.received(["a" * 32])
    bridge._pace_log.on_row({"event_kind": "act_event", "game": {"ticks": 41_500},
                             "e2": {"act_id": "a" * 32, "phase": "PUSHED", "tuning_name": "x_Y"}})
    assert bridge._pace_log.costs() == [{"interaction": "x_Y", "game_minutes": 1.0}]
