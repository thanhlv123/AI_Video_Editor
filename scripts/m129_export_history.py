"""Inspect completed project video exports without modifying files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from creator_studio.export_history import find_completed_exports

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args(argv)
    exports = find_completed_exports(args.project_root)
    print(json.dumps([str(item.output_path) for item in exports], ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
