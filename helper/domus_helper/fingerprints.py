"""Detected build and fingerprint reads (helper-side, DS2).

Local reads only: game install files, user-data files, tasklist. No network.
"""
import csv
import hashlib
import io
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .paths import Paths

ARCHIVE_NAMES = ("base.zip", "core.zip", "simulation.zip")
GAMEPLAY_REL = Path("Data/Simulation/Gameplay")
BIN_REL = Path("Game/Bin")
EXE_REL = BIN_REL / "TS4_x64.exe"
DEFAULT_INI_REL = BIN_REL / "Default.ini"
GAME_VERSION_TXT = "GameVersion.txt"
DELTA_REL = Path("Delta")
VERSION_INI = "Version.ini"

DEFAULT_GAME_ROOT = r"E:\SteamLibrary\steamapps\common\The Sims 4"


def game_root(paths=None):
    override = os.environ.get("DOMUS_GAME_ROOT")
    if override:
        return Path(override)
    if paths is not None and getattr(paths, "game_root", None) is not None:
        return Path(paths.game_root)
    return Path(DEFAULT_GAME_ROOT)


def _read_text(path):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-8"):
        try:
            return raw.decode(encoding)
        except (ValueError, UnicodeError):
            continue
    return None


def _ini_value(text, key):
    if not text:
        return None
    match = re.search(r"(?im)^\s*%s\s*=\s*(\S+)" % re.escape(key), text)
    return match.group(1) if match else None


def _exe_version(exe_path):
    try:
        import ctypes
    except ImportError:
        return None
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(exe_path), None)
    except (OSError, AttributeError):
        return None
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    try:
        if not ctypes.windll.version.GetFileVersionInfoW(str(exe_path), 0, size, buffer):
            return None
        for lang in ("040904B0", "040904E4", "000004B0"):
            length = ctypes.c_uint()
            value = ctypes.c_void_p()
            if ctypes.windll.version.VerQueryValueW(
                    buffer, "\\StringFileInfo\\%s\\FileVersion" % lang,
                    ctypes.byref(value), ctypes.byref(length)):
                text = ctypes.wstring_at(value.value)
                if text and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", text.strip()):
                    return text.strip()
        return None
    except (OSError, AttributeError):
        return None


_HELD = None  # (pid, handle, started)


def _kernel32():
    import ctypes
    return ctypes.windll.kernel32


def _release():
    global _HELD
    held = _HELD
    _HELD = None
    if held is None:
        return
    try:
        _kernel32().CloseHandle(held[1])
    except (OSError, AttributeError, ValueError):
        pass


def _filetime_iso(creation):
    filetime_int = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
    started = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=filetime_int // 10)
    return started.isoformat(timespec="seconds")


def _tasklist_pid():
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq TS4_x64.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].casefold() == "ts4_x64.exe":
            try:
                return int(row[1])
            except (TypeError, ValueError):
                continue
    return None


def _process():
    global _HELD
    if _HELD is not None:
        pid, handle, started = _HELD
        try:
            waited = _kernel32().WaitForSingleObject(handle, 0)
        except (OSError, AttributeError, ValueError):
            return pid, started
        if waited == 258:
            return pid, started
        try:
            _kernel32().CloseHandle(handle)
        except (OSError, AttributeError, ValueError):
            pass
        _HELD = None
    pid = _tasklist_pid()
    if pid is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        kernel = _kernel32()
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
    except (OSError, AttributeError, ValueError):
        return pid, None
    if not handle:
        return pid, None
    started = None
    try:
        import ctypes
        from ctypes import wintypes
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        kernel = _kernel32()
        if kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                   ctypes.byref(kernel_time), ctypes.byref(user_time)):
            started = _filetime_iso(creation)
    except (OSError, AttributeError, ValueError):
        try:
            _kernel32().CloseHandle(handle)
        except (OSError, AttributeError, ValueError):
            pass
        return pid, None
    _HELD = (pid, handle, started)
    return pid, started


def detected_build(*, paths=None, root=None):
    paths = paths or Paths.from_env()
    root = Path(root) if root is not None else game_root(paths)
    exe = root / EXE_REL
    exe_version = _exe_version(exe) if exe.is_file() else None
    txt = paths.sims_root / GAME_VERSION_TXT
    if not txt.is_file():
        txt = root / GAME_VERSION_TXT
    txt_text = _read_text(txt)
    txt_version = txt_text.strip().split()[0] if txt_text and txt_text.strip() else None
    ini_version = _ini_value(_read_text(root / DEFAULT_INI_REL), "gameversion")
    for candidate in (exe_version, txt_version, ini_version):
        if candidate:
            process = _process()
            return {"detected_build": candidate,
                    "sources": {"exe": exe_version, "game_version_txt": txt_version,
                                "default_ini": ini_version},
                    "game_root": str(root),
                    "pid": process[0] if process else None,
                    "pid_start_time": process[1] if process else None}
    raise FileNotFoundError("no build source under %s" % root)


def restarted(before, after):
    return (before or {}).get("pid") != (after or {}).get("pid")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(*, paths=None, root=None):
    paths = paths or Paths.from_env()
    root = Path(root) if root is not None else game_root(paths)
    detected = detected_build(paths=paths, root=root)
    archives = []
    for name in ARCHIVE_NAMES:
        path = root / GAMEPLAY_REL / name
        archives.append({"name": name,
                         "sha256": _sha256(path) if path.is_file() else None})
    packs = []
    delta = root / DELTA_REL
    try:
        names = sorted(p.name for p in delta.iterdir() if p.is_dir())
    except OSError:
        names = []
    for name in names:
        version = _ini_value(_read_text(delta / name / VERSION_INI), "packversion")
        if version is None and not (delta / name / VERSION_INI).is_file():
            continue
        packs.append({"name": name, "packversion": version})
    mods = []
    mods_root = paths.sims_root / "Mods"
    try:
        files = sorted(p for p in mods_root.rglob("*") if p.is_file())
    except OSError:
        files = []
    for path in files:
        try:
            mods.append({"path": path.relative_to(mods_root).as_posix(),
                         "bytes": path.stat().st_size, "sha256": _sha256(path)})
        except OSError:
            continue
    ini_text = _read_text(root / DEFAULT_INI_REL)
    return {"detected_build": detected["detected_build"],
            "game_root": str(root),
            "pid": detected["pid"], "pid_start_time": detected["pid_start_time"],
            "archives": archives, "packs": packs, "mods": mods,
            "code": {"codeversion": _ini_value(ini_text, "codeversion"),
                     "codechangelist": _ini_value(ini_text, "codechangelist"),
                     "codedatetime": _ini_value(ini_text, "codedatetime")}}
