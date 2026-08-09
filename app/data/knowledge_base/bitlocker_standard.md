# BitLocker Encryption Standard

## Purpose
Ensure all corporate Windows endpoints maintain full-disk encryption.

## Standard
- BitLocker must be enabled for OS volumes.
- Recovery keys must escrow to Entra ID.
- Suspended protection is allowed for a maximum of 2 hours during approved maintenance.

## Remediation
1. Enable BitLocker via Intune Disk Encryption policy.
2. Confirm protector creation and key escrow.
3. Reboot and validate encryption status = Enabled.
4. Mark compliance check as satisfied only after escrow confirmation.
