"""Device telemetry access helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.data.generator import load_devices, load_incidents


class TelemetryService:
    def __init__(self):
        self.devices = load_devices()
        self.incidents = load_incidents()

    def refresh(self) -> None:
        self.devices = load_devices()
        self.incidents = load_incidents()

    def get_device(self, device_id: str) -> dict[str, Any]:
        match = self.devices[self.devices["device_id"] == device_id]
        if match.empty:
            raise KeyError(f"Unknown device_id: {device_id}")
        return match.iloc[0].to_dict()

    def list_devices(self) -> pd.DataFrame:
        return self.devices.copy()

    def incidents_for(self, device_id: str) -> list[dict[str, Any]]:
        match = self.incidents[self.incidents["device_id"] == device_id]
        return match.to_dict(orient="records")

    def fleet_summary(self) -> dict[str, Any]:
        df = self.devices
        healthy = int((df["risk_score"] < 30).sum())
        at_risk = int(((df["risk_score"] >= 30) & (df["risk_score"] < 70)).sum())
        critical = int((df["risk_score"] >= 70).sum())
        return {
            "endpoints": int(len(df)),
            "healthy": healthy,
            "at_risk": at_risk,
            "critical": critical,
            "avg_dex": round(float(df["dex_score"].mean()), 1),
            "avg_risk": round(float(df["risk_score"].mean()), 1),
        }

    def device_prompt_block(self, device_id: str) -> str:
        device = self.get_device(device_id)
        lines = [f"{k}: {v}" for k, v in device.items()]
        return "\n".join(lines)
