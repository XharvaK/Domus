# Domus host helper

Python >=3.12, Windows host only for live use. Never install or import this
package in the game. The probe is 2.4.0. Only local command files and
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
Read tools include status, verdicts, telemetry, lineage, `atlas_dump`,
`atlas_progress`, `atlas_import`, `atlas_query` and `tuned_scan`. `atlas_dump`
and `tuned_scan` are read-only and are not actuating commands. The atlas database is
`E:\Domus\atlas.db` unless `DOMUS_DATA_DIR` is set. The data folder is
not under AppData: a packaged app (the Claude desktop app) has its AppData writes
redirected into its own package folder, which other processes do not see.
`detected_build`
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

## Bridge

`python -m domus_helper.bridge --once` reads new telemetry, updates attachment,
sends the changes it sees as views (`coalesce.py`), sends one heartbeat when Ashley is configured,
and flushes the observation outbox. `python -m domus_helper.bridge --interval 5`
repeats until Ctrl+C.

Seen and heard (SS4-v2): she names a Sim only when she sees them. Indoors that is the same room
and the same level as her body; outdoors, within 4 m on the same level. A Sim she hears instead
(another room, another level, or farther) appears in the portrait's `company` as
`{"heard": true, "handle", "room", "distance_m", "on_lot"}` with no id, name or doing. The
`handle` is a keyed hash of the presence id under a per-install key kept in the spool (`heard_key`);
it is stable across samples and restarts, never the id, and it is never logged. A heard Sim's seen
state changes only after two samples in a row that agree. Addressing her from another room is heard.

Portrait facts of 2.32.0 (schema 15, W5d): `self.life` (age stage, pregnant, sick, dead, ghost, npc);
`near_conditions` (the notable states of the near objects, no ids); `building` while in build or buy mode (not
"paused"); `fire_on_lot`; `user_plays_another` when the User plays another household Sim (her acts are refused
meanwhile); `zone.room_label` and `room_label` on company entries, the room named by the object families in it
("the room with the fridge and the stove"), never a room number. A company entry for a pet carries `pet`, `species`
and, for an occult form, `occult`. A BODY_GONE record reaches her as a lineage percept with its `reason` fact.
Object conditions reach the notebook as `object_condition` facts; object rooms come from the 16 nearest objects.

Game-only inputs: `python -m domus_helper.inputs game-only` keeps the User's
conversations out of Ashley's game passes; `full` lifts it and `show` prints the
state. The switch travels in the heartbeat (`inputs: game_only`, sent at once on a
flip), each pass Ashley admits while it is on is stamped game-only, and every flip
is appended to `inputs_log.jsonl` in the data folder.

