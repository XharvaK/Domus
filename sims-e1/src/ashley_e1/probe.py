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

from . import atlas
from . import food
from . import preflight
from . import cmdbox
from . import tuned
from . import e2_actuator
from . import e2_admission
from . import e2_control
from . import observers
from . import schema
from .writer import TelemetryWriter, bootstrap_from_module_path, derive_telemetry_root, read_command_file, write_command_reply


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
_ARMED_NAME = None
_CALIBRATE = False
_CAL_SPEED = None
_OBSERVE_REFUSED = ("prepare", "sit", "sit_trial", "pause", "release", "trial",
                     "preflight", "food_scan")
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
)

_ARM_NATIVE_TO_CANONICAL = {
    "lab_e1": "LAB_E1",
    "lab_e1_fork": "LAB_E1_FORK",
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
    if args or kwargs:
        return False
    return _cmd_disarm(_connection=_session_id)


def _dispatch_start(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    return _cmd_start(_connection=_session_id)


def _dispatch_stop(*args, _session_id=0, **kwargs):
    if args or kwargs:
        _emit_stop_failure("STOP_DISPATCH_INVALID_SHAPE")
        return False
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
        return True
    except Exception:
        return False


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
                preflight=_scan_progress(_PREFLIGHT), food=_scan_progress(_FOOD))


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
    if name == 'atlas_dump':
        return _dispatch_atlas_dump(connection)
    if name == 'tuned_scan':
        return _dispatch_tuned_scan(connection)
    if name == 'preflight':
        return _dispatch_preflight(connection)
    if name == 'food_scan':
        return _dispatch_food_scan(connection)
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
        for affordance in tuned.affordances_of(obj):
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
            ok, reason = False, excluded
        else:
            ok, reason = e2_actuator.preflight_test(
                _sim, job["obj"], job["affordance"], _context)
        return {
            "kind": "preflight", "object_id": job["object_id"],
            "guid64": job["guid64"], "name": job["name"],
            "ok": bool(ok), "reason": reason,
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
        for affordance in tuned.affordances_of(obj):
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
    finally:
        _INBOX_BUSY = False


def _inbox_tick_body():
    global _INBOX_ERRORS
    root = os.path.join(_TELEMETRY_ROOT, 'cmd')
    inbox = os.path.join(root, 'inbox')
    try:
        names = sorted(name for name in os.listdir(inbox) if name.endswith('.json'))[:4]
    except OSError:
        return
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
             _dispatch_arm, 'Arm the Ashley E1 probe in LAB_E1 or LAB_E1_FORK.',
             'ashley_e1.arm LAB_E1 | ashley_e1.arm LAB_E1_FORK', CommandType.Live)
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
    global _LAST_CAPTURE_COUNTERS, _CALIBRATE, _CAL_SPEED
    if arm_name not in ("LAB_E1", "LAB_E1_FORK"):
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
    _SESSION_OPENED = False
    _LAST_CAPTURE_COUNTERS = None
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
    _E2.storm.clear()
    return True


def _cmd_start(_connection=None) -> bool:
    global _STATE, _ALARM_HANDLE
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
    return schema.make_record(
        "session_open", telemetry_session_id=_TELEMETRY_SESSION_ID,
        wall_timestamp_ms=row["wall_timestamp_ms"], monotonic_ns=row["monotonic_ns"],
        attestation=schema.attestation(_ARMED_NAME, None, snapshot_guid,
                                       snapshot_slot, snapshot_sim),
        save=save, zone=row.get("zone", {}), body=body,
    )


def _poll_tick(alarm_handle=None):
    global _POLL_BUSY
    if _STATE != "SAMPLING":
        return
    if alarm_handle is not None and alarm_handle is not _ALARM_HANDLE:
        _cmd_stop()
        return
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


def _poll_tick_body():
    global _SESSION_OPENED, _LAST_CAPTURE_COUNTERS
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
    row = dict(row)
    row["attestation"] = schema.attestation(
        _ARMED_NAME, None, _ARMED_SNAPSHOT["guid"], _ARMED_SNAPSHOT["slot_id"],
        _ARMED_SNAPSHOT["sim_id"])
    if not _emit(row):
        _cmd_stop()
        return
    if row.get("event_kind") == "presence_snapshot":
        _note_calibrate_speed(row)
    try:
        _E2.on_poll_row(row)
    except Exception as error:
        _emit(schema.make_record(
            "guard_exhausted", telemetry_session_id=_TELEMETRY_SESSION_ID,
            wall_timestamp_ms=int(time.time() * 1000),
            monotonic_ns=time.perf_counter_ns(),
            reason="E2_POLL_FAILURE:%s" % type(error).__name__))
