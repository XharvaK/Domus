STATUS: DONE. In release builds `sims4.commands.output()` does nothing (its whole body is `return None`). The engine passes the connection as `_session_id`. Reply with `cheat_output(text, _session_id)` or `CheatOutput(_session_id)`.

# R-H2: Why Domus probe replies were invisible in the cheat console

Target build: PC 1.128.90.1030 (patch 2026-09-22), Python 3.7.
Labels: SOURCE-CONFIRMED (I read it in source or bytecode), COMMUNITY (a third-party mod, doc or paste), INFERENCE (my reasoning from evidence), UNKNOWN.

## Q1: Why were `sims4.commands.output(text, connection)` replies invisible?

**Answer: SOURCE-CONFIRMED for the mirrored build; INFERENCE that it still holds on 1.128.**
In the shipped release scripts, `sims4.commands.output(s, context)` has an empty body. It compiles to `LOAD_CONST None; RETURN_VALUE`, touches no globals, and never calls `_commands.output`. So whatever connection you pass, the text is dropped. The value of `_session_id` did not matter.
Only `cheat_output()`, and `CheatOutput.__call__` which uses it, forwards text to the native `_commands.output(s, context)`. That is the only path that reaches the console. `Output.__call__` calls the no-op `output()`, so `sims4.commands.Output(conn)` is also silent.

Notes:
- (SOURCE-CONFIRMED) Vanilla's own decorator error path (`output("Error: {}".format(e), _session_id)`) and argument-parse errors (`_parse_arg` -> `output(...)`) also use the no-op `output()`. Those messages are silent in retail too.
- (INFERENCE) Some public mods still call `sims4.commands.output(...)`, for example lot51 core-library `commands.py` line 9 (import) and line 18. Those calls would also be invisible. This does not contradict the bytecode.

## Q2: Which keyword does the engine pass? How does the decorator wrap handlers? What does output do with 0 or None?

**Keyword: `_session_id`.** Confidence is high.
- (SOURCE-CONFIRMED) The vanilla decorator registers a wrapper with the signature `invoke_command(*args, _session_id=0, **kw)` as the native callback. Varnames are `_session_id, args, kw`, with 1 keyword-only argument. Vanilla commands work in retail through this wrapper, so the native dispatcher must supply `_session_id` as a keyword. (INFERENCE, strong.)
- (COMMUNITY, runtime) A 2020 traceback dump from build 1.63.136.1010 shows the live locals of `sims4\commands.py ... in invoke_command`: `_session_id : 3` ... `kw : {'_connection': 3}`. So the engine passed `_session_id=3`, and the Python wrapper created `_connection`.
- (COMMUNITY source) S4CL registers commands through raw `register()` with exactly this handler signature: `_invoke_command(*args: str, _session_id: int=0, **kwargs)`. It builds its output as `CommonConsoleCommandOutput(_session_id)`, a `CheatOutput` subclass.
- The engine does **not** pass `_connection`. `_connection` and `_account` are created only by the Python decorator, and only when the decorated function's signature declares them. (SOURCE-CONFIRMED)
- (INFERENCE) The engine does not normally pass other keywords. Many vanilla decorated functions have no `**kwargs`, and `invoke_command` forwards `**kw` unchanged, so extra keywords would crash them. The probe's `if kwargs: return False` guard should therefore not trigger. Verify live (see below).

**How the decorator path works:** SOURCE-CONFIRMED from bytecode. Original EA line numbers below.
1. `Command(*aliases, command_type=CommandType.DebugOnly, command_restrictions=CommandRestrictionFlags.UNRESTRICTED, pack=None, console_type=None)` (L332) computes two values:
   - `relevant_type`: `console_type` if it is set and `not paths.IS_DESKTOP`, otherwise `command_type` (L349-352).
   - `most_limited_type`: `min(command_type, console_type)`, or `command_type` if there is no console_type (L360-363).
2. `named_command(func)` (L377) returns `None` if `is_valid_command()` fails. That happens when the type is DebugOnly or a required pack is missing (L365-). Otherwise:
   - It **inspects the signature** with `full_arg_spec = inspect.getfullargspec(func)` (L381).
   - It defines `invoke_command(*args, _session_id=0, **kw)` (L383).
   - It sets `invoke_command.__name__ = 'invoke_command ({})'` (L408) and builds usage from `inspect.formatargspec` (L409).
   - It loops over aliases and calls `register(alias, command_restrictions, invoke_command, description, usage, most_limited_type)` (L419-420). It then returns the **original, unwrapped `func`** (L422).
