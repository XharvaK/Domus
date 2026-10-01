STATUS: PARTIAL. A vanilla no-injection chain exists (ZoneManager object-add → ZoneState.RUNNING → alarm), but probe import ordering and exact 1.128 Python scripts remain unverified.

# R-Z1: Starting the inbox pump on zone load

Target: PC 1.128.90.1030. Labels: SOURCE-CONFIRMED = inspected vanilla bytecode; COMMUNITY = third-party source/stubs; INFERENCE = reasoning; UNKNOWN = unresolved. Recommendations are PROPOSED. Research stayed read-only; decompilation/disassembly was in memory. No game, Windows/XQX access, login, communications, or remote mutations performed.

## Q1: Public registration APIs

**SOURCE-CONFIRMED:** `sims4.callback_utils.add_callbacks(events, *callbacks)` is callable without a zone, but its enum has no zone-load/game-running event. Pass an iterable of events. `invoke_callbacks(events, *args, **kwargs)` executes synchronously in its caller. **INFERENCE:** module-global registrations survive ordinary zone replacement; they do not marshal work between threads.

**SOURCE-CONFIRMED:** `Zone.register_callback(self, callback_type, callback)` is a registration API. Exact call: `z.register_callback(zone.zone_types.ZoneState.RUNNING, on_running)`; callback takes no arguments. It calls immediately if the state has been reached, ignores registration during shutdown, otherwise stores a one-shot callback on that zone. It does not transfer to the next Zone. **INFERENCE:** with no zone at import, this alone cannot bootstrap.

**SOURCE-CONFIRMED, additional candidate:** `services.get_zone_manager().register_callback(callback_type, callback)` is inherited from `IndexedManager`. `ON_OBJECT_ADD = 0` receives the newly added object. `ZoneManager.create_zone` constructs a Zone and calls `self.add(new_zone)`, dispatching that callback. This permits manager object-add → register RUNNING on new Zone → create alarm, without replacing a method. **INFERENCE:** manager registrations survive zone replacement while the same manager lives.

**UNKNOWN:** whether Domus imports after `services.start_global_services` assigns `_zone_manager`. Vanilla creates that manager before starting global tuning services, but this does not establish mod import order. If imported earlier, `get_zone_manager()` is None and there is no demonstrated retry/bootstrap. Main-menu `current_zone()` can be None even with an existing manager; these are different preconditions.

Other candidates:
- **SOURCE-CONFIRMED:** `sims4.zone_utils.register_zone_change_callback(callback)` is reachable at import but overwrites a SINGLE global callback slot. Vanilla installs `ZoneManager._update_current_zone` there. **INFERENCE:** replacing it could break zone tracking or be overwritten; chaining/replacing it is effectively injection and is not proposed.
- **SOURCE-CONFIRMED:** `InstanceManager.add_on_load_complete(self, callback)` queues until tuning loads, or immediately calls `callback(self)` when complete. **INFERENCE:** tuning completion is not per-zone readiness; potentially useful for deferred manager registration, but ordering and manager selection need validation. Not a verified fallback.
- **SOURCE-CONFIRMED:** `PersistenceService.add_save_unlock_callback(self, callback)` queues while save-locked, otherwise calls immediately. It is not zone-load notification.
- **SOURCE-CONFIRMED:** `ServiceManager.register_service(self, service, is_init_critical=False)` appends a service. Game services creates its manager and starts its fixed list in `start_services(save_slot_data)`. **UNKNOWN:** a supported pre-import registration window. Late append alone does not establish service start/setup. Do not fabricate a manager or start game services from a probe.

## Q2: Alarm at main-menu import / cross_zone

**SOURCE-CONFIRMED:** `alarms.add_alarm_real_time(owner, time_span, callback, repeating=False, use_sleep_time=True, cross_zone=False)` obtains `services.time_service()` and dereferences `ts.wall_clock_timeline.now`, then schedules on that timeline. `time_service()` dereferences `game_services.service_manager.time_service`. Owner must be non-None and weak-referenceable; retain it strongly.

**INFERENCE:** main-menu import is not a reliable alarm bootstrap: manager, time service or started timeline may be absent. Alarm creation does not directly require `current_zone()`, so a missing zone alone is not proof it must fail. **UNKNOWN:** exact time-service availability at this probe's import on 1.128.

