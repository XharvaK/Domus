"""Ashley ingress client. Stdlib HTTPS with default certificate checks."""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .contract import ContractError, validate_heartbeat, validate_observation

_log = logging.getLogger("domus.transport")
# SNAPSHOT: a picture of up to 6 MiB, base64-encoded, can take longer than an act round trip.
SNAPSHOT_TIMEOUT_S = 30


@dataclass(frozen=True)
class TransportResult:
    kind: str
    status: int | None
    # A9-4: the server's own reason for a 400 (its "error" code, e.g. clock_skew), when it gave one.
    reason: str | None = None


@dataclass(frozen=True)
class SyncRefused:
    """W12 (B4): Mint refused an acts sync as a whole (a 400 with its own short reason). Not a failed round trip."""
    reason: str | None


@dataclass(frozen=True)
class Credentials:
    url: str | None
    token: str | None
    disabled: str | None

    def __repr__(self):
        if self.disabled:
            return "Credentials(disabled=%s)" % self.disabled
        return "Credentials(enabled)"


class AshleyClient:
    def __init__(self, url, token, timeout_s=10):
        self._url = url.rstrip("/")
        self._token = token
        self._timeout_s = timeout_s

    def __repr__(self):
        return "AshleyClient(<redacted>)"

    def post_heartbeat(self, body):
        try:
            validate_heartbeat(body)
        except ContractError:
            return TransportResult("rejected", None)
        return self._post("/domus/heartbeat", body, heartbeat=True)

    def post_observation(self, body, *, now_ms=None):
        try:
            if now_ms is None:
                now_ms = int(time.time() * 1000)
            validate_observation(body, now_ms)
        except ContractError as error:
            kind = "expired" if error.code == "expired" else "rejected"
            return TransportResult(kind, None)
        return self._post("/domus/observation", body, heartbeat=False)

    def sync_acts(self, body):
        """8f: one act round trip. The parsed 200 response, None (no answer: nothing applied), or a SyncRefused when
        Mint refused the batch (W12, B4)."""
        return self._round_trip("/domus/acts/sync", body, refusals=True)

    def post_feed(self, body):
        """E3: her settled game passes for the overlay. The parsed 200 response, or None."""
        return self._round_trip("/domus/feed", body)

    def post_memory(self, body):
        """D7b: the world's memory answer for one of her asks. The parsed 200 response, or None."""
        return self._round_trip("/domus/memory", body)

    def post_snapshot(self, body):
        """SNAPSHOT: one requested picture, or the reason there is none. HE15: a TransportResult whose kind is
        "sent" when Ashley took it, and otherwise why not (the same kinds as the other posts)."""
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self._url + "/domus/snapshot", data=raw, method="POST",
            headers={"Content-Type": "application/json", "X-Domus-Token": self._token})
        try:
            with urllib.request.urlopen(request, timeout=SNAPSHOT_TIMEOUT_S) as response:
                status = response.status
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return TransportResult(_kind(error.code, False), error.code)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return TransportResult("unavailable", None)
        if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
            return TransportResult("sent", status)
        return TransportResult("rejected", status)

    def _round_trip(self, path, body, timeout_s=None, *, refusals=False):
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self._url + path, data=raw, method="POST",
            headers={"Content-Type": "application/json", "X-Domus-Token": self._token})
        timeout = self._timeout_s if timeout_s is None else timeout_s
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if refusals and error.code == 400:
                return SyncRefused(_reason(error))
            return None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) and payload.get("status") == "ok" else None

    def _post(self, path, body, *, heartbeat):
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self._url + path,
            data=raw,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Domus-Token": self._token,
            },
        )
        reason = None
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                status = response.status
                response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            reason = _reason(error)
        except (urllib.error.URLError, TimeoutError, OSError):
            return TransportResult("unavailable", None)
        if reason is not None and status == 400:
            _log.warning("ashley refused a %s: %s", "heartbeat" if heartbeat else "observation", reason)
        return TransportResult(_kind(status, heartbeat), status, reason if status == 400 else None)


def _reason(error):
    """A9-4: the error code of a refusal (a short word from the server, never the body). None when it has none."""
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (OSError, ValueError, AttributeError):
        return None
    code = payload.get("error") if isinstance(payload, dict) else None
    return code if isinstance(code, str) and 0 < len(code) <= 32 else None


def _kind(status, heartbeat):
    if status == 202:
        return "admitted"
    if status == 200:
        return "admitted" if heartbeat else "duplicate"
    if status == 409:
        return "conflict"
    if status == 410:
        return "expired"
    if status == 400:
        return "rejected"
    if status == 401:
        return "unauthorized"
    if status == 413:
        return "too_large"
    return "unavailable"


def load_credentials(paths):
    url = os.environ.get("DOMUS_ASHLEY_URL")
    token = os.environ.get("DOMUS_ASHLEY_TOKEN")
    if url is None:
        file = paths.data_dir / "ashley_url"
        url = file.read_text(encoding="utf-8") if file.is_file() else ""
    if token is None:
        file = paths.data_dir / "ashley_token"
        token = file.read_text(encoding="utf-8") if file.is_file() else ""
    url = url.strip()
    token = token.strip()
    if not url:
        return Credentials(None, None, "missing_url")
    if not token:
        return Credentials(None, None, "missing_token")
    if len(token.encode("utf-8")) < 32:
        return Credentials(None, None, "short_token")
    return Credentials(url, token, None)
