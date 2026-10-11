"""N8 (Domus after the first live play): the helper's fixes for the menu, the refs, the pictures and the words.
Fixtures are invented; tuning names are the game's own interaction names, and no game text appears here."""
from domus_helper.acts import OPENS_SCREEN, WITHHELD_SEED, RefBook, dialog_options, options, queue_options


def phone_menu(*names):
    acts = [{"guid64": str(5000 + index), "name": name, "text_key": None} for index, name in enumerate(names)]
    return {"room": "1", "objects": [{"object_id": "21", "class": "object_phone", "distance_m": 0.5,
                                      "same_room": True, "acts": acts}]}


def test_the_seed_names_open_a_screen_before_the_notebook_has_seen_them():
    acts = options(phone_menu("phone_PlanEvent", "phone_CallOver_EventNPC"))[0]["acts"]
    assert acts[0]["opens"] == OPENS_SCREEN
    assert "opens" not in acts[1]
    assert [act["guid64"] for act in acts] == ["5000", "5001"]


def test_the_seed_covers_the_planner_create_a_sim_change_sim_and_outfit_screens():
    for name in ("phone_PlanEvent", "terrain-createsim_female-adult", "terrain-createsim_male-teen",
                 "dresser_ChangeSim", "PlanOutfit", "tent_PlanOutfit", "dresser_TryOnOutfits_Start",
                 "Dresser_TryOnOutfit_00"):
        assert name in WITHHELD_SEED
        assert options(phone_menu(name))[0]["acts"][0]["opens"] == OPENS_SCREEN


# F3: stable refs for one helper session.
def thing(object_id, *acts, distance=1.0):
    """An object in the probe's menu: acts are (guid64, tuning name) pairs."""
    return {"object_id": object_id, "class": "object_thing", "distance_m": distance, "same_room": True,
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts]}


def refs_of(result):
    return {(item["object_id"], act["guid64"]): act["ref"] for item in result for act in item["acts"]}


def test_a_ref_keeps_its_meaning_as_objects_reorder_appear_vanish_and_come_back():
    book = RefBook()

    def view(*objects):
        return refs_of(options({"room": "1", "objects": list(objects)}, refs=book))

    a = thing("21", ("4001", "Read"), ("4002", "Sit"))
    b = thing("22", ("4003", "Wave"))
    first = view(a, b)
    assert first == {("21", "4001"): "a1", ("21", "4002"): "a2", ("22", "4003"): "a3"}
    assert view(b, a) == first
    third = view(b, a, thing("23", ("4004", "Poke")))
    assert third[("23", "4004")] == "a4" and all(third[key] == first[key] for key in first)
    fourth = view(b, thing("23", ("4004", "Poke")))
    assert ("21", "4001") not in fourth and fourth[("23", "4004")] == "a4"
    fifth = view(thing("24", ("4005", "Hum")), a, b)
    assert fifth[("21", "4001")] == "a1" and fifth[("21", "4002")] == "a2"
    assert fifth[("24", "4005")] == "a5"  # a new number: a1 is never given to something else


def test_a_queue_item_and_a_question_row_keep_their_refs_when_the_views_change():
    book = RefBook()
    queue_row = {"interactions": {"observed": [{"interaction_id": "901", "membership": "RUNNING",
                                                "affordance_text": "<class 'sims.Stir'>"}]}}
    question = {"telemetry_session_id": "s", "dialogs": {"open": [{
        "dialog_id": "51", "held": True, "cause": "hers", "title_key": None, "text_key": None,
        "rows": [{"option_id": "7", "name_key": None, "enabled": True, "price": None}],
        "responses": [{"response": "cancel", "text_key": None}]}]}}
    first = dialog_options(question, refs=book) + queue_options(queue_row, refs=book)
    assert [act["ref"] for entry in first for act in entry["acts"]] == ["a1", "a2", "a3"]
    again = dialog_options(question, refs=book) + queue_options(queue_row, refs=book)
    assert [act["ref"] for entry in again for act in entry["acts"]] == ["a1", "a2", "a3"]
    assert queue_options({}, refs=book) == []
    back = queue_options(queue_row, refs=book)
    assert back[0]["acts"][0]["ref"] == "a3"
