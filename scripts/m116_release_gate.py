from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
DEFAULT_PATTERN = "test_*.py"


@dataclass
class GateResult:
    mode: str
    status: str
    tests_discovered: int
    loader_errors: int
    exit_code: int
    duration_seconds: float


def discover() -> tuple[unittest.TestSuite, unittest.TestLoader]:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS), pattern=DEFAULT_PATTERN)
    return suite, loader


def run_import_gate() -> GateResult:
    started = time.monotonic()
    suite, loader = discover()
    count = suite.countTestCases()
    errors = len(loader.errors)
    if loader.errors:
        print("\n\n".join(loader.errors), file=sys.stderr)
    return GateResult(
        mode="import",
        status="passed" if errors == 0 else "failed",
        tests_discovered=count,
        loader_errors=errors,
        exit_code=0 if errors == 0 else 1,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def run_full_gate(verbosity: int) -> GateResult:
    started = time.monotonic()
    suite, loader = discover()
    count = suite.countTestCases()
    errors = len(loader.errors)
    if errors:
        print("\n\n".join(loader.errors), file=sys.stderr)
        return GateResult(
            mode="full", status="failed", tests_discovered=count,
            loader_errors=errors, exit_code=1,
            duration_seconds=round(time.monotonic() - started, 3),
        )
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    ok = result.wasSuccessful()
    return GateResult(
        mode="full",
        status="passed" if ok else "failed",
        tests_discovered=count,
        loader_errors=errors,
        exit_code=0 if ok else 1,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def run_compile_gate() -> GateResult:
    started = time.monotonic()
    targets = [
        "ai", "automation", "config", "core", "creator_studio",
        "engine", "media", "pipeline", "scenes", "stock",
        "subtitles", "transcription",
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", *targets],
        cwd=ROOT,
        check=False,
    )
    ok = completed.returncode == 0
    return GateResult(
        mode="compile", status="passed" if ok else "failed",
        tests_discovered=0, loader_errors=0, exit_code=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def write_report(result: GateResult, report_path: Path | None) -> None:
    payload = asdict(result)
    print(json.dumps(payload, indent=2))
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="M116 deterministic release gate for AI Video Editor.")
    parser.add_argument("mode", choices=("compile", "import", "full"), nargs="?", default="import")
    parser.add_argument("--verbosity", type=int, default=1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.mode == "compile":
        result = run_compile_gate()
    elif args.mode == "import":
        result = run_import_gate()
    else:
        result = run_full_gate(args.verbosity)
    write_report(result, args.report)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
