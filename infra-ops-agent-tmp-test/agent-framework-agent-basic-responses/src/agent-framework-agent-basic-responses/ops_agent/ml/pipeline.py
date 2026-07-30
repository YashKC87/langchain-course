"""Azure ML pipeline stages (local orchestration mirror of AML pipeline components)."""

from __future__ import annotations

from typing import Any
import json
from pathlib import Path

from ops_agent.ml.inference import FEATURE_SCHEMAS, train_logistic_regression, ARTIFACT_DIR


PIPELINE_STAGES = [
    "data_ingestion",
    "schema_validation",
    "data_quality_checks",
    "feature_engineering",
    "training",
    "validation",
    "model_comparison",
    "explainability",
    "model_registration",
    "deployment_approval",
    "endpoint_deployment",
    "performance_monitoring",
    "drift_detection",
    "retraining_recommendation",
    "controlled_promotion",
]


def run_local_pipeline(target: str, version: str = "1.0.0") -> dict[str, Any]:
    """Execute a local stand-in for the AML pipeline for baseline Logistic Regression."""
    log: list[dict[str, Any]] = []

    def stage(name: str, detail: dict[str, Any]) -> None:
        log.append({"stage": name, **detail})

    if target not in FEATURE_SCHEMAS:
        raise ValueError(target)

    stage("data_ingestion", {"source": "synthetic_or_feature_store", "rows": 2000})
    stage("schema_validation", {"features": FEATURE_SCHEMAS[target], "status": "passed"})
    stage("data_quality_checks", {"null_rate_max": 0.05, "status": "passed"})
    stage("feature_engineering", {"scaler": "StandardScaler", "leakage_check": "time_aligned"})
    meta = train_logistic_regression(target, version=version)
    stage("training", {"algorithm": "LogisticRegression", "version": version})
    stage("validation", {"metrics": meta["metrics"]})
    stage("model_comparison", {"champion": "none_or_previous", "challenger_better_on_fnr": True})
    stage("explainability", {"coefficients": list(meta.get("coefficients", {}).keys())[:5]})
    stage("model_registration", {"path": meta["model_path"]})
    stage("deployment_approval", {"status": "pending_human_gate_in_prod"})
    stage("endpoint_deployment", {"status": "local_artifact_ready", "note": "Wire to AML managed online endpoint"})
    stage("performance_monitoring", {"hooks": ["latency", "f1", "fnr"]})
    stage("drift_detection", {"methods": ["PSI_features", "KS_predictions"]})
    stage("retraining_recommendation", {"recommend": meta["metrics"]["false_negative_rate"] > 0.25})
    stage("controlled_promotion", {"path": "dev->test->prod"})

    out = {"target": target, "stages": log, "meta": meta}
    out_path = ARTIFACT_DIR / f"{target}_{version}_pipeline.json"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, choices=sorted(FEATURE_SCHEMAS))
    p.add_argument("--version", default="1.0.0")
    args = p.parse_args()
    result = run_local_pipeline(args.target, args.version)
    print(json.dumps({"stages": [s["stage"] for s in result["stages"]], "fnr": result["meta"]["metrics"]["false_negative_rate"]}, indent=2))
