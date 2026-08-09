# VPN Troubleshooting SOP

## Purpose
Restore secure remote connectivity for managed endpoints.

## Diagnosis
1. Count VPN disconnects in the last 24 hours.
2. Capture Wi-Fi signal, latency, and packet loss during failure windows.
3. Confirm gateway health and authentication token freshness.

## Approved Remediation
1. Toggle Wi-Fi / switch to wired if available.
2. Reset the corporate VPN profile using the approved self-service script.
3. Re-authenticate with Conditional Access.
4. Test split-tunnel policy destinations used by Teams and OneDrive.
5. Collect always-on VPN logs if disconnects exceed 3 in 24 hours.

## Escalation
Escalate to Network Services when packet loss > 3% continues after profile reset.
