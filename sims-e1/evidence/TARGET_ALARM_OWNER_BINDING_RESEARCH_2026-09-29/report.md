# Project Ashley — Target-Runtime Alarm Owner / Handle Identity Research

Date: `2026-09-29`

This is a read-only investigation against the exact Sims 4 PC 1.128.90.1030
`alarms.pyc`. No Ashley source, build, installation, save, or Sims command was
changed or issued. Sims was closed during the inspection.

## Candidate and target identity

- Ashley HEAD: `d678f098057bc1a590d4501c13e85f59830db2ac`
- Ashley tree: `92d9ee964ea03d6ac15d9f743a4a9f62d7222f53`
- Probe: `1.0.6`
- Product: `Embodiment 1.0.0`
- Target archive: `simulation.zip`
- Target archive SHA256: `B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC`
- Target member: root member `alarms.pyc`
- Member bytes: `7859`
- Member SHA256: `8C019CC9696AD12FA7FD1AEB0D07090FE1D8ECB956687E2A9BE489FDF0362C58`
- Bytecode magic: `420d0d0a` / decimal `3394`
- Exact interpreter: CPython `3.7.0` x64

The preserved bounded extraction was reused from
`C:\Users\Xharv\AppData\Local\Temp\ashley-e1-scheduler-binding-20260929\alarms.pyc`.

## A — `AlarmHandle` owner contract

The recovered class body declares:

```text
__slots__ = ('_element_handle', '_owner_ref', '__weakref__')
```

`AlarmHandle.__init__` facts:

```text
co_argcount = 9
co_varnames = ('self', 'owner', 'callback', 't', 'when', 'repeating',
               'repeat_interval', 'accurate_repeat', 'cross_zone', 'e')
co_names = ('ValueError', 'AlarmElementCrossZone', 'AlarmElement',
            'RepeatingAlarmElementCrossZone', 'RepeatingAlarmElement',
            'LossyRepeatingAlarmElementCrossZone',
            'LossyRepeatingAlarmElement', 'schedule', '_element_handle',
            '_register_auto_cleanup', 'weakref', 'ref',
            '_owner_destroyed_callback', '_owner_ref')
```

The exact constructor order is:

1. If `owner is None`, raise `ValueError('Alarm created without owner')`.
2. Construct the selected alarm element. `cross_zone` only selects the
   element class in the repeating/non-repeating branches.
3. Call `t.schedule(e, when)`.
4. Store the returned element handle in `self._element_handle`.
5. Call `_register_auto_cleanup(self)`.
6. Call `weakref.ref(owner, self._owner_destroyed_callback)`.
7. Store that weak reference in `self._owner_ref` and return.

The decisive bytecode is mechanically:

```text
LOAD_FAST owner; compare to None; raise ValueError if None
construct e
t.schedule(e, when)
self._element_handle = scheduled_handle
_register_auto_cleanup(self)
self._owner_ref = weakref.ref(owner, self._owner_destroyed_callback)
```

Therefore:

```text
OWNER_WEAKREF_REQUIRED = YES
```

The owner must be non-`None` and weak-referenceable. The target imposes no
additional Sims/game-object, service, client, or world-state requirement.

## B — Exact CPython weak-reference proof

The proof ran under the pinned CPython 3.7.0 x64 interpreter:

```text
python_version=3.7.0
object_result=TypeError
object_message=cannot create weak reference to 'object' object
class_result=weakref
class_reference_alive=True
```

The minimal class used was:

```python
class ProbeAlarmOwner:
    pass
```

## C — Failure propagation

The target `add_alarm_real_time` directly constructs and returns
`AlarmHandle(...)`. Its recovered bytecode has no exception handling around
that call. A `TypeError` from `weakref.ref(owner, ...)` therefore propagates
out of `add_alarm_real_time`.

Current Ashley 1.0.6 source uses:

