# Intune Compliance Standard

## Purpose
Define required compliance posture for Digital Workplace endpoints.

## Required Controls
- Encryption enabled (BitLocker)
- Antivirus signatures current
- Patch age <= 30 days for critical updates
- Supported OS version
- Device registered to Entra ID / Intune

## Non-Compliance Handling
1. Notify user through Company Portal.
2. Trigger compliance remediation scripts.
3. Restrict access to sensitive apps via Conditional Access when encryption is disabled.
4. Re-evaluate compliance within 24 hours.
