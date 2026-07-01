# Handoff: `limpia-defensa` Custom Skill Integration

Welcome to the new chat session! This folder is an independent, isolated workspace set up to develop, test, and distribute the **`limpia-defensa`** system optimizer and malware scanner for macOS, alongside the Capacitor Android mobile engine.

---

## 📂 Current Workspace State
* **Location**: `/Users/xavasena/collectivo/limpiada`
* **VCS / Git**: Active Git repository on branch `clean-defense-branch`.

---

## 🛠️ Files Installed in this Directory
1. **`scripts/limpia_defensa.py`**: Portable Python 3 CLI engine that manages:
   * **Full-Spectrum Scan**: User/System caches, logs, browser history, App Support folders, and duplicate files.
   * **Dynamic Backup Mount Resolution**: Dynamic resolution of local/cloud mounts for staging.
   * **Non-Destructive Cleanup & Quarantine**: Stages files to backups before deletion; supports quarantined AV process termination.
   * **AV Scanner (Quetzal Core)**: Audits active memory, detects deleted-on-launch executables, unsigned binaries, and open socket anomalies.
2. **`scripts/LimpiaDefensaGUI.swift`**: Native macOS SwiftUI GUI source code containing views, state handlers, AppleScript elevation wrappers, and security controls.
3. **`scripts/limpia-defensa-gui`**: Mach-O arm64 compiled and code-signed macOS GUI app binary.
4. **`scripts/cloud_migration_stager.py`**: Automated disk migration script for moving large files/VMs to external disks/Drive.
5. **`ska-production-kit/`**: Capacitor mobile project synced with the remote GCP VM `antigravity-cloud-workspace`.
6. **`ska-mobile-engine.apk`**: Compiled debug Android package mirrored locally.

---

## 🚀 How to Execute & Sign Commands

### 1. Build and Code-Sign the GUI
To recompile the SwiftUI application as a library executable:
```bash
swiftc -parse-as-library scripts/LimpiaDefensaGUI.swift -o scripts/limpia-defensa-gui
```

To sign the compiled binary with an ad-hoc certificate for local macOS verification:
```bash
codesign --force --deep --sign - scripts/limpia-defensa-gui
```

To verify the code signature:
```bash
codesign -dvv scripts/limpia-defensa-gui
```

### 2. Antivirus Memory Scan & Quarantine
To run the AV audit via CLI:
```bash
python3 scripts/limpia_defensa.py av-scan --output threats_report.json
```

To quarantine a file and kill its running process (requires sudo):
```bash
sudo python3 scripts/limpia_defensa.py quarantine --file /path/to/binary --pid 1234
```

### 3. Remote Android Build
To synchronize assets, compile via the remote GCP Gradle runner, and fetch the APK:
```bash
# 1. Build web bundle
cd ska-production-kit && npm run build
# 2. Sync to VM
gcloud compute scp --recurse dist/ antigravity-cloud-workspace:~/ska-production-kit/ --zone=us-central1-a --project=sena-ai-team
# 3. Capacitor sync on VM
gcloud compute ssh antigravity-cloud-workspace --zone=us-central1-a --project=sena-ai-team --command="cd ~/ska-production-kit && npx cap sync android"
# 4. Gradle build on VM
gcloud compute ssh antigravity-cloud-workspace --zone=us-central1-a --project=sena-ai-team --command="cd ~/ska-production-kit/android && ./gradlew assembleDebug"
# 5. Fetch APK
gcloud compute scp antigravity-cloud-workspace:~/ska-production-kit/android/app/build/outputs/apk/debug/app-debug.apk ../ska-mobile-engine.apk --zone=us-central1-a --project=sena-ai-team
```

### 4. Enterprise REST API & Diagnostics
To launch the REST API server:
```bash
python3 scripts/limpia_defensa.py api-server --port 8080 --token my-enterprise-token
```

To capture a local diagnostic bug report bundle:
```bash
python3 scripts/limpia_defensa.py bug-report --output diagnostic_report.json
```

```

### 5. LaunchAgent & Kali Integration Test Runner
To install and run the LaunchAgent (auto-startup API server on login):
```bash
# 1. Copy plist to user LaunchAgents folder
cp scripts/com.limpiadefensa.agent.plist ~/Library/LaunchAgents/
# 2. Load the agent
launchctl load ~/Library/LaunchAgents/com.limpiadefensa.agent.plist
# 3. Check status
launchctl list | grep limpiadefensa
```

To execute the automated Kali-Style integration tests:
```bash
python3 scripts/kali_test_suite.py
```

---

## 📋 Recommended Next Steps

1. **Verify Sandbox Deployment**: Test the signed macOS GUI application using the newly implemented Elevated Mode (`do shell script` quoting) to confirm system caches/logs are successfully cleaned and backed up.
2. **Deploy Android Package**: Transfer the compiled `ska-mobile-engine.apk` to an emulator or physical testing device to verify Capacitor plugin integrations.
3. **Automate Test Suite**: Schedule `kali_test_suite.py` to run periodically as a cron job or integration hook.