```text
sims-e1/src/ashley_e1/probe.py:87  _PROBE_ALARM_OWNER = object()
sims-e1/src/ashley_e1/probe.py:297 owner=_PROBE_ALARM_OWNER
sims-e1/src/ashley_e1/probe.py:300 except Exception: clear handle and return False
```

`TypeError` is an `Exception`, so the current broad start catch swallows this
constructor failure exactly as observed: `_ALARM_HANDLE` is cleared and
`_cmd_start()` returns `False` before `SAMPLING` or writer sampling activation.

```text
CURRENT_OBJECT_OWNER = TARGET_INCOMPATIBLE_builtin_object_is_not_weakrefable
```

## D — Auto-cleanup consequence

`_register_auto_cleanup(alarm_handle)` captures the already scheduled
`alarm_handle._element_handle`, creates a closure, and stores:

```text
weakref.ref(alarm_handle, on_alarm_handle_collected)
```

in `_ALARM_ELEMENT_HANDLES[id(element_handle)]`.

When the partially constructed `AlarmHandle` becomes unreachable, the closure
callback removes the map entry and calls:

```text
element_handle.timeline.hard_stop(element_handle)
```

The target also has `_unregister_auto_cleanup`, and normal cancel/run paths
remove the map entry and tear down the handle. The owner weak-reference failure
occurs after scheduling and auto-cleanup registration, so the target cleanup
machinery is structurally capable of hard-stopping the scheduled element after
the failed construction. Absolute garbage-collection timing is not required
for this conclusion.

```text
NO_CALLBACK_AFTER_FAILED_CONSTRUCTION = EXPLAINED_BY_TARGET_CLEANUP
```

## E — Callback handle identity

`AlarmElement._run` and `RepeatingAlarmElement._run` both call the callback
with `_lookup_alarm_handle(self._element_handle)`.

`_lookup_alarm_handle(element_handle)` computes `id(element_handle)`, obtains
the weak reference from `_ALARM_ELEMENT_HANDLES`, calls that weak reference, and
returns its referent.

The map entry was created by `_register_auto_cleanup` for the same scheduled
element handle and stores a weak reference to the same `AlarmHandle` object.
`add_alarm_real_time` returns that `AlarmHandle` object directly. Therefore,
after successful construction:

```text
callback_handle is _ALARM_HANDLE
```

is the mechanically expected identity relation.

```text
CALLBACK_HANDLE_IDENTITY = MATCHES_ASHLEY_GUARD
```

The existing `_poll_tick(alarm_handle=None)` identity guard must not be
removed or weakened by this finding.

## F — Cross-zone and owner lifetime

`cross_zone=False` changes only which alarm-element class is constructed. The
owner `None` check and final `weakref.ref(owner, ...)` call are unconditional.
It does not remove or alter the weak-reference requirement.

A module-global weakref-able singleton is sufficiently long-lived for this
purpose. The target does not require a Sim, service, client, or other gameplay
object merely to anchor alarm lifetime.

## Plan and root-cause classifications

```text
V1_2A_ALARM_OWNER_BINDING = TARGET_FALSIFIED
ALARM_OWNER_ROOT_CAUSE = PROVEN
```

The proof satisfies all required conditions: exact target owner weakref,
exact CPython failure for `object()`, current Ashley `object()` owner, and
propagation into Ashley's broad start catch.

## Next smallest move (not performed)

If a repair is authorized later, the smallest target-compatible owner change is
an inert module-owned weakref-able singleton:

```python
class _ProbeAlarmOwner:
    pass

_PROBE_ALARM_OWNER = _ProbeAlarmOwner()
```

This research did not apply that change, rebuild, reinstall, or retry
acceptance.

## Boundary

- Source edit: `NO`
- Build: `NO`
- Install/uninstall: `NO`
- Sims launch/command: `NO`
- A–M continuation: `NO`
- E1-A/B/G: `NO`
- E2: `NO`
- Power action: `NO`

`SIMS4_E1_TARGET_ALARM_OWNER_BINDING: RESOLVED`
