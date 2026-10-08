"""Ashley ingress client. Stdlib HTTPS with default certificate checks."""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .contract import ContractError, validate_heartbeat, validate_observation

# SNAPSHOT: a picture of up to 6 MiB, base64-encoded, can take longer than an act round trip.
SNAPSHOT_TIMEOUT_S = 30


@dataclass(frozen=True)
class TransportResult:
    kind: str
    status: int | None


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
        """8f: one act round trip. The parsed 200 response, or None (nothing applied)."""
        return self._round_trip("/domus/acts/sync", body)

    def post_feed(self, body):
        """E3: her settled game passes for the overlay. The parsed 200 response, or None."""
        return self._round_trip("/domus/feed", body)

    def post_snapshot(self, body):
        """SNAPSHOT: one requested picture, or the reason there is none. The parsed 200 response, or None."""
        return self._round_trip("/domus/snapshot", body, timeout_s=SNAPSHOT_TIMEOUT_S)

    def _round_trip(self, path, body, timeout_s=None):
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
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                status = response.status
                response.read()
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, TimeoutError, OSError):
            return TransportResult("unavailable", None)
        return TransportResult(_kind(status, heartbeat), status)


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
