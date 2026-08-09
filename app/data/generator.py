"""Deterministic synthetic enterprise endpoint generator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
DEVICES_PATH = DATA_DIR / "devices.csv"
INCIDENTS_PATH = DATA_DIR / "incidents.csv"

REGIONS = ["NA-East", "NA-West", "EMEA", "APAC", "LATAM"]
DEVICE_TYPES = ["Laptop", "Desktop", "VDI"]
OS_VERSIONS = ["Windows 11 23H2", "Windows 11 22H2", "Windows 10 22H2"]


def _special_devices() -> list[dict]:
    return [
        {
            "device_id": "LAPTOP-1204",
            "device_name": "LAPTOP-1204",
            "user": "alex.morgan",
            "region": "NA-East",
            "os_version": "Windows 11 23H2",
            "device_type": "Laptop",
            "cpu_percent": 94,
            "memory_percent": 88,
            "disk_percent": 72,
            "disk_free_gb": 48.0,
            "battery_health": 82,
            "boot_time_seconds": 95,
            "teams_crashes_24h": 8,
            "outlook_crashes_24h": 2,
            "onedrive_sync_errors": 3,
            "vpn_disconnects_24h": 6,
            "wifi_signal": -68,
            "network_latency_ms": 210,
            "packet_loss_percent": 2.4,
            "compliance_status": "Compliant",
            "patch_age_days": 18,
            "antivirus_status": "Current",
            "encryption_status": "Enabled",
            "last_restart": "2026-08-05T08:11:00Z",
            "incident_count_30d": 7,
            "dex_score": 41,
            "risk_score": 86,
        },
        {
            "device_id": "LAPTOP-1507",
            "device_name": "LAPTOP-1507",
            "user": "priya.sharma",
            "region": "EMEA",
            "os_version": "Windows 11 23H2",
            "device_type": "Laptop",
            "cpu_percent": 38,
            "memory_percent": 55,
            "disk_percent": 96,
            "disk_free_gb": 3.2,
            "battery_health": 90,
            "boot_time_seconds": 48,
            "teams_crashes_24h": 0,
            "outlook_crashes_24h": 1,
            "onedrive_sync_errors": 17,
            "vpn_disconnects_24h": 1,
            "wifi_signal": -55,
            "network_latency_ms": 42,
            "packet_loss_percent": 0.1,
            "compliance_status": "Compliant",
            "patch_age_days": 12,
            "antivirus_status": "Current",
            "encryption_status": "Enabled",
            "last_restart": "2026-08-07T06:40:00Z",
            "incident_count_30d": 2,
            "dex_score": 58,
            "risk_score": 71,
        },
        {
            "device_id": "LAPTOP-2031",
            "device_name": "LAPTOP-2031",
            "user": "chris.nguyen",
            "region": "APAC",
            "os_version": "Windows 10 22H2",
            "device_type": "Laptop",
            "cpu_percent": 45,
            "memory_percent": 60,
            "disk_percent": 70,
            "disk_free_gb": 55.0,
            "battery_health": 70,
            "boot_time_seconds": 70,
            "teams_crashes_24h": 1,
            "outlook_crashes_24h": 0,
            "onedrive_sync_errors": 0,
            "vpn_disconnects_24h": 0,
            "wifi_signal": -60,
            "network_latency_ms": 55,
            "packet_loss_percent": 0.0,
            "compliance_status": "Non-Compliant",
            "patch_age_days": 120,
            "antivirus_status": "Outdated",
            "encryption_status": "Disabled",
            "last_restart": "2026-07-20T10:00:00Z",
            "incident_count_30d": 3,
            "dex_score": 49,
            "risk_score": 88,
        },
        {
            "device_id": "LAPTOP-3304",
            "device_name": "LAPTOP-3304",
            "user": "jamie.lee",
            "region": "NA-West",
            "os_version": "Windows 11 23H2",
            "device_type": "Laptop",
            "cpu_percent": 22,
            "memory_percent": 41,
            "disk_percent": 48,
            "disk_free_gb": 180.0,
            "battery_health": 95,
            "boot_time_seconds": 28,
            "teams_crashes_24h": 0,
            "outlook_crashes_24h": 0,
            "onedrive_sync_errors": 0,
            "vpn_disconnects_24h": 0,
            "wifi_signal": -48,
            "network_latency_ms": 24,
            "packet_loss_percent": 0.0,
            "compliance_status": "Compliant",
            "patch_age_days": 5,
            "antivirus_status": "Current",
            "encryption_status": "Enabled",
            "last_restart": "2026-08-08T01:15:00Z",
            "incident_count_30d": 0,
            "dex_score": 94,
            "risk_score": 8,
        },
        {
            "device_id": "LAPTOP-9910",
            "device_name": "LAPTOP-9910",
            "user": "taylor.brooks",
            "region": "NA-East",
            "os_version": "Windows 11 23H2",
            "device_type": "Laptop",
            "cpu_percent": 35,
            "memory_percent": 48,
            "disk_percent": 61,
            "disk_free_gb": 92.0,
            "battery_health": 88,
            "boot_time_seconds": 40,
            "teams_crashes_24h": 5,
            "outlook_crashes_24h": 1,
            "onedrive_sync_errors": 2,
            "vpn_disconnects_24h": 7,
            "wifi_signal": -78,
            "network_latency_ms": 160,
            "packet_loss_percent": 4.8,
            "compliance_status": "Compliant",
            "patch_age_days": 20,
            "antivirus_status": "Current",
            "encryption_status": "Enabled",
            "last_restart": "2026-08-06T21:05:00Z",
            "incident_count_30d": 9,
            "dex_score": 46,
            "risk_score": 79,
        },
    ]


def generate_devices(n: int = 100, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    special = {row["device_id"]: row for row in _special_devices()}
    rows: list[dict] = []
    for i in range(1, n + 1):
        device_id = f"LAPTOP-{i:04d}"
        if device_id in special:
            rows.append(special[device_id])
            continue
        cpu = int(rng.integers(8, 96))
        mem = int(rng.integers(20, 95))
        disk = int(rng.integers(30, 98))
        risk = int(np.clip(0.35 * cpu + 0.25 * mem + 0.2 * disk + rng.normal(0, 8), 1, 99))
        dex = int(np.clip(100 - risk + rng.normal(0, 5), 1, 99))
        rows.append(
            {
                "device_id": device_id,
                "device_name": device_id,
                "user": f"user.{i:04d}",
                "region": REGIONS[i % len(REGIONS)],
                "os_version": OS_VERSIONS[i % len(OS_VERSIONS)],
                "device_type": DEVICE_TYPES[i % len(DEVICE_TYPES)],
                "cpu_percent": cpu,
                "memory_percent": mem,
                "disk_percent": disk,
                "disk_free_gb": round(float(rng.uniform(2, 220)), 1),
                "battery_health": int(rng.integers(55, 100)),
                "boot_time_seconds": int(rng.integers(20, 120)),
                "teams_crashes_24h": int(rng.integers(0, 6)),
                "outlook_crashes_24h": int(rng.integers(0, 4)),
                "onedrive_sync_errors": int(rng.integers(0, 10)),
                "vpn_disconnects_24h": int(rng.integers(0, 6)),
                "wifi_signal": int(rng.integers(-85, -40)),
                "network_latency_ms": int(rng.integers(15, 220)),
                "packet_loss_percent": round(float(rng.uniform(0, 5)), 2),
                "compliance_status": "Compliant" if rng.random() > 0.15 else "Non-Compliant",
                "patch_age_days": int(rng.integers(1, 140)),
                "antivirus_status": "Current" if rng.random() > 0.12 else "Outdated",
                "encryption_status": "Enabled" if rng.random() > 0.08 else "Disabled",
                "last_restart": f"2026-08-{int(rng.integers(1, 8)):02d}T{int(rng.integers(0, 23)):02d}:00:00Z",
                "incident_count_30d": int(rng.integers(0, 8)),
                "dex_score": dex,
                "risk_score": risk,
            }
        )
    # Ensure specials exist even if n < their numbers
    for device_id, row in special.items():
        if device_id not in {r["device_id"] for r in rows}:
            rows.append(row)
    return pd.DataFrame(rows).sort_values("device_id").reset_index(drop=True)


def generate_incidents(devices: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 7)
    categories = [
        "CPU Saturation",
        "Memory Pressure",
        "Teams Crash",
        "VPN Disconnect",
        "Disk Full",
        "OneDrive Sync",
        "Compliance Drift",
        "Wi-Fi Instability",
    ]
    rows: list[dict] = []
    incident_id = 1
    for _, device in devices.iterrows():
        count = int(device["incident_count_30d"])
        for j in range(count):
            rows.append(
                {
                    "incident_id": f"INC-{incident_id:05d}",
                    "device_id": device["device_id"],
                    "category": categories[(incident_id + j) % len(categories)],
                    "severity": rng.choice(["Low", "Medium", "High", "Critical"], p=[0.35, 0.35, 0.2, 0.1]),
                    "opened_at": f"2026-07-{int(rng.integers(1, 28)):02d}T{int(rng.integers(0, 23)):02d}:00:00Z",
                    "summary": (
                        f"{device['device_id']} reported {categories[(incident_id + j) % len(categories)].lower()} "
                        f"with DEX {device['dex_score']}."
                    ),
                }
            )
            incident_id += 1
    # Guarantee rich history for key devices
    for device_id, extras in {
        "LAPTOP-1204": 3,
        "LAPTOP-9910": 4,
    }.items():
        for _ in range(extras):
            rows.append(
                {
                    "incident_id": f"INC-{incident_id:05d}",
                    "device_id": device_id,
                    "category": categories[incident_id % len(categories)],
                    "severity": "High",
                    "opened_at": f"2026-07-{int(rng.integers(1, 28)):02d}T12:00:00Z",
                    "summary": f"Recurring digital workplace degradation on {device_id}.",
                }
            )
            incident_id += 1
    return pd.DataFrame(rows)


def write_datasets(n: int = 100, seed: int = 42) -> tuple[Path, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    devices = generate_devices(n=n, seed=seed)
    incidents = generate_incidents(devices, seed=seed)
    devices.to_csv(DEVICES_PATH, index=False)
    incidents.to_csv(INCIDENTS_PATH, index=False)
    return DEVICES_PATH, INCIDENTS_PATH


def load_devices() -> pd.DataFrame:
    if not DEVICES_PATH.exists():
        write_datasets()
    return pd.read_csv(DEVICES_PATH)


def load_incidents() -> pd.DataFrame:
    if not INCIDENTS_PATH.exists():
        write_datasets()
    return pd.read_csv(INCIDENTS_PATH)


if __name__ == "__main__":
    devices_path, incidents_path = write_datasets()
    print(f"Wrote {devices_path}")
    print(f"Wrote {incidents_path}")
