INSTALL = FAIL (step 3; mandatory STOP before removal)
STATUS: STOP

TASK
J110: install probe 2.1.0 under the exact J108/J104/J102 procedure.

STATE
Stopped at step 3, before removal. Checkout BUILD_SHA256 differs from the required hash. verify.ps1 also exited 1 with VERIFY_FAIL REPRODUCIBLE.
Initial checkout was clean on e2-run (05ea413f7cd74eaa84bee5f53531ea8a2c4a6221); no untracked leftovers were present. TS4_x64 was absent before checkout and at the stop.
git checkout domus-next and git fetch origin succeeded. HEAD and origin/domus-next equal 1e052921f2201b2f0e46749a14c5566c65cf4eed; tree=82935e081998202e3314d1bdc05606ff0998b289. Live git ls-remote confirmed the same remote SHA. Origin is https://github.com/XharvaK/Domus.git.
No Domus-d9gate worktree existed. No existing worktree was removed by this job.

MODEL_USED
gpt-6.1-sol; model_reasoning_effort=low; service_tier=default, as specified by the session launcher in the user instruction.

CHANGED
Switched checkout to the required domus-next branch. Created the uncommitted evidence folder and regenerated ignored build outputs. Installed probe remains 2.0.2. No removal or installation was attempted.

EVIDENCE
Before inventory records every live save file and every file in all existing AshleyE1E1Backup_* folders, with relative path, length, LastWriteTime and SHA256.
Exactly one Ashley package existed under Mods: Mods\AshleyE1\ashley_e1_2.0.2.ts4script.
powershell -NoProfile -ExecutionPolicy Bypass -File sims-e1\tools\build.ps1 -Version 2.1.0 -ImplementedCommit 1e052921f2201b2f0e46749a14c5566c65cf4eed
BUILD_PASS; BUILD_SHA256=9D61E97A4BA86C47AF0D5A07AD28DD51ABD117E99E2882F4B59561802DBCBA0A
powershell -NoProfile -ExecutionPolicy Bypass -File sims-e1\tools\verify.ps1 -Version 2.1.0 -HostPythonPath C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe
VERIFY_FAIL REPRODUCIBLE BUILD_SHA256 mismatch: AF3E8DBD8140BA42B2CA28D9AB2323E39E2DA821E726053A0C61732C9345ECC5 expected=9D61E97A4BA86C47AF0D5A07AD28DD51ABD117E99E2882F4B59561802DBCBA0A
The fresh-worktree hash in the verifier matches the job's required hash; the checkout artifact does not. Cause was not investigated or repaired under this STOP procedure.
Full output: sims-e1/evidence/D9_INSTALL_2_1_0_2026-10-01/build_verify_j110.txt. Build manifest and verify.log are preserved there.
Read-only stop inventories confirm live saves and all pre-existing backup files remain identical to BEFORE.

NOT DONE
Removal, installation, new backup creation, installed 2.1.0 verification, post-install inventory, evidence commit and push. No game or Steam launch; no Mint, Discord or The Finals action.

NEXT
Resolve the checkout/fresh-worktree build mismatch through a separately authorized job before installation.

E2_RUN_SHA_BUILT=not applicable; required branch is domus-next
DOMUS_NEXT_SHA_BUILT=1e052921f2201b2f0e46749a14c5566c65cf4eed
BUILD_SHA256=9D61E97A4BA86C47AF0D5A07AD28DD51ABD117E99E2882F4B59561802DBCBA0A
EXPECTED_BUILD_SHA256=AF3E8DBD8140BA42B2CA28D9AB2323E39E2DA821E726053A0C61732C9345ECC5
BUILD_REPRODUCED=no
VERIFY_PASS_COUNT=7
VERIFY_FAIL_COUNT=1
VERIFY_SKIP_COUNT=0
REMOVE=not run
REMOVED=none
INSTALL=not run
BACKUP_FOLDER=not created
BACKUP_BYTES=not applicable
INSTALLED_ARTIFACT_SHA256=2B8550730465C390BD2438B9893F5027F58BDEAC8B7EA903484FE5A77ADFC415 (existing 2.0.2)
INSTALLED_SHA256=not applicable; 2.1.0 not installed
SAVES_IDENTICAL=yes (BEFORE versus stop snapshot; no installation occurred)
EXISTING_BACKUPS_IDENTICAL=yes
OPTIONS_INI=scriptmodsenabled = 1; modsdisabled = 0
AUTONOMY_OPTIONS=autonomyhousehold = 1; autonomydisabledforactivesim = 1
TELEMETRY_ROOT=exists; LEDGER=exists
EVIDENCE_COMMIT=none
PUSHED=no

DEVIATIONS
The explicitly required HostPythonPath workaround was used. An initial before-evidence command had a PowerShell parse error (empty pipe element); it executed no operations and was corrected before inventory capture. No source changes or build/install retries occurred. Stop-time read-only inventories were recorded instead of claiming post-install evidence.
