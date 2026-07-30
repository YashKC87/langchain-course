"""Copy SRE platform code from Logistic Regression into this hosted agent package."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "src" / "agent-framework-agent-basic-responses"
LR_SRC = Path(__file__).resolve().parents[3] / "Logistic Regression" / "src"
LR_CONFIG = Path(__file__).resolve().parents[3] / "Logistic Regression" / "config"
OPS = AGENT_SRC / "ops_agent"
CONFIG = AGENT_SRC / "config"


def main() -> None:
    if not LR_SRC.exists():
        raise SystemExit(f"Source not found: {LR_SRC}")

    if OPS.exists():
        shutil.rmtree(OPS)
    shutil.copytree(LR_SRC, OPS, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    CONFIG.mkdir(parents=True, exist_ok=True)
    for f in LR_CONFIG.glob("*.yaml"):
        shutil.copy2(f, CONFIG / f.name)

    for py in OPS.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        text = text.replace("from src.", "from ops_agent.")
        text = text.replace("import src.", "import ops_agent.")
        py.write_text(text, encoding="utf-8")

    inference = OPS / "ml" / "inference.py"
    text = inference.read_text(encoding="utf-8")
    text = text.replace(
        "ROOT = Path(__file__).resolve().parents[2]",
        "ROOT = Path(__file__).resolve().parents[2]  # agent src root (config/, artifacts/)",
    )
    inference.write_text(text, encoding="utf-8")

    print(f"Integrated ops_agent into {OPS}")
    print(f"Config copied to {CONFIG}")


if __name__ == "__main__":
    main()
