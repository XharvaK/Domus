"""Red-first DS2: detected build and fingerprint contracts (fakes only)."""
import hashlib
import json
from pathlib import Path

import pytest

from domus_helper import fingerprints as fp
from domus_helper.paths import Paths


def make_tree(tmp_path):
    game = tmp_path / "game"
    (game / "Game" / "Bin").mkdir(parents=True)
    (game / "Data" / "Simulation" / "Gameplay").mkdir(parents=True)
    (game / "Delta" / "EP01").mkdir(parents=True)
    (game / "Delta" / "SP01").mkdir(parents=True)
    sims = tmp_path / "sims"
    (sims / "Mods" / "AshleyE1").mkdir(parents=True)
    return game, sims


def write_game(game, sims, monkeypatch, exe_version="9.9.9.9", with_exe=True,
               with_txt=True, with_ini=True):
    if with_exe:
        (game / "Game" / "Bin" / "TS4_x64.exe").write_bytes(b"exe-bytes")
        monkeypatch.setattr(fp, "_exe_version", lambda p: exe_version)
    if with_txt:
        (sims / "GameVersion.txt").write_text(exe_version + "\n")
    if with_ini:
        (game / "Game" / "Bin" / "Default.ini").write_text(
            "[Version]\ngameversion = %s\ncodeversion = 1.2.3.4\n"
            "codechangelist = 99\ncodedatetime = 2026_01_01-00_00_00\n" % exe_version)
    for name in ("base", "core", "simulation"):
        (game / "Data" / "Simulation" / "Gameplay" / (name + ".zip")).write_bytes(
            b"archive-" + name.encode())
    for pack in ("EP01", "SP01"):
        (game / "Delta" / pack / "Version.ini").write_text(
            "[Version]\npackversion = %s\n" % exe_version)
    return exe_version


def test_detected_build_priority_and_missing_sources(tmp_path, monkeypatch):
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch, exe_version="1.0.0.0")
    paths = Paths(sims)
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setattr(fp, "_process", lambda: (1234, "2026-01-01T00:00:00"))
    detected = fp.detected_build(paths=paths)
    assert detected["detected_build"] == "1.0.0.0"
    assert detected["sources"]["exe"] == "1.0.0.0"
    assert detected["pid"] == 1234

    (game / "Game" / "Bin" / "TS4_x64.exe").unlink()
    (sims / "GameVersion.txt").write_text("2.0.0.0\n")
    (game / "Game" / "Bin" / "Default.ini").write_text(
        "[Version]\ngameversion = 3.0.0.0\n")
    detected = fp.detected_build(paths=paths)
    assert detected["detected_build"] == "2.0.0.0"
    assert detected["sources"]["exe"] is None

    (sims / "GameVersion.txt").unlink()
    detected = fp.detected_build(paths=paths)
    assert detected["detected_build"] == "3.0.0.0"

    (game / "Game" / "Bin" / "Default.ini").unlink()
    with pytest.raises(FileNotFoundError, match="no build source"):
        fp.detected_build(paths=paths)


