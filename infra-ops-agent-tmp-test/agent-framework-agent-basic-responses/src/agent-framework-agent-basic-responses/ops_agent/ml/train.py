"""CLI entrypoints for training and evaluation."""

from __future__ import annotations

import argparse
import json

from .inference import FEATURE_SCHEMAS, evaluate_target, train_logistic_regression


def main_train() -> None:
    parser = argparse.ArgumentParser(description="Train logistic regression baseline")
    parser.add_argument("--target", required=True, choices=sorted(FEATURE_SCHEMAS))
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--config", default="config/model_thresholds.yaml")
    args = parser.parse_args()
    meta = train_logistic_regression(args.target, version=args.version)
    print(json.dumps({"status": "trained", "target": args.target, "metrics": meta["metrics"]}, indent=2))


def main_evaluate() -> None:
    parser = argparse.ArgumentParser(description="Evaluate logistic regression baseline")
    parser.add_argument("--target", required=True, choices=sorted(FEATURE_SCHEMAS))
    args = parser.parse_args()
    meta = evaluate_target(args.target)
    print(json.dumps(meta.get("metrics", meta), indent=2))


if __name__ == "__main__":
    main_train()
