"""Domus tools, served exclusively over the SDK's stdio transport."""
import csv
import io
import os
import subprocess
from dataclasses import asdict

from mcp.server.mcpserver import MCPServer

from . import atlas as atlas_store
from . import calibration
from . import commands, telemetry as telemetry_reader
from . import fingerprints as fingerprint_reader
from .paths import Paths
from .vendor.cmdbox import valid_issuer

LAB_NAMES = {"LAB_E1", "LAB_E1_FORK"}
ACTUATING = {"arm", "start", "prepare", "sit", "sit_trial", "pause", "release", "trial"}


class SafetyError(RuntimeError):
    pass


class CommandFailed(RuntimeError):
    def __init__(self, reply):
        self.reply = reply
        super().__init__(f"{reply.status}: {reply.code}")


def game_running():
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq TS4_x64.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return any(row and row[0].casefold() == "ts4_x64.exe"
               for row in csv.reader(io.StringIO(result.stdout)))


class DomusTools:
    def __init__(self, *, paths=None):
        self.paths = paths or Paths.from_env()
        self.issuer = "agent:" + os.environ.get("DOMUS_AGENT_NAME", "mcp")
        if not valid_issuer(self.issuer):
            raise ValueError("invalid DOMUS_AGENT_NAME")

    def send(self, command, args):
        reply = commands.send(command, args, self.issuer, paths=self.paths)
        if reply.status != "OK":
            raise CommandFailed(reply)
        return reply

    def checked_status(self):
        if not game_running():
            raise SafetyError("TS4_x64.exe is not running")
        return self.send("status", {})

    def _require_build_match(self, status):
        try:
            detected = fingerprint_reader.detected_build(paths=self.paths)["detected_build"]
        except (OSError, FileNotFoundError, ValueError, UnicodeError):
            raise SafetyError("detected build unreadable")
        declared = status.result.get("sims_build")
        if declared is not None and declared != detected:
            raise SafetyError("build mismatch: declared %s, detected %s"
                              % (declared, detected))

    def detected_build_fn(self):
        self.checked_status()
        return fingerprint_reader.detected_build(paths=self.paths)

    def fingerprints_fn(self):
        self.checked_status()
        return fingerprint_reader.fingerprint(paths=self.paths)

    def command(self, name, args=None):
        status = self.checked_status()
        if name == "status":
            return status
        if name in ACTUATING:
            self._require_build_match(status)
        if name == "arm":
            if args != {"name": "lab_e1"} and args != {"name": "lab_e1_fork"}:
                raise SafetyError("arm requires lab_e1 or lab_e1_fork")
        elif name in ACTUATING and status.result.get("armed_name") not in LAB_NAMES:
            raise SafetyError("actuation requires LAB_E1 or LAB_E1_FORK")
        reply = self.send(name, args or {})
        if name == "arm":
            armed = self.checked_status()
            if armed.result.get("armed_name") not in LAB_NAMES:
                raise SafetyError("arming did not establish a LAB save")
        return reply


server = MCPServer("Domus")


def tools():
    return DomusTools()


@server.tool()
def status() -> dict:
    return asdict(tools().command("status"))


@server.tool()
def arm(save: str) -> dict:
    return asdict(tools().command("arm", {"name": save}))


@server.tool()
def start() -> dict:
    return asdict(tools().command("start"))


@server.tool()
def stop() -> dict:
    return asdict(tools().command("stop"))


@server.tool()
def disarm() -> dict:
    return asdict(tools().command("disarm"))


@server.tool()
def prepare(object_id: str) -> dict:
    return asdict(tools().command("prepare", {"object_id": object_id}))


@server.tool()
def sit(token: str) -> dict:
    return asdict(tools().command("sit", {"token": token}))


@server.tool()
def sit_trial(object_id: str) -> dict:
    return asdict(tools().command("sit_trial", {"object_id": object_id}))


@server.tool()
def trial(object_id: str, guid64: str) -> dict:
    return asdict(tools().command("trial", {"object_id": object_id, "guid64": guid64}))


@server.tool()
def pause() -> dict:
    return asdict(tools().command("pause"))


@server.tool()
def release() -> dict:
    return asdict(tools().command("release"))


@server.tool()
def verdicts(n: int = 5) -> list[dict]:
    client = tools()
    client.checked_status()
    return [r for r in telemetry_reader.tail(["experiment_event"], 10000, paths=client.paths)
            if r["e2"]["phase"] == "VERDICT"][-_count(n):]


def _count(n):
    if type(n) is not int or not 1 <= n <= 10000:
        raise ValueError("n must be between 1 and 10000")
    return n


@server.tool()
def telemetry(kinds: list[str], n: int = 20) -> list[dict]:
    client = tools()
    client.checked_status()
    return telemetry_reader.tail(kinds, n, paths=client.paths)


@server.tool()
def lineage() -> list[dict]:
    client = tools()
    client.checked_status()
    return telemetry_reader.lineage(paths=client.paths)


@server.tool()
def detected_build() -> dict:
    return tools().detected_build_fn()


@server.tool()
def fingerprints() -> dict:
    return tools().fingerprints_fn()


@server.tool()
def atlas_dump() -> dict:
    return asdict(tools().command("atlas_dump"))


@server.tool()
def tuned_scan() -> dict:
    return asdict(tools().command("tuned_scan"))


@server.tool()
def atlas_progress() -> dict:
    block = tools().checked_status().result.get("atlas")
    if not isinstance(block, dict):
        raise SafetyError("status has no atlas block")
    return block


@server.tool()
def atlas_import() -> dict:
    client = tools()
    detected = fingerprint_reader.detected_build(paths=client.paths)["detected_build"]
    source = client.paths.atlas_dir / ("tuning_%s.jsonl" % detected)
    if not source.is_file():
        raise FileNotFoundError(source)
    return atlas_store.import_tuning(client.paths.atlas_db, source)


@server.tool()
def atlas_query(build: str | None = None, name_contains: str | None = None,
                is_super: bool | None = None, is_social: bool | None = None,
                allow_autonomous: bool | None = None,
                allow_user_directed: bool | None = None,
                ladder: str | None = None, limit: int = 50) -> list[dict]:
    client = tools()
    chosen = build if build is not None else atlas_store.latest_build(client.paths.atlas_db)
    return atlas_store.query(
        client.paths.atlas_db, build=chosen, name_contains=name_contains,
        is_super=is_super, is_social=is_social, allow_autonomous=allow_autonomous,
        allow_user_directed=allow_user_directed, ladder=ladder, limit=limit)


@server.tool()
def cards(card_class: str | None = None) -> list[dict]:
    """Read cards for the detected build. Nothing is written."""
    client = tools()
    detected = fingerprint_reader.detected_build(paths=client.paths)["detected_build"]
    return atlas_store.list_cards(client.paths.atlas_db, detected, card_class)


@server.tool()
def bridge_status() -> dict:
    from .bridge import Bridge
    return Bridge(paths=Paths.from_env()).status()


@server.tool()
def thalamus_status() -> dict:
    from .bridge import Bridge
    return Bridge(paths=Paths.from_env()).thalamus_status()


@server.tool()
def calibrate() -> dict:
    return asdict(tools().command("calibrate"))


@server.tool()
def calibration_report(session: str = "latest") -> dict:
    client = tools()
    return calibration.report_for(session, client.paths)["coverage"]


if __name__ == "__main__":
    server.run(transport="stdio")
