# Ashley Embodiment Native Command Dispatch Diagnostic Runtime

Date: 2026-09-29

Internal diagnostic version: 1.0.4

Product-facing branding: Embodiment 1.0.0

Artifact: `ashley_e1_1.0.4.ts4script`

Artifact SHA256: `8AA3C31FD54F1085B7727030F10F7B837A5ACA606D2D98DA2591CB229430C84B`

Sims build: `1.128.90.1030`

Evidence root: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\AshleyE1Telemetry`

## Install

- Sims was closed before mutation.
- 1.0.3 removal: `REMOVE_PASS exact artifact absent; saves untouched`.
- 1.0.4 installation: `INSTALL_PASS`.
- Installed package count: exactly one.
- Installed filename: `ashley_e1_1.0.4.ts4script`.
- Installed SHA256: `8AA3C31FD54F1085B7727030F10F7B837A5ACA606D2D98DA2591CB229430C84B`.

## Diagnostic bootstrap

Fresh diagnostic row, recorded verbatim in `bootstrap_diagnostic_1.0.4.jsonl`:

```json
{"diagnostic_version":"1.0.4","diagnostic_kind":"bootstrap","wall_timestamp_ms":1790657388275,"native_bridge_attribute_present":true,"native_bridge_enabled":true,"native_commands_attribute_present":true,"native_commands_type":"module","native_commands_in_sys_modules":true,"sys_modules_native_commands_type":"module","register_callable":true,"command_callable":true}
```

Normal `load_disabled` bootstrap was present with `probe_version` `1.0.4`; the exact row is preserved in `load_disabled_bootstrap_1.0.4.jsonl`.

## Raw callback

`RAW_DIRECT_CALLBACK = OBSERVED`

The exact fresh row is preserved in `diagnostic_final.jsonl` and was:

```json
{"diagnostic_version":"1.0.4","diagnostic_kind":"raw_dispatch","command":"ashley_e1.diag_raw","wall_timestamp_ms":1790657490820,"positional_count":0,"positional":[],"positional_omitted":0,"keyword_count":0,"keyword_names":[],"keyword_names_omitted":0,"keywords":[],"session_id":{"type":"int","repr":"3"}}
```

Observed values:

- positional_count: `0`
- positional items: none
- keyword_count: `0`
- keyword_names: `[]`
- keyword items: none
- session_id type: `int`
- session_id repr: `3`
- wall timestamp: `1790657490820`

## Wrapped control

`WRAPPED_CONTROL_CALLBACK = OBSERVED`

The exact fresh row is preserved in `diagnostic_final.jsonl` and was:

```json
{"diagnostic_version":"1.0.4","diagnostic_kind":"wrapped_dispatch","command":"ashley_e1.diag_wrapped","wall_timestamp_ms":1790657537528,"connection":{"type":"int","repr":"3"},"account":{"type":"int","repr":"3"}}
```

Observed values:

- connection type/repr: `int` / `3`
- account type/repr: `int` / `3`
- wall timestamp: `1790657537528`

## Classification

`NATIVE_COMMAND_DISPATCH_PROVEN`

The direct six-argument registration path reached `_diag_raw`. The target
`Command` decorator path reached `_diag_wrapped`. No success was inferred
from a `register()` return value.

## 1.0.3 historical failure interpretation

`COMMAND_ADAPTER_ROOT_CAUSE = UNRESOLVED`

The authorized raw invocation had no positional or ordinary keyword
arguments. It does not mechanically establish the callback shape for the
prohibited `ashley_e1.arm LAB_E1` invocation. No real Ashley command was
run, so no adapter-cause claim is made.

## Next smallest move

Authorize one bounded downstream semantic-arm-path investigation, without
running an Ashley command or changing source, focused on `_TELEMETRY_ROOT`
admission and `TelemetryWriter(...)` construction/error handling.

## Boundary

- Real Ashley commands run: `NO`
- Normal `TelemetryWriter` created by diagnostic commands: `NO`
- Alarms created by diagnostic commands: `NO`
- Source changed: `NO`
- A-M run: `NO`
- E1-A/B/G: `NO`
- E2: `NO`
- Synthetic input: `NO`
- Power action: `NO`

1.0.4 remains installed. Earlier evidence remains preserved unchanged.

## Additional arm-shaped raw invocation

The additional authorized invocation appended one raw row. The exact row is
preserved in `diagnostic_after_arm_shape.jsonl` and was:

```json
{"diagnostic_version":"1.0.4","diagnostic_kind":"raw_dispatch","command":"ashley_e1.diag_raw","wall_timestamp_ms":1790657885239,"positional_count":1,"positional":[{"index":0,"type":"str","repr":"'lab_e1'"}],"positional_omitted":0,"keyword_count":0,"keyword_names":[],"keyword_names_omitted":0,"keywords":[],"session_id":{"type":"int","repr":"3"}}
```

`ARM_NATIVE_CALLBACK_SHAPE = COMPATIBLE_WITH_1_0_3_ADAPTER`

`1.0.3 ADAPTER COMPATIBILITY = COMPATIBLE`

The adapter checks only one positional argument and no ordinary keyword
arguments. It would pass the string to `_cmd_arm`. The native callback
delivered the value as lowercase `'lab_e1'`, not the typed uppercase form.
The 1.0.3 adapter would not reject that value; the downstream valid-arm-name
gate would reject it because `_cmd_arm` accepts only `LAB_E1` and
`LAB_E1_FORK`.

`HISTORICAL ARM FAILURE = ADAPTER_CAUSE_NOT_SUPPORTED`

The next investigation is downstream semantic arm-path truth only: first the
valid arm-name gate and then `_STATE` / `_WRITER_IDLE`, `_TELEMETRY_ROOT`,
`TelemetryWriter(...)` construction, and background writer start/open failure.
No such investigation was run in this diagnostic pass.
