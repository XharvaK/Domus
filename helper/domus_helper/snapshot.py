"""SNAPSHOT (helper side): a real picture of the game's own window, when Ashley asks for one.

Each acts round trip can hand back snapshot requests from Mint. Every id this helper process has
not handled yet is captured once and posted to POST /domus/snapshot: the PNG, or the reason there
is none (minimized, not_front, no_game_window, capture_failed). Only the game's top-level window is
captured, never the whole screen or another window. Windows only; stdlib and ctypes only.

Run: python -m domus_helper.snapshot test <out.png>
(captures the game once and writes the PNG to that path here; nothing is sent)
"""
import argparse
import base64
import json
import logging
import struct
import threading
import time
import types
import zlib

from . import fingerprints as fingerprint_reader

log = logging.getLogger(__name__)

MAX_WIDTH = 1600
PNG_LIMIT_BYTES = 6 * 1024 * 1024  # Mint refuses a decoded picture above this
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
DPI_AWARENESS_PER_MONITOR_V2 = -4
DIB_RGB_COLORS = 0
BI_RGB = 0
MAX_ID_LENGTH = 64
# HE15: a picture that did not reach Ashley is tried once more after this long.
RETRY_WAIT_S = 5

# Ids this process has already captured and posted (or tried to post). Process-local by design.
_HANDLED = set()
_LOCK = threading.Lock()
_WIN = None


