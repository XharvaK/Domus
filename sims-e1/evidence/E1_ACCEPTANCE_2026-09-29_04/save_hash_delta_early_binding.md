# E1_ACCEPTANCE_2026-09-29_04 — Save Hash Delta

The fresh baseline was captured at `2026-09-29T04:04:14.9825111Z` after the
Owner confirmed all four Autosave triggers OFF, completed the deliberate LAB
setup Save, and fully quit Sims. The post-command inspection was captured at
`2026-09-29T04:10:19.7179919Z`.

The following content hashes changed or appeared:

| File | Baseline | Post-check | Disposition |
|---|---|---|---|
| `Slot_ffffffff.save` | 1095721 bytes; `2400F383A11A3862A751CBA80AB56E8F5DD68ED84AA15AACB47737EE90947B57` | 1095750 bytes; `CEE0F95D0DF11E64A62621158DE9A996B6C11157A13C81351A402763775430F2` | hash changed |
| `Slot_ffffffff.save.ver1` | 1095753 bytes; `232B92532F883C706A25376EF1AE169035B2D1447523A3F64CBE2B1A3F2D318A` | 1095721 bytes; `2400F383A11A3862A751CBA80AB56E8F5DD68ED84AA15AACB47737EE90947B57` | hash changed |
| `Slot_ffffffff.save.ver2` | 943989 bytes; `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671` | 1095753 bytes; `232B92532F883C706A25376EF1AE169035B2D1447523A3F64CBE2B1A3F2D318A` | hash changed |
| `Slot_ffffffff.save.ver3` | absent | 943989 bytes; `FA92FEA250BBE90733769C4AC06928771A0BE4718E27C1773305A242104BE671` | new file |

`Slot_ffffffff.save.ver0` and `steam_autocloud.vdf` had timestamp changes but
their content hashes remained equal to baseline. The evidence does not assign
causality to the rejected unarmed command; it records that the required
baseline-to-post interval was not unchanged.
