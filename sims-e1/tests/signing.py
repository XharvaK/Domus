"""OPENVULN F1 (2026-11-03): the test side of the command MAC. An independent HMAC-SHA256 over the same canonical
JSON, so a test both signs as the helper does and cross-checks cmdbox.mac."""
import hashlib
import hmac
import json
import os

KEY = bytes(range(32))


def install_key(cmd_dir, key=KEY):
    os.makedirs(str(cmd_dir), exist_ok=True)
    with open(os.path.join(str(cmd_dir), "key"), "w", encoding="ascii") as handle:
        handle.write(key.hex())


def signed(row, key=KEY):
    body = dict((name, value) for name, value in row.items() if name != "mac")
    canonical = json.dumps(body, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return dict(body, mac=hmac.new(key, canonical, hashlib.sha256).hexdigest())


def signed_bytes(row, key=KEY):
    return json.dumps(signed(row, key)).encode("utf-8")
