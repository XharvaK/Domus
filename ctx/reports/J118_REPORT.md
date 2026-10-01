STATUS: PASS

COMMIT: 7b5b778a2ac2aab61f9b77a507edbe53e10b23f8
TREE: 918caa900f458734731fc0467d8367c6d1ffebd9
MODEL: gpt-6.1-sol; model_reasoning_effort=low; service_tier=default (Owner-supplied session identity).

PYTHON: CPython 3.7.0 x64; 3.7.0 (v3.7.0:1bf9cc5093, Jun 27 2018, 04:59:51) [MSC v.1914 64 bit (AMD64)].
PYTHON_PATH: C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe
HOST_PYTHON: Python 3.14.3; 3.14.3 (tags/v3.14.3:323c59a, Feb  3 2026, 16:04:56) [MSC v.1944 64 bit (AMD64)].
HOST_PYTHON_PATH: C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe

SUITE TALLIES
- Pinned CPython 3.7.0: 229 tests; 0 failures; 0 errors; 0 skips; OK; exit 0; 5.549s.
- Host Python 3.14.3: 229 tests; 0 failures; 0 errors; 0 skips; OK; exit 0; 5.165s.
- Whole sims-e1/tests suite, pattern test_*.py, using J116b's -c invocation and sys.path.insert(0, 'sims-e1/tests').
- verify.ps1 also passed both suite invocations in the gate checkout and each of its two fresh worktrees.

Suite invocation (each Python path above):
```python
import sys, unittest; sys.path.insert(0, 'sims-e1/tests'); suite = unittest.defaultTestLoader.discover('sims-e1/tests', pattern='test_*.py'); result = unittest.TextTestRunner(verbosity=1).run(suite); print('TALLY tests=%d failures=%d errors=%d skips=%d' % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped))); sys.exit(0 if result.wasSuccessful() else 1)
```

GUARDS: sims-e1/tools/check_guards.py sims-e1/src under pinned CPython 3.7.0; no output; exit 0; OK.

THREE BUILD HASHES
Checkout BUILD_SHA256=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
First fresh worktree BUILD_SHA256=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
Second fresh worktree BUILD_SHA256=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
All three equal.

BUILT-ARTIFACT GET-FILEHASH
Command: Get-FileHash -Algorithm SHA256 -LiteralPath sims-e1\build\ashley_e1_2.2.1.ts4script
Algorithm: SHA256
Hash: EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
Path: C:\Users\Xharv\Projects\Domus-d11gate\sims-e1\build\ashley_e1_2.2.1.ts4script
Equals all three build hashes.

BUILD OUTPUT (exit 0)
Command: powershell -NoProfile -ExecutionPolicy Bypass -File sims-e1\tools\build.ps1 -Version 2.2.1
```text
BUILD_PASS artifact=C:\Users\Xharv\Projects\Domus-d11gate\sims-e1\build\ashley_e1_2.2.1.ts4script
BUILD_SHA256=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
```

FULL VERIFY OUTPUT (exit 0)
Command: powershell -NoProfile -ExecutionPolicy Bypass -File sims-e1\tools\verify.ps1 -Version 2.2.1 -HostPythonPath C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe
```text
VERIFY_PASS compiler=3.7.0
VERIFY_PASS host=Python 3.14.3
VERIFY_PASS AST guards
VERIFY_PASS focused tests under CPython 3.7.0
VERIFY_PASS focused tests under host Python
VERIFY_PASS artifact layout, magic, hashes, manifest, source digest
VERIFY_PASS ZIPIMPORT PROBE_VERSION=2.2.1
VERIFY_PASS REPRODUCIBLE BUILD_SHA256=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07 first=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07 second=EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07
VERIFY_PASS all checks
```
VERIFY tallies: 9 PASS including summary; 0 FAIL; 0 SKIP in top-level output. All checks enabled. Only verifier-owned nested runs use -SkipReproducible.

BUILT ARTIFACT PATH
C:\Users\Xharv\Projects\Domus-d11gate\sims-e1\build\ashley_e1_2.2.1.ts4script
The artifact is removed with the gate worktree during required cleanup.

IDENTITY AND SCOPE
- Step 1: git rev-parse d11-autostart matched the exact candidate; git merge-base --is-ancestor 0605205745c88dd3529eda8aa0dafcad9a4812ad d11-autostart exited 0.
- Gate created with git worktree add C:\Users\Xharv\Projects\Domus-d11gate d11-autostart. All suite, guard, build and verify commands ran there.
- Main initially clean on domus-next at 0605205745c88dd3529eda8aa0dafcad9a4812ad; tree e6b4b3fa915867383198830738a174539803e0f2.
- Gate remained clean. Before report writing, only main and gate worktrees remained; verifier-owned temporary worktrees were removed.
- Read J118, J116b and its report, and the four referenced packets. J118 scope controls; no subsequent checkpoint actions executed.
- No source edits, commits, pushes, merges, installs, game operation, saves/Mods access, Mint or Discord contact. As in J116b, the required verifier read and hashed the recorded game Python DLL for its artifact check. No game file changed.
- No subagents used. Helper pytest excluded as required. PASS establishes the requested offline gate, not live game acceptance.

DEVIATIONS
No gate deviations. Suite invocation adds an explicit tally line without changing discovery or success criteria.

CLEANUP
Report written before gate removal. Cleanup result will be appended after execution.
git worktree remove C:\Users\Xharv\Projects\Domus-d11gate succeeded, exit 0, without --force. Gate path is absent. Only the main worktree remains. d11-autostart retained at 7b5b778a2ac2aab61f9b77a507edbe53e10b23f8. Main remains clean on domus-next at 0605205745c88dd3529eda8aa0dafcad9a4812ad, tree e6b4b3fa915867383198830738a174539803e0f2. Gate build artifacts were removed with the worktree.
