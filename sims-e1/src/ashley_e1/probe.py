"""Owner-command state machine and one real-time alarm callback."""

try:
    import alarms  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla real-time alarm API.
except ImportError:
    alarms = None
try:
    import clock  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla real-time interval API.
except ImportError:
    clock = None
try:
    import date_and_time  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla TimeSpan API.
except ImportError:
    date_and_time = None
try:
    import interactions.context as _interaction_context_module  # PRIOR_ART|RUNTIME_UNVERIFIED: read surface.
except ImportError:
    _interaction_context_module = None
try:
    import server.clientmanager as _clientmanager_module  # PRIOR_ART|RUNTIME_UNVERIFIED: client manager surface.
except ImportError:
    _clientmanager_module = None
try:
    import services as _services_module  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla service getters.
except ImportError:
    _services_module = None
try:
    from sims.sim import Sim as _Sim  # PRIOR_ART|RUNTIME_UNVERIFIED: approved Sim surface.
except ImportError:
    _Sim = None
try:
    from sims.sim_info import SimInfo as _SimInfo  # PRIOR_ART|RUNTIME_UNVERIFIED: approved SimInfo surface.
except ImportError:
    _SimInfo = None
try:
    import sims4.commands as _commands_module  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla command surface.
except ImportError:
    _commands_module = None
import os
import time
import uuid

try:
    from sims4.commands import (CommandType, CommandRestrictionFlags,
                                register)  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla command surface.
except ImportError:
    CommandType = None
    CommandRestrictionFlags = None
    register = None

from . import act_menu
from . import atlas
from . import food
from . import preflight
from . import situation
from . import cmdbox
from . import tuned
from . import e2_actuator
from . import e2_admission
from . import e2_control
from . import home  # 2.40.0 (W13 P2, home): her save, home edits and the catalogue dump.
from . import observers
from . import reach
from . import schema
from .writer import TelemetryWriter, bootstrap_from_module_path, derive_telemetry_root, read_command_file, write_command_reply
from .writer import read_small_json, remove_file, write_small_json


E1_PROBE_VERSION = schema.PROBE_VERSION
SIMS_BUILD = schema.SIMS_BUILD
try:
    TimeSpan = date_and_time.TimeSpan
except AttributeError:
    TimeSpan = None
try:
    interval_in_real_seconds = clock.interval_in_real_seconds
except AttributeError:
    interval_in_real_seconds = None
try:
    _alarms_add_alarm_real_time = alarms.add_alarm_real_time
except AttributeError:
    _alarms_add_alarm_real_time = None
try:
    _alarms_cancel_alarm = alarms.cancel_alarm
except AttributeError:
    _alarms_cancel_alarm = None
try:
    _services_sim_info_manager = _services_module.sim_info_manager
except AttributeError:
    _services_sim_info_manager = None
try:
    _services_client_manager = _services_module.client_manager
except AttributeError:
    _services_client_manager = None
try:
    _interaction_context_type = _interaction_context_module.InteractionContext
except AttributeError:
    _interaction_context_type = None
try:
    _commands_output = _commands_module.cheat_output
except AttributeError:
    _commands_output = None

_INITIALIZED = False


class _ProbeAlarmOwner:
    pass


_PROBE_ALARM_OWNER = _ProbeAlarmOwner()
_INBOX_ALARM_OWNER = _ProbeAlarmOwner()
_ATLAS_ALARM_OWNER = _ProbeAlarmOwner()
_ATLAS = None
_ATLAS_HANDLE = None
_TUNED_ALARM_OWNER = _ProbeAlarmOwner()
_TUNED = None
_TUNED_HANDLE = None
_PREFLIGHT_ALARM_OWNER = _ProbeAlarmOwner()
_PREFLIGHT = None
_PREFLIGHT_HANDLE = None
_FOOD_ALARM_OWNER = _ProbeAlarmOwner()
_FOOD = None
_FOOD_HANDLE = None
_SITUATION_ALARM_OWNER = _ProbeAlarmOwner()
_SITUATION = None
# 8f (2.16.0): the menu of what she can do near her body, rebuilt while sampling.
_MENU = None
_MENU_ZONE = None
_MENU_REV = 0
_MENU_LAST = None
_MENU_STARTED_S = None
_MENU_ROOM = None
_MENU_FAILURES = 0
# 2.37.0 (W10 P2): the far cache (its outcomes are cleared when the zone changes, _MENU_FAR_ZONE); the zone of the last
# build that finished (its first build in a zone writes the near part, _MENU_FIRST, as its far part starts).
_MENU_FAR = act_menu.FarCache(clock=lambda: _now_s())
_MENU_FAR_ZONE = None
_NO_ZONE = object()
_MENU_DONE_ZONE = _NO_ZONE
_MENU_FIRST = False
# 2.37.1: when the first build in a zone last wrote its menu so far (act_menu.FIRST_PARTIAL_S).
_MENU_PARTIAL_S = None
# 2.39.0 (W12 C1, G1): the newest finished build of this zone (zone, build), read by the near part on her move;
# the request of a look (request_menu_near); her body as the tick read it; the room the last tick saw.
_MENU_LAST_BUILD = None
_MENU_NEAR_REQUESTED = False
_MENU_BODY = (None, None)
_MENU_SEEN_ROOM = _NO_ZONE
_SITUATION_HANDLE = None
_INBOX_HANDLE = None
_INBOX_ZONE = None
_INBOX_STARTED_ZONE = None
_INBOX_AUTOSTART = "NOT_STARTED"
_INBOX_ARM_SOURCE = "manager"
_INBOX_ARMED_ZONES = []
_INBOX_ARMED_MANAGERS = []
_AUTOSTART_HOOKS = {}
_INBOX_BUSY = False
_INBOX_ERRORS = 0
_INBOX_USED_IDS = set()
_INBOX_VERDICTS = []
_STATE = "UNARMED"
# D41: travel. The User's start holds until the User's stop or disarm; the zone that
# sampling runs in; poll ticks with no selectable body (the loading screen) so far.
_RESUME_SAMPLING = False
_ALARM_ZONE = None
_ZERO_BODY_TICKS = 0
ZONE_SETTLE_TICKS = 60
# D43: the inbox tick watches sampling. A resume that could not start is retried; a
# sampler that has not ticked for SAMPLER_STALL_SECONDS is restarted, at most once per
# SAMPLER_RESTART_SPACING seconds.
_RESUME_PENDING = False
_LAST_TICK_S = None
_LAST_SUPERVISE_S = None
_LAST_RESTART_S = None
SAMPLER_STALL_SECONDS = 10.0
SAMPLER_RESTART_SPACING = 30.0
# D47 (live 2026-10-05): a relaunch left the probe unarmed and the User's first half
# hour of play (cleaning spoiled food, a book back on the shelf) was not recorded.
# The User's start is remembered for that save (AUTOSAMPLE_FILE beside the telemetry);
# loading the same save starts sampling again; the User's stop or disarm forgets it.
AUTOSAMPLE_FILE = "autosample.json"
# 2.15.3: HOME is Ashley's own save (her household and lot). It is sensed like a lab, but the
# lab-only tools (preflight, food, situation and E2 trials, helper actuation) check for a lab
# name and refuse there.
ARM_NAMES = schema.ARM_NAMES
_AUTOSTART_TRIED_ZONE = None
# D48: one TELEMETRY_DIR_75 checkpoint per session when the folder passes 75% of its cap.
_DIR_WARNED = False
_ARMED_NAME = None
_CALIBRATE = False
_CAL_SPEED = None
_OBSERVE_REFUSED = ("prepare", "sit", "sit_trial", "pause", "release", "trial",
                     "preflight", "food_scan", "act", "answer", "cancel", "camera", "talk", "pace",
                     "go", "event")
# 2.40.0 (W13 P2, home): her save, home edits and the catalogue dump are refused in calibrate mode too.
_OBSERVE_REFUSED = _OBSERVE_REFUSED + home.COMMANDS
_ARMED_SNAPSHOT = None
_TELEMETRY_SESSION_ID = None
_ALARM_HANDLE = None
_WRITER = None
_WRITER_IDLE = True
_SESSION_OPENED = False
_POLL_BUSY = False
_TELEMETRY_ROOT = None
_MISUSE_COUNT = 0
_LAST_CAPTURE_COUNTERS = None
_COUNTERS = {"dropped_queue": 0, "dropped_overrun": 0,
             "dropped_serialize": 0, "redundant_starts": 0}

def _output(text, connection):
    if isinstance(connection, _InboxReply):
        connection.lines.append(text)
        return
    if _commands_output is None:
        return
    try:
        _commands_output(text, connection)
    except Exception:
        pass


_E2 = e2_control.E2Control(
    emit=lambda row: _emit(row),
    get_state=lambda: _STATE,
    get_session_id=lambda: _TELEMETRY_SESSION_ID,
    get_armed_snapshot=lambda: _ARMED_SNAPSHOT,
    get_writer=lambda: _WRITER,
    output=_output,
    get_armed_name=lambda: _ARMED_NAME,
    get_zone=lambda: _current_zone(),
)

_ARM_NATIVE_TO_CANONICAL = {
    "lab_e1": "LAB_E1",
    "lab_e1_fork": "LAB_E1_FORK",
    "home": "HOME",
}


def _dispatch_arm(*args, _session_id=0, **kwargs):
    if len(args) != 1 or kwargs:
        return False
    native_name = args[0]
    if type(native_name) is not str:
        return False
    canonical_name = _ARM_NATIVE_TO_CANONICAL.get(native_name)
    if canonical_name is None:
        return False
    return _cmd_arm(canonical_name, _connection=_session_id)


def _dispatch_disarm(*args, _session_id=0, **kwargs):
    global _RESUME_SAMPLING
    if args or kwargs:
        return False
    _RESUME_SAMPLING = False
    _clear_resume_pending()
    _forget_autosample()
    return _cmd_disarm(_connection=_session_id)


def _dispatch_start(*args, _session_id=0, **kwargs):
    global _RESUME_SAMPLING
    if args or kwargs:
        return False
    started = _cmd_start(_connection=_session_id)
    if started:
        _RESUME_SAMPLING = True  # D41: the User wants sampling, in whatever zone
        _remember_autosample()  # D47: and after a relaunch of this save
    return started


def _dispatch_stop(*args, _session_id=0, **kwargs):
    global _RESUME_SAMPLING
    if args or kwargs:
        _emit_stop_failure("STOP_DISPATCH_INVALID_SHAPE")
        return False
    _RESUME_SAMPLING = False
    _clear_resume_pending()
    _forget_autosample()
    return _cmd_stop(_connection=_session_id)


def _dispatch_e2_prepare(*args, _session_id=0, **kwargs):
    if len(args) != 1 or kwargs or type(args[0]) is not str:
        return False
    object_id = args[0]
    if not object_id.isdigit() or len(object_id) > 20:
        return False
    return _E2.cmd_prepare(object_id, _session_id)


def _dispatch_e2_sit(*args, _session_id=0, **kwargs):
    if len(args) != 1 or kwargs or type(args[0]) is not str:
        return False
    token = args[0]
    if len(token) != 16 or any(ch not in "0123456789abcdef" for ch in token):
        return False
    return _E2.cmd_sit(token, _session_id)


