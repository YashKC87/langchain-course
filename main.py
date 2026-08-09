"""Convenience launcher for local demos."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="SLM + Frontier Pattern Lab launcher")
    parser.add_argument(
        "command",
        choices=["api", "ui", "data", "test"],
        help="api | ui | data | test",
    )
    args = parser.parse_args()
    if args.command == "api":
        raise SystemExit(
            subprocess.call(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"]
            )
        )
    if args.command == "ui":
        raise SystemExit(
            subprocess.call(
                [sys.executable, "-m", "streamlit", "run", "app/ui/dashboard.py"]
            )
        )
    if args.command == "data":
        raise SystemExit(subprocess.call([sys.executable, "-m", "app.data.generator"]))
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"]))


if __name__ == "__main__":
    main()