3. `invoke_command` does the following in order:
   - It **injects** `kw['_account'] = _session_id` if `_account` is in args or kwonlyargs (L386-387).
   - Separately, it injects `kw['_connection'] = _session_id` if `_connection` is in args or kwonlyargs (L388-389). These are two independent `if`s; uncompyle6's `elif` is a decompiler artifact, corrected from the bytecode.
   - It **parses args** with `parse_args(full_arg_spec, args, _session_id)` (L391). The raw console args are strings. They are converted using the annotations: `bool` via `BOOL_TRUE`/`BOOL_FALSE`, `int(x, base=0)`, `CustomParam` subclasses, or `arg_type(x)`.
   - It checks `is_command_available(relevant_type)`, which is `lambda command_type: True` in release (L59, L393-394). For `CommandType.Cheat` it writes a telemetry hook (L395-398).
   - It returns `func(*args, **kw)` (L399).
   - On `BaseException` it calls the no-op `output("Error: ...")` and `logger.warn`, then re-raises (L400-).
4. It does **not** wrap handlers with a `_connection=None` default. That default is only the modder's own convention, so the function can also be called without the engine.

**Raw `register` path, as used by Domus.** SOURCE-CONFIRMED:
- `register(name, restrictions, handler, description, usage, command_type)` (L118) only calls `_commands.register(name, description, usage, handler)` (L135-136).
- `restrictions` and `command_type` are **dropped** in this build. `CommandType.Live` has no effect on the raw path.
- The raw path has no signature inspection, no `_connection` injection, no argument parsing, no `is_command_available` check, no telemetry and no error handling.
- Your handler receives the raw string tokens as `*args` plus the native `_session_id=` keyword.

**`output()` with 0 or None:** It does nothing in either case. It is a no-op for every context. (SOURCE-CONFIRMED)

**`cheat_output()`, for comparison:** SOURCE-CONFIRMED:
- Its only special case is `context != NO_CONTEXT`, where `NO_CONTEXT = 18446744073709551615` (2**64-1, L56).
  - Any other context, including `0` and `None`, is passed straight to `_commands.output(s, context)` (L192-193).
  - `NO_CONTEXT` goes to `logger.always(s)`, which writes to the log only (L195).
- What the native `_commands.output` does with session 0 or None is **UNKNOWN**:
  - The native docstring only says `output(s)`.
  - TURBODRIVER's `session_id: 'int' = 0` default is a hand annotation (COMMUNITY).
  - (INFERENCE) `None` may raise TypeError in native code. Vanilla `execute()` explicitly rewrites `None` to `0` before calling native (L157-158), which suggests native code expects an int.
  - (INFERENCE) Session 0 is probably not the live client's session. Runtime evidence shows the UI session as 3, so 0 would likely go nowhere visible.

## Quoted source evidence

### E1. Vanilla `sims4/commands.py`, decompiled from a public mirror (SOURCE-CONFIRMED)
- Repo: https://github.com/asiamserrano/TheSims4ScriptModBuilder, commit `40fadf822da383cdff76949a5c0c50e3b2e6968e` (committed 2025-02-11 01:25 TRT).
- File: `game/unzip/core/sims4/commands.pyc`, sha256 `1463a5e9b2e61c9d9543d5360715078af89a680688ab8c640984fa56fda3d972`. It is byte-identical to the `sims4/commands.pyc` entry in `game/zip/gameplay/core.zip` in the same commit. The zip entries are dated 2024-11-14; zip time has no zone.
- pyc header: magic `420d0d0a` (CPython 3.7, 3394). Embedded filename `T:\InGame\Gameplay\Scripts\Core\sims4\commands.py`. Source mtime 2022-01-18 20:16:37 UTC (23:16 TRT). Source size 18298 bytes.
- Tools: I decompiled it with uncompyle6 3.9.3 and disassembled it with xdis 6.1.7 `pydisasm`. Both were run locally in /workspace/wt/r-h2. Line numbers are EA's original source lines, taken from the bytecode line table. The code text is uncompyle6's reconstruction; I corrected it against the disassembly where noted. The repo config (`Sims4GameContentDir = /Applications/EA Games/The Sims 4.app/Contents`) shows these files came from the macOS install.

