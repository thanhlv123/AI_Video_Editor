"""M132 Windows-local release-candidate acceptance gate.

Local mode validates the repository-local environment created by M131.
CI mode validates the same runtime/GUI capabilities using the CI interpreter
without requiring a repository-local .venv.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from creator_studio import launcher
from creator_studio import runtime_doctor
from scripts import m131_bootstrap


ROOT = Path(__file__).resolve().parents[1]


def run_acceptance(*, ci_mode: bool = False) -> dict:
    bootstrap = m131_bootstrap.inspect_environment(ROOT)
    startup = launcher.inspect_runtime()
    doctor = runtime_doctor.diagnose()

    prerequisites_ready = (
        startup.get("status") == "ready"
        and doctor.get("status") == "ready"
        and (ci_mode or bootstrap.get("status") == "ready")
    )

    smoke: dict
    if prerequisites_ready:
        try:
            smoke = launcher.smoke_gui()
        except Exception as exc:
            smoke = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
    else:
        smoke = {
            "status": "skipped",
            "reason": "prerequisites_not_ready",
        }

    ready = prerequisites_ready and smoke.get("status") == "passed"
    return {
        "format": "creator_studio.windows_local_acceptance.v1",
        "mode": "ci" if ci_mode else "local",
        "status": "ready" if ready else "blocked",
        "bootstrap": bootstrap,
        "startup": startup,
        "runtime_doctor": doctor,
        "gui_smoke": smoke,
    }


def write_report(report: dict, path: Path | None) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Windows-local Creator Studio release readiness."
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Use current CI Python instead of requiring repository-local .venv.",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    report = run_acceptance(ci_mode=args.ci)
    write_report(report, args.report)
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
