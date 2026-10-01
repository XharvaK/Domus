# D10 live check: probe 2.2.0 on XQX, 2026-10-01 ~04:28–04:31 TRT

Run by the architect (agent:architect) on XQX, with the Owner at the game. Read-only: no arm, no trial.

1. The Owner loaded LAB_E1 and typed nothing. The bootstrap at 04:27 (main-menu import) recorded `inbox_autostart: "MANAGER_UNAVAILABLE"`: `services.get_zone_manager()` is None at module import, so the C3b zone-RUNNING registration never happened, and `cmd/` was absent after the lot loaded. **The C3b automatic start FAILED at runtime** (RUNTIME_UNVERIFIED → FALSIFIED for the import-time registration).
2. Fallback: the Owner typed `ashley_e1.inbox`. The console replied `INBOX ON`, which is visible, so the `cheat_output` fix (C0/R-H2) is **live-verified**. `cmd/{inbox,outbox,done}` were created.
3. A `status` envelope (id c74835f6…) was answered in about 2 s: `status OK`, UNARMED, probe 2.2.0, schema 3, `inbox "on"`, issuer attributed `agent:architect`, and the done marker was written. (Note: `inbox_autostart` then read "STARTED" because the fallback shares the start function. It doesn't distinguish console from zone starts.)
4. An expired `status` envelope (id ac4e273e…) got `REJECTED EXPIRED`, `result {ok:false, lines:[]}`: the B1 behaviour is live-verified.

Files: the bootstrap summary, plus a `cmd/` snapshot (two outbox replies, two done markers).
