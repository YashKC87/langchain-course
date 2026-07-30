"""Logistic Regression training, explainability, metrics, and inference."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import json
import joblib
import numpy as np
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "models"
CONFIG_PATH = ROOT / "config" / "model_thresholds.yaml"

# Feature schemas per target (baseline explainable set)
FEATURE_SCHEMAS: dict[str, list[str]] = {
    "vm_failure_1h": [
        "cpu_util_p95",
        "mem_available_pct_min",
        "disk_latency_p95",
        "disk_queue_depth_max",
        "iops_p95",
        "net_packet_loss_pct",
        "net_throughput_mbps_p95",
        "failed_service_count",
        "guest_heartbeat_ok",
        "boot_diagnostic_error_count",
        "update_compliance_gap",
        "availability_event_count",
        "resource_health_unhealthy",
        "config_change_count_24h",
        "defender_alert_count_7d",
        "historical_incident_30d",
        "app_response_p95",
    ],
    "endpoint_incident_24h": [
        "cpu_util_p95",
        "mem_util_p95",
        "disk_free_pct",
        "disk_latency_p95",
        "vpn_packet_loss_pct",
        "vpn_disconnect_count",
        "teams_crash_count",
        "defender_alert_count_7d",
        "intune_sync_age_hours",
        "update_compliance_gap",
        "historical_incident_30d",
        "battery_health_score",
        "startup_process_count",
    ],
    "intune_compliance_failure": [
        "days_since_last_sync",
        "missing_update_count",
        "encryption_noncompliant",
        "firewall_noncompliant",
        "antivirus_noncompliant",
        "password_policy_gap",
        "device_age_days",
        "historical_compliance_failures_30d",
    ],
    "avd_session_failure": [
        "host_cpu_p95",
        "host_mem_p95",
        "session_latency_p95",
        "broker_error_count",
        "profile_attach_failures",
        "network_rtt_p95",
        "host_pool_utilization",
        "recent_image_change",
    ],
    "app_deployment_failure": [
        "pipeline_duration_z",
        "test_fail_rate",
        "change_size_loc",
        "dependency_vulnerability_count",
        "target_error_rate_pre",
        "rollback_count_30d",
        "config_drift_score",
        "approval_bypassed",
    ],
    "ticket_escalation_required": [
        "priority_numeric",
        "reopen_count",
        "customer_impact_score",
        "sla_remaining_pct",
        "similar_incident_escalation_rate",
        "assignment_group_backlog",
        "prediction_risk_score",
        "business_vip",
    ],
}


def load_thresholds() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def risk_category(probability: float, bands: dict[str, list[float]]) -> str:
    for name, (lo, hi) in bands.items():
        if lo <= probability <= hi:
            return name.capitalize()
    return "Unknown"


def synthesize_training_frame(target: str, n: int = 2000, seed: int = 42) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Generate realistic correlated synthetic data for baseline training/demo.

    Replace with live feature-store extracts in AML pipeline (OPS_AGENT_DATA_MODE=live).
    """
    rng = np.random.default_rng(seed)
    features = FEATURE_SCHEMAS[target]
    x = rng.normal(size=(n, len(features)))
    # Domain-ish shifts for positive class signal
    weights = rng.normal(0.4, 0.35, size=len(features))
    logits = x @ weights + rng.normal(0, 0.5, size=n)
    # Emphasize a few operationally critical signals
    if "net_packet_loss_pct" in features:
        idx = features.index("net_packet_loss_pct")
        x[:, idx] = rng.gamma(2.0, 0.8, size=n)
        logits += 0.8 * x[:, idx]
    if "mem_util_p95" in features:
        idx = features.index("mem_util_p95")
        x[:, idx] = rng.uniform(40, 99, size=n)
        logits += 0.05 * (x[:, idx] - 70)
    if "disk_free_pct" in features:
        idx = features.index("disk_free_pct")
        x[:, idx] = rng.uniform(2, 60, size=n)
        logits += -0.08 * x[:, idx]
    if "guest_heartbeat_ok" in features:
        idx = features.index("guest_heartbeat_ok")
        x[:, idx] = rng.binomial(1, 0.92, size=n).astype(float)
        logits += -1.2 * x[:, idx]
    if "resource_health_unhealthy" in features:
        idx = features.index("resource_health_unhealthy")
        x[:, idx] = rng.binomial(1, 0.08, size=n).astype(float)
        logits += 1.5 * x[:, idx]
    probs = 1 / (1 + np.exp(-logits))
    y = (probs > 0.5).astype(int)
    return x.astype(float), y, features


@dataclass
class MetricsReport:
    precision: float
    recall: float
    f1: float
    roc_auc: float
    accuracy: float
    confusion_matrix: list[list[int]]
    false_positive_rate: float
    false_negative_rate: float
    brier: float
    inference_latency_ms_p95_estimate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "accuracy": self.accuracy,
            "confusion_matrix": self.confusion_matrix,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
            "calibration_brier": self.brier,
            "inference_latency_ms_p95_estimate": self.inference_latency_ms_p95_estimate,
        }