def _dispatch_e2_pause(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    return _E2.cmd_pause(_session_id)


def _dispatch_e2_release(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    return _E2.cmd_release(_session_id)


def _dispatch_e2_trial(*args, _session_id=0, **kwargs):
    if len(args) != 2 or kwargs:
        return False
    object_id, guid64 = args
    if type(object_id) is not str or type(guid64) is not str:
        return False
    if not object_id.isdigit() or not guid64.isdigit():
        return False
    if not (1 <= len(object_id) <= 20 and 1 <= len(guid64) <= 20):
        return False
    return _E2.cmd_trial(object_id, guid64, _session_id)


def _dispatch_e2_act(act_id, object_id, guid64, _session_id=0, owner=False, variant=None, sim_id=None):
    """8f: Ashley's chosen action (helper inbox only; cmdbox checked the shapes). 2.39.0 (W12 G1): variant names a pie
    choice of that act (cmd_act checks it). 2.40.0 (W13 P1): sim_id names the Sim a Sim picker takes (cmd_act checks it)."""
    return _E2.cmd_act(act_id, object_id, guid64, _session_id, owner=owner, variant=variant, sim_id=sim_id)


class _InboxReply:
    def __init__(self, issuer):
        self.issuer = issuer
        self.lines = []
        self.code = None


def _reject_code(lines):
    """The code of the first TRIAL_REJECT line, or None."""
    for line in lines:
        if type(line) is str and line.startswith("TRIAL_REJECT "):
            word = line[len("TRIAL_REJECT "):].split(" ")[0]
            return word[:64] or None
    return None


def _arm_inbox_zone(z, source):
    global _INBOX_ZONE, _INBOX_ARM_SOURCE
    if hasattr(z, "register_callback"):
        if any(armed is z for armed in _INBOX_ARMED_ZONES):
            return
        _INBOX_ZONE = z
        _INBOX_ARM_SOURCE = source
        _INBOX_ARMED_ZONES.append(z)
        try:
            # 6 is zone_types.ZoneState.RUNNING (no new import root).
            z.register_callback(6, _start_inbox_pump)
        except Exception:
            _INBOX_ARMED_ZONES.remove(z)
            raise


def _on_zone_added(z):
    try:
        _arm_inbox_zone(z, 'manager')
    except Exception:
        pass


def _try_arm_zone(source):
    global _INBOX_AUTOSTART
    try:
        m = _services_module.get_zone_manager()
        if m is None:
            if _INBOX_HANDLE is None:
                _INBOX_AUTOSTART = "MANAGER_UNAVAILABLE"
        elif not any(armed is m for armed in _INBOX_ARMED_MANAGERS):
            _INBOX_ARMED_MANAGERS.append(m)
            try:
                # 0 is indexed_manager.CallbackTypes.ON_OBJECT_ADD (no new import root).
                m.register_callback(0, _on_zone_added)
            except Exception:
                _INBOX_ARMED_MANAGERS.remove(m)
                return
    except Exception:
        return
    try:
        z = _services_module.current_zone()
        if z is not None:
            _arm_inbox_zone(z, source)
    except Exception:
        pass


def _register_autostart_hooks():
    try:
        import sims4.resources as resources
        _services_module.get_instance_manager(resources.Types.SNIPPET).add_on_load_complete(
            lambda *a, **k: _try_arm_zone('tuning'))
        _AUTOSTART_HOOKS['tuning'] = 'registered'
    except Exception:
        _AUTOSTART_HOOKS['tuning'] = 'failed'
    _try_arm_zone('tuning')
    for source in ('posture', 'household', 'transition'):
        try:
            import sims4.callback_utils as callbacks
            if source == 'posture':
                event = callbacks.CallbackEvent.POSTURE_GRAPH_BUILD_EXIT
            elif source == 'household':
                event = callbacks.CallbackEvent.HOUSEHOLD_EXIT
            else:
                event = callbacks.CallbackEvent.TRANSITION_SEQUENCE_EXIT
            callbacks.add_callbacks((event,),
                                    lambda *a, _source=source, **k: _try_arm_zone(_source))
            _AUTOSTART_HOOKS[source] = 'registered'
        except Exception:
            _AUTOSTART_HOOKS[source] = 'failed'
        _try_arm_zone(source)
    try:
        _try_arm_zone('import')
        _AUTOSTART_HOOKS['import'] = 'registered'
    except Exception:
        _AUTOSTART_HOOKS['import'] = 'failed'


def _start_inbox_pump(source=None):
    global _INBOX_HANDLE, _INBOX_STARTED_ZONE, _INBOX_AUTOSTART
    try:
        if _INBOX_HANDLE is not None and _INBOX_STARTED_ZONE is _INBOX_ZONE:
            return True
        if _INBOX_HANDLE is not None:
            alarms.cancel_alarm(_INBOX_HANDLE)
            _INBOX_HANDLE = None
            _INBOX_AUTOSTART = "NOT_STARTED"
        if _TELEMETRY_ROOT is None:
            return False
        for directory in ('inbox', 'outbox', 'done'):
            os.makedirs(os.path.join(_TELEMETRY_ROOT, 'cmd', directory), exist_ok=True)
        _INBOX_HANDLE = alarms.add_alarm_real_time(
            owner=_INBOX_ALARM_OWNER, time_span=interval_in_real_seconds(1),
            callback=_inbox_tick, repeating=True, use_sleep_time=False,
            cross_zone=False)
        _INBOX_STARTED_ZONE = _INBOX_ZONE
        _INBOX_AUTOSTART = "ZONE:" + (source or _INBOX_ARM_SOURCE)
    except Exception:
        return False
    try:
        _resume_sampling_in_zone()
    except Exception:
        pass
    return True


def _current_zone():
    try:
        return _services_module.current_zone()
    except Exception:
        return None


def _now_s():
    return time.monotonic()


def _autosample_path():
    return None if _TELEMETRY_ROOT is None else os.path.join(_TELEMETRY_ROOT, AUTOSAMPLE_FILE)


def _remember_autosample():
    """Write the save this sampling belongs to (after session_open has its identity)."""
    path = _autosample_path()
    if path is None or _ARMED_SNAPSHOT is None or not _RESUME_SAMPLING:
        return False
    return write_small_json(path, {
        "armed_name": _ARMED_NAME, "save_slot_guid": _ARMED_SNAPSHOT["guid"],
        "slot_id": _ARMED_SNAPSHOT["slot_id"], "sim_id": _ARMED_SNAPSHOT["sim_id"]})


def _forget_autosample():
    path = _autosample_path()
    if path is not None:
        remove_file(path)


def _autostart_from_memory(zone):
    """D47: while unarmed, once per zone: if the User's last start was for the save that
    is loaded now, arm and start again (AUTOSTARTED). Another save is never sampled."""
    global _AUTOSTART_TRIED_ZONE, _RESUME_SAMPLING
    if _STATE != "UNARMED" or _AUTOSTART_TRIED_ZONE is zone:
        return False
    path = _autosample_path()
    remembered = None if path is None else read_small_json(path)
    if remembered is None:
        _AUTOSTART_TRIED_ZONE = zone
        return False
    try:
        save = observers._save_snapshot()
    except Exception:
        return False  # the save is not readable yet; the next tick tries again
    if save.get("save_slot_guid") is None:
        return False
    _AUTOSTART_TRIED_ZONE = zone
    if type(remembered) is not dict or \
            remembered.get("armed_name") not in ARM_NAMES or \
            save.get("save_slot_guid") != remembered.get("save_slot_guid") or \
            save.get("slot_id") != remembered.get("slot_id"):
        return False
    if not _cmd_arm(remembered["armed_name"]):
        return False
    if not _cmd_start():
        return False
    _RESUME_SAMPLING = True
    _emit(schema.make_record("session_checkpoint", telemetry_session_id=_TELEMETRY_SESSION_ID,
                             wall_timestamp_ms=int(time.time() * 1000),
                             monotonic_ns=time.perf_counter_ns(),
                             checkpoint_reason="AUTOSTARTED"))
    return True


def _clear_resume_pending():
    global _RESUME_PENDING
    _RESUME_PENDING = False


def _cancel_quietly(handle):
    if handle is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        pass


def _resume_sampling_in_zone():
    """D41 (live, 2.14.0): each trip to another lot stopped sampling until the User
    started it again. The sampling alarm is not cross-zone (it goes with the zone that
    unloads), and on the loading screen there is no selectable body
    (LAB_IDENTITY_AMBIGUOUS:0). While the User's start holds, sampling resumes when the
    next zone is running, in the same session, after a ZONE_RESUMED checkpoint.

    D43 (live, 2.15.0): coming home, sampling resumed and then stopped a second later
    without a row. Real-time alarms outlive a lot change (TimeService.on_teardown
    filters only the sim timeline; bytecode time_service, alarms), so the old zone's
    timer kept ticking, and its next tick met the stale-handle guard, which stopped
    sampling. The old timer is now cancelled here, a stale tick only retires itself,
    a start that fails is reported and retried, and the inbox tick watches the rest."""
    global _STATE, _ALARM_HANDLE, _ZERO_BODY_TICKS, _RESUME_PENDING
    if not _RESUME_SAMPLING:
        return False
    zone = _current_zone()
    if _STATE == "SAMPLING":
        if zone is not None and _ALARM_ZONE is zone:
            return True
        old = _ALARM_HANDLE
        _ALARM_HANDLE = None  # it belonged to the zone that unloaded
        _cancel_quietly(old)
        _STATE = "ARMED"
        _set_writer_sampling(False)
        _E2.on_stop("ZONE_CHANGE")
    if _STATE != "ARMED":
        return False
    if zone is None:
        _RESUME_PENDING = True  # no zone yet; the inbox tick tries again
        return False
    _ZERO_BODY_TICKS = 0
    if _cmd_start():
        _RESUME_PENDING = False
        _emit(schema.make_record("session_checkpoint",
                                 telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000),
                                 monotonic_ns=time.perf_counter_ns(),
                                 checkpoint_reason="ZONE_RESUMED"))
        return True
    if not _RESUME_PENDING:
        _emit(schema.make_record("guard_exhausted", telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000),
                                 monotonic_ns=time.perf_counter_ns(),
                                 reason="ZONE_RESUME_FAILED"))
    _RESUME_PENDING = True
    return False


def _supervise_sampling():
    """D43: run from the inbox tick, which the game restarts in every zone. While the
    User's start holds, sampling is kept alive: a pending resume is retried, a zone
    change not yet seen is resumed, and a sampler that stopped ticking is restarted
    after a SAMPLER_RESTARTED checkpoint. A pause of the whole game (the inbox tick
    was late too) is not a stall."""
    global _STATE, _ALARM_HANDLE, _LAST_TICK_S, _LAST_SUPERVISE_S, _LAST_RESTART_S
    now = _now_s()
    game_stalled = (_LAST_SUPERVISE_S is not None and
                    now - _LAST_SUPERVISE_S > SAMPLER_STALL_SECONDS / 2)
    _LAST_SUPERVISE_S = now
    zone = _current_zone()
    if zone is None:
        return False
    if _STATE == "UNARMED":
        return _autostart_from_memory(zone)
    if not _RESUME_SAMPLING:
        return False
    if _STATE == "ARMED":
        return _resume_sampling_in_zone() if _RESUME_PENDING else False
    if _STATE != "SAMPLING":
        return False
    if _ALARM_ZONE is not zone:
        return _resume_sampling_in_zone()
    if game_stalled or _LAST_TICK_S is None:
        _LAST_TICK_S = now
        return True
    if now - _LAST_TICK_S < SAMPLER_STALL_SECONDS:
        return True
    if _LAST_RESTART_S is not None and now - _LAST_RESTART_S < SAMPLER_RESTART_SPACING:
        return False
    _LAST_RESTART_S = now
    old = _ALARM_HANDLE
    _ALARM_HANDLE = None
    _cancel_quietly(old)
    _STATE = "ARMED"
    _emit(schema.make_record("session_checkpoint", telemetry_session_id=_TELEMETRY_SESSION_ID,
                             wall_timestamp_ms=int(time.time() * 1000),
                             monotonic_ns=time.perf_counter_ns(),
                             checkpoint_reason="SAMPLER_RESTARTED"))
    return _cmd_start()