class SnapshotFailed(Exception):
    """The picture could not be taken. code is the reason Mint is told."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def downscale_bgra(buf, w, h, max_w=MAX_WIDTH):
    """Integer-step sampling of a top-down BGRA frame to at most max_w wide, as RGB bytes.
    Returns (rgb_bytes, new_w, new_h)."""
    if len(buf) != w * h * 4:
        raise ValueError("frame size")
    step = max(1, -(-w // max_w))
    out_w = -(-w // step)
    span = 4 * step
    stride = 4 * w
    rows = []
    for y in range(0, h, step):
        row = buf[y * stride:(y + 1) * stride]
        line = bytearray(out_w * 3)
        line[0::3] = row[2::span]  # R
        line[1::3] = row[1::span]  # G
        line[2::3] = row[0::span]  # B
        rows.append(bytes(line))
    return b"".join(rows), out_w, -(-h // step)


def encode_png_rgb(rgb_bytes, w, h):
    """An 8-bit RGB PNG (colour type 2), every row prefixed by filter byte 0, zlib-compressed."""
    if w <= 0 or h <= 0 or len(rgb_bytes) != w * h * 3:
        raise ValueError("rgb size")
    stride = 3 * w
    raw = b"".join(b"\x00" + rgb_bytes[y * stride:(y + 1) * stride] for y in range(h))
    header = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6))
            + _chunk(b"IEND", b""))


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def capture_game_window(pid=None, *, is_iconic=None, foreground_window=None):
    """PNG bytes of the game's own top-level window. Raises SnapshotFailed with the reason.
    F8: a window that is minimized, or not the front window, still holds its last frame, so none is taken.
    is_iconic(hwnd) and foreground_window() are the two Win32 reads; None reads the real ones."""
    if pid is None:
        held = fingerprint_reader._process()
        if held is None:
            raise SnapshotFailed("no_game_window")
        pid = held[0]
    win = _win32()
    # Per-monitor DPI awareness, so the client size and the pixels are the real ones.
    previous = _dpi_aware(win)
    try:
        hwnd = _game_window(win, pid)
        if hwnd is None:
            raise SnapshotFailed("no_game_window")
        _only_of_now(hwnd, is_iconic or win.user32.IsIconic,
                     foreground_window or win.user32.GetForegroundWindow)
        return _window_png(win, hwnd)
    finally:
        if previous:
            win.user32.SetThreadDpiAwarenessContext(previous)


def handle_requests(snapshot_ids, client, capture=capture_game_window, *, helper_session):
    """Capture and post each requested picture once. Never raises: the acts loop goes on.
    snapshot_ids is what Mint returned: rows with a snapshot_id, or bare ids."""
    _post_all(_claim_new(snapshot_ids), client, capture, helper_session)


def handle_requests_in_background(snapshot_ids, client, *, helper_session, start=None):
    """handle_requests off the acts loop: the ids are claimed here, so a later round trip never
    claims them again, and the capture and the post run on a daemon thread, so a slow post never
    holds up her acts."""
    fresh = _claim_new(snapshot_ids)
    if not fresh:
        return
    run = lambda: _post_all(fresh, client, capture_game_window, helper_session)
    if start is not None:
        start(run)
        return
    threading.Thread(target=run, name="domus-snapshot", daemon=True).start()


def _claim_new(snapshot_ids):
    if not isinstance(snapshot_ids, list):
        return []
    fresh = []
    with _LOCK:
        for item in snapshot_ids:
            snapshot_id = _snapshot_id(item)
            if snapshot_id is None or snapshot_id in _HANDLED:
                continue
            _HANDLED.add(snapshot_id)
            fresh.append(snapshot_id)
    return fresh


def _post_all(snapshot_ids, client, capture, helper_session):
    for snapshot_id in snapshot_ids:
        body = _body(snapshot_id, helper_session, capture)
        if _send(client, snapshot_id, body) == "sent":
            continue
        time.sleep(RETRY_WAIT_S)
        kind = _send(client, snapshot_id, body)
        if kind != "sent":
            log.warning("snapshot %s not sent after a retry: %s", snapshot_id, kind)


def _send(client, snapshot_id, body):
    """One post. Returns the kind of the answer; a failure is logged by its kind, never its picture."""
    try:
        result = client.post_snapshot(body)
    except Exception as error:
        log.warning("snapshot %s not sent: %s", snapshot_id, type(error).__name__)
        return "error"
    kind = getattr(result, "kind", None) or "unknown"
    if kind != "sent":
        log.warning("snapshot %s not sent: %s", snapshot_id, kind)
    return kind


def _snapshot_id(item):
    value = item.get("snapshot_id") if isinstance(item, dict) else item
    return value if isinstance(value, str) and 0 < len(value) <= MAX_ID_LENGTH else None


def _body(snapshot_id, helper_session, capture):
    body = {"v": 1, "helper_session": helper_session, "snapshot_id": snapshot_id}
    try:
        png = capture()
        if not isinstance(png, (bytes, bytearray)) or not png:
            raise SnapshotFailed("capture_failed")
        body["png_base64"] = base64.b64encode(bytes(png)).decode("ascii")
    except SnapshotFailed as failure:
        body["failed"] = failure.code
    except Exception:
        body["failed"] = "capture_failed"
    return body


def _only_of_now(hwnd, is_iconic, foreground_window):
    """F8: a picture is taken only of the game as it is on screen now. Minimized is checked first."""
    if is_iconic(hwnd):
        raise SnapshotFailed("minimized")
    if foreground_window() != hwnd:
        raise SnapshotFailed("not_front")


def _window_png(win, hwnd):
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    win.user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise SnapshotFailed("capture_failed")
    rgb, out_w, out_h = downscale_bgra(_frame(win, hwnd, w, h), w, h)
    png = encode_png_rgb(rgb, out_w, out_h)
    if len(png) > PNG_LIMIT_BYTES:
        raise SnapshotFailed("capture_failed")
    return png


def _frame(win, hwnd, w, h):
    """The client area as top-down BGRA bytes. PrintWindow first; the screen only when the game
    is the foreground window and PrintWindow gave nothing but black."""
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = win.user32, win.gdi32
    size = w * h * 4
    memdc = gdi32.CreateCompatibleDC(None)
    if not memdc:
        raise SnapshotFailed("capture_failed")
    bitmap = old = None
    try:
        info = win.bitmap_info()
        info.bmiHeader.biSize = ctypes.sizeof(win.bitmap_header)
        info.bmiHeader.biWidth = w
        info.bmiHeader.biHeight = -h  # negative height: rows run top-down
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(memdc, ctypes.byref(info), DIB_RGB_COLORS,
                                        ctypes.byref(bits), None, 0)
        if not bitmap or not bits.value:
            raise SnapshotFailed("capture_failed")
        old = gdi32.SelectObject(memdc, bitmap)
        printed = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)
        frame = ctypes.string_at(bits.value, size)
        if printed and not _all_black(frame):
            return frame
        if user32.GetForegroundWindow() != hwnd:
            raise SnapshotFailed("capture_failed")
        screen = user32.GetDC(None)
        if not screen:
            raise SnapshotFailed("capture_failed")
        try:
            origin = wintypes.POINT()
            user32.ClientToScreen(hwnd, ctypes.byref(origin))
            if not gdi32.BitBlt(memdc, 0, 0, w, h, screen, origin.x, origin.y, SRCCOPY):
                raise SnapshotFailed("capture_failed")
        finally:
            user32.ReleaseDC(None, screen)
        frame = ctypes.string_at(bits.value, size)
        if _all_black(frame):
            raise SnapshotFailed("capture_failed")
        return frame
    finally:
        if old:
            gdi32.SelectObject(memdc, old)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memdc)


def _all_black(frame):
    """True when every red, green and blue byte of a BGRA frame is zero (alpha is ignored)."""
    return all(frame[channel::4].count(0) == len(frame) // 4 for channel in (0, 1, 2))


def _game_window(win, pid):
    """The game's largest visible top-level window; a restored one is preferred to a minimised one."""
    import ctypes
    from ctypes import wintypes

    found = []

    def visit(hwnd, _lparam):
        owner = wintypes.DWORD()
        win.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and win.user32.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            win.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            area = (rect.right - rect.left) * (rect.bottom - rect.top)
            found.append((not win.user32.IsIconic(hwnd), area, hwnd))
        return True

    callback = win.enum_proc(visit)
    win.user32.EnumWindows(callback, 0)
    return max(found)[2] if found else None


