"""N8 (Domus after the first live play): the helper's fixes for the menu, the refs, the pictures and the words.
Fixtures are invented; tuning names are the game's own interaction names, and no game text appears here."""
from domus_helper.acts import OPENS_SCREEN, WITHHELD_SEED, options


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
