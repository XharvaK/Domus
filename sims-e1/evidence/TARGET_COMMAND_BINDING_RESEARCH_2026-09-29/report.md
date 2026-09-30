# Project Ashley — Target-Runtime Command Dispatch Binding Research

Date: `2026-09-29`

This is a read-only investigation against the installed Sims 4 runtime. No
Ashley source, artifact, game archive, installation, or runtime state was
modified.

## Identity and extraction

- Ashley HEAD: `2c1a3ea94a069a7d63176a43cf3bd84e06305e36`
- Ashley tree: `d03c949a70ed8b1a0f8cb104c9d1193a01f4c0c6`
- Game archive:
  `E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\core.zip`
- `core.zip` SHA256:
  `641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B`
- Archive entries: `137`
- Target member: `sims4/commands.pyc`
- Member uncompressed size: `9786` bytes
- Member compressed size: `4732` bytes
- Member CRC: `1463286189`
- Extracted SHA256:
  `1463A5E9B2E61C9D9543D5360715078AF89A680688AB8C640984FA56FDA3D972`
- Bounded extraction path:
  `C:\Users\Xharv\AppData\Local\Temp\ashley_e1_target_command_binding_20260929\commands.pyc`

The exact CPython executable used for inspection was:
`C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe`
and reported `3.7.0`.

The pyc header is timestamp/size form, not PEP-552 hash form:

- magic: `420d0d0a`
- magic decimal: `3394`
- flags: `0`
- header word 1: `1642536997`
- header word 2: `18298`
- header bytes: `420d0d0a000000002520e7617a470000`

No native `_commands` module, `.pyd`, `.dll`, or `.so` member was present in
`core.zip`. The Python module imports `_commands` as a separate runtime module.

## Target Python-level contract

### `CommandType` and restrictions

The target class code defines:

```text
CommandType.DebugOnly = 1
CommandType.Automation = 3
CommandType.Cheat = 4
CommandType.Live = 5

CommandRestrictionFlags.UNRESTRICTED = 0
CommandRestrictionFlags.RESTRICT_SAVE_UNLOCKED = 1
```

The module-level `get_command_type` returns `CommandType.Live` and
`get_command_restrictions` returns `CommandRestrictionFlags.UNRESTRICTED`.

### `register`

Code object facts:

```text
co_name              = register
co_firstlineno       = 118
co_argcount          = 6
co_kwonlyargcount    = 0
co_varnames          = ('name', 'restrictions', 'handler', 'description',
                        'usage', 'command_type')
co_flags             = 67
```

The disassembly is mechanically:

```text
if __enable_native_commands:
    _commands.register(name, description, usage, handler)
return None
```

The target Python `register(...)` positional order is therefore:

```text
register(name, restrictions, handler, description, usage, command_type)
```

`restrictions` and `command_type` are accepted by the Python function but are
not forwarded to native `_commands.register`. Native receives four positional
values in this order:

```text
name, description, usage, handler
```

Registration is a no-op when the module-level `_commands` import failed and
`__enable_native_commands` is false.

### `Command`

Code object facts:

```text
co_name              = Command
co_firstlineno       = 332
co_argcount          = 0
co_kwonlyargcount    = 4
co_flags             = 7
co_varnames          = ('command_type', 'command_restrictions', 'pack',
                        'console_type', 'aliases', 'named_command')
```

The recovered callable shape is:

```python
Command(
    *aliases,
    command_type=CommandType.DebugOnly,
    command_restrictions=CommandRestrictionFlags.UNRESTRICTED,
    pack=None,
    console_type=None,
)
```

It computes `relevant_type` from `console_type` and `paths.IS_DESKTOP`,
computes `most_limited_type` with `min(command_type, console_type)` when a
console type exists, and creates `is_valid_command` plus `named_command`.

`is_valid_command` rejects `DebugOnly` and rejects unavailable packs. The
target `is_command_available` function is the reload-protected lambda that
returns `True` for the recovered build. The `Live` value therefore does not
fail this Python-level availability check.

### `named_command` and registration wrapper

Code object facts:

```text
co_name              = named_command
co_firstlineno       = 377
co_argcount          = 1
co_kwonlyargcount    = 0
co_varnames          = ('func', 'invoke_command', 'usage', 'description',
                        'alias')
```

For each alias, the decorator:

1. obtains `inspect.getfullargspec(func)`;
2. constructs `invoke_command`;
3. sets its name to `invoke_command (<alias>)`;
4. derives usage from `inspect.formatargspec(full_arg_spec)`;
5. calls:

```text
register(alias, command_restrictions, invoke_command, description,
         usage, most_limited_type)
```

The decorated function returned to the caller is the original `func`, not the
wrapper.

### `invoke_command`

Code object facts:

```text
co_name              = invoke_command
co_firstlineno       = 383
co_argcount          = 0
co_kwonlyargcount    = 1
co_varnames          = ('_session_id', 'args', 'kw', 'hook', 'e')
co_flags             = 31
```

The recovered wrapper signature is:

```python
invoke_command(*args, _session_id=0, **kw)
```

The bytecode performs this exact sequence:

1. If the original function declares `_account` in `args` or `kwonlyargs`,
   set `kw['_account'] = _session_id`.
2. If the original function declares `_connection` in `args` or
   `kwonlyargs`, set `kw['_connection'] = _session_id`.
