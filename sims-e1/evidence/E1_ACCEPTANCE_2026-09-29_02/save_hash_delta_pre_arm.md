# E1_ACCEPTANCE_2026-09-29_02 — H STOP: Persisted Save Delta Before ARM

The pre-acceptance inventory was captured before removal/install and before
launch. The pre-ARM inventory was captured after the Owner reported stable
`LAB_E1` gameplay and before any probe command was entered.

Capture time for the post-load inventory: `2026-09-29T03:27:00.1828526Z`.

Observed deltas:

- `Slot_ffffffff.save` changed from 943989 bytes,
  `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671`,
  to 1095721 bytes,
  `2400F383A11A3862A751CBA80AB56E8F5DD68ED84AA15AACB47737EE90947B57`.
- New `Slot_ffffffff.save.day.ver0` appeared with SHA256
  `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671`.
- New `Slot_ffffffff.save.ver0` appeared with SHA256
  `232B92532F883C706A25376EF1AE169035B2D1447523A3F64CBE2B1A3F2D318A`.
- New `Slot_ffffffff.save.ver1` appeared with SHA256
  `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671`.
- `Slot_ffffffff.save` last-write timestamp: `2026-09-29T03:24:07.7770013Z`.
- `Slot_ffffffff.save.ver0` last-write timestamp: `2026-09-29T03:23:38.0000000Z`.

No Owner Save was reported during the acceptance interval. The delta is
therefore unexplained for this qualification run. No ARM, START, STOP, or
DISARM command was entered after the delta was detected.

Disposition: `H = BLOCKED`; finite blocker is unexplained persisted save-file
mutation before probe qualification. This run is stopped under V1.2a
§14-H/§21.1. Historical evidence remains untouched.