Module header (L21-25):
```
__enable_native_commands = True
try:
    import _commands
except:
    __enable_native_commands = False
```
L56: `NO_CONTEXT = 18446744073709551615`
L59 (inside `with sims4.reload.protected(globals()):`): `is_command_available = lambda command_type: True`

`register` (def L118, body L135-136):
```
def register(name, restrictions, handler, description, usage, command_type):
    if __enable_native_commands:
        _commands.register(name, description, usage, handler)
```
`execute` (def L145, body L156-159):
```
def execute(command_line, _connection):
    if __enable_native_commands:
        if _connection is None:
            _connection = 0
        _commands.execute(command_line, _connection)
```
**`output` (def L174). The body at L179 is the only bytecode:**
```
def output(s, context):
    return
```
Disassembly (pydisasm), with Names empty and no reference to `_commands`:
```
# Method Name:       output
# First Line:        174
# Varnames:
#	s, context
179:           0 LOAD_CONST           (None)
               2 RETURN_VALUE
```
**`cheat_output` (def L186, body L191-195):**
```
def cheat_output(s, context):
    if __enable_native_commands:
        if context != NO_CONTEXT:
            _commands.output(s, context)
        else:
            logger.always(s)
```
`automation_output` (def L197, body L201-205): has the same shape and calls `_commands.automation_output(s, context)`. Its signature is `def automation_output(s, context=0)`.

`Command` / `named_command` / `invoke_command` (L332-423). This is the uncompyle6 text, with the two `elif`s restored to `if` as the bytecode shows:
```
def Command(*aliases, command_type=CommandType.DebugOnly, command_restrictions=CommandRestrictionFlags.UNRESTRICTED, pack=None, console_type=None):
    ...
    def named_command(func):
        if not is_valid_command():
            return
        name = aliases[0]
        full_arg_spec = inspect.getfullargspec(func)

        def invoke_command(*args, _session_id=0, **kw):
            if "_account" in full_arg_spec.args or "_account" in full_arg_spec.kwonlyargs:
                kw["_account"] = _session_id
            if "_connection" in full_arg_spec.args or "_connection" in full_arg_spec.kwonlyargs:   # bytecode L388: independent if
                kw["_connection"] = _session_id
            args = parse_args(full_arg_spec, args, _session_id)
            try:
                if not is_command_available(relevant_type):
                    return
                if relevant_type == CommandType.Cheat:
                    with sims4.telemetry.begin_hook(cheats_writer, TELEMETRY_HOOK_COMMAND) as hook:
                        hook.write_string(TELEMETRY_FIELD_NAME, name)
                        hook.write_string(TELEMETRY_FIELD_ARGS, str(args))
                return func(*args, **kw)
            except BaseException as e:
                output("Error: {}".format(e), _session_id)
                logger.warn("Error executing command")
                ...
                raise

        invoke_command.__name__ = "invoke_command ({})".format(name)
        usage = prettify_usage(str.format((inspect.formatargspec)(*full_arg_spec)))
        description = ""
        for alias in aliases:
            register(alias, command_restrictions, invoke_command, description, usage, most_limited_type)
        return func
    return named_command
```
invoke_command disassembly header: `Keyword-only arguments: 1`; `Varnames: _session_id, args, kw, hook, e`; `First Line: 383`. The L388 block begins at offset 28. That is also the jump target of the `_account` test at offset 18, which proves the two tests are independent `if`s.

Output classes: `Output.__call__` (L440-441) calls `output(s, self._context)`. `CheatOutput(Output).__call__` (L448-449) calls `cheat_output(s, self._context)`. `AutomationOutput.__call__` (L466-467) calls `automation_output(s, self._context)`.
```
class Output:
    __slots__ = ('_context', )
    def __init__(self, context):
        self._context = context
    def __call__(self, s):
        output(s, self._context)

class CheatOutput(Output):
    def __call__(self, s):
        cheat_output(s, self._context)
```
`CommandType` (L27): `DebugOnly = 1, Automation = 3, Cheat = 4, Live = 5`. A 2014 modthesims quote lists `Automation = 2`, so values have changed over time. `CommandRestrictionFlags` (L33): `UNRESTRICTED = 0, RESTRICT_SAVE_UNLOCKED = 1`.