3. Call `parse_args(full_arg_spec, args, _session_id)`.
4. Check `is_command_available(relevant_type)` and return `None` if false.
5. Emit cheat telemetry only when the relevant type is `CommandType.Cheat`.
6. Call the semantic function as `func(*args, **kw)`.
7. Catch `BaseException`, write command error output and a warning, then
   re-raise after the target warning logic.

The target wrapper therefore explicitly declares `_session_id` as keyword-only
metadata. `_connection` and `_account` are not directly declared native
metadata at this layer; they are conditionally synthesized for the semantic
function.

An isolated CPython 3.7 execution of the recovered `Command` code confirmed:

```text
wrapper.args       = []
wrapper.varargs    = 'args'
wrapper.kwonlyargs = ['_session_id']
wrapper.varkw      = 'kw'
wrapper.kwdefaults = {'_session_id': 0}
```

For a semantic function declaring `_connection`, calling the wrapper with
`('LAB_E1', _session_id=42)` produced the semantic call
`('LAB_E1', _connection=42)`. For `_account`, it produced
`(_account=42)`. For a function with `**kwargs`, an additional
`unexpected=True` keyword was accepted and forwarded.

### `parse_args`

Code object facts:

```text
co_name              = parse_args
co_firstlineno       = 250
co_argcount          = 3
co_varnames          = ('spec', 'args', 'account', 'index', 'name',
                        'arg_type', 'arg_count', 'arg_value',
                        'arg_values', 'vararg_list')
```

It copies the raw positional list, walks the declared positional arguments,
and converts annotated values through `_parse_arg`. The target conversion
handles booleans, integers, enum values, `CustomParam`, and ordinary callable
types. It also handles annotated `*args`. The `_session_id` value is passed to
conversion error output as `account`. Unannotated string arguments remain raw
strings.

## 1.0.3 comparison

Current 1.0.3 source registers four direct handlers:

```text
register(name, restrictions, _dispatch_*, description, usage,
         CommandType.Live)
```

This six-positional registration call shape and order **MATCHES_TARGET** at
the Python `sims4.commands.register` boundary.

The direct handlers are:

```python
def _dispatch_arm(*args, _session_id=0, **kwargs):
    if len(args) != 1 or kwargs:
        return False
    return _cmd_arm(args[0], _connection=_session_id)
```

The corresponding disarm/start/stop adapters require zero positional
arguments and reject every remaining keyword argument. They manually map the
single `_session_id` keyword to `_connection`.

The current path does **not** use target `Command`, `named_command`, or
`invoke_command`. It therefore bypasses target behavior that is proven by the
bytecode:

- wrapper creation and its keyword-only `_session_id` contract;
- `parse_args` conversion and `CustomParam` handling;
- target availability gating;
- conditional `_account` / `_connection` injection based on the semantic
  function signature;
- target command error handling and Cheat telemetry.

The current adapters accept the Python wrapper's known `_session_id` keyword
and raw positional argument convention if native invokes them with exactly
that shape. They reject any additional kwargs. They also reject or misread a
hidden positional metadata value because arm requires exactly one positional
argument and the other commands require none.

The Python bytecode does not establish whether native `_commands` supplies
additional kwargs, supplies `_connection` or `_account` directly, or places
metadata positionally. That final call is implemented by the native module
imported as `_commands`, which is not present as inspectable Python bytecode
in the target archives examined here.

Finite comparison classification:

```text
REGISTER_CALL_SHAPE = MATCHES_TARGET
CURRENT_1_0_3 = MISMATCH_COMMAND_DECORATOR_SEMANTICS
NATIVE_METADATA_CALL_SHAPE = UNRESOLVED
```

The proven Python-layer mismatch is not sufficient to prove which native
metadata shape caused the two runtime failures.

## Root-cause confidence

`STRONGLY_SUPPORTED` for a Python-layer command-decorator semantic mismatch.
The exact native callback shape remains unresolved. The runtime blocker is
therefore not fully resolved by this archive inspection.

## Next smallest move

Do not repair yet. In a separately authorized diagnostic build, register one
temporary no-op command through the same direct six-argument
`sims4.commands.register` boundary. Its handler should have the broadest
capture-only shape:

```python
def _dispatch_diagnostic(*args, _session_id=0, **kwargs):
    # write exactly one bounded evidence row, then return False
```

The single row should record only:

- positional argument count and bounded type/value representations;
- sorted keyword names and bounded type/value representations;
- `_session_id` type and value;
- a timestamp and diagnostic command name.

It must not call `_STATE`, allocate a session UUID, create a writer, arm an
alarm, sample, or alter save/game state. The one synchronous row may be
written to a dedicated telemetry evidence file. One owner-entered diagnostic
command is sufficient: a row proves the native callback reached the handler
and reveals the actual args/kwargs shape; no row distinguishes registration or
native dispatch failure. This diagnostic is a proposal only and was not
implemented in this pass.

Insufficiency marker:

`PYTHON_LAYER_RESOLVED_NATIVE_DISPATCH_REMAINS_OPAQUE`

## Boundary

- source changed: `NO`
- artifact built: `NO`
- Sims launched during this research pass: `NO`
- game files modified: `NO`
- E1 witnesses during this research pass: `NO`
- E2: `NO`
- shutdown/reboot/sleep/hibernate: `NO`

SIMS4_E1_TARGET_COMMAND_BINDING: NATIVE_DISPATCH_REMAINS_OPAQUE
