"""A9-7: a portrait cut to fit names the parts it left out, so Thought never reads a partial scene as a whole one."""
from domus_helper.thalamus import observation


def _busy_row():
    return {"sim_signals": [
        {"kind": "MOODLET", "tuning_id": str(index), "tuning_name": "m" * 1500, "visible": True, "magnitude": "w:1"}
        for index in range(200)]}


def test_a_portrait_that_fits_whole_carries_no_marker():
    portrait = observation._portrait({"motives": []}, None)
    assert "shed" not in portrait


def test_a_portrait_cut_to_fit_names_the_parts_it_shed_and_how_many(monkeypatch):
    monkeypatch.setattr(observation, "_PORTRAIT_LIMIT", 10 ** 9)
    whole = observation._portrait(_busy_row(), None)
    monkeypatch.setattr(observation, "_PORTRAIT_LIMIT", 8192)
    portrait = observation._portrait(_busy_row(), None)
    assert observation._bytes(portrait) <= observation._PORTRAIT_LIMIT
    assert portrait["shed"] == [{"part": "moodlets", "dropped": len(whole["moodlets"]) - len(portrait["moodlets"])}]
    assert portrait["shed"][0]["dropped"] > 0


def test_the_marker_counts_the_notebook_it_drops_and_stays_within_the_limit():
    note = {"procedures": [{"interaction": "invented_snack", "n": 3, "needs": {"hunger": 25}}]}
    with_note = observation._portrait(_busy_row(), None, notebook=note)
    assert "notebook" not in with_note
    assert {"part": "notebook", "dropped": 1} in with_note["shed"]
    assert observation._bytes(with_note) <= observation._PORTRAIT_LIMIT