### E2. Native `_commands` module stubs for exactly 1.128.90 (COMMUNITY, generated from the game's CPython module)
- Repo: https://github.com/TURBODRIVER/TS4CPythonStubs, commit `76338aa350fb1bf723d03397c3ef44c375441b13`, message "1.128.90", dated 2026-09-23 06:07 TRT. That commit only touched `_filemonitor.pyi`. `_commands.pyi` was last changed in `320ca7a` (annotation pass, 2026-09-16). The README says: "auto-generated from CPython files ... This is not The Sims 4 source code", and "Maxis documentation contains incorrect information."
- File: `_commands.pyi`
```
43 def output(s: 'str', session_id: 'int' = 0):
44     """
45     output(s)
46
47     Output the given string to the command system's output stream.
48     """
...
51 def register(name: 'str', description: 'str', usage: 'str', callback: 'Callable[..., None]') -> 'bool':
52     """
53     register(name, description, usage, callable) -> bool
```
Also lines 9 (`automation_output`), 17 (`client_cheat`), 25 (`describe`), 35 (`execute`) and 59 (`unregister`).
The native module has **no** `cheat_output`, so `cheat_output` exists only in Python. The native `register` takes 4 arguments `(name, description, usage, callback)`, which matches E1's Python `register` forwarding. This is consistent with the E1 layout still applying on 1.128. (INFERENCE)

### E3. S4CL raw-register wrapper (COMMUNITY source, a widely used library)
- Repo: https://github.com/DeviantGameMods/Sims4CommunityLibrary, commit `db1ca99dc448589d4cb1ab315cf4a3bb26c115be` (2026-08-27 20:10 TRT). This is a current mirror that mimics the vanilla decorator.
- File: `Scripts/sims4communitylib/services/commands/common_console_command.py`
```
425            def _invoke_command(*args: str, _session_id: int=0, **kwargs):
426                output = CommonConsoleCommandOutput(_session_id)
...
443                    kwargs['_account'] = _session_id
444                    kwargs['_connection'] = _session_id
...
464                register(alias, command_restrictions, _invoke_command, description, usage, most_limited_type)
```
- File: `Scripts/sims4communitylib/services/commands/common_console_command_output.py`
```
13 from sims4.commands import CheatOutput
16 class CommonConsoleCommandOutput(CheatOutput):
...
19     def connection(self) -> int:
20         """The connection id to the console."""
21         return self._context
```

### E4. uco "unlimited cheat output" mod: an independent reimplementation of vanilla `cheat_output` (COMMUNITY)
- Repo: https://github.com/rivforthesesh/uco, commit `695a387b092d33a6b62254bec0dc692e506079f6` (2021-07-21 00:23 TRT). File: `riv_unlimited_cheat_output.py`
```
13 NO_CONTEXT = sims4.commands.NO_CONTEXT
17 def cheat_output(s, context):
18     if __enable_native_commands:
19         if context != NO_CONTEXT:
...
22                 _commands.output(s, context)
...
39         else:
40             logger.always(s)
...
44 sims4.commands.cheat_output = cheat_output
```
(COMMUNITY) This independently matches E1's `cheat_output` → `_commands.output` path.

### E5. Runtime traceback showing the engine passes `_session_id` (COMMUNITY paste, build 1.63.136.1010, June 2020)
- URL: https://rentry.co/26qwb ("Game Version: 1.63.136.1010, WickedWhims Version: v155i", published 12 Jun 2020 00:56 UTC, which is 03:56 TRT)
- Exact excerpt:
  `File "T:\InGame\Gameplay\Scripts\Core\sims4\commands.py", line 395, in invoke_command [ _session_id : 3, args : [773787236151329571, <PickType.PICK_OBJECT = 2>, ...], kw : {'_connection': 3}, full_arg_spec : FullArgSpec(args=['target_id', ..., '_connection'], ...`
