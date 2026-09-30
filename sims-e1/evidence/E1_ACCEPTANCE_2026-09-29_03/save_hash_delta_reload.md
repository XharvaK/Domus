# E1_ACCEPTANCE_2026-09-29_03 — H STOP After Fresh Reload

Baseline: `pre_acceptance.json`, captured after the Owner's autosave-disabled
setup and before this fresh `Load Game -> LAB_E1` reload.

Post-load capture: `2026-09-29T03:38:32.2873022Z`.

Changed or newly present save files:

- `Slot_ffffffff.save.ver0`
  - baseline SHA256: `232B92532F883C706A25376EF1AE169035B2D1447523A3F64CBE2B1A3F2D318A`
  - post-load SHA256: `2400F383A11A3862A751CBA80AB56E8F5DD68ED84AA15AACB47737EE90947B57`
- `Slot_ffffffff.save.ver1`
  - baseline SHA256: `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671`
  - post-load SHA256: `232B92532F883C706A25376EF1AE169035B2D1447523A3F64CBE2B1A3F2D318A`
- `Slot_ffffffff.save.ver2`
  - baseline: absent
  - post-load SHA256: `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671`

The save delta recurred after all four Autosave triggers were Owner-attested
`OFF`. No Ashley command was entered. No ARM or START occurred.

Disposition: `H = BLOCKED`; separate investigation is required. This run is
stopped under the Owner's explicit retry rule and V1.2a §14-H/§21.1.
