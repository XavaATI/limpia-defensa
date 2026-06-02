#!/usr/bin/env python3
import os
import sys
import json
import hashlib
import shutil
import datetime
import argparse
import subprocess
from collections import defaultdict

# ==============================================================================
# ✊ LIMPIA-DEFENSA (CLEAN-DEFENSE) SYSTEM UTILITY
# ==============================================================================

USER_HOME = os.path.expanduser("~")

# Look up Google Drive root directory dynamically inside Library/CloudStorage
def find_gdrive_root():
    cloud_storage_dir = os.path.join(USER_HOME, "Library/CloudStorage")
    if os.path.exists(cloud_storage_dir):
        try:
            for item in os.listdir(cloud_storage_dir):
                if item.startswith("GoogleDrive"):
                    path = os.path.join(cloud_storage_dir, item, "My Drive")
                    if os.path.exists(path):
                        return path
        except Exception:
            pass
    return os.path.join(USER_HOME, "Library/CloudStorage/GoogleDrive/My Drive")

GDRIVE_ROOT = find_gdrive_root()
BACKUP_FOLDER_NAME = "ComradeCleanup_Backup"

SCAN_DIRECTORIES = [
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(USER_HOME, "Documents")
]

# Helper for sizes
def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    import math
    p = int(math.floor(math.log(size_bytes, 1024)))
    s = round(size_bytes / math.pow(1024, p), 2)
    return f"{s} {size_name[p]}"

