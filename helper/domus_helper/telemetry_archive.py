"""D38: keep the probe's telemetry folder under its cap by archiving finished sessions.

The probe stops recording when its telemetry folder reaches its cap (CAP_REACHED).
This moves older session files (the session JSONL and its rotations) into gzip files
under the helper's data folder, keeps each file's time, verifies each copy byte for
byte, and only then removes the original. It never touches the newest session, a
session written to within --min-age-hours, the lineage ledger, the command folders,
bootstrap files or the atlas folder.

With --weekly-after-days (the User's rule, 2026-10-05: 7), archived sessions older
than that are packed into one zip per ISO week of their last write
(`telemetry-archive/weekly/<year>-W<week>.zip`, the gzip files stored as they are) and
kept: nothing is deleted, so every session can be read again when the outcome records
are rebuilt. Each member is verified byte for byte before its loose copy is removed.

    python -m domus_helper.telemetry_archive [--min-age-hours 24] [--weekly-after-days 7] [--dry-run]
"""
import argparse
import datetime
import gzip
import hashlib
import os
import shutil
import time
import zipfile

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
    stat = path.stat()
    os.utime(target, (stat.st_atime, stat.st_mtime))  # its age is the session's
    path.unlink()
    return stat.st_size


def week_of(timestamp):
    year, week, _ = datetime.date.fromtimestamp(timestamp).isocalendar()
    return "%d-W%02d" % (year, week)


def weekly(*, paths, now, after_days, dry_run=False, out=print):
    """Pack archived sessions older than after_days into weekly zips; delete nothing."""
    archive_root = paths.data_dir / "telemetry-archive"
    packed = 0
    if not archive_root.is_dir():
        return packed
    for folder in sorted(archive_root.iterdir()):
        if not folder.is_dir() or not folder.name.startswith("ashley_e1_"):
            continue
        parts = sorted(path for path in folder.glob("*.gz") if path.is_file())
        if not parts:
            continue
        newest = max(path.stat().st_mtime for path in parts)
        if now - newest < after_days * 86400:
            continue
        bundle = archive_root / "weekly" / ("%s.zip" % week_of(newest))
        if dry_run:
            out("would pack %s into %s" % (folder.name, bundle.name))
            packed += len(parts)
            continue
        bundle.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle, "a", compression=zipfile.ZIP_STORED) as archive:
            present = set(archive.namelist())
            for path in parts:
                member = "%s/%s" % (folder.name, path.name)
                if member not in present:
                    archive.write(path, member)
        with zipfile.ZipFile(bundle) as archive:
            for path in parts:
                with path.open("rb") as source, \
                        archive.open("%s/%s" % (folder.name, path.name)) as copy:
                    if _digest(source) != _digest(copy):
                        raise RuntimeError("weekly verification failed for %s" % path.name)
        for path in parts:
            path.unlink()
            packed += 1
        if not any(folder.iterdir()):
            folder.rmdir()
    out("%s %d archived files into weekly zips" % ("plan: pack" if dry_run else "packed",
                                                   packed))
    return packed


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
    parser.add_argument("--weekly-after-days", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    paths, now = Paths.from_env(), time.time()
    run(paths=paths, now=now, min_age_hours=args.min_age_hours, dry_run=args.dry_run)
    if args.weekly_after_days is not None:
        weekly(paths=paths, now=now, after_days=args.weekly_after_days, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
