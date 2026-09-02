# Ska Mobile Engine Workspace Rules

This file outlines the configuration and instructions for the remote Google Cloud VM build system to ensure seamless continuity across agent sessions.

## 🖥️ Remote VM Build Target
* **Instance Name**: `antigravity-cloud-workspace`
* **GCP Project**: `sena-ai-team`
* **Zone**: `us-central1-a`
* **External IP**: `34.27.116.144`
* **Active GCP Account**: `schicanoloco@gmail.com`
* **SSH Connection**: Passwordless key-based login via `gcloud compute ssh antigravity-cloud-workspace --zone=us-central1-a --project=sena-ai-team`.

## ⚙️ Runtime Specifications
* **Node.js**: `v22.23.0` (installed on both local host and remote VM to satisfy Capacitor CLI 8 requirements).
* **Java Development Kit**: OpenJDK `21.0.11` (installed on remote VM to satisfy Gradle build requirements).
* **Android SDK**: Configured at `/home/xavasena/Android/Sdk` on remote VM with `local.properties` matching this path.

## 📂 Codebase & Mapping
* **Local Root**: `/Users/xavasena/collectivo/limpiada/ska-production-kit`
* **Remote VM Root**: `/home/xavasena/ska-production-kit`

## 🛠️ Build Commands
1. **React Application Compilation**:
   ```bash
   npm run build
   ```
2. **Capacitor Assets Sync**:
   ```bash
   npx cap sync android
   ```
3. **Remote Gradle Build Execution**:
   ```bash
   gcloud compute ssh antigravity-cloud-workspace --zone=us-central1-a --project=sena-ai-team --command="cd ~/ska-production-kit/android && ./gradlew assembleDebug"
   ```
4. **Retrieve Compiled APK**:
   ```bash
   gcloud compute scp antigravity-cloud-workspace:~/ska-production-kit/android/app/build/outputs/apk/debug/app-debug.apk /Users/xavasena/collectivo/limpiada/ska-mobile-engine.apk --zone=us-central1-a --project=sena-ai-team
   ```

# 🚀 Sena's AI Colectivo Workspace Architecture

## 💻 Machine Context
- **Primary Development Machine**: `Xava’s MacBook Air` (`Xavas-MacBook-Air.local` / `arm64`)
- **Location**: Field / Taos / Mobile Workstation
- **Workspace Root**: `/Users/xavasena/collectivo/limpiada`

## 🛡️ Core Independent Products
1. **Limpia-Defensa**:
   - Native macOS System Security, Heuristic Antivirus (Quetzal Core), and Storage Optimization Engine.
   - Independent REST API Daemon on port 8989.
   - Native SwiftUI Application (`LimpiaDefensa.app`).
   - Solo-operator release & quality gate pipeline (`scripts/release_pipeline.py`).
2. **Ska Mobile Engine**:
   - Video Production Kit & Capacitor/Android remote build system via `antigravity-cloud-workspace`.

## 🔒 Independence Directive
- Zero dependencies on external third-party team repositories or SentinelOps infrastructure.
- All code, distributions, models, and branding strictly belong to **Sena's AI Colectivo**.