def get_file_md5(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def is_gdrive_active():
    return os.path.exists(GDRIVE_ROOT)

# ==============================================================================
# 1. SCAN ENGINE
# ==============================================================================
def find_orphans():
    orphans = []
    app_support_dir = os.path.join(USER_HOME, "Library/Application Support")
    if not os.path.exists(app_support_dir):
        return orphans
    
    # Get installed app names from /Applications and ~/Applications
    installed_apps = set()
    for apps_dir in ["/Applications", os.path.join(USER_HOME, "Applications")]:
        if os.path.exists(apps_dir):
            try:
                for item in os.listdir(apps_dir):
                    if item.endswith(".app"):
                        name = item.replace(".app", "").lower()
                        installed_apps.add(name)
                        # also add parts of name to avoid false positives
                        installed_apps.update(name.split())
            except Exception:
                pass
                
    # Scan Application Support folders
    try:
        for item in os.listdir(app_support_dir):
            item_path = os.path.join(app_support_dir, item)
            if os.path.isdir(item_path) and not item.startswith("."):
                name_lower = item.lower()
                # If the folder name doesn't match any installed apps or common system folders
                common_systems = {"adobe", "apple", "microsoft", "google", "com.apple.", "discord", "spotify", "steam", "helper"}
                if not any(sys_name in name_lower for sys_name in common_systems):
                    # Check if matches any installed app
                    matched = False
                    for app in installed_apps:
                        if app in name_lower or name_lower in app:
                            matched = True
                            break
                    if not matched:
                        # Get folder size
                        size = 0
                        for root, _, files in os.walk(item_path):
                            for f in files:
                                try:
                                    size += os.path.getsize(os.path.join(root, f))
                                except Exception:
                                    pass
                        orphans.append({
                            "name": item,
                            "path": item_path,
                            "size": size,
                            "size_str": format_size(size)
                        })
    except Exception:
        pass
    return orphans

def run_scan():
    results = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gdrive_connected": is_gdrive_active(),
        "categories": {
            "caches": [],
            "logs": [],
            "installers": [],
            "duplicates": [],
            "orphans": []
        },
        "summary": {
            "total_size": 0,
            "reclaimable_size": 0
        }
    }
    
    # 1. Caches Scan
    cache_dirs = [
        (os.path.join(USER_HOME, "Library/Caches"), "User Cache"),
        ("/Library/Caches", "System Cache"),
        (os.path.join(USER_HOME, "Library/Caches/Google/Chrome/Default/Cache"), "Chrome Cache"),
        (os.path.join(USER_HOME, "Library/Caches/com.apple.Safari"), "Safari Cache")
    ]
    for path, label in cache_dirs:
        if os.path.exists(path):
            size = 0
            file_count = 0
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(root, f))
                        file_count += 1
                    except Exception:
                        pass
            if size > 0:
                results["categories"]["caches"].append({
                    "name": label,
                    "path": path,
                    "size": size,
                    "size_str": format_size(size),
                    "files_count": file_count
                })

    # 2. Logs Scan
    log_dirs = [
        (os.path.join(USER_HOME, "Library/Logs"), "User Logs"),
        ("/Library/Logs", "System Logs"),
        ("/var/log", "Unix System Logs")
    ]
    for path, label in log_dirs:
        if os.path.exists(path):
            size = 0
            file_count = 0
            for root, _, files in os.walk(path):
                for f in files:
                    if f.endswith(".log") or ".log." in f or f.endswith(".crash") or f.endswith(".diag"):
                        try:
                            size += os.path.getsize(os.path.join(root, f))
                            file_count += 1
                        except Exception:
                            pass
            if size > 0:
                results["categories"]["logs"].append({
                    "name": label,
                    "path": path,
                    "size": size,
                    "size_str": format_size(size),
                    "files_count": file_count
                })

    # 3. Installers Scan
    for s_dir in [os.path.join(USER_HOME, "Downloads"), os.path.join(USER_HOME, "Desktop")]:
        if os.path.exists(s_dir):
            try:
                for item in os.listdir(s_dir):
                    item_path = os.path.join(s_dir, item)
                    if os.path.isfile(item_path) and item.lower().endswith((".dmg", ".pkg")):
                        try:
                            size = os.path.getsize(item_path)
                            results["categories"]["installers"].append({
                                "name": item,
                                "path": item_path,
                                "size": size,
                                "size_str": format_size(size)
                            })
                        except Exception:
                            pass
            except Exception:
                pass

    # 4. Duplicates Scan (Files > 1MB)
    files_by_size = defaultdict(list)
    for s_dir in SCAN_DIRECTORIES:
        if os.path.exists(s_dir):
            for root, _, files in os.walk(s_dir):
                # Avoid hidden directories
                if any(part.startswith('.') for part in root.split(os.sep)):
                    continue
                for f in files:
                    if f.startswith('.'):
                        continue
                    filepath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(filepath)
                        if size >= 1024 * 1024:  # Only check files >= 1MB for duplicates
                            files_by_size[size].append(filepath)
                    except Exception:
                        pass
                        
    duplicate_groups = []
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            hashes = defaultdict(list)
            for path in paths:
                h = get_file_md5(path)
                if h:
                    hashes[h].append(path)
            for h, matching_paths in hashes.items():
                if len(matching_paths) > 1:
                    duplicate_groups.append({
                        "size": size,
                        "size_str": format_size(size),
                        "hash": h,
                        "paths": matching_paths
                    })
    results["categories"]["duplicates"] = duplicate_groups

    # 5. Orphans Scan
    results["categories"]["orphans"] = find_orphans()

    # Calculate Totals
    total_reclaimable = 0
    for cat, list_val in results["categories"].items():
        if cat == "duplicates":
            # For duplicates, we keep the first one and delete the rest
            for group in list_val:
                total_reclaimable += group["size"] * (len(group["paths"]) - 1)
        else:
            for entry in list_val:
                total_reclaimable += entry["size"]
                
    results["summary"]["reclaimable_size"] = total_reclaimable
    results["summary"]["reclaimable_str"] = format_size(total_reclaimable)
    return results