def test_process_waits_on_a_handle_and_reads_the_start_time(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from subprocess import CompletedProcess

    fp._release()
    calls = []
    low, high = 1_000_000_000, 1
    filetime_int = (high << 32) | low
    expected = (datetime(1601, 1, 1, tzinfo=timezone.utc)
                + timedelta(microseconds=filetime_int // 10)).isoformat(timespec="seconds")

    def run(args, **kwargs):
        calls.append(list(args))
        assert "/V" not in args
        text = '"TS4_x64.exe","4242"\n' if len(calls) == 1 else "INFO: No tasks\n"
        return CompletedProcess(args, 0, text)

    kernel = type("K", (), {})()
    kernel.wait = 258
    kernel.fail_open = False
    kernel.opens = 0
    kernel.closes = 0

    def OpenProcess(access, inherit, pid):
        kernel.opens += 1
        assert access == 0x00100000 | 0x1000
        return 0 if kernel.fail_open else 7

    def WaitForSingleObject(handle, timeout):
        assert timeout == 0 and handle == 7
        return kernel.wait

    def CloseHandle(handle):
        kernel.closes += 1
        return 1

    def GetProcessTimes(handle, creation, exit_time, kernel_time, user_time):
        creation._obj.dwLowDateTime = low
        creation._obj.dwHighDateTime = high
        return 1

    kernel.OpenProcess = OpenProcess
    kernel.WaitForSingleObject = WaitForSingleObject
    kernel.CloseHandle = CloseHandle
    kernel.GetProcessTimes = GetProcessTimes
    monkeypatch.setattr(fp.subprocess, "run", run)
    monkeypatch.setattr(fp, "_kernel32", lambda: kernel)
    try:
        assert fp._process() == (4242, expected)
        assert kernel.opens == 1 and fp._HELD is not None
        assert fp._process() == (4242, expected)
        assert len(calls) == 1
        kernel.wait = 0
        assert fp._process() is None
        assert kernel.closes == 1 and len(calls) == 2 and fp._HELD is None
        calls.clear()
        kernel.fail_open = True
        monkeypatch.setattr(fp.subprocess, "run", lambda args, **kwargs: CompletedProcess(
            args, 0, '"TS4_x64.exe","99"\n'))
        assert fp._process() == (99, None)
        assert fp._HELD is None
        seen = []
        monkeypatch.setattr(fp.subprocess, "run", lambda args, **kwargs: seen.append(list(args)) or CompletedProcess(
            args, 0, "INFO: No tasks\n"))
        assert fp._process() is None
        assert seen and all("/V" not in args for args in seen)
    finally:
        fp._release()


def test_process_absent_and_pid_change(tmp_path, monkeypatch):
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch)
    paths = Paths(sims)
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setattr(fp, "_process", lambda: None)
    detected = fp.detected_build(paths=paths)
    assert detected["pid"] is None
    assert fp.restarted({"pid": 1}, {"pid": 2}) is True
    assert fp.restarted({"pid": 1}, {"pid": 1}) is False
    assert fp.restarted({"pid": None}, {"pid": 1}) is True


def test_fingerprint_shapes(tmp_path, monkeypatch):
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch, exe_version="1.128.90.1030")
    (sims / "Mods" / "AshleyE1" / "ashley_e1_2.3.0.ts4script").write_bytes(b"probe")
    paths = Paths(sims)
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setattr(fp, "_process", lambda: (7, "t"))
    print = fp.fingerprint(paths=paths)
    assert print["detected_build"] == "1.128.90.1030"
    assert {a["name"] for a in print["archives"]} == {"base.zip", "core.zip", "simulation.zip"}
    for archive in print["archives"]:
        assert archive["sha256"] == hashlib.sha256(
            b"archive-" + archive["name"][:-4].encode()).hexdigest()
    assert [p["name"] for p in print["packs"]] == ["EP01", "SP01"]
    assert all(p["packversion"] == "1.128.90.1030" for p in print["packs"])
    mods = {m["path"]: m for m in print["mods"]}
    assert mods["AshleyE1/ashley_e1_2.3.0.ts4script"]["sha256"] == hashlib.sha256(b"probe").hexdigest()
    assert print["code"]["codeversion"] == "1.2.3.4"


def test_mismatch_blocks_actuation_not_reads(tmp_path, monkeypatch):
    from domus_helper import mcp_server as mcp
    from conftest import replier
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch, exe_version="9.9.9.9")
    paths = Paths(sims)
    for directory in (paths.inbox, paths.outbox, paths.done):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(sims))
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    monkeypatch.setattr(fp, "_process", lambda: (7, "t"))
    declared = dict(state="ARMED", armed_name="LAB_E1", probe_version="2.3.0",
                    sims_build="1.128.90.1030", inbox_errors=0, inbox_autostart="ZONE:tuning")
    with replier(paths, lambda row: dict(status="OK", code=None, result=dict(declared))):
        client = mcp.DomusTools(paths=paths)
        assert client.command("status").result["sims_build"] == "1.128.90.1030"
        with pytest.raises(mcp.SafetyError, match="build mismatch"):
            client.command("arm", {"name": "lab_e1"})
        with pytest.raises(mcp.SafetyError, match="build mismatch"):
            client.command("start")
        assert client.detected_build_fn()["detected_build"] == "9.9.9.9"
        assert client.fingerprints_fn()["detected_build"] == "9.9.9.9"


def test_match_allows_actuation(tmp_path, monkeypatch):
    from domus_helper import mcp_server as mcp
    from conftest import replier
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch, exe_version="1.128.90.1030")
    paths = Paths(sims)
    for directory in (paths.inbox, paths.outbox, paths.done):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(sims))
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    monkeypatch.setattr(fp, "_process", lambda: (7, "t"))
    declared = dict(state="ARMED", armed_name="LAB_E1", probe_version="2.3.0",
                    sims_build="1.128.90.1030", inbox_errors=0, inbox_autostart="ZONE:tuning")
    with replier(paths, lambda row: dict(status="OK", code=None,
                                         result=dict(declared, **(
                                             {"armed_name": "LAB_E1"} if row["command"] == "arm" else {})))):
        client = mcp.DomusTools(paths=paths)
        assert client.command("arm", {"name": "lab_e1"}).status == "OK"

