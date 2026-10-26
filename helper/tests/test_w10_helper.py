"""2.37.0 (W10 H1 to H3): the helper says why a view was refused (H1), never goes blind on her options (H2), and
puts game text with tokens into words for her (H3). Every string here is invented."""
import pytest

from domus_helper import tokens
from domus_helper.contract import ContractError, options_why, refusal_text, validate_observation
from test_bridge import NOW, sample
from test_bridge_thalamus import BUILD, WALL, _append, _bridge, _data, _lineage, _log_lines, _payloads, _snap

MENU = {"menu_rev": 1, "room": "4", "tested": 1, "refused": 0, "build_ms": 1.0, "objects": [
    {"object_id": "11", "definition_id": None, "class": "object_bookshelf", "distance_m": 2.0, "same_room": True,
     "acts": [{"guid64": "4242", "name": "bookshelf_ReadBook", "text_key": None}]}]}


MENU_ROWS = [
    {"event_kind": "lineage_event", "written_sequence": 1, "wall_timestamp_ms": WALL,
     "monotonic_ns": WALL * 1_000_000, "telemetry_session_id": "sess-1", "sims_build": BUILD, "probe_version": "2.37.0",
     "e2": {"slot_id": 3, "guid": "abc", "lineage_class": "HOUSEHOLD"}},
    {"event_kind": "act_menu", "written_sequence": 2, "wall_timestamp_ms": WALL, "monotonic_ns": WALL * 1_000_000,
     "telemetry_session_id": "sess-1", "sims_build": BUILD, "probe_version": "2.37.0", "e2": MENU},
    _snap(3, "ok", WALL, 10),
]


def _refuse_when(bridge, should_refuse, error_factory):
    """Puts the real spool's enqueue behind a refusal: a view that should_refuse(obs) is refused with the error."""
    real = bridge.spool.enqueue_observation

    def guarded(obs, now_ms):
        if should_refuse(obs):
            raise error_factory()
        return real(obs, now_ms)
    bridge.spool.enqueue_observation = guarded


def _send_one(paths, tmp_path, monkeypatch, bridge_setup):
    data = _data(paths, tmp_path, monkeypatch)
    _append(paths, bridge_setup)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    return data, bridge, mono


def _second_tick(bridge, mono):
    bridge.tick(WALL)
    mono["ms"] = WALL + 1500
    bridge.tick(WALL + 1500)


# H1: the reason a view is refused
def test_a_refused_body_names_the_key_it_failed_on():
    body = sample(world="")
    with pytest.raises(ContractError) as caught:
        validate_observation(body, NOW)
    assert caught.value.code == "invalid_body"
    assert caught.value.where == "world"


def test_a_refusal_text_carries_the_code_and_the_key_when_there_is_one():
    assert refusal_text(ContractError("invalid_body", "world")) == "ContractError: invalid_body (world)"
    assert refusal_text(ContractError("expired")) == "ContractError: expired"


def test_the_options_and_the_cut_name_themselves_when_they_are_refused():
    with pytest.raises(ContractError) as caught:
        validate_observation(sample(options=[{}] * 161), NOW)
    assert caught.value.where == "options"
    with pytest.raises(ContractError) as caught:
        validate_observation(sample(options_cut={"objects": 0, "rooms": []}), NOW)
    assert caught.value.where == "options_cut"


def test_the_decision_log_says_why_a_view_was_refused(paths, tmp_path, monkeypatch):
    data, bridge, mono = _send_one(paths, tmp_path, monkeypatch, MENU_ROWS)
    _refuse_when(bridge, lambda obs: True, lambda: ContractError("invalid_body", "world"))
    _second_tick(bridge, mono)
    line = _log_lines(data)[-1]
    assert line["enqueued"] is False
    assert line["error"] == "ContractError: invalid_body (world)"


# H2: never blind on her options
def test_a_view_refused_for_its_options_is_sent_again_without_them_and_says_why(paths, tmp_path, monkeypatch):
    data, bridge, mono = _send_one(paths, tmp_path, monkeypatch, MENU_ROWS)
    _refuse_when(bridge, lambda obs: "options" in obs, lambda: ContractError("invalid_body", "options"))
    _second_tick(bridge, mono)
    payloads = _payloads(bridge)
    assert len(payloads) == 1
    assert "options" not in payloads[0]
    dropped = [item for item in payloads[0]["percepts"] if item["kind"] == "options_dropped"]
    assert len(dropped) == 1 and dropped[0]["facts"]["why"] == "malformed"
    line = _log_lines(data)[-1]
    assert line["enqueued"] is True and "error" not in line


def test_a_view_refused_for_its_options_and_its_cut_is_sent_without_both(paths, tmp_path, monkeypatch):
    data, bridge, mono = _send_one(paths, tmp_path, monkeypatch, MENU_ROWS)
    _refuse_when(bridge, lambda obs: "options" in obs or "options_cut" in obs,
                 lambda: ContractError("invalid_body", "options_cut"))
    _second_tick(bridge, mono)
    payloads = _payloads(bridge)
    assert len(payloads) == 1 and "options_cut" not in payloads[0] and "options" not in payloads[0]