def train_logistic_regression(target: str, version: str = "1.0.0") -> dict[str, Any]:
    if target not in FEATURE_SCHEMAS:
        raise ValueError(f"Unknown target: {target}")
    x, y, features = synthesize_training_frame(target)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=7, stratify=y)

    base = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )
    # Calibration for reliable probabilities
    model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
    model.fit(x_train, y_train)

    # Latency estimate
    import time

    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        model.predict_proba(x_test[:1])
        times.append((time.perf_counter() - t0) * 1000)
    latency_p95 = float(np.percentile(times, 95))

    proba = model.predict_proba(x_test)[:, 1]
    thr_cfg = load_thresholds()
    decision_thr = thr_cfg.get("models", {}).get(target, {}).get(
        "decision_threshold", thr_cfg["defaults"]["decision_threshold"]
    )
    y_pred = (proba >= decision_thr).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0

    report = MetricsReport(
        precision=float(precision_score(y_test, y_pred, zero_division=0)),
        recall=float(recall_score(y_test, y_pred, zero_division=0)),
        f1=float(f1_score(y_test, y_pred, zero_division=0)),
        roc_auc=float(roc_auc_score(y_test, proba)),
        accuracy=float(accuracy_score(y_test, y_pred)),
        confusion_matrix=cm.tolist(),
        false_positive_rate=float(fpr),
        false_negative_rate=float(fnr),
        brier=float(brier_score_loss(y_test, proba)),
        inference_latency_ms_p95_estimate=latency_p95,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACT_DIR / f"{target}_{version}.joblib"
    meta_path = ARTIFACT_DIR / f"{target}_{version}.meta.json"
    joblib.dump({"model": model, "features": features, "target": target, "version": version}, model_path)

    # Coefficient explainability from underlying LR when available
    coef_map = extract_coefficients(model, features)

    meta = {
        "target": target,
        "version": version,
        "model_path": str(model_path),
        "features": features,
        "metrics": report.to_dict(),
        "decision_threshold": decision_thr,
        "risk_bands": thr_cfg["defaults"]["risk_bands"],
        "coefficients": coef_map,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "LogisticRegression+StandardScaler+PlattCalibration",
        "data_note": "Synthetic baseline — replace with live AML feature ingestion for production",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Also write "latest" pointer
    latest = ARTIFACT_DIR / f"{target}_latest.meta.json"
    latest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "features": features, "target": target, "version": version}, ARTIFACT_DIR / f"{target}_latest.joblib")
    return meta


def extract_coefficients(model: CalibratedClassifierCV, features: list[str]) -> dict[str, float]:
    """Best-effort coefficient extraction for linear explainability."""
    try:
        # CalibratedClassifierCV stores calibrated classifiers
        est = model.calibrated_classifiers_[0].estimator
        if hasattr(est, "named_steps"):
            clf = est.named_steps["clf"]
            coefs = clf.coef_.ravel()
            return {f: float(c) for f, c in zip(features, coefs)}
    except Exception:  # noqa: BLE001
        pass
    return {f: 0.0 for f in features}


class LogisticRegressionPredictor:
    def __init__(self, bundle: dict[str, Any], meta: dict[str, Any]):
        self.bundle = bundle
        self.meta = meta
        self.model = bundle["model"]
        self.features = bundle["features"]
        self.version = bundle["version"]
        self.target = bundle["target"]

    @classmethod
    def load_or_train_baseline(cls, target: str) -> "LogisticRegressionPredictor":
        latest_model = ARTIFACT_DIR / f"{target}_latest.joblib"
        latest_meta = ARTIFACT_DIR / f"{target}_latest.meta.json"
        if not latest_model.exists():
            train_logistic_regression(target)
        bundle = joblib.load(latest_model)
        meta = json.loads(latest_meta.read_text(encoding="utf-8"))
        return cls(bundle, meta)

    def _vectorize(self, feature_payload: dict[str, Any]) -> np.ndarray:
        row = []
        for f in self.features:
            val = feature_payload.get(f, 0.0)
            if isinstance(val, bool):
                val = float(val)
            row.append(float(val) if val is not None else 0.0)
        return np.array([row], dtype=float)

    def predict(self, feature_payload: dict[str, Any]) -> dict[str, Any]:
        x = self._vectorize(feature_payload)
        proba = float(self.model.predict_proba(x)[0, 1])
        thr = float(self.meta.get("decision_threshold", 0.5))
        bands = self.meta.get("risk_bands") or load_thresholds()["defaults"]["risk_bands"]
        pred_class = "Yes" if proba >= thr else "No"

        # Contribution ≈ coefficient * standardized value (approx using raw * coef for transparency)
        coefs = self.meta.get("coefficients") or {}
        contributions = []
        for f in self.features:
            raw = float(feature_payload.get(f, 0.0) or 0.0)
            contributions.append({"feature": f, "contribution": float(coefs.get(f, 0.0)) * raw, "value": raw})
        contributions_sorted = sorted(contributions, key=lambda c: c["contribution"], reverse=True)
        top_pos = [c for c in contributions_sorted if c["contribution"] > 0][:5]
        top_neg = sorted([c for c in contributions_sorted if c["contribution"] < 0], key=lambda c: c["contribution"])[:5]

        return {
            "probability": round(proba, 4),
            "prediction_class": pred_class,
            "risk_category": risk_category(proba, bands),
            "top_positive_contributors": top_pos,
            "top_negative_contributors": top_neg,
            "model_version": f"{self.target}:{self.version}",
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "calibration": {
                "method": "platt",
                "brier_train_eval": self.meta.get("metrics", {}).get("calibration_brier"),
            },
            "threshold_used": thr,
            "risk_thresholds": bands,
            "prediction_window": load_thresholds().get("models", {}).get(self.target, {}).get("prediction_window", ""),
        }


def evaluate_target(target: str) -> dict[str, Any]:
    meta_path = ARTIFACT_DIR / f"{target}_latest.meta.json"
    if not meta_path.exists():
        return train_logistic_regression(target)
    return json.loads(meta_path.read_text(encoding="utf-8"))
