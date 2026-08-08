# OneDrive Sync Troubleshooting SOP

## Purpose
Restore OneDrive synchronization for corporate files on Windows endpoints.

## Diagnosis
1. Confirm OneDrive sync error count and affected libraries.
2. Verify free disk space is above 5 GB.
3. Check Files On-Demand and Known Folder Move status.

## Approved Remediation
1. Pause sync for 5 minutes.
2. Ensure free disk capacity is restored using the Disk Space Remediation SOP.
3. Reset OneDrive with `onedrive.exe /reset` then relaunch.
4. Re-apply Known Folder Move policy if Desktop/Documents/Pictures are unsynced.
5. Confirm zero sync errors for 30 minutes.

## Escalation
Escalate to Collaboration Services when a specific SharePoint library remains unsynced after reset and disk recovery.
