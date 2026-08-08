# Microsoft Teams Troubleshooting SOP

## Purpose
Stabilize Teams crashes and media quality issues on managed Windows endpoints.

## Diagnosis
1. Review Teams crash count for the last 24 hours.
2. Confirm GPU driver currency and overlay conflicts.
3. Check whether VPN or packet loss coincides with meeting failures.

## Approved Remediation
1. Clear the Teams cache under `%AppData%\Microsoft\Teams`.
2. Repair the Teams app from Company Portal / Intune.
3. Disable hardware acceleration temporarily for testing.
4. Update Teams to the enterprise-approved channel build.
5. Validate with a 10-minute test call.

## Escalation
Escalate when crashes persist after cache clear + repair, especially with concurrent VPN instability.