Overlay pages: while the bridge runs (`--interval`), it serves local pages on
`http://127.0.0.1:47213/` (16:9), `/vertical` (9:16), `/curtain` and `/work`, for a
capture tool's browser source, and their state on `/state.json`. They answer this PC
only (the Host header must be `127.0.0.1` or `localhost`). They show her body (needs,
mood, moodlets, the game clock, what her body is doing and whose hand started it: her
choice, her body, the game, or a human) and her settled game passes from Ashley's
`POST /domus/feed`, polled every 8 s. A pass without the game-only stamp is refused;
with the switch off the pages show only the curtain. Lines matching
`overlay_privacy.txt` in the data folder (one name or place per line, `#` for
comments) are held and shown as "…". A human at the controls (a click from the
game's menu, a pop-up answered by hand, a helper restart) is labelled for 2 minutes.
`python -m domus_helper.overlay curtain on|off|show` draws the curtain by hand;
it also falls whenever the game is not attached.

Social talk (probe 2.26.0 or later): each new social sentence in her portrait, what
she is doing now and what someone does to her, in the local phrase dictionary's words,
goes to the probe as one `talk` line, shown on the User's screen as the game's own
notification. A sentence shows once while it lasts and again only after a minute gone;
at most one line each 2.1 s and three waiting (the newest kept). It needs no Ashley
connection and changes nothing in the game. `python -m domus_helper.talk on|off|show`.

Snapshots (Windows only, stdlib and ctypes): when Ashley asks for a picture in a pass,
Mint hands the request back in the next acts round trip. The helper captures the game's
own top-level window once per request id, never the whole screen or another window:
PrintWindow into a client-area bitmap, and only if that gives a black frame and the game
is the foreground window, a copy of the screen over that area. A minimised or missing
window, or a failed capture, is reported as its reason instead. The picture is an 8-bit
RGB PNG at most 1600 px wide, posted once to `POST /domus/snapshot` (a 30 s timeout), and
Mint sends it to the User's DM only. `python -m domus_helper.snapshot test <out.png>`
captures the game once and writes the PNG to that file here; it sends nothing.

Proof kit (`proof/` in the data folder, all append-only and hash-chained, each line
carrying the previous hash): `trace-YYYYMMDD.jsonl` records every pass of hers the
overlay showed, once, as it was shown, with what produced it (agent build, model,
provider, provider request id, tokens, helper build, probe version, the switch).
`python -m domus_helper.proof root [YYYYMMDD]` verifies a day and appends its root to
`roots.jsonl` for timestamping; `proof verify FILE` checks any chain; `proof ledger
arranged|unarranged|viewer_change|flagged|note "NOTE" [--link URL]` records an
opportunity, tip or change. A word-watch flag from Ashley (`marks` in her feed) is
ledgered as `flagged`, and, when `obs_ws.json` (`{"port": 4455, "password": ...}`, a
secret) is present, the capture tool is asked over its local control socket to save
its replay buffer and mark the recording. Once a day is over, its trace is timestamped with OpenTimestamps (every 6 h while the bridge runs, or `proof stamp [YYYYMMDD]`): only the file's sha256 goes to two public calendars, and a standard `.ots` proof is written beside it (`.ots2` for the second calendar), checkable later with the official client.

After `read_new`, each new spool row (SQLite `rowid` after `last_rowid`) goes
through `Extractor.step` and `decide`, using the row's `monotonic_ns // 1_000_000`
as `now_ms`. One empty `decide` then advances deadlines and boredom on the
bridge monotonic clock. `prune` drops recovered keys and foreign-lineage novelty
counts. State, extractor state, `last_rowid`, and `obs_seq` persist in the spool
`kv` table (`user_version` 2; a v1 database upgrades in place) so a helper
restart does not repeat observations.

A view is enqueued only when transport is enabled and the session is not
`telemetry_only`. `thalamus/observation.py` builds one v1 observation:
`{helper_session}.{obs_seq}`, world `slot{slot_id}` (or `unknown`), branch from
the lineage guid, session from `telemetry_session_id`, body from `body.sim_id`,
snapshot from the last row's `written_sequence`, a 600000 ms expiry, lineage
class `[A-Z_]{1,32}` or `PENDING`, up to 32 percepts (salience clamped to
0..1, facts capped at 2048 bytes), and a present-tense portrait capped at
8192 bytes. `seq` increments only when the outbox accepts the observation.

Every view sent appends one JSON line to `data_dir/thalamus/decisions-YYYYMMDD.jsonl`
(UTC): time, trigger (`quiet`, `oldest`, `question`, or `look`), percept count, kinds, and
observation id. `DECISION_LOG_QUOTA_BYTES` in `thalamus/parameters.py` (50 MiB) is the
Owner-adjustable cap. After a write, the oldest files other than today's are deleted until the
directory fits. There is no scorer and no decision (D2): every change is sent, coalesced.

Credentials: `E:\Domus\ashley_url` and `ashley_token` (or
`DOMUS_DATA_DIR`). Overrides: `DOMUS_ASHLEY_URL` and `DOMUS_ASHLEY_TOKEN`.
The token is at least 32 bytes. A missing URL, missing token, or short token
disables transport. MCP `bridge_status` reports attachment, spool and outbox
counts, the last heartbeat, transport, and a `thalamus` block. MCP
`thalamus_status` returns that block. Neither tool requires the game, and
neither prints the URL or the token.

Attachment states: `attached` (process up, latest row at most 30 seconds old),
`stale` (process up, row older), `game_exited` (process gone, close reason
present), `crash_suspected` (process gone, no close), `sleep_resume` (one
tick when wall time jumps more than 30 seconds ahead of the monotonic clock),
`version_mismatch` (row `sims_build` differs from the detected build;
`telemetry_only` is true). The spool is `E:\Domus\spool.db`.

## Crawl (DA6)

The lab save must be `LAB_E1_FORK`, with aging off and **autonomy off** so foreign roots do not drown attribution. Keep speed at normal or 3, and keep the Sim fed.

```powershell
python -m domus_helper.crawl --per-hour 30 --max-trials 200 --verdict-timeout-s 600
python -m domus_helper.crawl --dry-run --tuned-file C:\path\tuned.jsonl
```

`--per-hour` defaults to 30 and cannot exceed 60. It is the minimum spacing between `trial` sends. `--dry-run` prints the plan and sends nothing. The driver sends only when status is `SAMPLING`, the armed save is `LAB_E1_FORK`, and calibrate is off. Otherwise it waits 10 seconds. `BODY_BUSY` and `CLOCK_PAUSED` wait 15 seconds and retry the same candidate without a ledger row.

The process exits 2 on: 5 consecutive `PUSH_FAILED`, or 8 of the last 10; a `TRIAL_STORM` reply; `NEED_DISTRESS` twice in a row (`the lab Sim needs care: feed/rest her, then restart`); a change of `lineage_class` or `designated_sim_id` from the start of the run; a build-mismatch `SafetyError`; or `--max-trials`. One JSONL line per send and per outcome is appended under the helper data dir at `runs/crawl_<session>.jsonl`.

`qualification()` (and the same atlas function) reports, per guid64, `pass_n`, `unknown_n`, `reject_n`, `push_failed_n`, and `state`. `QUALIFIED` means at least 3 `PASS` and zero `OUTCOME_UNKNOWN`. `FAILED` means 3 unknowns, 2 `PUSH_FAILED`, or a `TRIAL_EXCLUDED` reject. No rows is `UNTESTED`. Anything else is `IN_PROGRESS`. MCP `trials`, `qualification`, and `crawl_plan` only read.

Test from `helper/`: `.venv/bin/python -m pytest` (on Windows use
`.venv/Scripts/python.exe`). Tests fake the inbox/replier and process check;
no game or credentials are needed. The vendored cmdbox and full schema v4
validator are pure Python copies from da68647. AST equality tests detect
changes to their vocabulary, shapes, key sets and validation behavior.
The existing probe guard is invoked only on `sims-e1/src/ashley_e1`.

## Scheduled tasks

Two Windows tasks keep the helper running, and `tools\install_tasks.ps1` registers both (OP15). Run it from `helper/` with `-WhatIf` first to see the plan, then without it to register:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install_tasks.ps1 -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install_tasks.ps1
```

- "Domus bridge": `tools\bridge.ps1` starts at logon and again every 5 minutes. The watcher runs one bridge while the game is open; a named mutex keeps a second watcher from starting. Without the venv (`.venv\Scripts\python.exe`) it writes a line to `domus_bridge_watcher.log` in the temp folder and exits.
- "Domus telemetry archive": `tools\daily_archive.ps1` runs daily at 12:00, and as soon as possible after a missed run.
