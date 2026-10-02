# Domus 2.3.1 install evidence (L0 motive fix)

STATUS: PASS
DOMUS_NEXT_SHA_BUILT=b9b1f31
BUILD_SHA256=7C8F0522A34370E586E032499707497E50AFFCFAC81850B9B0D1847512A7A913
INSTALLED_SHA256=7C8F0522A34370E586E032499707497E50AFFCFAC81850B9B0D1847512A7A913
VERIFY_PASS_COUNT=9
VERIFY_FAIL_COUNT=0
VERIFY_SKIP_COUNT=0
POST_INSTALL_VERIFY=8 PASS / 0 FAIL / 1 SKIP (-SkipReproducible; full triple at gate b9b1f31)
REMOVED=Mods\AshleyE1\ashley_e1_2.3.0.ts4script (via remove.ps1 -Version 2.3.0)
INSTALL=INSTALL_PASS; remove-then-install; exit 0
MODS_DIFF=only 2.3.0 removed, 2.3.1 added, install_manifest.json rewritten
GAME=closed; never launched or terminated
GATE_HASH_MATCH=yes (installed hash equals gate build hash 7C8F0522)
NOTE=install.ps1 refuses when any ashley_e1 package exists under Mods
(duplicate guard); the 2.3.0->2.3.1 path is remove.ps1 then install.ps1.