def _dpi_aware(win):
    set_context = getattr(win.user32, "SetThreadDpiAwarenessContext", None)
    return set_context(DPI_AWARENESS_PER_MONITOR_V2) if set_context is not None else None


def _win32():
    """user32 and gdi32 with argument and return types set once. Handles are pointer-sized,
    so every handle argument and return is declared, never left to ctypes' default int."""
    global _WIN
    if _WIN is not None:
        return _WIN
    import ctypes
    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

    handle = wintypes.HANDLE
    pointer = ctypes.POINTER
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, pointer(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, pointer(wintypes.RECT)]
    user32.GetClientRect.argtypes = [wintypes.HWND, pointer(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, pointer(wintypes.POINT)]
    user32.GetForegroundWindow.restype = handle
    user32.GetDC.argtypes = [handle]
    user32.GetDC.restype = handle
    user32.ReleaseDC.argtypes = [handle, handle]
    user32.PrintWindow.argtypes = [wintypes.HWND, handle, wintypes.UINT]
    user32.SetThreadDpiAwarenessContext.argtypes = [handle]
    user32.SetThreadDpiAwarenessContext.restype = handle
    gdi32.CreateCompatibleDC.argtypes = [handle]
    gdi32.CreateCompatibleDC.restype = handle
    gdi32.DeleteDC.argtypes = [handle]
    gdi32.CreateDIBSection.argtypes = [handle, pointer(BITMAPINFO), wintypes.UINT,
                                       pointer(ctypes.c_void_p), handle, wintypes.DWORD]
    gdi32.CreateDIBSection.restype = handle
    gdi32.SelectObject.argtypes = [handle, handle]
    gdi32.SelectObject.restype = handle
    gdi32.DeleteObject.argtypes = [handle]
    gdi32.BitBlt.argtypes = [handle, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             handle, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    _WIN = types.SimpleNamespace(user32=user32, gdi32=gdi32, enum_proc=enum_proc,
                                 bitmap_info=BITMAPINFO, bitmap_header=BITMAPINFOHEADER)
    return _WIN


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.snapshot")
    parser.add_argument("command", choices=["test"])
    parser.add_argument("out", help="the PNG file to write on this PC")
    args = parser.parse_args(argv)
    try:
        png = capture_game_window()
    except SnapshotFailed as failure:
        print(json.dumps({"failed": failure.code}))
        return 1
    with open(args.out, "wb") as handle:
        handle.write(png)
    print(json.dumps({"bytes": len(png)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