**SOURCE-CONFIRMED:** `cross_zone=True` only changes alarm element selection; the same time-service lookup happens first. It cannot create a missing timeline. `TimeService.on_teardown` filters cross-zone elements on the SIM timeline during travel; `stop` tears down the WALL-CLOCK timeline. **INFERENCE:** do not promise menu/save-reload persistence from this flag. Re-arm per zone, explicitly cancel old real-time handles, and validate travel behavior. Real-time callbacks depend on game updates, not an independent OS timer or hard 1 Hz guarantee.

## Q3: Polling thread → game thread

**INFERENCE:** a `threading.Thread` can poll files and enqueue plain data in `queue.Queue`, but that queue cannot establish its own game-thread consumer. After Q1 installs an alarm, its callback can drain the queue; a worker is optional. Do not call services/alarms/timeline mutation from the worker to bootstrap.

**SOURCE-CONFIRMED:** vanilla has locked tick-based command marshalling in `sims4.gsi.command_buffer.CommandBufferService.add_command` / `on_tick`. Mirrored retail `sims4.core_services.SUPPORT_GSI = False`; its accessor raises `RuntimeError("The CommandBufferService is not available")`. **INFERENCE:** this is not an available retail drain. `Timeline.schedule` forwards to `_schedule`; no thread-safe call-soon API was established. **UNKNOWN:** additional native retail dispatcher; native stubs do not prove absence.

## Q4: Community hooks

**COMMUNITY:** S4CL injects `Zone.load_zone`, `Zone.do_zone_spin_up`, `Zone.on_loading_screen_animation_finished` and `ZoneManager.start`, then dispatches its event registry. Registering a library event does not make its underlying hook injection-free.

**COMMUNITY:** lot51 injects `ZoneSpinUpService.on_loading_screen_animation_finished`. Its `GlobalService.on_zone_load` dispatches ZONE_LOAD, but installing those services injects `GameServiceManager.start_services`. Both routes depend on injection.

**UNKNOWN:** MCCC and TURBODRIVER gameplay-mod hook implementations were not established from supplied sources. TURBODRIVER CPython stubs are not its mod source. Do not claim all their hooks are injection-based, or that every workable vanilla path requires injection: the manager-add chain is a concrete counter-candidate.

## Q5: Ranked PROPOSED recommendation

1. **PROPOSED, conditional, best fit:** register manager object-add at import, then RUNNING per Zone. No method replacement; imports stay under permitted roots. Numeric 0 is source-confirmed `indexed_manager.CallbackTypes.ON_OBJECT_ADD`, avoiding a new import root. `zone.zone_types` is vanilla's imported module. Exact conceptual calls:

```python
import services, zone, alarms, clock

# owner is a retained, weak-referenceable probe object.
# pump is the bounded game-thread inbox/queue drain.
def start_pump():
    owner.handle = alarms.add_alarm_real_time(
        owner, clock.interval_in_real_seconds(1), pump,
        repeating=True, use_sleep_time=False, cross_zone=False)

def arm_zone(z):
    if isinstance(z, zone.Zone):
        z.register_callback(zone.zone_types.ZoneState.RUNNING, start_pump)

manager = services.get_zone_manager()
if manager is not None:
    manager.register_callback(0, arm_zone)  # ON_OBJECT_ADD
    existing = services.current_zone()
    if existing is not None:
        arm_zone(existing)
```

**INFERENCE:** production code needs per-zone idempotence, cancellation/replacement of previous handles, teardown cleanup and bounded work. `cross_zone=False` alone must not be assumed to cancel a wall-clock handle on every travel. Probe-specific owner/pump are intentionally undefined: this is research, not an installed implementation. If manager is None, record bootstrap unavailable rather than claiming unattended readiness.

2. **PROPOSED fallback:** one `ashley_e1.inbox` command inside a loaded lot creates the same alarm and can install manager callbacks for later zones. This relaxes unattended initial startup, preserves no injection. One-command-per-launch still requires menu/reload lifetime checks.
3. **PROPOSED amendment if import registration cannot be made reliable:** narrowly guarded injection after `Zone.on_loading_screen_animation_finished`, re-arm idempotently with the same alarm call. This violates current guards and requires the architect's amendment; no implementation was performed.

## Quoted source evidence

