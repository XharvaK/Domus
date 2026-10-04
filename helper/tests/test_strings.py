"""S0: the game's string tables, read from a synthetic package (no EA text here)."""
import struct
import zlib

import pytest

from domus_helper import strings


def _stbl(entries):
    body = b"".join(struct.pack("<IBH", key, 0, len(text.encode())) + text.encode()
                    for key, text in entries)
    return (b"STBL" + struct.pack("<HBQ2sI", 5, 0, len(entries), b"\0\0",
                                  sum(len(t.encode()) + 1 for _, t in entries)) + body)


def _refpack_literal(raw):
    """A valid RefPack stream that only uses literal and stop opcodes."""
    out = bytearray([0x10, 0xFB]) + len(raw).to_bytes(3, "big")
    pos = 0
    while len(raw) - pos >= 4:
        chunk = min(112, (len(raw) - pos) // 4 * 4)
        out.append(0xE0 + (chunk - 4) // 4)
        out += raw[pos:pos + chunk]
        pos += chunk
    rest = len(raw) - pos
    out.append(0xFC + rest)
    out += raw[pos:]
    return bytes(out)


def _package(resources):
    """DBPF 2.1 with an index of (type, group, instance, data, compression)."""
    header_size = 96
    blobs = b""
    index = struct.pack("<I", 0)
    offset = header_size
    for kind, group, instance, raw, compression in resources:
        stored = raw if compression == 0 else (zlib.compress(raw) if compression == 0x5A42
                                                else _refpack_literal(raw))
        index += struct.pack("<IIIIIII", kind, group, instance >> 32, instance & 0xFFFFFFFF,
                             offset, len(stored) | 0x80000000, len(raw))
        index += struct.pack("<HH", compression, 1)
        blobs += stored
        offset += len(stored)
    header = bytearray(header_size)
    header[0:4] = b"DBPF"
    struct.pack_into("<II", header, 4, 2, 1)
    struct.pack_into("<I", header, 36, len(resources))
    struct.pack_into("<I", header, 44, len(index))
    struct.pack_into("<Q", header, 64, header_size + len(blobs))
    return bytes(header) + blobs + index


def test_reads_plain_zlib_and_refpack_tables(tmp_path):
    path = tmp_path / "Strings_ENG_US.package"
    path.write_bytes(_package([
        (strings.STBL_TYPE, 0, 1, _stbl([(0x10, "Plain words")]), 0),
        (strings.STBL_TYPE, 0, 2, _stbl([(0x20, "Zipped words")]), 0x5A42),
        (strings.STBL_TYPE, 0, 3, _stbl([(0x30, "Packed words, long enough to need chunks")]), 0xFFFF),
        (0x12345678, 0, 4, b"not a string table", 0),
    ]))
    found = strings.read_package(path)
    assert found == {0x10: "Plain words", 0x20: "Zipped words",
                     0x30: "Packed words, long enough to need chunks"}


def test_index_build_resolve_and_refresh(tmp_path, monkeypatch):
    game = tmp_path / "game"
    (game / "Data" / "Client").mkdir(parents=True)
    (game / "Delta" / "EP01").mkdir(parents=True)
    (game / "Data" / "Client" / "Strings_ENG_US.package").write_bytes(
        _package([(strings.STBL_TYPE, 0, 1, _stbl([(0xc4338c38, "Hungry")]), 0)]))
    (game / "Delta" / "EP01" / "Strings_ENG_US.package").write_bytes(
        _package([(strings.STBL_TYPE, 0, 2, _stbl([(0x0d644e79, "Nauseous")]), 0)]))
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "data"))
    from domus_helper.paths import Paths
    paths = Paths(tmp_path / "sims", game)
    assert strings.build(paths, locale="en_US") == (2, True)
    assert strings.build(paths, locale="en_US") == (2, False)
    resolve = strings.Resolver(paths, locale="en_US")
    assert resolve(str(0xc4338c38)) == "Hungry"
    assert resolve("0x0d644e79") == "Nauseous"
    assert resolve("12") is None and resolve(None) is None


def test_rejects_other_formats(tmp_path):
    path = tmp_path / "bad.package"
    path.write_bytes(b"DBPF" + struct.pack("<II", 3, 0) + b"\0" * 88)
    with pytest.raises(strings.StringsError):
        strings.read_package(path)
