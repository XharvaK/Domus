"""W13 fixes (helper, 2026-10-12): the probe's real shapes, checked against the helper. The probe is read here only as
its wire shape (digit-string ids, one-word placements, names of buy categories); every name is invented and the game
is a fake. The room id rule (cmdbox `_digits`) is copied, because the vendored cmdbox is still the 2.39.0 copy."""
import json

from domus_helper import catalog, catalog_ask, reach
from domus_helper.acts import RefBook
from test_w13_helper import CATALOG_NAMES, _catalog_db, _flag


def _probe_flag(definition, categories, placement, price, purchasable=True):
    """A catalogue item as the probe writes it (2.40.0): the id is a digit string, the placement is one word."""
    return {"definition_id": str(definition), "price": price, "buy_category": categories,
            "placement": placement, "tags": ["Test"], "purchasable": purchasable}


def test_a_probe_row_with_a_digit_string_id_is_stored_and_found_by_its_words(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(301, 1301)])
    assert catalog.store_flags(paths, "1.128", [_probe_flag(301, ["COMFORT"], ["floor"], 80)]) == 1
    assert catalog.has_flags(paths, "1.128")
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (
        1, [{"definition_id": 301, "name": "Test Chair", "price": 80, "placement": "floor", "category": "comfort"}])


def test_a_dump_with_no_usable_rows_keeps_the_flags_it_would_have_replaced(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(301, 1301)])
    catalog.store_flags(paths, "1.128", [_probe_flag(301, ["COMFORT"], ["floor"], 80)])
    assert catalog.store_flags(paths, "1.128", [{"definition_id": None}, "x", {"definition_id": "x1"}]) == 0
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get)[0] == 1


def test_an_item_the_probe_could_not_read_a_category_for_is_never_offered(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(309, 1301)])
    catalog.store_flags(paths, "1.128", [_probe_flag(309, [], None, 80)])
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (0, [])
    catalog.store_flags(paths, "1.128", [_probe_flag(309, None, ["floor"], 80)])
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (0, [])


def test_an_answer_names_one_placement_word_and_a_filter_matches_that_word(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(304, 1304)])
    catalog.store_flags(paths, "1.128", [_probe_flag(304, ["LIGHTING"], ["wall"], 30)])
    matched, items = catalog.search(paths, "1.128", "lamp", placement="wall", resolve=CATALOG_NAMES.get)
    assert matched == 1 and items[0]["placement"] == "wall" and items[0]["category"] == "lighting"
    assert catalog.search(paths, "1.128", "lamp", placement="floor", resolve=CATALOG_NAMES.get) == (0, [])


def test_a_probe_placement_list_keeps_one_word_and_a_category_list_keeps_its_names(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(304, 1304)])
    catalog.store_flags(paths, "1.128", [_probe_flag(304, ["LIGHTING", "DECOR"], ["wall", "floor"], 30)])
    assert catalog.search(paths, "1.128", "lamp", placement="floor", resolve=CATALOG_NAMES.get) == (0, [])
    matched, items = catalog.search(paths, "1.128", "lamp", placement="wall", resolve=CATALOG_NAMES.get)
    assert matched == 1 and items[0]["placement"] == "wall" and items[0]["category"] == "decor, lighting"