- This was a vanilla UI command (`interactions.has_choices`). The engine supplied `_session_id=3`, and the Python wrapper turned it into `_connection=3`. Line 395 in 1.63 corresponds to the `return func(*args, **kw)` region; it is L399 in the E1 build, because line numbers moved between builds.

### E6. Other community references (COMMUNITY)
- lot51/core-library, commit `a4fc43efdd59e7222c0e68ea6c4917fbc04cf3e2`:
  - `tunables/commands.py` line 80: `client_id = services.client_manager().get_first_client_id()`, used for `execute`/`client_cheat` when no connection is available.
  - `commands.py` line 18: `output('Successfully refreshed picker stock: {}'.format(purchase_picker.__name__), _connection)` (would be silent per E1).
- https://modthesims.info/t/536436 (2014) quotes the vanilla `class CheatOutput(Output): ... cheat_output(s, self._context)`.
- The Medium tutorial by June Hanabi (https://medium.com/analytics-vidhya/the-sims-4-modern-python-modding-part-2-hello-world-77c5bfd3ce4e) documents the `_connection=None` plus `CheatOutput(_connection)` convention.

## Decorator path vs raw `register` (summary)
| | `@sims4.commands.Command(...)` | raw `sims4.commands.register(...)` |
|---|---|---|
| Callback given to native | vanilla `invoke_command(*args, _session_id=0, **kw)` | your handler as-is |
| Connection keyword received | `_connection` / `_account`, injected only if declared in the signature | `_session_id` (native) |
| Arg parsing | `parse_args` via annotations (bool/int/enum/CustomParam) | none; raw strings |
| `command_type` / `restrictions` | used for `is_valid_command`, `is_command_available`, telemetry and `most_limited_type` | discarded by Python `register` in the release build |
| DebugOnly / pack gating | yes; the command is never registered | none |
| Errors | `output("Error: ...")` (silent in retail), `logger.warn`, re-raise | whatever your handler does |
| Return value | the original func (undecorated) | n/a |

## PROPOSED fix
PROPOSED: Keep the raw path and the `_session_id` keyword; it is correct. Replace `sims4.commands.output` with `cheat_output`, or the `CheatOutput` object. If `_session_id` is 0 or None, fall back to the first client id.

```python
import sims4.commands
from sims4.commands import CommandRestrictionFlags, CommandType

def _resolve_connection(session_id):
    # The engine passes _session_id (non-zero for a real console/UI session).
    if session_id:
        return session_id
    try:
        import services
        cid = services.client_manager().get_first_client_id()   # same call lot51 uses (E6)
        if cid:
            return cid
    except Exception:
        pass
    return session_id

def _reply(text, session_id):
    # cheat_output -> _commands.output; sims4.commands.output is a release no-op.
    sims4.commands.cheat_output(str(text), _resolve_connection(session_id))

def _dispatch_x(*args, _session_id=0, **kwargs):
    if kwargs:
        _reply('domus: unexpected kwargs {}'.format(sorted(kwargs)), _session_id)
        return False
    _reply('domus.x ok args={}'.format(list(args)), _session_id)
    return True

sims4.commands.register('domus.x', CommandRestrictionFlags.UNRESTRICTED, _dispatch_x,
                        'Domus probe', 'domus.x [args...]', CommandType.Live)
```
Equivalent one-liner inside a handler: `out = sims4.commands.CheatOutput(_session_id); out('text')`.

PROPOSED alternative (decorator):
```python
@sims4.commands.Command('domus.x', command_type=sims4.commands.CommandType.Live)
def _domus_x(*args, _connection=None):
    out = sims4.commands.CheatOutput(_connection)
    out('domus.x ok args={}'.format(list(args)))
    return True
```
With the decorator you must declare `_connection` (or `_account`) in the signature to receive it. Annotated parameters get parsed. Do not use `sims4.commands.Output(...)` or `sims4.commands.output(...)` for anything that must be visible.

PROPOSED, low level (not recommended): `import _commands; _commands.output(text, session_id)`. This is exactly what `cheat_output` does, minus the `NO_CONTEXT` guard.

## Version caveats
- E1 (vanilla source) comes from a **macOS** install whose `core.zip` entries are dated 2024-11-14. The exact build number is UNKNOWN; it is probably the late-2024 patch line (~1.111). `commands.py` itself had a source mtime of 2022-01-18. That is about 22 months before 1.128.90.1030 (2026-09-22), so the gap is real.
- (INFERENCE) The no-op `output()` very likely still holds on 1.128:
  - `commands.py` was unchanged from 2022-01 to at least 2024-11.
  - TURBODRIVER's 1.128.90 stubs show the same native `_commands` surface (4-arg `register`, `output(s)`, no `cheat_output`).
  - S4CL (Aug 2026) still relies on `_session_id` + `CheatOutput`.
  - macOS and PC share the gameplay Python scripts.
  I have not confirmed the 1.128 PC bytecode itself.
- E5's runtime evidence is from 1.63 (2020). Line numbers differ from E1, but the mechanism is the same.
- uncompyle6 output has known artifacts: `elif` instead of `if` in `Command` and `invoke_command`, and slice rendering like `args[index[:None]]`. I checked the key functions (`output`, `cheat_output`, `register`, `execute`, `invoke_command`, `Command`, `Output`/`CheatOutput`) against the raw disassembly.

## Open questions / how to verify live
1. Confirm `output()` is a no-op on 1.128. From a probe command, write this to a log file (not the console): `sims4.commands.output.__code__.co_names` (expect `()`) and `dis.dis(sims4.commands.output)` (expect only `LOAD_CONST None / RETURN_VALUE`). For contrast, `sims4.commands.cheat_output.__code__.co_names` should include `_commands` and `output`.
2. A/B test in one command: call `sims4.commands.output('A', s)`, then `sims4.commands.cheat_output('B', s)`, then `sims4.commands.CheatOutput(s)('C')`. Expect only B and C to appear.
3. Log `_session_id`, `sorted(kwargs)` and `services.client_manager().get_first_client_id()` for a console-typed command. Expect `_session_id` to be non-zero and equal to the first client id, with kwargs empty.
4. UNKNOWN: native `_commands.output` behaviour for session `0` and `None`. Test `cheat_output('x', 0)` and `cheat_output('x', None)` inside try/except, and log any exception.
5. UNKNOWN: whether another installed mod monkeypatches `sims4.commands.output` or `cheat_output` (uco does the latter). Check the `__module__` and `__code__.co_filename` of both at runtime.
6. Not found: the requested "fivesim" Sims 4 repo. GitHub/web searches only returned unrelated 5SIM SMS-API wrappers (nickpick42/FiveSim, znmn/fivesim-api, ubuygold/FiveSim_TS). I found no public decompiled-script mirror named like TS4-Scripts / Sims4-Decompiled. GitHub code search needs auth (`gh` is not logged in), grep.app returned a Vercel challenge (429), and Sourcegraph returned 0 matches.

## Sources
- https://github.com/asiamserrano/TheSims4ScriptModBuilder @ 40fadf822da383cdff76949a5c0c50e3b2e6968e: `game/unzip/core/sims4/commands.pyc`, `game/zip/gameplay/core.zip`, `config.ini` (vanilla bytecode, decompiled locally).
- https://github.com/TURBODRIVER/TS4CPythonStubs @ 76338aa350fb1bf723d03397c3ef44c375441b13 ("1.128.90"): `_commands.pyi`, `README.md`.
- https://github.com/DeviantGameMods/Sims4CommunityLibrary @ db1ca99dc448589d4cb1ab315cf4a3bb26c115be: `Scripts/sims4communitylib/services/commands/common_console_command.py` (L347-467), `.../common_console_command_output.py` (L13-21).
- https://github.com/rivforthesesh/uco @ 695a387b092d33a6b62254bec0dc692e506079f6: `riv_unlimited_cheat_output.py` (L1-54).
- https://github.com/lot51/core-library @ a4fc43efdd59e7222c0e68ea6c4917fbc04cf3e2: `commands.py` (L9, L18), `tunables/commands.py` (L80), `unit_tests/__init__.py` (L34).
- https://rentry.co/26qwb: runtime traceback, build 1.63.136.1010.
- https://modthesims.info/t/536436 (2014 tutorial); https://medium.com/analytics-vidhya/the-sims-4-modern-python-modding-part-2-hello-world-77c5bfd3ce4e (community docs).