def _dispatch_inbox(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    global _INBOX_AUTOSTART
    if _INBOX_HANDLE is not None and _INBOX_STARTED_ZONE is _INBOX_ZONE:
        source = (_INBOX_AUTOSTART[5:] if _INBOX_AUTOSTART.startswith('ZONE:')
                  else _INBOX_AUTOSTART)
        _output('INBOX ON (already, %s)' % source, _session_id)
        return True
    if not _start_inbox_pump('import'):
        return False
    _INBOX_AUTOSTART = 'CONSOLE'
    _output('INBOX ON', _session_id)
    return True


def _dispatch_status(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    _output('state: %s inbox: %s' % (_STATE, 'on' if _INBOX_HANDLE is not None else 'off'),
            _session_id)
    return True


def _inbox_status():
    return dict(state=_STATE, armed_name=_ARMED_NAME, calibrate=_CALIBRATE,
                probe_version=E1_PROBE_VERSION, schema_version=schema.OBSERVATION_SCHEMA_VERSION,
                signatures=dict(_E2.learner.signatures),
                continuation={key: sorted(value) for key, value in _E2.learner.continuation.items()},
                lineage_class=_E2.lineage_class, designated_sim_id=_E2.designated_sim_id,
                verdicts=[dict(row) for row in _INBOX_VERDICTS], inbox='on',
                inbox_autostart=_INBOX_AUTOSTART, inbox_errors=_INBOX_ERRORS,
                motive_diag=observers.motive_diag(),
                atlas=_atlas_progress(), tuned=_tuned_progress(),
                preflight=_scan_progress(_PREFLIGHT), food=_scan_progress(_FOOD),
                situation=_scan_progress(_SITUATION),
                telemetry_dir=dict(zip(("bytes", "cap"), _telemetry_dir())),
                autosample=_autosample_path() is not None and
                os.path.exists(_autosample_path()))


_IDLE_SCAN = {"state": "idle", "done": 0, "total": 0, "chunks": 0, "max_chunk_ms": 0,
              "file": None}
# D22 (live 2026-10-04): a 6025-row preflight at one 5 ms chunk per second took
# ten minutes and looked stuck. Same budget per chunk, four chunks per second
# (clock.interval_in_real_seconds -> TimeSpan(ceil(seconds * 1000)) takes a float).
SCAN_TICK_S = 0.25


def _scan_progress(scan):
    if scan is None:
        return dict(_IDLE_SCAN)
    return scan.progress()


def _refuse_observe_only(connection, name):
    connection.code = "CALIBRATE_OBSERVE_ONLY"
    _INBOX_VERDICTS.append({
        "phase": "VERDICT", "code": "CALIBRATE_OBSERVE_ONLY",
        "experiment_id": None, "detail": name})
    del _INBOX_VERDICTS[:-5]
    return False


def _pace_block(row):
    """2.31.0 (W3p): her pace as the probe applies it for this observation (never raises: None on a fault)."""
    try:
        return _E2.pace_row(row)
    except Exception:
        return None


def _inbox_dispatch(cmd, connection):
    name, args = cmd['command'], cmd['args']
    if _CALIBRATE and name in _OBSERVE_REFUSED:
        return _refuse_observe_only(connection, name)
    if name == 'calibrate':
        return _cmd_calibrate(connection)
    if name == 'arm':
        return _dispatch_arm(args['name'], _session_id=connection)
    if name == 'prepare':
        return _dispatch_e2_prepare(args['object_id'], _session_id=connection)
    if name == 'sit':
        return _dispatch_e2_sit(args['token'], _session_id=connection)
    if name == 'sit_trial':
        if not _dispatch_e2_prepare(args['object_id'], _session_id=connection):
            return False
        return _dispatch_e2_sit(_E2.last_prepared_token, _session_id=connection)
    if name == 'trial':
        return _dispatch_e2_trial(args['object_id'], args['guid64'], _session_id=connection)
    if name == 'act':
        return _dispatch_e2_act(args['act_id'], args['object_id'], args['guid64'],
                                _session_id=connection, owner=args.get('owner') is True,
                                variant=args.get('variant'), sim_id=args.get('sim_id'))
    # 2.40.0 (W13 P1): her trip, her planned event, and a fresh read of the lists. Own lines, so other blocks merge.
    if name == 'go':
        return _E2.cmd_go(args['act_id'], args['zone_id'], connection, _KNOWN_ZONES)
    if name == 'event':
        return _E2.cmd_event(args['act_id'], args['situation_id'], args['guests'], args['start'], connection)
    if name == 'lists_now':
        return request_lists_now()
    if name == 'answer':
        return _E2.cmd_answer(args['act_id'], args['dialog_id'], args['pick'], connection,
                              rows=args.get('rows'), text=args.get('text'))
    if name == 'cancel':
        return _E2.cmd_cancel(args['act_id'], args['interaction_id'], connection)
    if name == 'camera':
        return _E2.cmd_camera(args['op'], args['target_id'], connection)
    if name == 'talk':
        return _E2.cmd_talk(args['text'], args.get('sim_id'), connection)
    if name == 'pace':
        return _E2.cmd_pace(args['need_drain'], args['slow_time'], connection)
    if name in home.COMMANDS:
        # 2.40.0 (W13 P2, home): her save, her home edits and the catalogue dump (home.py answers each).
        return home.dispatch(_E2, name, args, connection)
    if name == 'menu_near':
        return request_menu_near()
    if name == 'atlas_dump':
        return _dispatch_atlas_dump(connection)
    if name == 'tuned_scan':
        return _dispatch_tuned_scan(connection)
    if name == 'preflight':
        return _dispatch_preflight(connection)
    if name == 'food_scan':
        return _dispatch_food_scan(connection)
    if name == 'situation_scan':
        return _dispatch_situation_scan(connection)
    dispatchers = {'start': _dispatch_start, 'stop': _dispatch_stop,
                   'disarm': _dispatch_disarm, 'pause': _dispatch_e2_pause,
                   'release': _dispatch_e2_release, 'status': _dispatch_status}
    return dispatchers[name](_session_id=connection)


def _atlas_progress():
    if _ATLAS is None:
        return {"state": "idle", "done": 0, "total": 0, "chunks": 0,
                "max_chunk_ms": 0, "file": None}
    return _ATLAS.progress()


def _cancel_atlas():
    global _ATLAS_HANDLE
    handle = _ATLAS_HANDLE
    _ATLAS_HANDLE = None
    if handle is None or alarms is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        return


def _interaction_classes():
    try:
        import services
        import sims4.resources as resources
    except ImportError:
        return None, "ATLAS_NO_MANAGER"
    try:
        managers = services.tuning_managers
    except AttributeError:
        return None, "ATLAS_NO_MANAGER"
    if managers is None:
        return None, "ATLAS_NO_MANAGER"
    try:
        manager = dict.get(managers, resources.Types.INTERACTION)
    except (AttributeError, TypeError):
        return None, "ATLAS_NO_MANAGER"
    if manager is None:
        return None, "ATLAS_NO_MANAGER"
    try:
        loaded = manager.all_instances_loaded
    except AttributeError:
        return None, "ATLAS_NOT_LOADED"
    if loaded is not True:
        return None, "ATLAS_NOT_LOADED"
    try:
        classes = manager._tuned_classes
    except AttributeError:
        return None, "ATLAS_NOT_LOADED"
    return classes, None


def _dispatch_atlas_dump(connection):
    global _ATLAS, _ATLAS_HANDLE
    if _INBOX_HANDLE is None:
        connection.code = "ATLAS_NO_PUMP"
        return False
    if _ATLAS is not None and _ATLAS.state == "running":
        connection.code = "ATLAS_BUSY"
        return False
    classes, code = _interaction_classes()
    if code is not None:
        connection.code = code
        return False
    folder = os.path.join(_TELEMETRY_ROOT, "atlas")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "tuning_%s.jsonl" % SIMS_BUILD)
    _ATLAS = atlas.AtlasDump(classes, path)
    _ATLAS_HANDLE = alarms.add_alarm_real_time(
        owner=_ATLAS_ALARM_OWNER, time_span=interval_in_real_seconds(SCAN_TICK_S),
        callback=_atlas_tick, repeating=True, use_sleep_time=False,
        cross_zone=False)
    return True


def _tuned_progress():
    if _TUNED is None:
        return {"state": "idle", "done": 0, "total": 0, "chunks": 0,
                "max_chunk_ms": 0, "file": None}
    return _TUNED.progress()


def _cancel_tuned():
    global _TUNED_HANDLE
    handle = _TUNED_HANDLE
    _TUNED_HANDLE = None
    if handle is None or alarms is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        return


def _lot_affordances(obj, context):
    """D35 (live: a served grilled cheese offered no eat; generic_consume_food comes
    from its consumable component, not class tuning): the class-tuned list, then
    what the object offers through its components, once per guid."""
    listed = list(tuned.affordances_of(obj))
    seen = set()
    for affordance in listed:
        seen.add(tuned._class_plain(affordance, "guid64"))
    try:
        extra = e2_actuator.offered(obj, context)
    except Exception:
        extra = []
    for affordance in extra:
        guid = tuned._class_plain(affordance, "guid64")
        if type(guid) is int and guid not in seen:
            seen.add(guid)
            listed.append(affordance)
    return listed


def _lot_snapshot():
    if _services_module is None:
        return None, "TUNED_NO_LOT"
    try:
        manager = _services_module.object_manager()
    except AttributeError:
        return None, "TUNED_NO_LOT"
    if manager is None:
        return None, "TUNED_NO_LOT"
    try:
        objects = manager._objects
    except AttributeError:
        return None, "TUNED_NO_LOT"
    try:
        values = dict.values(objects)
    except (AttributeError, TypeError):
        return None, "TUNED_NO_LOT"
    return list(values), None


def _dispatch_tuned_scan(connection):
    global _TUNED, _TUNED_HANDLE
    if _INBOX_HANDLE is None:
        connection.code = "TUNED_NO_PUMP"
        return False
    if _TUNED is not None and _TUNED.state == "running":
        connection.code = "TUNED_BUSY"
        return False
    snapshot, code = _lot_snapshot()
    if code is not None:
        connection.code = code
        return False
    folder = os.path.join(_TELEMETRY_ROOT, "atlas")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(
        folder, "tuned_%s_%d.jsonl" % (SIMS_BUILD, int(time.time() * 1000)))
    _TUNED = tuned.TunedScan(snapshot, path)
    _TUNED_HANDLE = alarms.add_alarm_real_time(
        owner=_TUNED_ALARM_OWNER, time_span=interval_in_real_seconds(SCAN_TICK_S),
        callback=_tuned_tick, repeating=True, use_sleep_time=False,
        cross_zone=False)
    return True


def _dispatch_preflight(connection):
    """A28: ask the game which tuned offers it would refuse. No push."""
    global _PREFLIGHT, _PREFLIGHT_HANDLE
    if _STATE not in ("ARMED", "SAMPLING"):
        connection.code = "PREFLIGHT_UNARMED"
        return False
    if _ARMED_NAME not in ("LAB_E1", "LAB_E1_FORK"):
        connection.code = "PREFLIGHT_NOT_LAB"
        return False
    if _INBOX_HANDLE is None:
        connection.code = "PREFLIGHT_NO_PUMP"
        return False
    if _PREFLIGHT is not None and _PREFLIGHT.state == "running":
        connection.code = "PREFLIGHT_BUSY"
        return False
    snapshot, code = _lot_snapshot()
    if code is not None:
        connection.code = code
        return False
    try:
        sim_info, sim = observers.select_lab_body(
            _services_module.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
    except Exception:
        connection.code = "PREFLIGHT_NO_SIM"
        return False
    del sim_info
    context = e2_actuator.build_context(sim)
    jobs = []
    for obj in snapshot:
        found = tuned._plain(obj, "id", True)
        object_id = None if type(found) is not int else str(found)
        if object_id is None:
            try:
                object_id = str(int(found))
            except (TypeError, ValueError):
                object_id = None
        for affordance in _lot_affordances(obj, context):
            guid = tuned._class_plain(affordance, "guid64")
            if type(guid) is not int:
                continue
            try:
                name = affordance.__name__
            except Exception:
                name = ""
            if type(name) is not str:
                name = ""
            excluded = e2_actuator.excluded(affordance)
            if object_id in e2_control.EXCLUDED_OBJECT_IDS:
                # D31 (live: the crawl spent a trial and a rate slot on sofa_Nap, then
                # TRIAL_REJECT OBJECT_EXCLUDED): the E1 witness sofa is never a target.
                excluded = e2_admission.OBJECT_EXCLUDED
            jobs.append({
                "object_id": object_id, "guid64": guid, "name": name[:128],
                "obj": obj, "affordance": affordance,
                "excluded": excluded,
            })

    def _run(job, _sim=sim, _context=context):
        excluded = job["excluded"]
        if excluded is not None:
            ok, reason, reason_key = False, excluded, None
        else:
            ok, reason, reason_key = e2_actuator.preflight_test(
                _sim, job["obj"], job["affordance"], _context)
        return {
            "kind": "preflight", "object_id": job["object_id"],
            "guid64": job["guid64"], "name": job["name"],
            "ok": bool(ok), "reason": reason, "reason_key": reason_key,
        }

    folder = os.path.join(_TELEMETRY_ROOT, "atlas")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(
        folder, "preflight_%s_%d.jsonl" % (SIMS_BUILD, int(time.time() * 1000)))
    _PREFLIGHT = preflight.PreflightScan(jobs, path, _run)
    _PREFLIGHT_HANDLE = alarms.add_alarm_real_time(
        owner=_PREFLIGHT_ALARM_OWNER, time_span=interval_in_real_seconds(SCAN_TICK_S),
        callback=_preflight_tick, repeating=True, use_sleep_time=False,
        cross_zone=False)
    return True


def _flag_value(value):
    if type(value) is bool or (type(value) is int and value in (0, 1)):
        return value
    return None


def _food_affordance_row(affordance, object_id):
    """One try for the whole read. A raising field becomes an error row."""
    try:
        guid = affordance.guid64
        guid = int(guid) if type(guid) is int else None
        name = affordance.__name__
        if type(name) is not str:
            name = ""
        mro = []
        for cls in e2_actuator._mro(affordance):
            mro.append(str(cls.__name__))
        # D1 (live 2026-10-04, 704/704 rows AttributeError): these exist only on some
        # classes (bytecode: favorite_recipe on crafting, auto_pick on object pickers,
        # use_pie_menu on PickerSuperInteractionMixin). Absent is data, not an error.
        try:
            favorite_none = affordance.favorite_recipe is None
        except AttributeError:
            favorite_none = None
        try:
            auto = affordance.auto_pick
        except AttributeError:
            auto = None
        auto_name = None if auto is None else type(auto).__name__
        try:
            pie = affordance.use_pie_menu
        except AttributeError:
            pie = None
        use_pie = bool(pie()) if callable(pie) else None
        try:
            user_directed = affordance.allow_user_directed
        except AttributeError:
            user_directed = None
        try:
            autonomous = affordance.allow_autonomous
        except AttributeError:
            autonomous = None
        return {
            "kind": "food_affordance",
            "object_id": object_id,
            "guid64": guid,
            "name": name[:128],
            "mro": mro,
            "excluded": e2_actuator.excluded(affordance),
            "food_route": e2_actuator.food_route(affordance),
            "allow_user_directed": _flag_value(user_directed),
            "allow_autonomous": _flag_value(autonomous),
            "use_pie_menu": use_pie,
            "favorite_recipe_is_none": favorite_none,
            "auto_pick": auto_name,
        }
    except Exception as error:
        return {"kind": "food_affordance", "object_id": object_id,
                "error": food.error_text(error)}


def _recipe_name(tag):
    """D19 (live: every recipe read 'TuningBlueprint'): a menu tag is a lazy
    TuningBlueprint instance (bytecode sims4/tuning/instances: __name__ is a property,
    tuning_name a slot). Its own name first, the class name last."""
    for read in (lambda: tag.__name__, lambda: tag.tuning_name):
        try:
            value = read()
        except AttributeError:
            continue
        if type(value) is str and value:
            return value
    return type(tag).__name__


def _has_menu(affordance):
    """D20 (live: the stove's first crafting class was autonomous and has no
    picker_rows_gen): only a class that offers a picker can show a menu."""
    try:
        affordance.picker_rows_gen
    except AttributeError:
        return False
    return True


def _food_menu_rows(affordance, obj, context, object_id, guid):
    # D2: picker_rows_gen is a flexmethod; __get__ binds (cls, None) already
    # (bytecode sims4/utils: partial(func, owner, instance)). Pass target, context.
    try:
        generated = iter(affordance.picker_rows_gen(obj, context))
    except Exception as error:
        return [{
            "kind": "food_menu", "object_id": object_id, "guid64": guid,
            "error": food.error_text(error),
        }]
    rows = []
    while len(rows) < food.MENU_CAP:
        try:
            item = next(generated)
        except StopIteration:
            break
        except Exception as error:
            rows.append({
                "kind": "food_menu", "object_id": object_id, "guid64": guid,
                "error": food.error_text(error),
            })
            break
        try:
            tag = item.tag
            recipe_name = _recipe_name(tag)
            rows.append({
                "kind": "food_menu",
                "object_id": object_id,
                "guid64": guid,
                "recipe_guid64": item.recipe_id,
                "recipe_name": recipe_name,
                "is_enable": bool(item.is_enable),
                "price": item.price,
                "skill_level": item.skill_level,
            })
        except Exception as error:
            rows.append({
                "kind": "food_menu", "object_id": object_id, "guid64": guid,
                "error": food.error_text(error),
            })
    return rows


def _dispatch_food_scan(connection):
    """A30: read food affordances and one crafting menu per object. No push."""
    global _FOOD, _FOOD_HANDLE
    if _STATE not in ("ARMED", "SAMPLING"):
        connection.code = "FOOD_UNARMED"
        return False
    if _ARMED_NAME not in ("LAB_E1", "LAB_E1_FORK"):
        connection.code = "FOOD_NOT_LAB"
        return False
    if _INBOX_HANDLE is None:
        connection.code = "FOOD_NO_PUMP"
        return False
    if _FOOD is not None and _FOOD.state == "running":
        connection.code = "FOOD_BUSY"
        return False
    snapshot, code = _lot_snapshot()
    if code is not None:
        connection.code = code
        return False
    try:
        sim_info, sim = observers.select_lab_body(
            _services_module.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
    except Exception:
        connection.code = "FOOD_NO_SIM"
        return False
    del sim_info
    context = e2_actuator.build_context(sim)
    jobs = []
    menus = {}
    for obj in snapshot:
        found = tuned._plain(obj, "id", True)
        object_id = None if type(found) is not int else str(found)
        if object_id is None:
            try:
                object_id = str(int(found))
            except (TypeError, ValueError):
                object_id = None
        for affordance in _lot_affordances(obj, context):
            try:
                guid = affordance.guid64
                name = affordance.__name__
            except Exception:
                jobs.append({"object_id": object_id, "guid64": None, "affordance": affordance,
                             "obj": obj, "broken": True})
                continue
            if type(guid) is not int:
                continue
            if type(name) is not str:
                name = ""
            if not food.name_hit(name, guid):
                continue
            jobs.append({
                "object_id": object_id, "guid64": guid, "name": name[:128],
                "obj": obj, "affordance": affordance,
            })
            mro_names = []
            for cls in e2_actuator._mro(affordance):
                try:
                    mro_names.append(cls.__name__)
                except Exception:
                    continue
            if object_id not in menus and any(
                    type(item) is str and item.startswith("StartCrafting")
                    for item in mro_names) and _has_menu(affordance):
                menus[object_id] = {
                    "menu": True, "object_id": object_id, "guid64": guid,
                    "obj": obj, "affordance": affordance,
                }
    jobs.extend(menus.values())

    def _run(job, _context=context):
        if job.get("broken"):
            raise RuntimeError("unreadable")
        if job.get("menu"):
            return _food_menu_rows(
                job["affordance"], job["obj"], _context, job["object_id"], job["guid64"])
        return _food_affordance_row(job["affordance"], job["object_id"])

    folder = os.path.join(_TELEMETRY_ROOT, "atlas")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(
        folder, "food_%s_%d.jsonl" % (SIMS_BUILD, int(time.time() * 1000)))
    _FOOD = food.FoodScan(jobs, path, _run)
    _FOOD_HANDLE = alarms.add_alarm_real_time(
        owner=_FOOD_ALARM_OWNER, time_span=interval_in_real_seconds(SCAN_TICK_S),
        callback=_food_tick, repeating=True, use_sleep_time=False,
        cross_zone=False)
    return True


def _dispatch_situation_scan(connection):
    """S1: what is on the lot, as the game holds it. Plain reads; no tests, no push."""
    global _SITUATION, _SITUATION_HANDLE
    if _STATE not in ("ARMED", "SAMPLING"):
        connection.code = "SITUATION_UNARMED"
        return False
    if _ARMED_NAME not in ("LAB_E1", "LAB_E1_FORK"):
        connection.code = "SITUATION_NOT_LAB"
        return False
    if _INBOX_HANDLE is None:
        connection.code = "SITUATION_NO_PUMP"
        return False
    if _SITUATION is not None and _SITUATION.state == "running":
        connection.code = "SITUATION_BUSY"
        return False
    snapshot, code = _lot_snapshot()
    if code is not None:
        connection.code = code
        return False
    try:
        ticks = _services_module.time_service().sim_now.absolute_ticks()
    except Exception:
        ticks = None
    header = {}
    try:
        sim_info, sim = observers.select_lab_body(
            _services_module.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        header["body_id"] = str(sim_info.id)
        header["body"] = observers.zone_snapshot(sim)
    except Exception:
        header["body"] = None
    folder = os.path.join(_TELEMETRY_ROOT, "atlas")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(
        folder, "situation_%s_%d.jsonl" % (SIMS_BUILD, int(time.time() * 1000)))
    _SITUATION = situation.SituationScan(snapshot, path, ticks if type(ticks) is int else None,
                                         header=header)
    _SITUATION_HANDLE = alarms.add_alarm_real_time(
        owner=_SITUATION_ALARM_OWNER, time_span=interval_in_real_seconds(SCAN_TICK_S),
        callback=_situation_tick, repeating=True, use_sleep_time=False,
        cross_zone=False)
    return True


def _situation_tick(alarm_handle=None):
    try:
        if _SITUATION is None or _SITUATION.state != "running":
            _cancel_situation()
            return
        _SITUATION.step()
        if _SITUATION.state != "running":
            _cancel_situation()
    except Exception:
        if _SITUATION is not None:
            _SITUATION.state = "error"
        _cancel_situation()


def _cancel_situation():
    global _SITUATION_HANDLE
    handle = _SITUATION_HANDLE
    _SITUATION_HANDLE = None
    if handle is None or alarms is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        return


def _food_tick(alarm_handle=None):
    try:
        if _FOOD is None or _FOOD.state != "running":
            _cancel_food()
            return
        _FOOD.step()
        if _FOOD.state != "running":
            _cancel_food()
    except Exception:
        if _FOOD is not None:
            _FOOD.state = "error"
        _cancel_food()


def _cancel_food():
    global _FOOD_HANDLE
    handle = _FOOD_HANDLE
    _FOOD_HANDLE = None
    if handle is None or alarms is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        return


def _preflight_tick(alarm_handle=None):
    try:
        if _PREFLIGHT is None or _PREFLIGHT.state != "running":
            _cancel_preflight()
            return
        _PREFLIGHT.step()
        if _PREFLIGHT.state != "running":
            _cancel_preflight()
    except Exception:
        if _PREFLIGHT is not None:
            _PREFLIGHT.state = "error"
        _cancel_preflight()


def _cancel_preflight():
    global _PREFLIGHT_HANDLE
    handle = _PREFLIGHT_HANDLE
    _PREFLIGHT_HANDLE = None
    if handle is None or alarms is None:
        return
    try:
        alarms.cancel_alarm(handle)
    except Exception:
        return


def _tuned_tick(alarm_handle=None):
    try:
        if _TUNED is None or _TUNED.state != "running":
            _cancel_tuned()
            return
        _TUNED.step()
        if _TUNED.state != "running":
            _cancel_tuned()
    except Exception:
        if _TUNED is not None:
            _TUNED.state = "error"
        _cancel_tuned()


def _atlas_tick(alarm_handle=None):
    try:
        if _ATLAS is None or _ATLAS.state != "running":
            _cancel_atlas()
            return
        _ATLAS.step()
        if _ATLAS.state != "running":
            _cancel_atlas()
    except Exception:
        if _ATLAS is not None:
            _ATLAS.state = "error"
        _cancel_atlas()


def _inbox_tick(alarm_handle=None):
    global _INBOX_BUSY, _INBOX_ERRORS
    if _INBOX_HANDLE is None or _INBOX_BUSY:
        return
    if alarm_handle is not None and alarm_handle is not _INBOX_HANDLE:
        return
    _INBOX_BUSY = True
    try:
        _inbox_tick_body()
    except Exception:
        _INBOX_ERRORS += 1
    try:
        _supervise_sampling()
    except Exception:
        _INBOX_ERRORS += 1
    finally:
        _INBOX_BUSY = False


_INBOX_SCAN = 64


def _issued_key(path, name):
    """2.33.0 (A9-11): (no readable issue time, issue time, name). A command read from its envelope sorts by when it was issued."""
    try:
        raw = read_command_file(path)
        envelope = cmdbox.decode(raw) if len(raw) <= 4096 else None
    except (OSError, ValueError, UnicodeError, RecursionError):
        envelope = None
    issued = envelope.get('issued_at_ms') if type(envelope) is dict else None
    issued_ok = type(issued) is int
    return (not issued_ok, issued if issued_ok else 0, name)


def _expired_act_event(identity):
    """2.33.0 (A9-11): an act that came too late is refused as an act: Ashley hears REJECTED, code EXPIRED, for its id,
    not only a command reply (the helper never hears the reply)."""
    args = identity.get('args')
    act_id = args.get('act_id') if type(args) is dict else None
    if not isinstance(act_id, str) or not act_id or len(act_id) > 64 or _WRITER is None or _WRITER_IDLE:
        return False
    body = dict((key, None) for key in schema.E2_PAYLOAD_KEYS['act_event'])
    body.update(act_id=act_id, phase='REJECTED', code='EXPIRED')
    try:
        row = schema.make_record('act_event', telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000), monotonic_ns=time.perf_counter_ns(), e2=body)
    except schema.SchemaError:
        return False
    return _emit(row)


def _inbox_tick_body():
    global _INBOX_ERRORS
    root = os.path.join(_TELEMETRY_ROOT, 'cmd')
    inbox = os.path.join(root, 'inbox')
    try:
        names = sorted(name for name in os.listdir(inbox) if name.endswith('.json'))[:_INBOX_SCAN]
    except OSError:
        return
    # 2.33.0 (A9-11): the oldest command goes first, by when it was issued, not by its random file name.
    names = sorted(names, key=lambda name: _issued_key(os.path.join(inbox, name), name))[:4]
    for name in names:
        path = os.path.join(inbox, name)
        taken = path + '.taken'
        command_id = uuid.uuid4().hex
        identity = None
        error_reply_written = False
        try:
            try:
                os.replace(path, taken)
            except OSError:
                continue
            raw = read_command_file(taken)
            cmd, code = cmdbox.parse(raw, int(time.time() * 1000), _INBOX_USED_IDS)
            # A rejected JSON still needs a safe reply name. An invalid/missing id
            # gets a fresh local id, never an untrusted pathname component.
            identity = cmd
            if identity is None:
                try:
                    identity = cmdbox.decode(raw)
                except (ValueError, UnicodeError, RecursionError):
                    identity = None
            if type(identity) is dict and cmdbox.valid_hex(identity.get('id'), 32):
                command_id = identity['id']
            else:
                command_id = uuid.uuid4().hex
            if cmd is None and code == 'EXPIRED' and type(identity) is dict and identity.get('command') == 'act':
                _expired_act_event(identity)
            done = os.path.join(root, 'done', command_id + '.json')
            persistent_replay = os.path.exists(done)
            if persistent_replay:
                cmd, code = None, 'REPLAYED'
            status, result = 'REJECTED', {'ok': False, 'lines': []}
            if cmd is not None:
                _INBOX_USED_IDS.add(command_id)
                connection = _InboxReply(cmd['issuer'])
                try:
                    ok = bool(_inbox_dispatch(cmd, connection))
                    status = 'OK' if ok else 'REJECTED'
                    if not ok and connection.code:
                        code = connection.code
                    elif not ok:
                        # D34 (live: a BODY_BUSY trial refusal replied REJECTED with
                        # code null; the reason lived only in its TRIAL_REJECT line).
                        code = _reject_code(connection.lines)
                    result = (_inbox_status() if cmd['command'] == 'status' else
                              {'ok': ok, 'lines': connection.lines})
                except Exception as error:
                    _INBOX_ERRORS += 1
                    status, code = 'ERROR', type(error).__name__[:64]
                    result = {'ok': False, 'lines': connection.lines}
            else:
                _INBOX_USED_IDS.add(command_id)
            issuer = identity.get('issuer') if type(identity) is dict else None
            payload = cmdbox.attribute_reply(
                cmdbox.reply(command_id, status, code, result), issuer)
            write_command_reply(os.path.join(root, 'outbox', command_id + '.json'), payload)
            error_reply_written = status == 'ERROR'
            # Retain the original completion marker on a persistent replay.
            if persistent_replay:
                os.remove(taken)
            else:
                os.replace(taken, done)
            if (_WRITER is not None and not _WRITER_IDLE and
                    type(identity) is dict and cmdbox.valid_issuer(identity.get('issuer')) and
                    identity.get('command') in cmdbox.COMMANDS):
                _emit(schema.make_record('command_event',
                    telemetry_session_id=_TELEMETRY_SESSION_ID,
                    wall_timestamp_ms=int(time.time() * 1000), monotonic_ns=time.perf_counter_ns(),
                    e2=dict(id=command_id, issuer=identity['issuer'], command=identity['command'],
                            status=status, code=code)))
        except Exception as error:
            _INBOX_ERRORS += 1
            if not error_reply_written:
                try:
                    issuer = identity.get('issuer') if type(identity) is dict else None
                    payload = cmdbox.attribute_reply(
                        cmdbox.reply(command_id, 'ERROR', type(error).__name__[:64],
                                     {'ok': False, 'lines': []}), issuer)
                    write_command_reply(
                        os.path.join(root, 'outbox', command_id + '.json'), payload)
                except Exception:
                    pass
            try:
                done = os.path.join(root, 'done', command_id + '.json')
                if os.path.exists(done):
                    os.remove(taken)
                else:
                    os.replace(taken, done)
            except Exception:
                pass
            continue


def _register_commands():
    if register is None or CommandType is None or CommandRestrictionFlags is None:
        return False
    register('ashley_e1.inbox', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_inbox, 'Start the local command inbox.',
             'ashley_e1.inbox', CommandType.Live)
    register('ashley_e1.status', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_status, 'Report probe and inbox state.',
             'ashley_e1.status', CommandType.Live)
    register('ashley_e1.arm', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_arm, 'Arm the Ashley E1 probe in LAB_E1, LAB_E1_FORK or HOME.',
             'ashley_e1.arm LAB_E1 | ashley_e1.arm LAB_E1_FORK | ashley_e1.arm HOME', CommandType.Live)
    register('ashley_e1.disarm', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_disarm, 'Disarm the Ashley E1 probe and close the session.',
             'ashley_e1.disarm', CommandType.Live)
    register('ashley_e1.start', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_start, 'Start Ashley E1 1 Hz sampling.',
             'ashley_e1.start', CommandType.Live)
    register('ashley_e1.stop', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_stop, 'Stop Ashley E1 sampling (remains armed).',
             'ashley_e1.stop', CommandType.Live)
    register('ashley_e2.prepare', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_e2_prepare, 'Prepare one E2 sit experiment on an object id.',
             'ashley_e2.prepare <object_id>', CommandType.Live)
    register('ashley_e2.sit', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_e2_sit, 'Admit and push one prepared E2 sit experiment.',
             'ashley_e2.sit <token>', CommandType.Live)
    register('ashley_e2.pause', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_e2_pause, 'Push the E2 probe pause request.',
             'ashley_e2.pause', CommandType.Live)
    register('ashley_e2.release', CommandRestrictionFlags.UNRESTRICTED,
             _dispatch_e2_release, 'Remove the E2 probe pause request.',
             'ashley_e2.release', CommandType.Live)
    return True


def _required_import_summary():
    return {
        "alarms": alarms is not None,
        "alarms.add_alarm_real_time": callable(_alarms_add_alarm_real_time),
        "alarms.cancel_alarm": callable(_alarms_cancel_alarm),
        "clock": clock is not None,
        "clock.interval_in_real_seconds": callable(interval_in_real_seconds),
        "date_and_time": date_and_time is not None,
        "date_and_time.TimeSpan": callable(TimeSpan),
        "services": _services_module is not None,
        "services.sim_info_manager": callable(_services_sim_info_manager),
        "services.client_manager": callable(_services_client_manager),
        "server.clientmanager": _clientmanager_module is not None,
        "sims.sim.Sim": _Sim is not None,
        "sims.sim_info.SimInfo": _SimInfo is not None,
        "interactions.context": _interaction_context_module is not None,
        "interactions.context.InteractionContext": _interaction_context_type is not None,
        "sims4.commands": _commands_module is not None,
        "sims4.commands.CommandType": CommandType is not None,
        "sims4.commands.CommandRestrictionFlags": CommandRestrictionFlags is not None,
        "sims4.commands.register": callable(register),
        "sims4.commands.output": callable(_commands_output),
        "e2.actuator": e2_control.e2_actuator is not None,
    }


def initialize_probe():
    global _INITIALIZED, _TELEMETRY_ROOT, _INBOX_AUTOSTART
    if _INITIALIZED:
        return
    _STATE_RESET()
    command_registration_result = _register_commands()
    if not command_registration_result:
        return
    _INITIALIZED = True
    _TELEMETRY_ROOT = derive_telemetry_root(__file__)
    _register_autostart_hooks()
    print('ashley_e1 bootstrap autostart hooks: %s' % dict(_AUTOSTART_HOOKS),
          flush=True)
    if _TELEMETRY_ROOT is not None:
        bootstrap_from_module_path(
            __file__, E1_PROBE_VERSION, SIMS_BUILD,
            required_imports=_required_import_summary(),
            inbox_autostart=_INBOX_AUTOSTART,
        )


def _STATE_RESET():
    global _STATE, _ARMED_NAME, _ARMED_SNAPSHOT, _TELEMETRY_SESSION_ID
    global _ALARM_HANDLE, _WRITER, _WRITER_IDLE, _SESSION_OPENED, _POLL_BUSY
    global _MISUSE_COUNT, _LAST_CAPTURE_COUNTERS, _INBOX_ERRORS
    global _CALIBRATE, _CAL_SPEED
    _STATE = "UNARMED"
    _ARMED_NAME = None
    _CALIBRATE = False
    _CAL_SPEED = None
    _ARMED_SNAPSHOT = None
    observers.prefer_body(None)  # 2.32.0 (PR6)
    _TELEMETRY_SESSION_ID = None
    _ALARM_HANDLE = None
    _WRITER = None
    _WRITER_IDLE = True
    _SESSION_OPENED = False
    _POLL_BUSY = False
    _MISUSE_COUNT = 0
    _INBOX_ERRORS = 0
    _LAST_CAPTURE_COUNTERS = None
    _COUNTERS["dropped_queue"] = 0
    _COUNTERS["dropped_overrun"] = 0
    _COUNTERS["dropped_serialize"] = 0
    _COUNTERS["redundant_starts"] = 0


def get_status():
    writer_state = "OK"
    rotation_index = 0
    if _WRITER is not None:
        try:
            writer_state = _WRITER.state
            rotation_index = _WRITER.rotation_index
        except AttributeError:
            pass
    return {
        "state": _STATE,
        "armed_name": _ARMED_NAME,
        "calibrate": _CALIBRATE,
        "armed_snapshot": _ARMED_SNAPSHOT,
        "telemetry_session_id": _TELEMETRY_SESSION_ID,
        "alarm_handle": _ALARM_HANDLE,
        "writer_idle": _WRITER_IDLE,
        "counters": dict(_COUNTERS),
        "misuse_count": _MISUSE_COUNT,
        "writer": {"state": writer_state, "rotation_index": rotation_index},
    }


def _telemetry_dir():
    """(bytes the writer counts in the telemetry folder, its cap) or (None, None)."""
    try:
        return _WRITER._logical_directory_bytes, _WRITER.max_dir_bytes
    except AttributeError:
        return None, None


def _warn_dir_fill():
    """D48 (live 2026-10-05): the folder was at 121 of 200 MB and would have stopped
    sampling after about two more hours of play without a word before it."""
    global _DIR_WARNED
    used, cap = _telemetry_dir()
    if _DIR_WARNED or type(used) is not int or type(cap) is not int or used * 4 < cap * 3:
        return False
    _DIR_WARNED = True
    return _emit(schema.make_record("session_checkpoint",
                                    telemetry_session_id=_TELEMETRY_SESSION_ID,
                                    wall_timestamp_ms=int(time.time() * 1000),
                                    monotonic_ns=time.perf_counter_ns(),
                                    checkpoint_reason="TELEMETRY_DIR_75"))


def _writer_became_idle():
    global _WRITER_IDLE
    _WRITER_IDLE = True


def _set_writer_sampling(active):
    if _WRITER is not None:
        try:
            _WRITER.set_sampling(active)
        except AttributeError:
            pass


def _emit_stop_failure(reason):
    if _WRITER is None or _STATE == "UNARMED":
        return False
    try:
        return _emit(schema.make_record(
            "guard_exhausted",
            telemetry_session_id=_TELEMETRY_SESSION_ID,
            wall_timestamp_ms=int(time.time() * 1000),
            monotonic_ns=time.perf_counter_ns(),
            reason=reason,
        ))
    except Exception:
        return False


def _current_clock_speed():
    try:
        game = observers._game_snapshot()
    except Exception:
        return None
    if type(game) is not dict:
        return None
    speed = game.get("clock_speed")
    if type(speed) is not str:
        return None
    return speed


def _cmd_calibrate(_connection=None) -> bool:
    global _CALIBRATE, _CAL_SPEED
    if _ARMED_NAME is None:
        return False
    speed = _current_clock_speed()
    _CALIBRATE = True
    _CAL_SPEED = speed
    detail = "clock_speed=%s armed_name=%s" % (speed, _ARMED_NAME)
    _E2._experiment_event("CALIBRATE_START", detail=detail[:schema.MAX_DETAIL_LENGTH])
    return True


def _note_calibrate_speed(row):
    global _CAL_SPEED
    if not _CALIBRATE:
        return
    game = row.get("game") or {}
    speed = game.get("clock_speed")
    if _CAL_SPEED is None and speed is None:
        return
    if speed == _CAL_SPEED:
        return
    detail = "from=%s to=%s ticks=%s" % (_CAL_SPEED, speed, game.get("ticks"))
    _E2._experiment_event("CALIBRATE_SPEED", detail=detail[:schema.MAX_DETAIL_LENGTH])
    _CAL_SPEED = speed


def _cmd_arm(arm_name: str, _connection=None) -> bool:
    global _STATE, _ARMED_NAME, _ARMED_SNAPSHOT, _TELEMETRY_SESSION_ID
    global _WRITER, _WRITER_IDLE, _SESSION_OPENED, _MISUSE_COUNT
    global _LAST_CAPTURE_COUNTERS, _CALIBRATE, _CAL_SPEED, _DIR_WARNED
    if arm_name not in ARM_NAMES:
        _MISUSE_COUNT += 1
        return False
    if _STATE != "UNARMED" or not _WRITER_IDLE:
        return False
    if _TELEMETRY_ROOT is None:
        return False
    _TELEMETRY_SESSION_ID = str(uuid.uuid4())
    _ARMED_NAME = arm_name
    _CALIBRATE = False
    _CAL_SPEED = None
    _ARMED_SNAPSHOT = None
    observers.prefer_body(None)  # 2.32.0 (PR6)
    _SESSION_OPENED = False
    _LAST_CAPTURE_COUNTERS = None
    _DIR_WARNED = False
    for key in _COUNTERS:
        _COUNTERS[key] = 0
    try:
        _WRITER = TelemetryWriter(_TELEMETRY_ROOT, _TELEMETRY_SESSION_ID,
                                  E1_PROBE_VERSION, SIMS_BUILD,
                                  on_idle=_writer_became_idle)
    except (OSError, IOError, ValueError):
        _WRITER = None
        _ARMED_NAME = None
        _CALIBRATE = False
        _CAL_SPEED = None
        _TELEMETRY_SESSION_ID = None
        return False
    _WRITER_IDLE = False
    _STATE = "ARMED"
    _E2.on_arm()
    _menu_reset()
    _E2.storm.clear()
    return True


def _cmd_start(_connection=None) -> bool:
    global _STATE, _ALARM_HANDLE, _ALARM_ZONE, _LAST_TICK_S
    if _STATE == "SAMPLING":
        _COUNTERS["redundant_starts"] += 1
        if _WRITER is not None:
            try:
                _WRITER.counters["redundant_starts"] = _COUNTERS["redundant_starts"]
            except AttributeError:
                pass
        return True
    if _STATE != "ARMED":
        return False
    try:
        _ALARM_HANDLE = alarms.add_alarm_real_time(owner=_PROBE_ALARM_OWNER,
            time_span=interval_in_real_seconds(1), callback=_poll_tick,
            repeating=True, use_sleep_time=False, cross_zone=False)
    except Exception:
        _ALARM_HANDLE = None
        return False
    _ALARM_ZONE = _current_zone()
    _LAST_TICK_S = _now_s()
    _STATE = "SAMPLING"
    _set_writer_sampling(True)
    return True


def _cmd_stop(_connection=None) -> bool:
    global _STATE, _ALARM_HANDLE
    if _STATE == "UNARMED":
        return False
    if _STATE == "SAMPLING":
        if _ALARM_HANDLE is not None:
            try:
                alarms.cancel_alarm(_ALARM_HANDLE)
            except Exception as error:
                _emit_stop_failure("STOP_CANCEL_FAILURE:%s" %
                                   type(error).__name__)
                return False
        _ALARM_HANDLE = None
        _STATE = "ARMED"
        _set_writer_sampling(False)
        _E2.on_stop("STOP")
    return True


def _cmd_disarm(_connection=None) -> bool:
    global _STATE, _ARMED_NAME, _ARMED_SNAPSHOT, _SESSION_OPENED, _WRITER_IDLE
    global _CALIBRATE, _CAL_SPEED
    if _STATE == "UNARMED":
        return True
    if not _cmd_stop():
        return False
    _set_writer_sampling(False)
    _E2.on_disarm()
    _menu_reset()
    close_reason = "DISARM_CLEAN" if _SESSION_OPENED else "ARMED_NEVER_STARTED"
    if _WRITER is not None:
        _WRITER.signal_close(close_reason)
        try:
            _WRITER_IDLE = _WRITER.is_idle
        except AttributeError:
            _WRITER_IDLE = False
    _STATE = "UNARMED"
    _ARMED_NAME = None
    _CALIBRATE = False
    _CAL_SPEED = None
    _ARMED_SNAPSHOT = None
    observers.prefer_body(None)  # 2.32.0 (PR6)
    _SESSION_OPENED = False
    return True


def _emit(row):
    if row.get("event_kind") == "experiment_event" and row.get("e2", {}).get("phase") == "VERDICT":
        payload = row["e2"]
        _INBOX_VERDICTS.append({key: payload[key] for key in ("phase", "code", "experiment_id", "detail")})
        del _INBOX_VERDICTS[:-5]
    if _WRITER is None:
        return False
    for key, value in _COUNTERS.items():
        try:
            if value > _WRITER.counters.get(key, 0):
                _WRITER.counters[key] = value
        except AttributeError:
            break
    accepted = _WRITER.try_put(row)
    if not accepted:
        try:
            writer_counters = _WRITER.counters
        except AttributeError:
            writer_counters = {}
        accounted = False
        for key in ("dropped_queue", "dropped_serialize"):
            if writer_counters.get(key, 0) > _COUNTERS.get(key, 0):
                _COUNTERS[key] = writer_counters[key]
                accounted = True
        if not accounted:
            _COUNTERS["dropped_queue"] += 1
    return accepted


def _session_open_from(row):
    global _ARMED_SNAPSHOT
    save = row.get("save", {})
    body = row.get("body", {})
    snapshot_guid = save.get("save_slot_guid")
    snapshot_slot = save.get("slot_id")
    snapshot_sim = body.get("sim_id")
    _ARMED_SNAPSHOT = {"guid": snapshot_guid, "slot_id": snapshot_slot,
                       "sim_id": snapshot_sim,
                       "wall_ms": row["wall_timestamp_ms"],
                       "monotonic_ns": row["monotonic_ns"]}
    observers.prefer_body(snapshot_sim)  # 2.32.0 (PR6): her body when several Sims are selectable
    return schema.make_record(
        "session_open", telemetry_session_id=_TELEMETRY_SESSION_ID,
        wall_timestamp_ms=row["wall_timestamp_ms"], monotonic_ns=row["monotonic_ns"],
        attestation=schema.attestation(_ARMED_NAME, None, snapshot_guid,
                                       snapshot_slot, snapshot_sim),
        save=save, zone=row.get("zone", {}), body=body,
    )



def _menu_reset(keep_last=False):
    global _MENU, _MENU_ZONE, _MENU_STARTED_S, _MENU_LAST, _MENU_ROOM, _MENU_DONE_ZONE, _MENU_LAST_BUILD
    global _MENU_SEEN_ROOM
    _MENU = None
    _MENU_ZONE = None
    _MENU_STARTED_S = None
    if not keep_last:
        _MENU_LAST = None
        _MENU_ROOM = None
        _MENU_DONE_ZONE = _NO_ZONE  # 2.37.0 (W10 P2): the next build is the first of its zone again
        _MENU_FAR.clear()
        _MENU_LAST_BUILD = None  # 2.39.0 (W12 C1): a zone's near part reads that zone's build only
        _MENU_SEEN_ROOM = _NO_ZONE


def _menu_hidden(affordance):
    """2.16.2 (live: the mailbox offered "Power Consumption" acts): the game's own cheat,
    debug and automation flags on the interaction tuning (interactions/base/interaction).
    Those acts are for testers, not her."""
    for flag in ("cheat", "debug", "automation"):
        if tuned._class_plain(affordance, flag) is True:
            return True
    return False



def _menu_offers(item, sim, context):
    """The candidate acts of one object: user-directed offers the trial guard does not exclude and the game does not
    mark as a cheat, at most CANDIDATE_ACTS distinct texts. 2.39.0 (W12 C12): a text repeated is folded before the cap.
    2.39.0 (W12 G1): a pie-menu act is not an act itself; each of its choices is one act, with its variant."""
    obj = item["obj"]
    jobs = []
    folded = set()
    for affordance in _lot_affordances(obj, context):
        if len(folded) >= act_menu.CANDIDATE_ACTS:
            break
        guid = tuned._class_plain(affordance, "guid64")
        if type(guid) is not int:
            continue
        if e2_actuator.is_pie(affordance):
            if e2_actuator.user_directed(affordance) and not _menu_hidden(affordance):
                jobs.extend(_pie_jobs(item, affordance, guid, sim, context, folded))
            continue
        if (e2_actuator.act_excluded(affordance, item.get("person") is True) is not None
                or not e2_actuator.user_directed(affordance)):
            continue
        if _menu_hidden(affordance):
            continue
        text_key = observers._string_key(tuned._class_plain(affordance, "display_name"))
        name = _affordance_name(affordance)
        fold = act_menu.fold_key({"text_key": text_key, "name": name, "guid64": str(guid)})
        if fold in folded:
            continue
        folded.add(fold)
        jobs.append({
            "object_id": item["object_id"], "definition_id": item["definition_id"], "class": item["class"],
            "distance_m": item["distance_m"], "same_room": item["same_room"], "room": item.get("room"),
            "on_lot": item.get("on_lot"),
            "person": item.get("person") is True,  # 2.37.0 (W10 P2): a Sim is never a far candidate (the cache)
            "guid64": str(guid), "name": name, "text_key": text_key,
            "obj": obj, "affordance": affordance, "sim": sim, "context": context,
        })
    return jobs


def _choice_name(choice):
    """2.39.0 (W12 G1): a pie choice's affordance name ("" when unreadable)."""
    try:
        return _affordance_name(choice.affordance)
    except Exception:
        return ""


def _pie_jobs(item, pie, guid, sim, context, folded):
    """2.39.0 (W12 G1): one job per choice of a pie-menu act: the choice's own name and text, its variant (its place in
    the game's list), and the choice itself, which is tested and later run as its own pair. A choice with no name key,
    a choice the guard excludes, and a text already folded are left out."""
    obj = item["obj"]
    jobs = []
    for index, choice in enumerate(e2_actuator.pie_choices(pie, obj, context)):
        if len(folded) >= act_menu.CANDIDATE_ACTS:
            break
        text_key, key = e2_actuator.choice_names(choice, context)
        if key is None:
            continue
        fold = act_menu.fold_key({"text_key": text_key, "name": key})
        if fold in folded or e2_actuator.choice_excluded(choice) is not None:
            continue
        folded.add(fold)
        jobs.append({
            "object_id": item["object_id"], "definition_id": item["definition_id"], "class": item["class"],
            "distance_m": item["distance_m"], "same_room": item["same_room"], "room": item.get("room"),
            "on_lot": item.get("on_lot"), "person": False,
            "guid64": str(guid), "name": _choice_name(choice),
            "text_key": text_key, "variant": index, "variant_key": key,
            "choice": choice, "obj": obj, "affordance": choice, "sim": sim, "context": context,
        })
    return jobs


def _phone_exclusion(affordance):
    """2.37.0 (W10 P3): why her phone's act is left out before the game tests it, or None. The reasons are
    named in the menu (excluded_phone): pie_picker, deny_name or travel (e2_actuator), not_user_directed, hidden."""
    why = e2_actuator.phone_act_excluded(affordance)
    if why is not None:
        return why
    if not e2_actuator.user_directed(affordance):
        return "not_user_directed"
    if _menu_hidden(affordance):
        return "hidden"
    return None


def _affordance_name(affordance):
    try:
        name = affordance.__name__
    except Exception:
        name = ""
    return name if type(name) is str else ""


def _menu_phone_offers(item, sim, context, excluded):
    """2.29.0: the candidate acts of her own phone. Her phone's affordances the trial guard does
    not exclude (as her own acts, so never a social), the game does not mark as a cheat, debug or
    automation, and that do not take her off the lot. Each is tested like any other candidate;
    the target of each is her own Sim. 2.37.0 (P3): up to act_menu.PHONE_CANDIDATES, and each act left
    out before the test is named in excluded (act_menu.note_excluded)."""
    jobs = []
    for affordance in e2_actuator.phone_affordances(sim):
        if len(jobs) >= act_menu.PHONE_CANDIDATES:
            break
        guid = tuned._class_plain(affordance, "guid64")
        if type(guid) is not int:
            continue
        why = _phone_exclusion(affordance)
        if why is not None:
            act_menu.note_excluded(excluded, _affordance_name(affordance), why)
            continue
        name = _affordance_name(affordance)
        jobs.append({
            "object_id": item["object_id"], "definition_id": None, "class": "phone",
            "distance_m": None, "same_room": None, "room": None, "phone": True, "on_lot": True,
            "guid64": str(guid), "name": name if type(name) is str else "",
            "text_key": observers._string_key(tuned._class_plain(affordance, "display_name")),
            "obj": sim, "affordance": affordance, "sim": sim, "context": context,
            # 2.40.0 (W13 P1): a phone act that opens a Sim picker is listed with needs_sim (she names the Sim).
            "needs_sim": True if e2_actuator.needs_sim(affordance) else None,
        })
    return jobs


def _on_lot(obj):
    try:
        value = obj.is_on_active_lot()
    except Exception:
        return None
    return value if type(value) is bool else None


class _MenuJobs(object):
    """2.35.0 (D3): the jobs of one menu build, read lazily as _lazy_jobs reads them, with the spots the build has
    found so far (the build's table; it is published when the build finishes). 2.39.0 (W12 C11): and the spot stage
    counters, which the build writes into its part 0."""

    def __init__(self, pairs, spots, excluded_phone, spot_stages=None):
        self._jobs = _lazy_jobs(pairs)
        self.spots = spots
        # 2.37.0 (W10 P3): her phone's acts the guard left out, named as the build reads them.
        self.excluded_phone = excluded_phone
        self.spot_stages = {} if spot_stages is None else spot_stages

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._jobs)


def _same_room(room, body_room):
    """The menu's same_room: an object in her room (outdoors is never her room)."""
    return room is not None and body_room is not None and room == body_room and room != "0"


def _routing_surface(obj):
    try:
        return obj.routing_surface
    except Exception:
        return None


def _level_of(obj):
    try:
        return obj.level
    except Exception:
        return None


def _planar(vector):
    """2.35.0 (D3): {x, z} of a game Vector3, rounded to 0.01, or None when unread."""
    try:
        return {"x": round(float(vector.x), 2), "z": round(float(vector.z), 2)}
    except Exception:
        return None


def _spot_item(obj, kind, room, level, distance, body_room):
    """2.35.0 (D3): one spot to look for. It is never an object of the game: it has no definition and no class of
    its own, and it is on her lot."""
    return {"object_id": None, "obj": obj, "spot": kind, "room": room, "level": level, "distance_m": distance,
            "on_lot": True, "same_room": _same_room(room, body_room), "person": False,
            "definition_id": None, "class": "spot"}


def _spot_anchors(items, body_room):
    """2.35.0 (D3): one spot to look for per (room, level) of the lot's objects. Its anchor is the object nearest the
    group's centre; the game's search starts there when the build asks for the spot (never here, so a build stays
    within its steps). A group without a level or a position is left out."""
    groups = {}
    for item in items:
        position = item.get("position")
        if (item["on_lot"] is not True or item["person"] is True or item["room"] is None or position is None
                or type(position.get("level")) is not int):
            continue  # a person is not an object: she is never the place the search starts from
        groups.setdefault((item["room"], position["level"]), []).append(item)
    anchors = []
    for (room, level), members in groups.items():
        centre_x = sum(member["position"]["x"] for member in members) / len(members)
        centre_z = sum(member["position"]["z"] for member in members) / len(members)
        anchor = min(members, key=lambda member: (member["position"]["x"] - centre_x) ** 2 +
                     (member["position"]["z"] - centre_z) ** 2)
        anchors.append(_spot_item(anchor["obj"], "room", room, level, anchor["distance_m"], body_room))
    return anchors


def _front_door_anchors(body_position, body_room):
    """2.35.0 (D3): the front door's spot to look for, when the game has a front door. The spot is on the door's
    outdoor side: one metre along its forward axis, in front or behind, whichever is outdoors (room "0"), since a
    door may face either way. A door with neither side outdoors, or no readable room, gives no spot."""
    door = e2_actuator.front_door()
    if door is None:
        return []
    level = _level_of(door)
    if type(level) is not int:
        return []
    for side in (1.0, -1.0):
        start = e2_actuator.spot_start(door, "front_door", side)
        if start is not None and e2_actuator.room_at(door, start, level) == "0":
            distance = observers._distance(observers._position(door), body_position)
            item = _spot_item(door, "front_door", "0", level, distance, body_room)
            item["side"] = side
            return [item]
    return []



def _spot_offers(item, sim, body_position, terrain, spots, seen, stages=None):
    """2.35.0 (D3): the Go Here act of one spot, for the build that asks for it. The game's standable search runs
    here, inside the build's steps, from the spot's anchor. The spot counts only in the room it was asked for, once
    per (room, level, kind), and only when the terrain offers Go Here at it; its id comes from the session's registry
    and its record goes into the build's table under that id. A search that fails leaves the spot out.
    2.39.0 (W12 C11): each stage the spot reaches is counted in stages (found, room, target, go_here, offers)."""
    stages = {} if stages is None else stages

    def count(name):
        stages[name] = stages.get(name, 0) + 1

    kind, room, level = item["spot"], item["room"], item["level"]
    surface = _routing_surface(item["obj"])
    found = e2_actuator.standable_spot(sim, e2_actuator.spot_start(item["obj"], kind, item.get("side", 1.0)), surface)
    if found is None:
        return []
    count("found")
    position, orientation = found
    if e2_actuator.room_at(item["obj"], position, level) != room:
        return []
    count("room")
    key = (room, level, kind)
    if key in seen or terrain is None:
        return []
    spot = {"position": position, "orientation": orientation, "routing_surface": surface, "level": level,
            "room": room, "kind": kind}
    point, spot_context = e2_actuator.spot_target(sim, spot)
    if point is None:
        return []
    count("target")
    picked = []
    for affordance in e2_actuator.go_here_offered(terrain, spot_context):
        if len(picked) >= act_menu.CANDIDATE_ACTS:
            break
        guid = tuned._class_plain(affordance, "guid64")
        if type(guid) is not int:
            continue
        if (e2_actuator.act_excluded(affordance, False) is not None
                or not e2_actuator.user_directed(affordance) or _menu_hidden(affordance)):
            continue
        picked.append((affordance, guid))
    if not picked:
        return []
    count("go_here")
    spot_id = _E2.spot_ids.id_for(room, level, kind)
    if spot_id is None:
        return []
    seen.add(key)
    spots[str(spot_id)] = spot
    count("offers")
    distance = observers._distance(_planar(position), body_position)
    return [{"object_id": str(spot_id), "definition_id": None, "class": "spot", "distance_m": distance,
             "same_room": item["same_room"], "room": room, "level": level, "spot": kind,
             "guid64": str(guid), "name": e2_actuator.GO_HERE_NAME, "text_key": None, "on_lot": True,
             "obj": point, "affordance": affordance, "sim": sim, "context": spot_context}
            for affordance, guid in picked]


def _menu_jobs(row):
    """8f: (jobs, room) for a new menu build: the user-directed offers of the lot she is on,
    her room first (act_menu.ordered and pick). Plain reads only; the runner tests. Jobs
    are None when the lot or her body cannot be read (no menu, rather than an empty one)."""
    zone = row.get("zone") or {}
    body_position = zone.get("position")
    body_room = zone.get("room")
    objects, code = _lot_snapshot()
    if code is not None:
        return None, body_room
    sim_info, sim = observers.select_lab_body(
        _services_module.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
    del sim_info
    if sim is None:
        return None, body_room
    context = e2_actuator.build_context(sim)
    # 2.29.0: her own phone is one entry, carrying her Sim's id (the object she is, not a person).
    sim_id = situation._int_id(tuned._plain(sim, "id", True))
    items = []
    for obj in objects:
        try:
            person = obj.is_sim is True or observers._is_pet_object(obj)  # 2.32.0 (PR13): pets are persons
        except Exception:
            continue
        if person and obj is sim:
            continue
        object_id = situation._int_id(tuned._plain(obj, "id", True))
        if object_id is None or object_id in e2_control.EXCLUDED_OBJECT_IDS:
            continue
        position = observers._position(obj)
        distance = observers._distance(position, body_position)
        on_lot = _on_lot(obj)
        # The room lookup is only worth it for objects of this lot or near her.
        room = (observers._room(obj, position)
                if on_lot is True or (distance is not None and distance <= 20.0) else None)
        # 2.38.0 (W11 H2): a Sim on her lot she cannot see is heard, and is offered too (the helper says so); off the
        # lot, a Sim she cannot see is not offered (2.32.0, SS4-v2, PR3).
        if person and on_lot is not True and not observers.seen_here(
                room, None if position is None else position.get("level"),
                distance, body_room, None if body_position is None else body_position.get("level")):
            continue
        items.append({
            "object_id": object_id, "obj": obj, "distance_m": distance, "on_lot": on_lot,
            "room": room, "person": person, "position": position,
            "same_room": _same_room(room, body_room),
        })
    # 2.35.0 (D3): the spots of her lot (one per room and level, and the front door), searched when the build asks.
    spots, seen = {}, set()
    excluded_phone = []  # 2.37.0 (W10 P3): her phone's acts left out before the test, named
    terrain = e2_actuator.terrain_object()
    anchors = _spot_anchors(items, body_room) + _front_door_anchors(body_position, body_room)
    # 2.39.0 (W12 C11): how far the spots got, counted as the build reads them (part 0 carries them).
    spot_stages = {"anchors": len(anchors), "placement": e2_actuator.placement is not None,
                   "terrain": terrain is not None}
    for name in ("found", "room", "target", "go_here", "offers"):
        spot_stages[name] = 0
    ordered = act_menu.ordered(items + anchors)
    phone = []
    if sim_id is not None and sim_id not in e2_control.EXCLUDED_OBJECT_IDS:
        phone.append({"object_id": sim_id, "obj": sim, "phone": True, "person": False,
                      "same_room": None, "on_lot": None, "distance_m": None, "room": None})

    def offers(item):
        # 2.34.0: a build reads objects across ticks, and an object can go meanwhile; one that cannot be read
        # offers nothing in this build, and the rest of the lot is still listed.
        try:
            if item.get("phone") is True:
                return _menu_phone_offers(item, sim, context, excluded_phone)
            if item.get("spot") is not None:
                return _spot_offers(item, sim, body_position, terrain, spots, seen, spot_stages)
            return _menu_offers(item, sim, context)
        except Exception:
            return []

    for item in ordered:
        if item.get("spot") is not None:
            continue  # 2.35.0 (D3): a spot is a place; its class and definition are set when it is found
        if item["person"]:
            # One person is never "the same kind" as another; the helper names them.
            item["definition_id"] = None
            item["class"] = "sim"
            continue
        try:
            item["definition_id"] = situation._int_id(item["obj"].definition.id)
        except Exception:
            item["definition_id"] = None
        item["class"] = situation._name(type(item["obj"])) or ""
    return _MenuJobs(act_menu.iter_pick(phone + ordered, offers), spots, excluded_phone, spot_stages), body_room


def _lazy_jobs(pairs):
    """2.34.0 (F4): the jobs of each (item, acts) pair, read one object at a time as the build asks for
    them (a lazy sequence, so a full lot is stepped across ticks and never read in one)."""
    reach = {}
    for item, acts in pairs:
        for job in acts:
            # Her phone's reach is not asked: the game's connectivity check is for objects. 2.35.0 (D3): nor a spot's.
            job["reach_seen"] = None if item.get("phone") is True or item.get("spot") is not None else reach
            yield job


def _menu_reach(job):
    """2.25.0: the first act of each object also asks, once per build, whether the game sees a way from her to it; the
    answer travels with the object (shown, never hidden). 2.38.0 (W11 P3): per object, so a candidate whose outcome
    the far cache gave is asked too."""
    seen = job.get("reach_seen")
    if seen is not None:
        if job["object_id"] not in seen:
            seen[job["object_id"]] = e2_actuator.reachable(job["sim"], job["obj"])
        job["reach"] = seen[job["object_id"]]



def _menu_test(job):
    """One candidate act: the game's own test of the push (its reach first, see _menu_reach). A pie choice is tested
    as its own pair (2.39.0, G1); any other act by the game's preflight test."""
    _menu_reach(job)
    if job.get("choice") is not None:
        ok, _reason, reason_key = e2_actuator.choice_test(job["choice"], job["context"])
    elif job.get("needs_sim") is True:
        # 2.40.0 (W13 P1): a Sim picker is listed when the game has a Sim it could choose; the Sim is her pick at the push.
        ok, reason_key = e2_actuator.picker_offers(job["affordance"], job["obj"], job["context"]) is True, None
    else:
        ok, _reason, reason_key = e2_actuator.preflight_test(
            job["sim"], job["obj"], job["affordance"], job["context"])
    if not ok:
        # 2.35.0 (D3): a refusal (not an error) is named in the menu for her phone's offers (refused_phone).
        # 2.39.0 (W12 C4): and for a near object's acts (refusals), by the act's own text and the game's reason.
        job["refused"], job["reason_key"] = True, reason_key
    return bool(ok)



def _menu_tick(row):
    """8f: one small step of the menu each sampling tick. A finished build is written as an act_menu row when it
    differs from the last one; a new build starts when there is none, her room changed, or REBUILD_S passed.
    2.39.0 (W12 C1): the near part is written on her move into another room and on a look (request_menu_near); each
    build writes its near part as its far part starts. The pie choices of the menu are published with it (G1)."""
    global _MENU, _MENU_ZONE, _MENU_REV, _MENU_LAST, _MENU_STARTED_S, _MENU_ROOM
    global _MENU_FAR_ZONE, _MENU_DONE_ZONE, _MENU_FIRST, _MENU_PARTIAL_S
    global _MENU_LAST_BUILD, _MENU_NEAR_REQUESTED, _MENU_BODY, _MENU_SEEN_ROOM
    now = _now_s()
    zone = row.get("zone") or {}
    room = zone.get("room")
    _MENU_BODY = (zone.get("position"), room)
    # 2.37.0 (W10 P2): the far cache belongs to one zone; a new zone starts it empty.
    if _current_zone() is not _MENU_FAR_ZONE:
        _MENU_FAR.clear()
        _MENU_FAR_ZONE = _current_zone()
    moved = _MENU_SEEN_ROOM is not _NO_ZONE and room != _MENU_SEEN_ROOM
    _MENU_SEEN_ROOM = room
    if _MENU_NEAR_REQUESTED or moved:
        _MENU_NEAR_REQUESTED = False
        _menu_near_now()
    if _MENU is not None and not _MENU.done:
        _MENU.step()
        # 2.37.1: the first build in a zone writes what it has so far, so the house reaches her as it is tested.
        # Only in the zone it was built for: a zone she has left never gets her menu written (the done branch's rule).
        if (_MENU_FIRST and not _MENU.done and _MENU_PARTIAL_S is not None and _MENU_ZONE is _current_zone()
                and now - _MENU_PARTIAL_S >= act_menu.FIRST_PARTIAL_S):
            _MENU_PARTIAL_S = now
            _menu_partial_part(_MENU)
    if _MENU is not None and _MENU.done:
        build, build_zone = _MENU, _MENU_ZONE
        _MENU = None
        if build_zone is _current_zone() and not build.failed:
            # 2.35.0 (D3): the spots of the build that finished are the ones an act may name (the newest build).
            _E2.publish_spots(build_zone, build.spots)
            _E2.publish_variants(build_zone, build.variants)
            payload = build.payload(_MENU_REV + 1, _MENU_ROOM)
            _MENU_LAST_BUILD = (build_zone, build)
            # 2.37.0 (W10 P2): the first build in a zone is written whole even when it matches the last menu.
            if _MENU_FIRST or not act_menu.same_menu(payload, _MENU_LAST):
                # 2.34.0 (F4): the menu is written in parts, each one record; it counts as written when all are.
                written = [_E2._event("act_menu", part) for part in act_menu.parts(payload)]
                if all(written):
                    _MENU_REV += 1
                    _MENU_LAST = payload
            _MENU_DONE_ZONE = build_zone
    if _MENU is None and (_MENU_STARTED_S is None or room != _MENU_ROOM or
                          now - _MENU_STARTED_S >= act_menu.REBUILD_S):
        jobs, body_room = _menu_jobs(row)
        _MENU_STARTED_S = now
        _MENU_ROOM = body_room
        if jobs is not None:
            zone = _current_zone()
            # 2.37.0 (W10 P2): the first build in a zone writes its near part as its far part starts.
            _MENU_FIRST = _MENU_DONE_ZONE is not zone
            _MENU_PARTIAL_S = now
            # 2.39.0 (W12 C1): every build writes its near part as its far part starts (on_near), not only the first.
            _MENU = act_menu.MenuBuild(jobs, _menu_test, spots=jobs.spots, excluded_phone=jobs.excluded_phone,
                                       budget_ms=act_menu.FIRST_BUDGET_MS if _MENU_FIRST else 8.0,
                                       far=_MENU_FAR, on_near=_menu_near_part, reach=_menu_reach,
                                       stages=jobs.spot_stages)
            _MENU_ZONE = zone



def _menu_near_part(build):
    """2.39.0 (W12 C1): her near part of this build, as far as it has got: her phone, her room, the Sims on her lot and
    what is within NEAR_M, each distance and room read now (_near_refresh). It has the menu_rev the whole menu will
    have; the whole menu follows when the build finishes. Written on every build, on her move and on a look.
    2.37.0 (W10 P2): a build's near part is written as its far part starts, as it always was for the first build."""
    if build.failed:
        return
    payload = build.payload(_MENU_REV + 1, _MENU_BODY[1], near=True, refresh=_near_refresh)
    if not payload["objects"]:
        return  # no near object: an empty part would only stand in for the menu; the whole menu follows
    _E2.publish_variants(_current_zone(), build.variants)
    for part in act_menu.parts(payload):
        _E2._event("act_menu", part)


def _menu_near_now():
    """2.39.0 (W12 C1): the near part of the newest build of this zone, written now: the build in progress, else the
    last one finished. Nothing when there is no build of this zone."""
    if _MENU is not None:
        build, build_zone = _MENU, _MENU_ZONE
    elif _MENU_LAST_BUILD is not None:
        build_zone, build = _MENU_LAST_BUILD
    else:
        return
    if build_zone is not _current_zone():
        return
    _menu_near_part(build)


def _near_refresh(head):
    """2.39.0 (W12 C1): the fields a near part reads when it is written: an object's distance from her body and its
    room (read now), and whether it is in her room. A phone and a spot keep what they were given."""
    body_position, body_room = _MENU_BODY
    if head.get("phone") is True or head.get("spot") is not None:
        return {}
    obj = head.get("obj")
    if obj is None:
        return {}
    position = observers._position(obj)
    distance = observers._distance(position, body_position)
    room = head.get("room")
    if head.get("on_lot") is True or (distance is not None and distance <= 20.0):
        room = observers._room(obj, position)
    return {"distance_m": distance, "room": room, "same_room": _same_room(room, body_room)}


def _menu_partial_part(build):
    """2.37.1: the menu so far, every act_menu.FIRST_PARTIAL_S seconds of the first build in a zone (the whole menu so
    far, not only the near part). It has the menu_rev the whole menu will have."""
    payload = build.payload(_MENU_REV + 1, _MENU_ROOM)
    if not payload["objects"]:
        return  # no near object: an empty part would only stand in for the menu; the whole menu follows
    for part in act_menu.parts(payload):
        _E2._event("act_menu", part)


def request_menu_near():
    """2.39.0 (W12 C1): the next menu tick writes a near part (her room, her phone, the Sims on her lot, and what is
    within NEAR_M), its distances read then. Idempotent: several requests before one tick are one write. True: the
    menu_near command is answered OK."""
    global _MENU_NEAR_REQUESTED
    _MENU_NEAR_REQUESTED = True
    return True


# ---------------------------------------------------------------- 2.40.0 (W13 P1): her reach (lists, discovery)
# The lists her view counts are written when their content changed: each list at most once every 60 real seconds, and
# on a zone load or a lists_now command (reach.ListWriter). The discovery record is written once per zone load, after
# the zone runs. Both are reads: nothing here changes the game. The places she knows are kept for the go command.
def _lists_emit(kind, row):
    """Writes one lists row; the places' ids are kept (the go command accepts only a place of the newest places list)."""
    if kind == "places":
        if row.get("part") == 0:
            _KNOWN_ZONES.clear()
        _KNOWN_ZONES.update(item["zone_id"] for item in row.get("items") or ())
    return bool(_E2._event("lists", row))


_LISTS = reach.ListWriter(_lists_emit)
_KNOWN_ZONES = set()
_LISTS_ZONE = _NO_ZONE
_LISTS_FORCE = False
_DISCOVERY_ZONE = _NO_ZONE
_DISCOVERY_REV = 0


def request_lists_now():
    """2.40.0 (W13 P1): the next sampling tick writes every list whose content changed (lists_now is idempotent)."""
    global _LISTS_FORCE
    _LISTS_FORCE = True
    return True


def _things_reader():
    """2.40.0 (W13 P2, home): the things list: her home's objects and her inventory (home.things_items shapes them).
    None when the read is unreadable, so the writer keeps the list it sent last."""
    rows = e2_actuator.things_rows()
    return None if rows is None else home.things_items(rows)


def _lists_readers():
    """The readers of the lists her view counts (people, places, events, things). places reads its own people, so a
    tick that reads places alone still has the households she knows."""
    def people():
        return observers.read_people(observers.her_sim_info())

    def places():
        sim_info = observers.her_sim_info()
        return observers.read_places(sim_info, observers.read_people(sim_info))

    return {"people": people, "places": places, "events": observers.read_events, "things": _things_reader}


def _write_discovery():
    """2.40.0 (W13 P1): the discovery record of this zone load, once. Read-only; each section is guarded. Her Sim must
    be instanced; when it is not, this zone has no record (the next zone load tries again)."""
    global _DISCOVERY_REV
    sim_info = observers.her_sim_info()
    sim = observers._safe(lambda: sim_info.get_sim_instance())
    if sim_info is None or sim is None:
        return
    known = observers._safe(lambda: list(sim_info.relationship_tracker.get_target_sim_infos())) or []
    pickers, tests = e2_actuator.phone_discovery(sim, e2_actuator.phone_affordances(sim), known)
    _DISCOVERY_REV += 1
    _E2._event("discovery", {"discovery_rev": _DISCOVERY_REV,
                             "sections": observers.read_discovery(sim_info, pickers, tests)})


def _reach_tick(row):
    """2.40.0 (W13 P1): her reach, one step each sampling tick. The verbs' pending trip is checked on every tick. Once the
    zone runs: the discovery record (once per zone load), and the lists that are due (or all of them after a zone load or
    a lists_now). A sense: the caller catches what it raises."""
    global _LISTS_ZONE, _LISTS_FORCE, _DISCOVERY_ZONE
    _E2.tick_verbs()
    if row.get("event_kind") != "presence_snapshot" or not _E2._zone_running():
        return
    zone = _current_zone()
    if zone is not _LISTS_ZONE:
        _LISTS_ZONE = zone
        _LISTS.new_zone()
        _LISTS_FORCE = True
    if _DISCOVERY_ZONE is not zone:
        _DISCOVERY_ZONE = zone
        _write_discovery()
    force, _LISTS_FORCE = _LISTS_FORCE, False
    _LISTS.tick(_lists_readers(), force=force)


def _poll_tick(alarm_handle=None):
    global _POLL_BUSY, _LAST_TICK_S
    if _STATE != "SAMPLING":
        return
    if alarm_handle is not None and alarm_handle is not _ALARM_HANDLE:
        # D43: a timer from an earlier start or lot. It retires itself; it never stops
        # the sampling that is running.
        _cancel_quietly(alarm_handle)
        return
    if _ALARM_ZONE is not None and _current_zone() is not _ALARM_ZONE:
        # D44 (live 2.15.0): rows read while the next lot loads showed her off the lot
        # and without half her skills. No rows until the resume in the next zone.
        return
    _LAST_TICK_S = _now_s()
    if _POLL_BUSY:
        _COUNTERS["dropped_overrun"] += 1
        if _WRITER is not None:
            try:
                _WRITER.note_drop("SAMPLER_OVERRUN")
            except AttributeError:
                pass
        return
    _POLL_BUSY = True
    try:
        _poll_tick_body()
    finally:
        _POLL_BUSY = False


def _body_gone_stop():
    """2.32.0 (PR5): True when her body is dead, after writing its BODY_GONE record and stopping sampling."""
    armed = _ARMED_SNAPSHOT or {}
    sim_id = armed.get("sim_id")
    if sim_id is None:
        return False
    life = observers.body_life(sim_id)
    if life is None or life.get("dead") is not True:
        return False
    reason = "GHOST" if life.get("ghost") is True else "DEAD"
    _E2.body_gone(reason, sim_id)
    _emit(schema.make_record(
        "session_checkpoint", telemetry_session_id=_TELEMETRY_SESSION_ID,
        wall_timestamp_ms=int(time.time() * 1000), monotonic_ns=time.perf_counter_ns(),
        checkpoint_reason="BODY_GONE"))
    _cmd_stop()
    return True


def _poll_tick_body():
    global _SESSION_OPENED, _LAST_CAPTURE_COUNTERS, _ZERO_BODY_TICKS, _MENU_FAILURES
    try:
        row = observers.poll_once(_TELEMETRY_SESSION_ID, _ARMED_NAME)
    except observers.SelectabilityReadFailure:
        _emit(schema.make_record("guard_exhausted", telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000),
                                 monotonic_ns=time.perf_counter_ns(),
                                 reason="SELECTABILITY_READ_FAILURE"))
        _cmd_stop()
        return
    except observers.LabIdentityAmbiguous as error:
        if error.eligible_count == 0 and _body_gone_stop():
            # 2.32.0 (PR5): a death removes her from the selectable Sims. Her Sim info still says so: one
            # BODY_GONE record names the reason, and sampling ends cleanly (no wait, no unexplained stop).
            return
        if error.eligible_count == 0 and _RESUME_SAMPLING:
            # D41: a loading screen has no selectable body; wait it out (no rows).
            # 2.15.2: a first load after a relaunch (D47) can take longer than a
            # minute, so the wait has no end; one WAITING_FOR_BODY says it is waiting.
            _ZERO_BODY_TICKS += 1
            if _ZERO_BODY_TICKS == ZONE_SETTLE_TICKS:
                _emit(schema.make_record(
                    "session_checkpoint", telemetry_session_id=_TELEMETRY_SESSION_ID,
                    wall_timestamp_ms=int(time.time() * 1000),
                    monotonic_ns=time.perf_counter_ns(),
                    checkpoint_reason="WAITING_FOR_BODY"))
            return
        _emit(schema.make_record("guard_exhausted", telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000),
                                 monotonic_ns=time.perf_counter_ns(),
                                 reason="LAB_IDENTITY_AMBIGUOUS:%s" % error.eligible_count))
        _cmd_stop()
        return
    except Exception as error:
        reason = "OBSERVATION_FAILURE:%s" % type(error).__name__
        _emit(schema.make_record("guard_exhausted",
                                 telemetry_session_id=_TELEMETRY_SESSION_ID,
                                 wall_timestamp_ms=int(time.time() * 1000),
                                 monotonic_ns=time.perf_counter_ns(), reason=reason))
        _cmd_stop()
        return
    _ZERO_BODY_TICKS = 0
    current = dict(_COUNTERS)
    writer_state = "OK"
    if _WRITER is not None:
        try:
            writer_state = _WRITER.state
        except AttributeError:
            writer_state = "OK"
        try:
            writer_counters = _WRITER.counters
        except AttributeError:
            writer_counters = {}
        for key in ("dropped_queue", "dropped_overrun", "dropped_serialize"):
            if writer_counters.get(key, 0) > current.get(key, 0):
                current[key] = writer_counters[key]
    capture_loss = (_LAST_CAPTURE_COUNTERS is not None and any(
        current.get(key, 0) > _LAST_CAPTURE_COUNTERS.get(key, 0)
        for key in ("dropped_queue", "dropped_overrun", "dropped_serialize")))
    if writer_state != "OK":
        capture_loss = True
    _LAST_CAPTURE_COUNTERS = current
    if capture_loss:
        row = dict(row)
        interactions = dict(row.get("interactions", {}))
        interactions["observation_complete"] = False
        row["interactions"] = interactions
        row["observation_complete"] = False
    if not _SESSION_OPENED:
        save = row.get("save", {})
        body = row.get("body", {})
        if (save.get("save_slot_guid") is None or
                save.get("slot_id") is None or
                body.get("sim_id") is None):
            _emit(schema.make_record(
                "guard_exhausted",
                telemetry_session_id=_TELEMETRY_SESSION_ID,
                wall_timestamp_ms=int(time.time() * 1000),
                monotonic_ns=time.perf_counter_ns(),
                reason="OBSERVATION_FAILURE:SESSION_OPEN_IDENTITY_INCOMPLETE",
            ))
            _cmd_stop()
            return
        if not _emit(_session_open_from(row)):
            _cmd_stop()
            return
        _SESSION_OPENED = True
        _remember_autosample()
    row = dict(row)
    row["attestation"] = schema.attestation(
        _ARMED_NAME, None, _ARMED_SNAPSHOT["guid"], _ARMED_SNAPSHOT["slot_id"],
        _ARMED_SNAPSHOT["sim_id"])
    if row.get("event_kind") == "presence_snapshot":
        # 2.31.0 (W3p): the pace block is decided before the row is written: the probe applies her pace now.
        row["pace"] = _pace_block(row)
    if not _emit(row):
        _cmd_stop()
        return
    if row.get("event_kind") == "presence_snapshot":
        _note_calibrate_speed(row)
    _warn_dir_fill()
    try:
        _E2.on_poll_row(row)
    except Exception as error:
        _emit(schema.make_record(
            "guard_exhausted", telemetry_session_id=_TELEMETRY_SESSION_ID,
            wall_timestamp_ms=int(time.time() * 1000),
            monotonic_ns=time.perf_counter_ns(),
            reason="E2_POLL_FAILURE:%s" % type(error).__name__))
    if row.get("event_kind") == "presence_snapshot":
        try:
            _menu_tick(row)
        except Exception:
            # The menu is a sense, never a reason to stop sampling; the next build retries.
            _MENU_FAILURES += 1
            _menu_reset(keep_last=True)
    # 2.40.0 (W13 P1): her reach (the lists, the discovery record, a pending trip). A sense too: a failed read never stops sampling.
    try:
        _reach_tick(row)
    except Exception:
        pass