def test_a_refusal_of_anything_else_is_not_retried_and_is_logged(paths, tmp_path, monkeypatch):
    data, bridge, mono = _send_one(paths, tmp_path, monkeypatch, MENU_ROWS)
    calls = []
    _refuse_when(bridge, lambda obs: calls.append(1) or True, lambda: ContractError("clock_skew"))
    _second_tick(bridge, mono)
    # R3-H (SEAM3-7): the menu's arrival sends its own choices view at once (one attempt), and the quiet view after it is
    # the only other attempt; a refused view is never retried on a timer.
    assert len(calls) == 2
    assert _log_lines(data)[-1]["error"] == "ContractError: clock_skew"


def test_options_why_is_too_large_past_the_limits_and_malformed_otherwise():
    assert options_why([{}] * 161, "options") == "too_large"
    assert options_why([{"text": "x" * 40000}], "options") == "too_large"
    assert options_why([{}], "options") == "malformed"
    assert options_why({"objects": 0}, "options_cut") == "malformed"


# H3: game text with tokens, in words for her
HER = tokens.names_of("Ada Lark")


def test_her_names_fill_the_name_tokens_when_the_text_is_about_her():
    text = "{0.SimFirstName} is a chef; {0.SimLastName} runs the shop; {0.SimName} and {0.SimFullName}."
    assert tokens.fill(text, subject=HER) == "Ada is a chef; Lark runs the shop; Ada Lark and Ada Lark."


def test_a_name_token_with_no_one_named_is_someone():
    assert tokens.fill("Hi {1.SimFirstName}, {1.SimFullName}!", subject=None) == "Hi someone, someone!"
    assert tokens.names_of("someone") is None
    assert tokens.names_of(None) is None


def test_the_gender_pair_takes_the_first_form_unless_the_gender_is_known():
    assert tokens.fill("{M0.he}{F0.she} ran.") == "he ran."
    assert tokens.fill("{M0.he}{F0.she} ran.", gender="F") == "she ran."
    assert tokens.fill("{M0.he}{F0.she} ran.", gender="M") == "he ran."


def test_the_number_token_is_the_number_when_known_and_some_when_not():
    assert tokens.fill("Level {1.Number} of {0.SimFirstName}", subject=HER, number=3) == "Level 3 of Ada"
    assert tokens.fill("Level {1.Number}") == "Level some"


def test_any_other_token_is_dropped_and_nothing_raises():
    assert tokens.fill("A {0.Age} {x} b") == "A b"
    assert tokens.fill("{unclosed") == "{unclosed"
    assert tokens.fill(None) is None
    assert tokens.fill(12) is None


def test_the_words_resolver_fills_her_name_and_can_name_no_one():
    raw = {77: "{0.SimFirstName} is a chef.", 78: "Hi {1.SimFirstName}."}
    words = tokens.Words(lambda key: raw.get(key))
    assert words(77) == "someone is a chef."  # no one of hers named yet
    words.her = HER
    assert words(77) == "Ada is a chef."
    assert words.other(78) == "Hi someone."
    assert words(79) is None


def test_the_bridge_names_her_from_the_body_row_for_her_words(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    bridge._resolve_text._raw = lambda key: "{0.SimFirstName} is a chef." if key == 77 else None
    bridge._set_her({"presence": [{"id": "ASH", "is_body": True, "name": "Ada Lark"},
                                  {"id": "BOB", "is_body": False, "name": "Bob Stone"}]})
    assert bridge._resolve_text(77) == "Ada is a chef."
    bridge._set_her({"presence": []})
    assert bridge._resolve_text(77) == "someone is a chef."


def test_the_vendored_schema_is_2_37_1_and_accepts_menus_of_schema_18_and_19():
    from domus_helper.vendor import schema
    assert (schema.PROBE_VERSION, schema.OBSERVATION_SCHEMA_VERSION) == ("2.41.4", 21)
    assert {18, 19} <= set(schema.ACCEPTED_SCHEMA_VERSIONS)
    menu = {"menu_rev": 1, "room": "4", "tested": 1, "cached": 2, "refused": 0, "build_ms": 1.0, "part": 0,
            "parts": 1, "refused_phone": None, "excluded_phone": [{"name": "phone_thing", "why": "travel"}],
            "objects": []}
    schema.validate_record(schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                              monotonic_ns=1, e2=menu))
    older = dict(menu)
    del older["cached"], older["excluded_phone"]
    row = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=older)
    schema.validate_record(row)
    assert row["e2"]["cached"] is None and row["e2"]["excluded_phone"] is None


def test_another_sims_name_token_is_someone_even_when_her_names_are_known():
    assert tokens.fill("{0.SimFirstName} waves at {1.SimFirstName}.", subject=HER) == "Ada waves at someone."


def test_an_act_text_keeps_its_tokens_so_the_target_is_named():
    from domus_helper.acts import clean_text
    words = tokens.Words(lambda key: "Chat with {1.SimFirstName}" if key == 5 else None)
    words.her = HER
    assert words.raw(5) == "Chat with {1.SimFirstName}"
    assert clean_text(words.raw(5), "Bo Reed") == "Chat with Bo"
    assert words.raw(6) is None
