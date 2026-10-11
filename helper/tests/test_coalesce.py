"""H1 (D2): the coalescer keeps pending percepts and says when one view goes. The caller supplies now_ms."""
from domus_helper import coalesce
from domus_helper.thalamus.types import Percept


def _need(name, value="1"):
    return Percept("need", name, "", "low", facts=(("value", value),))


def _asked(number=1):
    return Percept("env", "dialog", str(number), "asked", urgency="wake")


def test_nothing_pending_sends_nothing():
    state = coalesce.Pending()
    assert coalesce.due(state, 0) is None
    assert coalesce.due(state, 10 ** 9) is None
    percepts, after = coalesce.take(state)
    assert percepts == () and after == state


def test_a_quiet_second_and_a_half_sends_one_view():
    state = coalesce.add(coalesce.Pending(), [_need("hunger")], 0)
    assert coalesce.due(state, 1_499) is None
    assert coalesce.due(state, 1_500) == "quiet"
    percepts, after = coalesce.take(state)
    assert [p.key for p in percepts] == ["need:hunger::low"]
    assert coalesce.due(after, 2_000) is None


def test_each_new_change_restarts_the_quiet_wait():
    state = coalesce.add(coalesce.Pending(), [_need("hunger")], 0)
    state = coalesce.add(state, [_need("thirst")], 1_000)
    assert coalesce.due(state, 2_499) is None
    assert coalesce.due(state, 2_500) == "quiet"


def test_the_oldest_pending_change_goes_after_eight_seconds_even_when_changes_keep_coming():
    state = coalesce.Pending()
    for step in range(8):
        state = coalesce.add(state, [_need("need%d" % step)], step * 1_000)
    assert coalesce.due(state, 7_999) is None
    assert coalesce.due(state, 8_000) == "oldest"
    percepts, _ = coalesce.take(state)
    assert len(percepts) == 8


def test_a_question_opened_for_her_goes_at_once():
    state = coalesce.add(coalesce.Pending(), [_asked(3)], 500)
    assert coalesce.due(state, 500) == "question"
    percepts, _ = coalesce.take(state)
    assert [p.bucket for p in percepts] == ["asked"]


def test_a_question_goes_with_older_changes_still_waiting():
    state = coalesce.add(coalesce.Pending(), [_need("hunger")], 0)
    state = coalesce.add(state, [_asked()], 100)
    assert coalesce.due(state, 100) == "question"


def test_the_same_key_is_kept_once_with_its_newest_percept():
    state = coalesce.add(coalesce.Pending(), [_need("hunger", "1")], 0)
    state = coalesce.add(state, [_need("hunger", "2")], 500)
    assert coalesce.due(state, 1_499) is None  # the newest arrival restarts the quiet wait
    percepts, _ = coalesce.take(state)
    assert len(percepts) == 1
    assert dict(percepts[0].facts)["value"] == "2"


def test_only_the_newest_32_pending_percepts_are_kept():
    state = coalesce.add(coalesce.Pending(), [_need("n%02d" % i) for i in range(40)], 0)
    percepts, _ = coalesce.take(state)
    assert [p.subject for p in percepts] == ["n%02d" % i for i in range(8, 40)]


def test_pending_percepts_survive_as_plain_data():
    state = coalesce.add(coalesce.Pending(), [_need("hunger", "7"), _asked(4)], 250)
    again = coalesce.from_list(coalesce.to_list(state))
    assert again == state
    assert coalesce.due(again, 250) == "question"
