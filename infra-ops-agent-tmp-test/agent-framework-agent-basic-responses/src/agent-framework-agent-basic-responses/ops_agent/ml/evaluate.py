"""Evaluate command module: python -m src.ml.evaluate --target vm_failure_1h"""

from .inference import evaluate_target, FEATURE_SCHEMAS
import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, choices=sorted(FEATURE_SCHEMAS))
    args = parser.parse_args()
    meta = evaluate_target(args.target)
    print(json.dumps({"target": args.target, "metrics": meta.get("metrics"), "version": meta.get("version")}, indent=2))


if __name__ == "__main__":
    main()
