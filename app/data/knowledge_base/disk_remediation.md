# Disk Space Remediation SOP

## Purpose
Recover endpoints with critically low free disk space.

## Thresholds
- Warning: disk utilization >= 85%
- Critical: disk utilization >= 95% or free space < 5 GB

## Approved Remediation
1. Empty Recycle Bin and `%TEMP%` using the approved cleanup package.
2. Clear Delivery Optimization and Windows Update leftovers.
3. Move large personal media out of the system disk.
4. Target free space of at least 15% before closing the ticket.
5. Re-run storage health validation and capture before/after free GB.

## OneDrive Interaction
If OneDrive sync errors are also present, complete disk cleanup before OneDrive repair so the sync engine has room to stage files.

## Escalation
Escalate to Desktop Engineering when free space cannot be restored above 10 GB using approved cleanup.
