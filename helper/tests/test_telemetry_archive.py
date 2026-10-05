"""D38: finished sessions leave the probe's capped telemetry folder, verified."""
import gzip
import os

from domus_helper import telemetry_archive
from domus_helper.paths import Paths

OLD = "ashley_e1_00000000-0000-4000-8000-000000000001.jsonl"
NEW = "ashley_e1_00000000-0000-4000-8000-000000000002.jsonl"
NOW = 2_000_000_000.0


def _setup(tmp_path, monkeypatch):
    sims = tmp_path / "sims"
    folder = sims / "AshleyE1Telemetry"
    folder.mkdir(parents=True)
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "data"))
    files = {}
    for name, body, age_h in ((OLD, b'{"a":1}\n', 72), (OLD + ".1", b'{"a":2}\n', 70),
                              (NEW, b'{"b":1}\n', 1),
                              ("ashley_e2_lineage_ledger.jsonl", b"{}\n", 99),
                              ("ashley_e1_bootstrap_x.jsonl", b"{}\n", 99)):
        path = folder / name
        path.write_bytes(body)
        os.utime(path, (NOW - age_h * 3600, NOW - age_h * 3600))
        files[name] = path
    return Paths(sims), files


def test_archives_old_sessions_only_and_verifies(tmp_path, monkeypatch):
    paths, files = _setup(tmp_path, monkeypatch)
    lines = []
    count, freed = telemetry_archive.run(paths=paths, now=NOW, out=lines.append)
    assert count == 2 and freed == 16
    assert not files[OLD].exists() and not files[OLD + ".1"].exists()
    for name in (NEW, "ashley_e2_lineage_ledger.jsonl", "ashley_e1_bootstrap_x.jsonl"):
        assert files[name].exists(), name
    archived = tmp_path / "data" / "telemetry-archive" / OLD[:-len(".jsonl")]
    with gzip.open(archived / (OLD + ".gz")) as handle:
        assert handle.read() == b'{"a":1}\n'
    with gzip.open(archived / (OLD + ".1.gz")) as handle:
        assert handle.read() == b'{"a":2}\n'


def test_dry_run_and_recent_sessions_stay(tmp_path, monkeypatch):
    paths, files = _setup(tmp_path, monkeypatch)
    count, _ = telemetry_archive.run(paths=paths, now=NOW, dry_run=True, out=lambda line: None)
    assert count == 2 and files[OLD].exists()
    count, _ = telemetry_archive.run(paths=paths, now=NOW, min_age_hours=100,
                                     out=lambda line: None)
    assert count == 0 and files[OLD].exists()


def test_failed_verification_keeps_the_original(tmp_path, monkeypatch):
    paths, files = _setup(tmp_path, monkeypatch)
    real = telemetry_archive._digest
    calls = []

    def flaky(handle):
        calls.append(1)
        return real(handle) + ("x" if len(calls) == 2 else "")

    monkeypatch.setattr(telemetry_archive, "_digest", flaky)
    try:
        telemetry_archive.run(paths=paths, now=NOW, out=lambda line: None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("verification failure must stop the run")
    assert files[OLD].exists()
    assert not list((tmp_path / "data").rglob("*.partial"))


def _archived(tmp_path, monkeypatch, age_days, records):
    paths, files = _setup(tmp_path, monkeypatch)
    os.utime(files[OLD], (NOW - age_days * 86400, NOW - age_days * 86400))
    os.utime(files[OLD + ".1"], (NOW - age_days * 86400, NOW - age_days * 86400))
    telemetry_archive.run(paths=paths, now=NOW, out=lambda line: None)
    if records:
        outcomes = tmp_path / "data" / "outcomes"
        outcomes.mkdir(parents=True)
        (outcomes / (OLD[len("ashley_e1_"):-len(".jsonl")] + ".jsonl")).write_text("{}\n")
    return paths, tmp_path / "data" / "telemetry-archive" / OLD[:-len(".jsonl")]


def test_archives_keep_the_sessions_age(tmp_path, monkeypatch):
    _, folder = _archived(tmp_path, monkeypatch, 3, records=False)
    assert abs((folder / (OLD + ".gz")).stat().st_mtime - (NOW - 3 * 86400)) < 2


def test_week_old_archives_with_records_are_deleted(tmp_path, monkeypatch):
    """The User's rule (2026-10-05): raw telemetry goes after 7 days."""
    paths, folder = _archived(tmp_path, monkeypatch, 8, records=True)
    removed, _ = telemetry_archive.prune(paths=paths, now=NOW, keep_days=7,
                                         out=lambda line: None)
    assert removed == 2 and not folder.exists()


def test_younger_archives_stay(tmp_path, monkeypatch):
    paths, folder = _archived(tmp_path, monkeypatch, 6, records=True)
    removed, _ = telemetry_archive.prune(paths=paths, now=NOW, keep_days=7,
                                         out=lambda line: None)
    assert removed == 0 and (folder / (OLD + ".gz")).exists()


def test_no_records_no_delete(tmp_path, monkeypatch):
    """Her outcome records are built from these rows; they must exist first."""
    paths, folder = _archived(tmp_path, monkeypatch, 30, records=False)
    lines = []
    removed, _ = telemetry_archive.prune(paths=paths, now=NOW, keep_days=7, out=lines.append)
    assert removed == 0 and (folder / (OLD + ".gz")).exists()
    assert lines[0].startswith("keep ")


def test_dry_run_deletes_nothing(tmp_path, monkeypatch):
    paths, folder = _archived(tmp_path, monkeypatch, 8, records=True)
    removed, _ = telemetry_archive.prune(paths=paths, now=NOW, keep_days=7, dry_run=True,
                                         out=lambda line: None)
    assert removed == 2 and (folder / (OLD + ".gz")).exists()
