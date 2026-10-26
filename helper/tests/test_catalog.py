"""Catalogue names: a synthetic package (no game text in the repo), Delta wins, unknown
layouts are skipped, and the scene names furniture from it."""
import struct
import zlib

from domus_helper import catalog, scene
from domus_helper.paths import Paths

COBJ = catalog.COBJ_TYPE


def _cobj(common, name_key, description_key, price):
    return struct.pack("<5I", 26, common, name_key, description_key, price) + b"\0" * 12


def _package(resources):
    """A DBPF 2.1 package with a per-entry (no constants) index; zlib-compress odd entries."""
    body = bytearray(b"\0" * 96)
    index = bytearray(struct.pack("<I", 0))
    for number, (kind, instance, raw) in enumerate(resources):
        stored = zlib.compress(raw) if number % 2 else raw
        start = len(body)
        body += stored
        index += struct.pack("<III", kind, 0, instance >> 32)
        index += struct.pack("<IIII", instance & 0xFFFFFFFF, start, len(stored) | 0x80000000, len(raw))
        index += struct.pack("<HH", 0x5A42 if number % 2 else 0, 1)
    position = len(body)
    body += index
    header = bytearray(96)
    header[:4] = b"DBPF"
    struct.pack_into("<II", header, 4, 2, 1)
    struct.pack_into("<I", header, 36, len(resources))
    struct.pack_into("<I", header, 44, len(index))
    struct.pack_into("<Q", header, 64, position)
    body[:96] = header
    return bytes(body)


def _paths(tmp_path):
    game = tmp_path / "game"
    (game / "Data" / "Client").mkdir(parents=True)
    (game / "Delta" / "EP01").mkdir(parents=True)
    sims = tmp_path / "sims"
    sims.mkdir()
    return Paths(sims, game), game


def test_build_reads_names_and_delta_wins(tmp_path, monkeypatch):
    paths, game = _paths(tmp_path)
    monkeypatch.setattr(Paths, "data_dir", property(lambda self: tmp_path / "data"))
    (game / "Data" / "Client" / "ClientFullBuild0.package").write_bytes(_package([
        (COBJ, 9929, _cobj(9, 111, 222, 130)),
        (COBJ, 7309, _cobj(9, 333, 444, 400)),
        (COBJ, 5, _cobj(77, 1, 2, 3)),            # unknown layout: skipped
        (0x220557DA, 9929, b"STBL"),              # another type: ignored
    ]))
    (game / "Delta" / "EP01" / "ClientDeltaBuild0.package").write_bytes(_package([
        (COBJ, 7309, _cobj(11, 555, 666, 410)),
    ]))
    (game / "Data" / "Client" / "ClientDeltaBuild9.package").write_bytes(_package([]))
    count, rebuilt = catalog.build(paths)
    assert (count, rebuilt) == (2, True)
    lookup = catalog.Catalog(paths)
    assert lookup(9929) == {"name_key": "111", "description_key": "222", "price": 130}
    assert lookup("7309")["name_key"] == "555" and lookup(7309)["price"] == 410
    assert lookup(5) is None and lookup("not a number") is None
    assert catalog.build(paths) == (2, False)


def test_scene_names_furniture_from_the_catalogue():
    body = {"room": "3", "position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}}
    sink = {"kind": "object", "object_id": "1", "definition_id": "9929",
            "class": "object_sinkCounterFC_01", "room": "3",
            "position": {"x": 1.0, "y": 0.0, "z": 0.0, "level": 0},
            "states": {"Dirty": "Dirty_Clean"}, "stats": {}, "craft": None}
    lamp = dict(sink, object_id="2", definition_id="1", class_="x")
    lamp["class"] = "object_light_ceiling"
    texts = {"111": "Plain Basin Sink"}
    table = {"9929": {"name_key": "111", "description_key": "222", "price": 130}}
    result = scene.layers({"body": body}, [sink, lamp], resolve=texts.get,
                          catalog=lambda definition_id: table.get(str(definition_id)))
    first, second = result["near"]
    assert (first["name"], first["name_source"], first["kind"]) == (
        "Plain Basin Sink", "CATALOG", "sinkCounterFC")
    assert first["catalog_price"] == 130
    assert (second["name"], second["name_source"]) == ("object_light_ceiling", "TUNING_NAME")