E1 — **SOURCE-CONFIRMED**, repo https://github.com/asiamserrano/TheSims4ScriptModBuilder, commit `40fadf822da383cdff76949a5c0c50e3b2e6968e`. Below, `core/...py` and `simulation/...py` correspond to `game/unzip/core/...pyc` and `game/unzip/simulation/...pyc`. Lines are ORIGINAL EA bytecode line-table numbers, not decompiler output lines. Python quotations reconstruct bytecode; decisive branches/calls were checked with xdis. Bytes came from local core.zip or read-only `git show HEAD:path`.

- `core/sims4/callback_utils.py` L22: `TUNING_CODE_RELOAD = 1`; L24–25: `AUTONOMY_PING_ENTER = 2`, `AUTONOMY_PING_EXIT = 4`; L27–28: POSTURE_GRAPH_BUILD ENTER=8, EXIT=16; L30–31: CONTENT_SET_GENERATE ENTER=32, EXIT=64; L33–34: PROCESS_EVENTS_FOR_HOUSEHOLD ENTER=128, EXIT=256; L36–37: TRANSITION_SEQUENCE ENTER=512, EXIT=1024. L39–40 compound flags OR content/household flags. L45: `_callbacks = collections.defaultdict(list)`. Def L47: `add_callbacks(events, *callbacks)`; L68: `_callbacks[event].append(callback)`. Def L70: `invoke_callbacks(events, *args, **kwargs)`; L80: `fn(*args, **kwargs)`.
- `simulation/zone.py` L182–183: `self._zone_state = zone_types.ZoneState.ZONE_INIT`; `self._zone_state_callbacks = {}`. Def L1133: `register_callback(self, callback_type, callback)`; L1140–1141 shutdown check returns. L1143–1145: `if callback_type <= self._zone_state: callback(); return`; L1147: `self._zone_state_callbacks[callback_type].append(callback)`. L1130–1131: `self._zone_state_callbacks[state]()`; `del self._zone_state_callbacks[state]`. `simulation/zone_types.py` L30: `RUNNING = 6`; L33: `SHUTDOWN_STARTED = 7`.
- `simulation/services/__init__.py` L419: `_zone_manager = ZoneManager()`; L440: `services.append(TuningInstanceManager(instantiated_tuning_managers))`; L447 includes `_zone_manager` in service list; L451: `sims4.core_services.start_services(init_critical_services, services)`. Def L511 / L515: `get_zone_manager(): return _zone_manager`. L521–523: `if _zone_manager is not None: return _zone_manager.current_zone`, otherwise None. L1066: `return game_services.service_manager.time_service`.
- `simulation/zone_manager.py` L7: `from indexed_manager import IndexedManager`; L19: `class ZoneManager(IndexedManager)`; constructor def L23 sets `current_zone = None`. L72: `new_zone = zone.Zone(zone_id, save_slot_data_id)`; L74: `self.add(new_zone)`; L82: `return new_zone`. L110: `sims4.zone_utils.register_zone_change_callback(self._update_current_zone)`.
- `simulation/indexed_manager.py` L47: `ON_OBJECT_ADD = 0`; def L142: `register_callback(self, callback_type, callback)`; L147: `self._registered_callbacks[callback_type].append(callback)`. Def L166 `add(self, obj)` calls `call_on_add`; L329: `self._registered_callbacks[CallbackTypes.ON_OBJECT_ADD](obj)`.
- `core/sims4/zone_utils.py` L17: `_zone_changed_callback = None`; L30: `zone_id = _zone_id`; L32: `_zone_changed_callback(zone_id)`; def L34: `register_zone_change_callback(callback)`; L41: `_zone_changed_callback = callback` (STORE_GLOBAL, no append).
- `simulation/alarms.py` def L71 has Q2 signature; L94: `ts = services.time_service()`; L95–100: `return AlarmHandle(owner, callback, ts.wall_clock_timeline, ts.wall_clock_timeline.now + time_span, repeating=repeating, repeat_interval=time_span, accurate_repeat=use_sleep_time, cross_zone=cross_zone)`. Constructor def L147 rejects None owner, schedules element and stores `weakref.ref(owner, self._owner_destroyed_callback)`.
- `simulation/time_service.py` constructor def L35 initializes timelines to None; L55–57 creates wall-clock Timeline using `services.server_clock_service().now()`. L78: `self.sim_timeline.filter_handles(cross_zone_alarm)`; L104–105: `self.wall_clock_timeline.teardown()`; `self.wall_clock_timeline = None`. L121: `self.wall_clock_timeline.simulate(services.server_clock_service().now())`.
- `core/sims4/core_services.py` L13: `SUPPORT_RELOADING_SCRIPTS = False and ...`; L18: `SUPPORT_GSI = False`. `command_buffer_service` def L64 guards SUPPORT_GSI and raises when unavailable; `on_tick` def L190 guards GSI drain. `core/sims4/gsi/command_buffer.py` L58: `self._lock = threading.Lock()`; L87–91 appends under lock; L99–103 copies/clears under lock; L105–106 iterates and `_execute_command(command)`.
- `core/sims4/tuning/instance_manager.py` def L327: `add_on_load_complete(self, callback)`; L337–340 queues until complete, otherwise `callback(self)`. `simulation/services/persistence_service.py` def L404 / L410–413: save-locked registration, otherwise `callback()`.
- `core/sims4/service_manager.py` def L261: `register_service(self, service, is_init_critical=False)`; L274: `self.services.append(service)`. `simulation/game_services.py` L59–60 creates manager when None; L132 instantiates TimeService; L197 registers fixed-list services; L199 starts services.