def generate_markdown_report(results, report_path):
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# ✊ Limpia-Defensa System Optimization Report\n\n")
        f.write(f"**Scan Executed At**: `{results['timestamp']}`  \n")
        f.write(f"**Google Drive Cloud Connection**: `{'CONNECTED (Active Staging Enabled)' if results['gdrive_connected'] else 'DISCONNECTED (Backup Dry-Run Only)'}`  \n")
        f.write(f"**Total Reclaimable SSD Space**: **{results['summary']['reclaimable_str']}**\n\n")
        
        f.write("## 🧹 Cleanup Categories Breakdown\n\n")
        
        # Caches
        f.write("### 🗄️ System & Application Caches\n")
        caches = results["categories"]["caches"]
        if not caches:
            f.write("No major caches indexed.\n")
        else:
            f.write("| Cache Type | Path | File Count | Reclaimable Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for c in caches:
                f.write(f"| {c['name']} | `{c['path']}` | {c['files_count']} | **{c['size_str']}** |\n")
        f.write("\n")
        
        # Logs
        f.write("### 📝 System Log Buffers\n")
        logs = results["categories"]["logs"]
        if not logs:
            f.write("No major logs indexed.\n")
        else:
            f.write("| Log Type | Path | File Count | Reclaimable Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for l in logs:
                f.write(f"| {l['name']} | `{l['path']}` | {l['files_count']} | **{l['size_str']}** |\n")
        f.write("\n")

        # Installers
        f.write("### 📦 DMG / PKG Installers\n")
        installers = results["categories"]["installers"]
        if not installers:
            f.write("No leftover installers found.\n")
        else:
            f.write("| Installer Name | Path | File Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for inst in installers:
                f.write(f"| {inst['name']} | `{inst['path']}` | **{inst['size_str']}** |\n")
        f.write("\n")

        # Orphans
        f.write("### 📱 Orphaned App Support Folders\n")
        orphans = results["categories"]["orphans"]
        if not orphans:
            f.write("No orphaned application support folders found.\n")
        else:
            f.write("| Application Folder | Path | Folder Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for o in orphans:
                f.write(f"| {o['name']} | `{o['path']}` | **{o['size_str']}** |\n")
        f.write("\n")

        # Duplicates
        f.write("### 📦 True Duplicate Clusters (Keep 1 copy)\n")
        dupes = results["categories"]["duplicates"]
        if not dupes:
            f.write("No identical duplicate clusters found.\n")
        else:
            for group in dupes:
                f.write(f"- **Size**: `{group['size_str']}` | **Hash**: `{group['hash'][:8]}`\n")
                for idx, path in enumerate(group["paths"]):
                    action = "KEEP" if idx == 0 else "PRUNE"
                    f.write(f"  - `[{action}]` `{path}`\n")
        f.write("\n")

# ==============================================================================
# 2. CLEAN ENGINE (WITH GDRIVE STAGING BACKUP)
# ==============================================================================
def stage_file_to_gdrive(source_path, category, run_date):
    if not is_gdrive_active():
        print(f"⚠️ Google Drive local mount not found! Cannot back up: {source_path}")
        return False
        
    try:
        # Strip user home path or leading root slash for safe subpath structuring
        rel_path = source_path
        if rel_path.startswith(USER_HOME):
            rel_path = rel_path[len(USER_HOME):].lstrip(os.sep)
        else:
            rel_path = rel_path.lstrip(os.sep)
            
        backup_dir = os.path.join(GDRIVE_ROOT, BACKUP_FOLDER_NAME, run_date, category, os.path.dirname(rel_path))
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_target_path = os.path.join(backup_dir, os.path.basename(source_path))
        
        # Copy file or directory
        if os.path.isdir(source_path):
            if os.path.exists(backup_target_path):
                shutil.rmtree(backup_target_path)
            shutil.copytree(source_path, backup_target_path)
        else:
            shutil.copy2(source_path, backup_target_path)
            
        # Verify sizes match
        src_size = os.path.getsize(source_path) if os.path.isfile(source_path) else 0
        tgt_size = os.path.getsize(backup_target_path) if os.path.isfile(backup_target_path) else 0
        if src_size == tgt_size or os.path.isdir(source_path):
            return True
        else:
            print(f"❌ Verification failed for copy: {source_path} (size mismatch)")
            return False
    except Exception as e:
        print(f"❌ Backup copy failed for {source_path}: {e}")
        return False

def perform_clean(results_json_path, categories_list, use_sudo=False):
    if not os.path.exists(results_json_path):
        print(f"Error: Scan results file not found at: {results_json_path}")
        sys.exit(1)
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    if not results.get("gdrive_connected") and not is_gdrive_active():
        print("❌ Error: Google Drive mount is inactive. Clean halted to prevent destructive deletions without backups.")
        sys.exit(1)

    run_date = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    deleted_paths = []
    failed_paths = []

    # Process Caches, Logs, Installers, Orphans
    for category in ["caches", "logs", "installers", "orphans"]:
        if category in categories_list:
            for entry in results["categories"][category]:
                path = entry["path"]
                # Skip folders if we are running user mode but it requires system permission
                is_system_path = path.startswith(("/Library", "/var/log"))
                if is_system_path and not use_sudo:
                    print(f"⏭️ Skipping system-level path (run with --sudo to clean): {path}")
                    continue
                    
                print(f"📦 Staging to Google Drive: {path}")
                if stage_file_to_gdrive(path, category, run_date):
                    try:
                        if os.path.isdir(path):
                            if use_sudo and is_system_path:
                                subprocess.run(["sudo", "rm", "-rf", path], check=True)
                            else:
                                shutil.rmtree(path)
                        else:
                            if use_sudo and is_system_path:
                                subprocess.run(["sudo", "rm", "-f", path], check=True)
                            else:
                                os.remove(path)
                        deleted_paths.append(path)
                        print(f"✅ Successfully pruned: {path}")
                    except Exception as e:
                        failed_paths.append({"path": path, "error": str(e)})
                        print(f"❌ Deletion failed for: {path} ({e})")
                else:
                    failed_paths.append({"path": path, "error": "Staging copy failed"})

    # Process Duplicates
    if "duplicates" in categories_list:
        for group in results["categories"]["duplicates"]:
            # Keep index 0, delete the rest
            for path in group["paths"][1:]:
                print(f"📦 Staging duplicate copy to Google Drive: {path}")
                if stage_file_to_gdrive(path, "duplicates", run_date):
                    try:
                        os.remove(path)
                        deleted_paths.append(path)
                        print(f"✅ Successfully pruned duplicate: {path}")
                    except Exception as e:
                        failed_paths.append({"path": path, "error": str(e)})
                        print(f"❌ Deletion failed for duplicate: {path} ({e})")
                else:
                    failed_paths.append({"path": path, "error": "Staging copy failed"})

    print(f"\n⚡ Clean Completed! Successfully pruned {len(deleted_paths)} items. Failures: {len(failed_paths)}")
    return {"deleted": deleted_paths, "failed": failed_paths, "backup_session": run_date}

# ==============================================================================
# 3. MODERN LIGHTWEIGHT ANTIVIRUS SCANNER
# ==============================================================================
def get_file_sha256(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def run_av_scan(threat_db_path=None):
    threat_hashes = set()
    if threat_db_path and os.path.exists(threat_db_path):
        try:
            with open(threat_db_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        threat_hashes.add(line.lower())
        except Exception as e:
            print(f"Warning: Failed to load threat-db: {e}")

    av_results = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "threats_found": [],
        "suspicious_items": [],
        "summary": {
            "total_threats": 0,
            "total_suspicious": 0
        }
    }

    # 1. Scan Launch Agents and Launch Daemons (Common Persistence Vectors)
    persistence_dirs = [
        "/Library/LaunchAgents",
        "/Library/LaunchDaemons",
        os.path.join(USER_HOME, "Library/LaunchAgents")
    ]
    for p_dir in persistence_dirs:
        if os.path.exists(p_dir):
            try:
                for item in os.listdir(p_dir):
                    item_path = os.path.join(p_dir, item)
                    if os.path.isfile(item_path) and item.endswith(".plist"):
                        # Parse plist content for suspect execution scripts
                        is_suspicious = False
                        reason = []
                        
                        # Read contents as text to check commands
                        try:
                            with open(item_path, "r", encoding="utf-8", errors="ignore") as pf:
                                content = pf.read()
                                
                            # Adware patterns
                            suspicious_keywords = ["curl", "wget", "chmod", "sh ", "bash", "/tmp/", "python", "eval"]
                            for kw in suspicious_keywords:
                                if kw in content:
                                    is_suspicious = True
                                    reason.append(f"Contains execution keyword: '{kw}'")
                        except Exception:
                            pass
                            
                        # Hash audit
                        sha256 = get_file_sha256(item_path)
                        if sha256 and sha256 in threat_hashes:
                            av_results["threats_found"].append({
                                "name": item,
                                "path": item_path,
                                "type": "Malicious Persistence Agent",
                                "sha256": sha256,
                                "reason": "Matches known signature in threat-db"
                            })
                        elif is_suspicious:
                            av_results["suspicious_items"].append({
                                "name": item,
                                "path": item_path,
                                "type": "Suspicious Persistence Agent",
                                "sha256": sha256 or "Unknown",
                                "reason": ", ".join(reason)
                            })
            except Exception:
                pass

    # 2. Check Crontab
    try:
        cron_proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if cron_proc.returncode == 0 and cron_proc.stdout.strip():
            cron_lines = cron_proc.stdout.strip().split("\n")
            for idx, line in enumerate(cron_lines):
                if line.strip() and not line.strip().startswith("#"):
                    # Check for curl / bash execution
                    if any(kw in line for kw in ["curl", "wget", "sh", "bash", "python", "/tmp"]):
                        av_results["suspicious_items"].append({
                            "name": f"Crontab Line {idx+1}",
                            "path": "User Crontab Configuration",
                            "type": "Suspicious Cron Task",
                            "sha256": "N/A",
                            "reason": f"Active execution command: {line}"
                        })
    except Exception:
        pass

    # 3. Check High-Risk Execution Directories (tmp, Downloads, Desktop)
    high_risk_dirs = [
        "/tmp",
        os.path.join(USER_HOME, "Downloads"),
        os.path.join(USER_HOME, "Desktop")
    ]
    for h_dir in high_risk_dirs:
        if os.path.exists(h_dir):
            try:
                for item in os.listdir(h_dir):
                    item_path = os.path.join(h_dir, item)
                    if os.path.isfile(item_path) and not item.startswith("."):
                        # Check if file has executable permissions
                        try:
                            stat_info = os.stat(item_path)
                            is_executable = (stat_info.st_mode & 0o111) != 0
                            
                            # Alternatively check header for shebang
                            is_script = False
                            if not is_executable:
                                with open(item_path, "rb") as f:
                                    header = f.read(2)
                                    if header == b"#!":
                                        is_script = True
                                        
                            if is_executable or is_script:
                                # Run codesign check to see if it is signed
                                is_signed = False
                                try:
                                    cs_proc = subprocess.run(["codesign", "-v", item_path], capture_output=True)
                                    if cs_proc.returncode == 0:
                                        is_signed = True
                                except Exception:
                                    pass
                                    
                                if not is_signed:
                                    # Flag unsigned executable/script in high risk directory
                                    sha256 = get_file_sha256(item_path)
                                    if sha256 and sha256 in threat_hashes:
                                        av_results["threats_found"].append({
                                            "name": item,
                                            "path": item_path,
                                            "type": "Malicious Unsigned Executable",
                                            "sha256": sha256,
                                            "reason": "Matches known signature in threat-db"
                                        })
                                    else:
                                        av_results["suspicious_items"].append({
                                            "name": item,
                                            "path": item_path,
                                            "type": "Unsigned Executable / Script in entry folder",
                                            "sha256": sha256 or "Unknown",
                                            "reason": "Unsigned file with execution privileges in high-risk folder"
                                        })
                        except Exception:
                            pass
            except Exception:
                pass

    av_results["summary"]["total_threats"] = len(av_results["threats_found"])
    av_results["summary"]["total_suspicious"] = len(av_results["suspicious_items"])
    return av_results

# ==============================================================================
# 4. RESTORE / REVERT ENGINE
# ==============================================================================
def perform_restore(backup_date, original_path_target):
    if not is_gdrive_active():
        print("Error: Google Drive local mount not active. Restore halted.")
        sys.exit(1)
        
    # Reconstruct GDrive backup path
    # Staged path structure: My Drive/ComradeCleanup_Backup/YYYY-MM-DD/[category]/[original path structure]
    # We will search under backup_date
    backup_base_dir = os.path.join(GDRIVE_ROOT, BACKUP_FOLDER_NAME, backup_date)
    if not os.path.exists(backup_base_dir):
        print(f"Error: No backup session found for date '{backup_date}' at: {backup_base_dir}")
        sys.exit(1)
        
    # Strip user home path or leading root slash
    rel_path = original_path_target
    if rel_path.startswith(USER_HOME):
        rel_path = rel_path[len(USER_HOME):].lstrip(os.sep)
    else:
        rel_path = rel_path.lstrip(os.sep)
        
    # Search all categories (caches, logs, installers, orphans, duplicates)
    found_backup_path = None
    for category in ["caches", "logs", "installers", "orphans", "duplicates"]:
        candidate_path = os.path.join(backup_base_dir, category, rel_path)
        if os.path.exists(candidate_path):
            found_backup_path = candidate_path
            break
            
    if not found_backup_path:
        print(f"Error: Could not locate backup of '{original_path_target}' in backup session '{backup_date}'")
        sys.exit(1)
        
    print(f"🔄 Restoring '{found_backup_path}' -> '{original_path_target}'")
    try:
        os.makedirs(os.path.dirname(original_path_target), exist_ok=True)
        if os.path.isdir(found_backup_path):
            if os.path.exists(original_path_target):
                shutil.rmtree(original_path_target)
            shutil.copytree(found_backup_path, original_path_target)
        else:
            shutil.copy2(found_backup_path, original_path_target)
        print(f"✅ Successfully restored file: {original_path_target}")
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)

# ==============================================================================
# MAIN PARSER ENTRYPOINT
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="✊ Limpia-Defensa macOS Utility CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Scan parser
    scan_parser = subparsers.add_parser("scan", help="Scan system for cleanup candidates")
    scan_parser.add_argument("--output", required=True, help="Path to write JSON results")
    scan_parser.add_argument("--report", help="Path to write Markdown report")

    # Clean parser
    clean_parser = subparsers.add_parser("clean", help="Clean candidate directories")
    clean_parser.add_argument("--input", required=True, help="Path to scanned JSON results")
    clean_parser.add_argument("--categories", required=True, help="Comma-separated categories to clean (caches,logs,installers,duplicates,orphans)")
    clean_parser.add_argument("--sudo", action="store_true", help="Elevate commands to system level")

    # AV Scan parser
    av_parser = subparsers.add_parser("av-scan", help="Lightweight antivirus audit scan")
    av_parser.add_argument("--output", required=True, help="Path to write JSON threat report")
    av_parser.add_argument("--threat-db", help="Path to local signature threat-db hash database")

    # Restore parser
    restore_parser = subparsers.add_parser("restore", help="Restore staging backups from Google Drive")
    restore_parser.add_argument("--date", required=True, help="Backup session date directory (YYYY-MM-DD_HHMMSS or similar)")
    restore_parser.add_argument("--path", required=True, help="Original file path to restore")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        print("🔎 Scanning system directories...")
        results = run_scan()
        # Save JSON
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Saved scan metadata results to: {args.output}")
        # Save report if specified
        if args.report:
            generate_markdown_report(results, args.report)
            print(f"📝 Saved markdown summary report to: {args.report}")
            
    elif args.command == "clean":
        cats = [c.strip().lower() for c in args.categories.split(",")]
        print(f"🧹 Commencing non-destructive cleanup for categories: {cats}...")
        perform_clean(args.input, cats, use_sudo=args.sudo)
        
    elif args.command == "av-scan":
        print("🛡️ Commencing modern AV threat audit...")
        av_results = run_av_scan(args.threat_db)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(av_results, f, indent=2)
        print(f"💾 Threat report successfully saved to: {args.output}")
        print(f"⚠️ Threats found: {av_results['summary']['total_threats']} | Suspicious items: {av_results['summary']['total_suspicious']}")
        
    elif args.command == "restore":
        perform_restore(args.date, args.path)

if __name__ == "__main__":
    main()
