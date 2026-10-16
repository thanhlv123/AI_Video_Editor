M116 - AUTONOMOUS BUILD & TEST PIPELINE
=======================================

Purpose
-------
M116 converts the repository from an interactive, operator-driven development
loop into a deterministic release-gate workflow that can run without manual
PowerShell intervention.

What M116 adds
--------------
The release gate applies to M116 and future creator-studio milestone branches.

1. A Windows GitHub Actions release gate.
2. A repository-local Python gate runner: scripts/m116_release_gate.py
3. A local one-command PowerShell wrapper: scripts/m116_release_gate.ps1
4. CI-only dependency declaration: requirements-ci.txt
5. Local autonomous state isolation through .automation/.

Release-gate stages
-------------------
compile - compiles production Python package directories.
import  - discovers test_*.py without executing the suite; loader errors fail.
full    - executes the complete automatic unittest suite.

Environment isolation
---------------------
The GitHub Actions workflow clears external API keys and runs Qt in offscreen
mode. M115 manual/live scripts named manual_*.py are not discovered.

Local use
---------
powershell -ExecutionPolicy Bypass -File scripts\m116_release_gate.ps1

Import-only:
powershell -ExecutionPolicy Bypass -File scripts\m116_release_gate.ps1 -Mode import

Reports are written under .automation\ and that directory is ignored by Git.

Safety
------
M116 does not modify protected production modules. The workflow does not store
or print API credentials and deliberately clears known provider keys in CI.
