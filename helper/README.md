# Domus host helper

Python >=3.12, Windows host only for live use. Never install or import this
package in the game. The probe remains 2.3.1. Only local command files and
stdio MCP are used; no HTTP listener or network client is started.

From the Domus root, after Owner approval on the Windows PC:

```powershell
py -3.13 -m venv helper/.venv
helper/.venv/Scripts/python.exe -m pip install 'mcp==2.2.0' 'pytest==9.1.1'
$env:PYTHONPATH = 'helper'
helper/.venv/Scripts/python.exe -m domus_helper.mcp_server
```

`.mcp.json` registers the Windows stdio server for Claude Code from the Domus
root. Codex configuration (replace `C:/Domus` with the actual checkout path):

```toml
[mcp_servers.domus]
command = "C:/Domus/helper/.venv/Scripts/python.exe"
args = ["-m", "domus_helper.mcp_server"]
cwd = "C:/Domus"

[mcp_servers.domus.env]
PYTHONPATH = "C:/Domus/helper"
DOMUS_AGENT_NAME = "mcp"
```

`DOMUS_SIMS_ROOT` overrides the default
`C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4`.
`DOMUS_AGENT_NAME` defaults to `mcp`, and must contain 1–34 lowercase ASCII
letters, digits, underscores or hyphens. Commands use issuer `agent:<name>`.
The inbox directories must already exist. Every tool checks `tasklist` for
`TS4_x64.exe` then gets an accepted status. Arming accepts only `lab_e1` or
`lab_e1_fork`; further actuation requires canonical LAB status after arming.
Read tools include status, verdicts, telemetry and lineage. `detected_build`
reports the installed client version bound to the running `TS4_x64.exe`
process (EXE file version, sims-root `GameVersion.txt`, `Default.ini`
`gameversion`); `fingerprints` adds the script-archive sha256, the installed
pack list and the Mods file list with hashes. A declared (`sims_build`) vs
detected mismatch blocks every actuating command — the session stays
telemetry-only. Stop/disarm remain
available without LAB attestation for cleanup.

The packet requires the Owner to launch the game, load LAB_E1 and type
`ashley_e1.inbox` once per launch (D11 pending). A timeout includes this hint;
it leaves the unanswered envelope intact. A late command can still execute
until its 30-second TTL expires. Cleanup also uses commands and therefore
cannot guarantee stop/disarm when the game or inbox is unavailable.

Run the later, separately Owner-gated replay:

```powershell
$env:PYTHONPATH = 'helper'
helper/.venv/Scripts/python.exe -m domus_helper.runs.trial --save lab_e1 --objects 123,456 --repeat 3 --out C:/DomusEvidence/replay1
```

Each trial waits up to 60 seconds for the VERDICT with the experiment id in
its own PUSHED reply. Failure attempts stop then disarm and exits nonzero.
The new evidence directory must be outside the Sims root. It contains the
session JSONL and its numbered rotation segments, lineage ledger, save inventory (path, bytes, mtime_ns, SHA256),
and session.md, a literal JSONL rendering of validated telemetry only.
`read_only: true` describes the inventory access, not the save's permissions.
Saves are opened only with `rb`. No git operation is part of the runner.
Session telemetry may end with an unfinished row while the writer is active;
readers ignore that row until it is newline terminated. Other malformed rows
fail closed. Evidence missing its ledger is an error, not fabricated data.

Test from `helper/`: `.venv/bin/python -m pytest` (on Windows use
`.venv/Scripts/python.exe`). Tests fake the inbox/replier and process check;
no game or credentials are needed. The vendored cmdbox and full schema v4
validator are pure Python copies from da68647. AST equality tests detect
changes to their vocabulary, shapes, key sets and validation behavior.
The existing probe guard is invoked only on `sims-e1/src/ashley_e1`.
