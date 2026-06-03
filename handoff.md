# Handoff: `limpia-defensa` Custom Skill Integration

Welcome to the new chat session! This folder is an independent, isolated workspace set up to develop, test, and distribute the **`limpia-defensa`** system optimizer and malware scanner for macOS.

---

## 📂 Current Workspace State
* **Location**: `/Users/xavasena/collectivo/limpiada`
* **VCS / Git**: Freshly initialized independent Git repository on branch `clean-defense-branch` (completely separated from the main root directories to prevent any accidental changes).

---

## 🛠️ Files Installed in this Directory
1. **`scripts/limpia_defensa.py`**: Portable Python 3 CLI engine that manages:
   * **Full-Spectrum Scan**: User/System caches, logs, browser history (Safari, Chrome), orphaned App Support folders, and duplicate files.
   * **Dynamic Google Drive Backup Mount Resolution**: Scans `~/Library/CloudStorage` dynamically to resolve local GDrive mount paths safely, removing hardcoded user emails.
   * **Non-Destructive Cleanup**: Stages all files to Google Drive under `ComradeCleanup_Backup/YYYY-MM-DD/` preserving path structure before deleting locally.
   * **Lightweight Security Audit (AV)**: Audits launch vectors (LaunchAgents, LaunchDaemons, crontab), queries shebang permissions, and runs signature hash lists.
   * **Fallback Restore**: Copies files back from GDrive backup staging directories to their original local paths.
2. **`SKILL.md`**: Custom agent instruction reference guide defining flags, categories, subcommands, and usage rules.
3. **`scan_results.json` & `cleanup_report.md`**: Sample outputs from the dry-run system scan verifying the scanning logic runs successfully.
4. **`threats_report.json`**: Sample output from the AV threat scan verifying codesign checks and persistence sweeps are clean.

---

## 🚀 How to Execute Commands

To run a scan:
```bash
python3 scripts/limpia_defensa.py scan \
  --output scan_results.json \
  --report cleanup_report.md
```

To run a clean (automatically backs up to Google Drive first):
```bash
python3 scripts/limpia_defensa.py clean \
  --input scan_results.json \
  --categories "caches,logs"
```

To run the AV audit:
```bash
python3 scripts/limpia_defensa.py av-scan \
  --output threats_report.json
```

---

## 📋 Recommended Next Steps

1. **Test the Restore Functionality**: Verify that running the `restore` subcommand successfully pulls files back from Google Drive to their original paths.
2. **SwiftUI / GUI Integration**: Discuss the best path to bundle this script inside a native macOS GUI app (such as writing a lightweight SwiftUI wrapper with a Web View panel).
3. **Homebrew Packaging**: Create a Homebrew Cask definition (`comrade-cleanup.rb`) to make it easily distributable and installable via:
   ```bash
   brew install --cask comrade-cleanup
   ```
