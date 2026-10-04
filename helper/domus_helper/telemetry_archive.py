"""D38: keep the probe's telemetry folder under its cap by archiving finished sessions.

The probe stops recording when its telemetry folder reaches 200 MiB (CAP_REACHED);
on 2026-10-04 it already held 126 MB. This moves older session files (the session
JSONL and its rotations) into gzip files under the helper's data folder, verifies
each copy byte for byte, and only then removes the original. It never touches the
newest session, a session written to within --min-age-hours, the lineage ledger,
the command folders, bootstrap files or the atlas folder.

    python -m domus_helper.telemetry_archive [--min-age-hours 24] [--dry-run]
"""
import argparse
import gzip
import hashlib
import shutil
import time

from .paths import Paths
from .telemetry import SESSION_NAME, latest_session, segments


def _digest(handle):
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(1 << 20), b""):
        digest.update(block)
    return digest.hexdigest()


def plan(*, paths, now, min_age_hours=24.0):
    """[(session path, [segment paths])] that may be archived, oldest first."""
    try:
        newest = latest_session(paths=paths)
    except FileNotFoundError:
        newest = None
    found = []
    for session in sorted(paths.telemetry.glob("ashley_e1_*.jsonl")):
        if SESSION_NAME.fullmatch(session.name) is None:
            continue
        if newest is not None and session.name == newest.name:
            continue
        parts = [path for path in segments(session) if path.is_file()]
        if not parts:
            continue
        last_write = max(path.stat().st_mtime for path in parts)
        if now - last_write < min_age_hours * 3600:
            continue
        found.append((last_write, session, parts))
    found.sort(key=lambda item: item[0])
    return [(session, parts) for _, session, parts in found]


def archive_segment(path, target):
    """Gzip path to target, verify the round trip, then remove path. Returns bytes freed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    with path.open("rb") as source:
        expected = _digest(source)
        source.seek(0)
        with gzip.open(partial, "wb", compresslevel=6) as sink:
            shutil.copyfileobj(source, sink)
    with gzip.open(partial, "rb") as check:
        actual = _digest(check)
    if actual != expected:
        # Closed first: Windows refuses to remove a file that is still open.
        partial.unlink()
        raise RuntimeError("archive verification failed for %s" % path.name)
    partial.replace(target)
    size = path.stat().st_size
    path.unlink()
    return size


def run(*, paths, now, min_age_hours=24.0, dry_run=False, out=print):
    archive_root = paths.data_dir / "telemetry-archive"
    freed = 0
    files = 0
    for session, parts in plan(paths=paths, now=now, min_age_hours=min_age_hours):
        for path in parts:
            target = archive_root / session.stem / (path.name + ".gz")
            if dry_run:
                out("would archive %s (%d bytes)" % (path.name, path.stat().st_size))
                freed += path.stat().st_size
            else:
                freed += archive_segment(path, target)
            files += 1
    out("%s %d files, %.1f MB freed" % ("plan:" if dry_run else "archived", files, freed / 1e6))
    return files, freed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    run(paths=Paths.from_env(), now=time.time(), min_age_hours=args.min_age_hours,
        dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
