# CPU Remediation SOP

## Purpose
Approved Digital Workplace steps for endpoints with sustained CPU utilization above 85%.

## Diagnosis
1. Confirm CPU > 85% for at least 15 minutes.
2. Capture top processes via Intune Endpoint Analytics or local Task Manager export.
3. Identify collaboration clients, browsers, and unmanaged utilities.

## Approved Remediation
1. Notify the user and request save/close of idle applications.
2. Restart Teams and browser extensions that inject overlays.
3. If a non-business process exceeds 30% CPU, quarantine via company software catalog policy.
4. Reboot once after process cleanup.
5. Re-measure DEX score after 30 minutes.

## Escalation
Escalate to Tier-2 Workplace Engineering when CPU remains > 85% after reboot and approved cleanup.
