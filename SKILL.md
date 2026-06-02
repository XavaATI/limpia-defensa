---
name: limpia-defensa
description: >-
  Runs full-spectrum system cleanup and lightweight, bloatware-free antivirus monitoring on macOS.
  Cleans caches, logs, browser history, installers, and duplicate files, staging copies dynamically
  to Google Drive first for a safe, non-destructive revert capability. Audits LaunchAgents, LaunchDaemons,
  cron tasks, and high-risk folders for unsigned binaries or threat signatures.
---

# Limpia-Defensa Skill

## Overview
The `limpia-defensa` skill packages system optimization and lightweight security auditing into a clean, automated workflow for macOS. It offers two distinct modes: **User-space mode** (safe, unprivileged cleaning/security checks) and **Elevated mode** (using root privileges via `--sudo` to clean system-level caches, logs, and inspect system-wide LaunchDaemons).

To guarantee safety, the skill integrates a non-destructive staging backup flow. No local files are permanently deleted unless they have been successfully copied to the user's active Google Drive mount first.

---

## Dependencies
* **Python 3**: Runs the core scanner and optimizer CLI utility (`scripts/limpia_defensa.py`).
* **Google Drive for Desktop Mount**: The folder `~/Library/CloudStorage/GoogleDrive*` must be mounted and active for cleanup operations (provides fallback/revert capabilities).

---

## Quick Start

### 1. Perform System Audit & Generate Report
```bash
python3 /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/scripts/limpia_defensa.py scan \
  --output /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/scan_results.json \
  --report /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/cleanup_report.md
```

### 2. Execute Non-Destructive Clean (e.g. Caches & Logs)
```bash
python3 /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/scripts/limpia_defensa.py clean \
  --input /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/scan_results.json \
  --categories "caches,logs"
```

### 3. Run Antivirus Audit
```bash
python3 /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/scripts/limpia_defensa.py av-scan \
  --output /Users/xavasena/Documents/NM\ Socialists/limpia-defensa/threats_report.json
```

---

## Utility Scripts

The core command-line script is located at `/Users/xavasena/Documents/NM Socialists/limpia-defensa/scripts/limpia_defensa.py`.

### Subcommands:

#### 1. `scan`
Scans User/System Caches, Log Buffers, left-over dmg/pkg Installers, duplicate file groups, and orphaned App Support folders.
* **Usage**:
  ```bash
  python3 limpia_defensa.py scan --output <json_file_path> [--report <markdown_file_path>]
  ```

#### 2. `clean`
Stages files to Google Drive Cloud Mount under `ComradeCleanup_Backup/YYYY-MM-DD/` and deletes local files.
* **Usage**:
  * *User Mode*:
    ```bash
    python3 limpia_defensa.py clean --input <scan_results_json> --categories "caches,logs,installers,orphans,duplicates"
    ```
  * *Elevated Mode (System paths)*:
    ```bash
    python3 limpia_defensa.py clean --input <scan_results_json> --categories "caches,logs" --sudo
    ```

#### 3. `av-scan`
Audits `/Library/LaunchAgents`, `/Library/LaunchDaemons`, user `cron` tasks, and executes unsigned binary checks in Downloads, Desktop, and `/tmp`.
* **Usage**:
  ```bash
  python3 limpia_defensa.py av-scan --output <threats_json> [--threat-db <hash_signatures_file>]
  ```

#### 4. `restore`
Restores/reverts a staged backup folder or file from Google Drive to its original path.
* **Usage**:
  ```bash
  python3 limpia_defensa.py restore --date <backup_session_directory> --path <original_file_path>
  ```

---

## Common Mistakes

1. **Google Drive Disconnected**: Running `clean` when Google Drive for Desktop is not running or mounted. The script will fail immediately to protect you from losing data without backups.
2. **Missing System Elevation**: Attempting to clean `/Library/Caches` or `/var/log` without passing the `--sudo` flag, resulting in permission failures.
3. **Deleting Staging Date Folders**: Removing session date folders inside `ComradeCleanup_Backup` on Google Drive, which breaks the `restore` revert subcommand lookup capability.