E2 — **COMMUNITY**, https://github.com/DeviantGameMods/Sims4CommunityLibrary @ `db1ca99dc448589d4cb1ab315cf4a3bb26c115be`, `Scripts/sims4communitylib/events/zone_spin/common_zone_spin_event_dispatcher.py`: L77 `@CommonInjectionUtils.inject_safely_into(ModInfo.get_identity(), Zone, Zone.load_zone.__name__, handle_exceptions=False)`; L84 targets `Zone.do_zone_spin_up`; L103 targets `Zone.on_loading_screen_animation_finished`; L110 targets `ZoneManager.start`. L106: `CommonZoneSpinEventDispatcher.get()._on_loading_screen_animation_finished(self)`.

E3 — **COMMUNITY**, https://github.com/lot51/core-library @ `a4fc43efdd59e7222c0e68ea6c4917fbc04cf3e2`: `events/zone.py` L9 `@inject_to(ZoneSpinUpService, 'on_loading_screen_animation_finished')`; L14 `event_service.process_event(CoreEvent.LOADING_SCREEN_LIFTED, context=context)`. `services/global.py` L42–44 `def on_zone_load(self, *args, **kwargs)` → `event_service.process_event(CoreEvent.ZONE_LOAD, context=context)`; L67 `service_manager.register_service(GlobalService)`. `services/service_manager.py` L52 `@inject_to(GameServiceManager, 'start_services')`; L72 `self.register_service(service, is_init_critical=False)`; L80 `original(self, *args, **kwargs)`.

E4 — **COMMUNITY/version boundary**, https://github.com/TURBODRIVER/TS4CPythonStubs @ `76338aa350fb1bf723d03397c3ef44c375441b13` (1.128.90). Native stubs only; do not confirm Python CallbackEvent, Zone, services or alarms for this build. Local `_pythonutils.pyi` / `_zone.pyi` searches did not establish a main-thread queue API.

## Version caveats / open questions with live checks

- **UNKNOWN:** mirrored vanilla exact build. Repo commit February 2025; core.zip entries November 2024; CPython bytecode 3.7. Not verified 1.128 PC scripts. Newer community library commits do not close the gap. Target-build conclusions remain INFERENCE.
- **PROPOSED live check for an authorized LAB operator:** log at actual probe import `services.get_zone_manager()`, `services.current_zone()` and time-service/timeline availability without creating an alarm. If manager is None, recommendation 1 lacks an established bootstrap. Separately validate tuning-completion ordering before claiming a fallback.
- **PROPOSED live check:** register object-add once; record object type/id and thread identity. Register RUNNING and record order and time-service readiness. Test first save load, travel, return to menu and second save load; confirm manager lifetime and callback persistence.
- **PROPOSED live check:** verify exactly one retained handle/drain per zone, explicit cancellation at teardown, pause behavior, travel with both cross_zone values, and no duplicate drains. Compare callback thread identity with a console-command thread. No live checks performed here.
- **UNKNOWN:** MCCC/TURBODRIVER mod-source hooks and any native retail marshalling API. These gaps prohibit a universal “all paths require injection” conclusion. Current evidence supports a conditional no-injection proposal, not guaranteed unattended startup.
