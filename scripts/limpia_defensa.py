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
            "orphans": [],
            "vms": [],
            "videos": [],
            "photos": [],
            "archives": []
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

    # 4. Media Scan
    vm_exts = {".qcow2", ".utm", ".pvm", ".vdi", ".vmdk"}
    video_exts = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv"}
    photo_exts = {".jpg", ".jpeg", ".png", ".heic", ".raw", ".tiff", ".gif"}
    archive_exts = {".zip", ".tar.gz", ".tgz", ".rar", ".7z", ".tar", ".gz"}
    
    for s_dir in SCAN_DIRECTORIES:
        if os.path.exists(s_dir):
            for root, _, files in os.walk(s_dir):
                if ".git" in root.split(os.sep):
                    continue
                if "Library/CloudStorage" in root:
                    continue
                if any(part.startswith('.') for part in root.split(os.sep)):
                    continue
                for f in files:
                    if f.startswith('.'):
                        continue
                    filepath = os.path.join(root, f)
                    try:
                        ext = os.path.splitext(f)[1].lower()
                        size = os.path.getsize(filepath)
                        
                        if ext in vm_exts:
                            results["categories"]["vms"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                        elif ext in video_exts and size >= 500 * 1024 * 1024:
                            results["categories"]["videos"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                        elif ext in photo_exts:
                            results["categories"]["photos"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                        elif ext in archive_exts:
                            results["categories"]["archives"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                    except Exception:
                        pass

    # 5. Duplicates Scan (Files > 1MB)
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

        # VMs
        f.write("### 🖥️ Virtual Machines\n")
        vms = results["categories"].get("vms", [])
        if not vms:
            f.write("No virtual machines found.\n")
        else:
            f.write("| VM File | Path | Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for vm in vms:
                f.write(f"| {vm['name']} | `{vm['path']}` | **{vm['size_str']}** |\n")
        f.write("\n")

        # Videos
        f.write("### 🎥 Large Videos (>500MB)\n")
        videos = results["categories"].get("videos", [])
        if not videos:
            f.write("No large videos found.\n")
        else:
            f.write("| Video File | Path | Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for vid in videos:
                f.write(f"| {vid['name']} | `{vid['path']}` | **{vid['size_str']}** |\n")
        f.write("\n")

        # Photos
        f.write("### 🖼️ Photos & Images\n")
        photos = results["categories"].get("photos", [])
        if not photos:
            f.write("No photos or images found.\n")
        else:
            f.write("| Photo File | Path | Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for photo in photos:
                f.write(f"| {photo['name']} | `{photo['path']}` | **{photo['size_str']}** |\n")
        f.write("\n")

        # Archives
        f.write("### 🗜️ Stale Archives\n")
        archives = results["categories"].get("archives", [])
        if not archives:
            f.write("No stale archive files found.\n")
        else:
            f.write("| Archive File | Path | Size |\n")
            f.write("| :--- | :--- | :--- |\n")
            for arch in archives:
                f.write(f"| {arch['name']} | `{arch['path']}` | **{arch['size_str']}** |\n")
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
def get_backup_dir(backup_type, backup_path):
    if backup_type == "cloud":
        root = backup_path if backup_path else GDRIVE_ROOT
        return os.path.join(root, BACKUP_FOLDER_NAME)
    else:
        if not backup_path:
            return os.path.join(USER_HOME, "Developer", BACKUP_FOLDER_NAME)
        return os.path.join(backup_path, BACKUP_FOLDER_NAME)

def get_file_sha256_hash(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def stage_file_to_backup(source_path, category, run_date, backup_type, backup_path, encrypt=False, passphrase=None, manifest=None):
    if category == "caches":
        return True
        
    backup_base = get_backup_dir(backup_type, backup_path)
    session_dir = os.path.join(backup_base, run_date)
    os.makedirs(session_dir, exist_ok=True)
    
    try:
        hashed_key = hashlib.sha256(source_path.encode()).hexdigest()
        
        if os.path.isdir(source_path):
            temp_zip_base = os.path.join("/tmp", f"zip_{hashed_key}")
            temp_zip_file = temp_zip_base + ".zip"
            if os.path.exists(temp_zip_file):
                os.remove(temp_zip_file)
                
            shutil.make_archive(temp_zip_base, 'zip', source_path)
            
            zip_size = os.path.getsize(temp_zip_file)
            zip_sha256 = get_file_sha256_hash(temp_zip_file)
            
            if encrypt:
                target_file_path = os.path.join(session_dir, hashed_key + ".enc")
                cmd = [
                    "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "100000",
                    "-k", passphrase, "-in", temp_zip_file, "-out", target_file_path
                ]
                res = subprocess.run(cmd, capture_output=True)
                if os.path.exists(temp_zip_file):
                    os.remove(temp_zip_file)
                if res.returncode != 0:
                    print(f"❌ Encryption failed: {res.stderr.decode().strip()}")
                    return False
            else:
                target_file_path = os.path.join(session_dir, hashed_key + ".zip")
                if os.path.exists(target_file_path):
                    os.remove(target_file_path)
                shutil.move(temp_zip_file, target_file_path)
                
            if manifest is not None:
                manifest["files"][hashed_key] = {
                    "original_path": source_path,
                    "type": "directory",
                    "checksum": zip_sha256,
                    "size": zip_size,
                    "category": category
                }
            return os.path.exists(target_file_path) and os.path.getsize(target_file_path) > 0
            
        else:
            file_size = os.path.getsize(source_path)
            file_sha256 = get_file_sha256_hash(source_path)
            
            if encrypt:
                target_file_path = os.path.join(session_dir, hashed_key + ".enc")
                cmd = [
                    "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "100000",
                    "-k", passphrase, "-in", source_path, "-out", target_file_path
                ]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode != 0:
                    print(f"❌ Encryption failed: {res.stderr.decode().strip()}")
                    return False
            else:
                ext = os.path.splitext(source_path)[1]
                target_file_path = os.path.join(session_dir, hashed_key + ext)
                shutil.copy2(source_path, target_file_path)
                
            if manifest is not None:
                manifest["files"][hashed_key] = {
                    "original_path": source_path,
                    "type": "file",
                    "checksum": file_sha256,
                    "size": file_size,
                    "category": category
                }
            return os.path.exists(target_file_path) and os.path.getsize(target_file_path) > 0
            
    except Exception as e:
        print(f"❌ Backup failed for {source_path}: {e}")
        return False

def perform_clean(results_json_path, categories_list, backup_type, backup_path, encrypt=False, passphrase=None, use_sudo=False):
    if not os.path.exists(results_json_path):
        print(f"Error: Scan results file not found at: {results_json_path}")
        sys.exit(1)
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    backup_base = get_backup_dir(backup_type, backup_path)
    if backup_type == "cloud" and not os.path.exists(backup_base):
        print(f"❌ Error: Cloud mount at {backup_base} is inactive. Clean halted to prevent destructive deletions without backups.")
        sys.exit(1)

    run_date = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_dir = os.path.join(backup_base, run_date)
    os.makedirs(session_dir, exist_ok=True)
    
    manifest = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backup_type": backup_type,
        "encrypted": encrypt,
        "files": {}
    }
    
    deleted_paths = []
    failed_paths = []

    for category in ["caches", "logs", "installers", "orphans", "vms", "videos", "photos", "archives"]:
        if category in categories_list:
            for entry in results["categories"].get(category, []):
                path = entry["path"]
                is_system_path = path.startswith(("/Library", "/var/log"))
                if is_system_path and not use_sudo:
                    print(f"⏭️ Skipping system-level path (run with --sudo to clean): {path}")
                    continue
                    
                print(f"📦 Staging to backup: {path}")
                if stage_file_to_backup(path, category, run_date, backup_type, backup_path, encrypt, passphrase, manifest):
                    try:
                        if os.path.isdir(path):
                            if use_sudo and is_system_path:
                                subprocess.run(["sudo", "rm", "-rf", path], check=True)
                            else:
                                shutil.rmtree(path, ignore_errors=True)
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

    if "duplicates" in categories_list:
        for group in results["categories"]["duplicates"]:
            for path in group["paths"][1:]:
                print(f"📦 Staging duplicate copy to backup: {path}")
                if stage_file_to_backup(path, "duplicates", run_date, backup_type, backup_path, encrypt, passphrase, manifest):
                    try:
                        os.remove(path)
                        deleted_paths.append(path)
                        print(f"✅ Successfully pruned duplicate: {path}")
                    except Exception as e:
                        failed_paths.append({"path": path, "error": str(e)})
                        print(f"❌ Deletion failed for duplicate: {path} ({e})")
                else:
                    failed_paths.append({"path": path, "error": "Staging copy failed"})

    plain_manifest_path = os.path.join(session_dir, "manifest.json")
    with open(plain_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    if encrypt:
        enc_manifest_path = os.path.join(session_dir, "manifest.json.enc")
        cmd = [
            "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "100000",
            "-k", passphrase, "-in", plain_manifest_path, "-out", enc_manifest_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0:
            os.remove(plain_manifest_path)
            print(f"🔒 Encrypted manifest created: {enc_manifest_path}")
        else:
            print(f"⚠️ Warning: Failed to encrypt manifest: {res.stderr.decode().strip()}")
            
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

def load_manifest(backup_date, backup_type, backup_path, passphrase=None):
    backup_base = get_backup_dir(backup_type, backup_path)
    session_dir = os.path.join(backup_base, backup_date)
    if not os.path.exists(session_dir):
        return None
        
    enc_manifest_path = os.path.join(session_dir, "manifest.json.enc")
    plain_manifest_path = os.path.join(session_dir, "manifest.json")
    
    if os.path.exists(enc_manifest_path):
        if not passphrase:
            raise Exception("Encryption passphrase required to read encrypted manifest.")
            
        temp_dec_manifest = os.path.join("/tmp", f"manifest_{backup_date}.json")
        cmd = [
            "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "100000",
            "-k", passphrase, "-in", enc_manifest_path, "-out", temp_dec_manifest
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            raise Exception(f"Decryption failed: {res.stderr.decode().strip()}")
            
        try:
            with open(temp_dec_manifest, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            return manifest
        finally:
            if os.path.exists(temp_dec_manifest):
                os.remove(temp_dec_manifest)
                
    elif os.path.exists(plain_manifest_path):
        with open(plain_manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return manifest
        
    return None

def restore_single_entry(backup_date, hashed_key, entry, backup_type, backup_path, passphrase=None):
    backup_base = get_backup_dir(backup_type, backup_path)
    session_dir = os.path.join(backup_base, backup_date)
    
    original_path = entry["original_path"]
    file_type = entry["type"]
    expected_checksum = entry["checksum"]
    
    is_encrypted = False
    backup_file_path = os.path.join(session_dir, hashed_key + ".enc")
    if os.path.exists(backup_file_path):
        is_encrypted = True
    else:
        if file_type == "directory":
            backup_file_path = os.path.join(session_dir, hashed_key + ".zip")
        else:
            backup_file_path = os.path.join(session_dir, hashed_key + os.path.splitext(original_path)[1])
            
    if not os.path.exists(backup_file_path):
        raise Exception(f"Backup file not found at: {backup_file_path}")
        
    os.makedirs(os.path.dirname(original_path), exist_ok=True)
    
    if is_encrypted:
        if not passphrase:
            raise Exception("Passphrase required to decrypt backup files.")
            
        temp_dec_file = os.path.join("/tmp", f"dec_{hashed_key}")
        cmd = [
            "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "100000",
            "-k", passphrase, "-in", backup_file_path, "-out", temp_dec_file
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            raise Exception(f"Decryption of file failed: {res.stderr.decode().strip()}")
            
        dec_checksum = get_file_sha256_hash(temp_dec_file)
        if dec_checksum != expected_checksum:
            if os.path.exists(temp_dec_file):
                os.remove(temp_dec_file)
            raise Exception(f"Integrity check failed: checksum mismatch (expected {expected_checksum}, got {dec_checksum})")
            
        try:
            if file_type == "directory":
                if os.path.exists(original_path):
                    shutil.rmtree(original_path)
                shutil.unpack_archive(temp_dec_file, original_path, 'zip')
            else:
                if os.path.exists(original_path):
                    os.remove(original_path)
                shutil.move(temp_dec_file, original_path)
        finally:
            if os.path.exists(temp_dec_file):
                os.remove(temp_dec_file)
    else:
        backup_checksum = get_file_sha256_hash(backup_file_path)
        if backup_checksum != expected_checksum:
            raise Exception(f"Integrity check failed: checksum mismatch (expected {expected_checksum}, got {backup_checksum})")
            
        if file_type == "directory":
            if os.path.exists(original_path):
                shutil.rmtree(original_path)
            shutil.unpack_archive(backup_file_path, original_path, 'zip')
        else:
            if os.path.exists(original_path):
                os.remove(original_path)
            shutil.copy2(backup_file_path, original_path)

def perform_restore(backup_date, original_path_target, backup_type, backup_path, passphrase=None):
    manifest = load_manifest(backup_date, backup_type, backup_path, passphrase)
    if not manifest:
        print(f"Error: Manifest not found for session {backup_date}")
        sys.exit(1)
        
    hashed_key = None
    target_entry = None
    for k, entry in manifest.get("files", {}).items():
        if entry["original_path"] == original_path_target:
            hashed_key = k
            target_entry = entry
            break
            
    if not target_entry:
        print(f"Error: Path '{original_path_target}' not found in backup session manifest.")
        sys.exit(1)
        
    print(f"🔄 Restoring '{original_path_target}' from backup...")
    try:
        restore_single_entry(backup_date, hashed_key, target_entry, backup_type, backup_path, passphrase)
        print(f"✅ Successfully restored: {original_path_target}")
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)

def perform_rollback(backup_date, backup_type, backup_path, passphrase=None):
    try:
        manifest = load_manifest(backup_date, backup_type, backup_path, passphrase)
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        sys.exit(1)
        
    if not manifest:
        print(f"❌ Rollback failed: Manifest not found for session {backup_date}")
        sys.exit(1)
        
    print(f"🔄 Commencing session rollback for session {backup_date}...")
    success_count = 0
    fail_count = 0
    
    for hashed_key, entry in manifest.get("files", {}).items():
        original_path = entry["original_path"]
        print(f"Restoring {original_path}...")
        try:
            restore_single_entry(backup_date, hashed_key, entry, backup_type, backup_path, passphrase)
            print(f"✅ Restored: {original_path}")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed to restore {original_path}: {e}")
            fail_count += 1
            
    print(f"\n⚡ Rollback completed! Success: {success_count}, Failures: {fail_count}")
    return {"success": success_count, "failures": fail_count}

def run_list_backups(backup_type, backup_path):
    backup_base = get_backup_dir(backup_type, backup_path)
    if not os.path.exists(backup_base):
        return {"connected": os.path.exists(os.path.dirname(backup_base)), "backups": []}
        
    backups = []
    try:
        for session in sorted(os.listdir(backup_base), reverse=True):
            session_path = os.path.join(backup_base, session)
            if os.path.isdir(session_path) and not session.startswith("."):
                enc_manifest = os.path.exists(os.path.join(session_path, "manifest.json.enc"))
                plain_manifest = os.path.exists(os.path.join(session_path, "manifest.json"))
                
                total_size = 0
                file_count = 0
                categories_found = []
                encrypted = False
                
                if enc_manifest:
                    encrypted = True
                    for root, _, files in os.walk(session_path):
                        for f in files:
                            if f == "manifest.json.enc" or f.startswith("."):
                                continue
                            file_count += 1
                            try:
                                total_size += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass
                    categories_found = ["unknown (encrypted)"]
                elif plain_manifest:
                    try:
                        with open(os.path.join(session_path, "manifest.json"), "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        encrypted = manifest.get("encrypted", False)
                        for hashed_key, entry in manifest.get("files", {}).items():
                            file_count += 1
                            total_size += entry.get("size", 0)
                            cat = entry.get("category", "unknown")
                            if cat not in categories_found:
                                categories_found.append(cat)
                    except Exception:
                        pass
                else:
                    for cat in os.listdir(session_path):
                        if cat.startswith("."):
                            continue
                        cat_path = os.path.join(session_path, cat)
                        if os.path.isdir(cat_path):
                            categories_found.append(cat)
                            for root, _, files in os.walk(cat_path):
                                for f in files:
                                    file_count += 1
                                    try:
                                        total_size += os.path.getsize(os.path.join(root, f))
                                    except Exception:
                                        pass
                backups.append({
                    "session": session,
                    "file_count": file_count,
                    "size": total_size,
                    "size_str": format_size(total_size),
                    "categories": categories_found,
                    "encrypted": encrypted
                })
    except Exception as e:
        print(f"Error listing backups: {e}", file=sys.stderr)
        
    return {"connected": True, "backups": backups}

def perform_quarantine(filepath, pid, backup_type, backup_path, encrypt=False, passphrase=None):
    # 1. Stage backup
    run_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    manifest = {
        "timestamp": run_date,
        "backup_type": backup_type,
        "encrypted": encrypt,
        "files": {}
    }
    
    print(f"🔒 Staging threat binary to backup target: {filepath}")
    success = stage_file_to_backup(filepath, "av-quarantine", run_date, backup_type, backup_path, encrypt, passphrase, manifest)
    if not success:
        print("❌ Warning: Staging backup failed or skipped, proceeding with remediation caution...")
    else:
        # Save manifest
        backup_base = get_backup_dir(backup_type, backup_path)
        session_dir = os.path.join(backup_base, run_date)
        manifest_name = "manifest.json.enc" if encrypt else "manifest.json"
        manifest_path = os.path.join(session_dir, manifest_name)
        try:
            manifest_data = json.dumps(manifest, indent=2)
            if encrypt:
                temp_manifest = os.path.join("/tmp", f"manifest_{run_date}.json")
                with open(temp_manifest, "w", encoding="utf-8") as f:
                    f.write(manifest_data)
                cmd = [
                    "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "100000",
                    "-k", passphrase, "-in", temp_manifest, "-out", manifest_path
                ]
                subprocess.run(cmd, check=True)
                os.remove(temp_manifest)
            else:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    f.write(manifest_data)
            print(f"✅ Threat binary archived in session: {run_date}")
        except Exception as e:
            print(f"❌ Failed to save quarantine manifest: {e}")

    # 2. Terminate PID
    if pid > 0:
        print(f"🛑 Terminating process PID {pid}...")
        try:
            os.kill(pid, 9)
            print(f"✅ Terminated process {pid}")
        except ProcessLookupError:
            print(f"ℹ️ Process {pid} already dead.")
        except PermissionError:
            print(f"⚠️ Permission denied. Retrying with sudo...")
            subprocess.run(["sudo", "kill", "-9", str(pid)], check=True)
            print(f"✅ Terminated process {pid} via sudo")
        except Exception as e:
            print(f"❌ Failed to terminate process {pid}: {e}")

    # 3. Delete binary from disk
    if os.path.exists(filepath):
        print(f"🗑️ Deleting file from disk: {filepath}")
        try:
            os.remove(filepath)
            print(f"✅ Deleted threat binary: {filepath}")
        except PermissionError:
            print(f"⚠️ Permission denied deleting file. Retrying with sudo...")
            subprocess.run(["sudo", "rm", "-f", filepath], check=True)
            print(f"✅ Deleted threat binary via sudo: {filepath}")
        except Exception as e:
            print(f"❌ Failed to delete file {filepath}: {e}")

# ==============================================================================
# ENTERPRISE REST API & DIAGNOSTICS ENGINES
# ==============================================================================
import http.server
import urllib.parse
import traceback
import tempfile

class EnterpriseAPIRequestHandler(http.server.BaseHTTPRequestHandler):
    server_token = ""
    
    def log_message(self, format, *args):
        pass

    def check_auth(self):
        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token == self.server_token:
                return True
        
        parsed_url = urllib.parse.urlparse(self.path)
        queries = urllib.parse.parse_qs(parsed_url.query)
        if "token" in queries and queries["token"][0] == self.server_token:
            return True
            
        return False

    def send_json(self, status_code, payload):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def send_unauthorized(self):
        self.send_json(401, {"error": "Unauthorized. Missing or invalid Bearer Token."})

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if not self.check_auth():
            self.send_unauthorized()
            return
            
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_docs_html().encode("utf-8"))
            
        elif path == "/api/scan":
            try:
                results = run_scan()
                self.send_json(200, results)
            except Exception as e:
                self.send_json(500, {"error": f"Scan failed: {e}", "trace": traceback.format_exc()})
                
        elif path == "/api/av":
            try:
                results = run_av_scan()
                self.send_json(200, results)
            except Exception as e:
                self.send_json(500, {"error": f"AV scan failed: {e}", "trace": traceback.format_exc()})
                
        elif path == "/api/store/status":
            try:
                catalog_path = os.path.join(os.getcwd(), "scripts/store_catalog.json")
                report = run_store_check(catalog_path)
                self.send_json(200, report)
            except Exception as e:
                self.send_json(500, {"error": f"Store catalog audit failed: {e}", "trace": traceback.format_exc()})
                
        else:
            self.send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if not self.check_auth():
            self.send_unauthorized()
            return
            
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            self.send_json(400, {"error": "Invalid JSON body"})
            return

        if path == "/api/clean":
            categories = body.get("categories", ["caches", "logs"])
            backup_type = body.get("backup_type", "cloud")
            backup_path = body.get("backup_path", None)
            encrypt = body.get("encrypt", False)
            passphrase = body.get("passphrase", None)
            use_sudo = body.get("sudo", False)
            
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp:
                results = run_scan()
                json.dump(results, tmp)
                tmp_path = tmp.name
                
            try:
                res = perform_clean(
                    results_json_path=tmp_path,
                    categories_list=categories,
                    backup_type=backup_type,
                    backup_path=backup_path,
                    encrypt=encrypt,
                    passphrase=passphrase,
                    use_sudo=use_sudo
                )
                self.send_json(200, {"status": "success", "results": res})
            except Exception as e:
                self.send_json(500, {"error": f"Cleanup failed: {e}"})
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        elif path == "/api/quarantine":
            file_path = body.get("file")
            pid = int(body.get("pid", 0))
            backup_type = body.get("backup_type", "cloud")
            backup_path = body.get("backup_path", None)
            encrypt = body.get("encrypt", False)
            passphrase = body.get("passphrase", None)
            
            if not file_path:
                self.send_json(400, {"error": "Missing 'file' field in payload"})
                return
                
            try:
                perform_quarantine(file_path, pid, backup_type, backup_path, encrypt, passphrase)
                self.send_json(200, {"status": "success", "message": f"Quarantined and terminated {file_path} (PID: {pid})"})
            except Exception as e:
                self.send_json(500, {"error": f"Quarantine failed: {e}"})
                
        elif path == "/api/sandbox":
            target_file = body.get("file")
            target_args = body.get("args", [])
            profile_type = body.get("profile_type", "no-network")
            
            if not target_file:
                self.send_json(400, {"error": "Missing 'file' field in payload"})
                return
                
            sb_profile = ""
            if profile_type == "no-network":
                sb_profile = """(version 1)
(allow default)
(deny network*)
(deny file-write* (subpath "/System"))
(deny file-write* (subpath "/Library"))
"""
            elif profile_type == "read-only":
                sb_profile = f"""(version 1)
(deny default)
(allow process*)
(allow file-read*)
(allow file-write* (subpath "{os.getcwd()}"))
(allow sysctl-read)
"""
            else:
                self.send_json(400, {"error": "Unsupported profile_type. Use 'no-network' or 'read-only'"})
                return
                
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".sb", delete=False) as tmp_sb:
                tmp_sb.write(sb_profile)
                tmp_sb_path = tmp_sb.name
                
            try:
                cmd = ["sandbox-exec", "-f", tmp_sb_path, target_file] + target_args
                res = subprocess.run(cmd, capture_output=True, text=True)
                self.send_json(200, {
                    "status": "success",
                    "returncode": res.returncode,
                    "stdout": res.stdout,
                    "stderr": res.stderr
                })
            except Exception as e:
                self.send_json(500, {"error": f"Sandbox execution failed: {e}"})
            finally:
                if os.path.exists(tmp_sb_path):
                    os.remove(tmp_sb_path)
                    
        elif path == "/api/bugreport":
            try:
                report = run_bug_report()
                self.send_json(200, report)
            except Exception as e:
                self.send_json(500, {"error": f"Failed to generate bug report: {e}"})
                
        else:
            self.send_json(404, {"error": "Endpoint not found"})

    def get_docs_html(self):
        return """<!DOCTYPE html>
<html>
<head>
    <title>Limpia-Defensa Enterprise API Console</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #121214;
            color: #e1e1e6;
            margin: 0;
            padding: 40px 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            color: #00b4d8;
            font-weight: 700;
            border-bottom: 2px solid #2a2a30;
            padding-bottom: 10px;
        }
        h2 {
            color: #52b788;
            margin-top: 30px;
        }
        code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            background: #1a1a1e;
            padding: 3px 6px;
            border-radius: 4px;
            color: #ffb703;
        }
        pre {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            background: #1a1a1e;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid #2a2a30;
        }
        .method {
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
            margin-right: 10px;
        }
        .get {
            background: #006400;
            color: #adff2f;
        }
        .post {
            background: #8b0000;
            color: #ff6347;
        }
        .endpoint-row {
            margin-bottom: 25px;
            padding: 15px;
            background: #18181c;
            border-radius: 8px;
            border-left: 4px solid #3a3a42;
        }
        .auth-note {
            background: rgba(255, 183, 3, 0.1);
            border: 1px solid #ffb703;
            color: #ffb703;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✊ Limpia-Defensa REST API Console</h1>
        <div class="auth-note">
            <strong>🔒 Bearer Token Authorization Active</strong><br>
            All endpoints require the header: <code>Authorization: Bearer &lt;token&gt;</code>.
        </div>
        
        <h2>Available API Endpoints</h2>
        
        <div class="endpoint-row">
            <span class="method get">GET</span> <code>/api/scan</code>
            <p>Runs a full disk scan and returns cache, log, and orphan size analysis in JSON format.</p>
        </div>
        
        <div class="endpoint-row">
            <span class="method get">GET</span> <code>/api/av</code>
            <p>Triggers Quetzal Core Memory process audit to identify evading and unsigned socket anomalies.</p>
        </div>
        
        <div class="endpoint-row">
            <span class="method post">POST</span> <code>/api/clean</code>
            <p>Executes a cleanup session for specific prunable categories.</p>
            <p><strong>Request Body:</strong></p>
            <pre>{
  "categories": ["caches", "logs"],
  "sudo": false,
  "backup_type": "cloud"
}</pre>
        </div>
        
        <div class="endpoint-row">
            <span class="method post">POST</span> <code>/api/quarantine</code>
            <p>Remediates a security threat, backup/quarantines the file, kills its PID, and deletes it.</p>
            <p><strong>Request Body:</strong></p>
            <pre>{
  "file": "/path/to/binary",
  "pid": 5831
}</pre>
        </div>
        
        <div class="endpoint-row">
            <span class="method post">POST</span> <code>/api/sandbox</code>
            <p>Executes any target file inside macOS <code>sandbox-exec</code> with limited network or write privileges.</p>
            <p><strong>Request Body:</strong></p>
            <pre>{
  "file": "/usr/bin/curl",
  "args": ["https://google.com"],
  "profile_type": "no-network"
}</pre>
        </div>
        
        <div class="endpoint-row">
            <span class="method post">POST</span> <code>/api/bugreport</code>
            <p>Generates a developers diagnostic report including OS build, hardware specs, tail of app logs, and scan stats.</p>
        </div>
    </div>
</body>
</html>
"""

def run_bug_report():
    report = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "os_info": {},
        "python_version": sys.version,
        "system_metrics": {},
        "engine_logs": [],
        "scan_stats": {}
    }
    try:
        uname_res = subprocess.run(["uname", "-a"], capture_output=True, text=True)
        report["os_info"]["uname"] = uname_res.stdout.strip()
    except Exception:
        pass
    try:
        sw_res = subprocess.run(["sw_vers"], capture_output=True, text=True)
        report["os_info"]["sw_vers"] = sw_res.stdout.strip()
    except Exception:
        pass
    try:
        cpu_res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
        report["system_metrics"]["cpu"] = cpu_res.stdout.strip()
    except Exception:
        pass
    try:
        mem_res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
        if mem_res.returncode == 0:
            bytes_mem = int(mem_res.stdout.strip())
            report["system_metrics"]["total_memory_gb"] = round(bytes_mem / (1024**3), 2)
    except Exception:
        pass
    log_path = os.path.expanduser("~/Library/Logs/LimpiaDefensa.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                report["engine_logs"] = [line.strip() for line in lines[-100:]]
        except Exception as e:
            report["engine_logs"] = [f"Error reading log file: {e}"]
    else:
        report["engine_logs"] = ["No log file found at ~/Library/Logs/LimpiaDefensa.log"]
    try:
        scan_data = run_scan()
        report["scan_stats"]["reclaimable_str"] = scan_data["summary"]["reclaimable_str"]
        report["scan_stats"]["categories"] = {
            cat: len(items) for cat, items in scan_data["categories"].items()
        }
    except Exception as e:
        report["scan_stats"]["error"] = str(e)
    return report

# ANSI terminal colors for CLI reports
RESET_COLOR = "\033[0m"
GREEN_COLOR = "\033[1;32m"
RED_COLOR = "\033[1;31m"
YELLOW_COLOR = "\033[1;33m"

def run_store_check(catalog_path):
    report = {
        "catalog_version": "0.0.0",
        "last_updated": "",
        "integrity_passed": True,
        "results": {}
    }
    
    if not os.path.exists(catalog_path):
        report["integrity_passed"] = False
        report["results"]["error"] = f"Catalog file not found: {catalog_path}"
        return report

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        
        report["catalog_version"] = catalog.get("version", "1.0.0")
        report["last_updated"] = catalog.get("last_updated", "")
        
        for module in catalog.get("modules", []):
            name = module.get("name")
            path = module.get("path")
            expected_hash = module.get("sha256")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            workspace_root = os.path.dirname(script_dir)
            abs_path = os.path.abspath(os.path.join(workspace_root, path))
            
            if not os.path.exists(abs_path):
                report["results"][path] = "MISSING"
                report["integrity_passed"] = False
                continue
                
            sha = hashlib.sha256()
            try:
                with open(abs_path, "rb") as bf:
                    while chunk := bf.read(65536):
                        sha.update(chunk)
                file_hash = sha.hexdigest()
                
                if file_hash == expected_hash:
                    report["results"][path] = "OK"
                else:
                    report["results"][path] = "MODIFIED"
                    report["integrity_passed"] = False
            except Exception as e:
                report["results"][path] = f"ERROR: {e}"
                report["integrity_passed"] = False
                
    except Exception as e:
        report["integrity_passed"] = False
        report["results"]["error"] = f"Failed to parse catalog: {e}"
        
    return report

def run_api_server(host, port, token):
    EnterpriseAPIRequestHandler.server_token = token
    server = http.server.HTTPServer((host, port), EnterpriseAPIRequestHandler)
    print(f"🚀 Limpia-Defensa Enterprise API Server running at http://{host}:{port}/")
    print(f"🔒 Secure Bearer Token: {token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server...")
        server.server_close()

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
    clean_parser.add_argument("--categories", required=True, help="Comma-separated categories to clean (caches,logs,installers,duplicates,orphans,vms,videos,photos,archives)")
    clean_parser.add_argument("--sudo", action="store_true", help="Elevate commands to system level")
    clean_parser.add_argument("--backup-type", default="cloud", choices=["local", "network", "cloud"], help="Backup target type")
    clean_parser.add_argument("--backup-path", help="Absolute path for custom backup targets")
    clean_parser.add_argument("--encrypt", action="store_true", help="Enable client-side AES-256 encryption")
    clean_parser.add_argument("--passphrase", help="Passphrase for encryption/decryption")

    # AV Scan parser
    av_parser = subparsers.add_parser("av-scan", help="Lightweight antivirus audit scan")
    av_parser.add_argument("--output", required=True, help="Path to write JSON threat report")
    av_parser.add_argument("--threat-db", help="Path to local signature threat-db hash database")

    # Restore parser
    restore_parser = subparsers.add_parser("restore", help="Restore staging backups")
    restore_parser.add_argument("--date", required=True, help="Backup session date directory")
    restore_parser.add_argument("--path", required=True, help="Original file path to restore")
    restore_parser.add_argument("--backup-type", default="cloud", choices=["local", "network", "cloud"], help="Backup target type")
    restore_parser.add_argument("--backup-path", help="Absolute path for custom backup targets")
    restore_parser.add_argument("--passphrase", help="Passphrase for decryption")

    # Rollback parser
    rollback_parser = subparsers.add_parser("rollback", help="Roll back an entire cleanup session")
    rollback_parser.add_argument("--date", required=True, help="Backup session date directory")
    rollback_parser.add_argument("--backup-type", default="cloud", choices=["local", "network", "cloud"], help="Backup target type")
    rollback_parser.add_argument("--backup-path", help="Absolute path for custom backup targets")
    rollback_parser.add_argument("--passphrase", help="Passphrase for decryption")

    # List Backups parser
    list_backups_parser = subparsers.add_parser("list-backups", help="List active backup sessions")
    list_backups_parser.add_argument("--backup-type", default="cloud", choices=["local", "network", "cloud"], help="Backup target type")
    list_backups_parser.add_argument("--backup-path", help="Absolute path for custom backup targets")

    # Quarantine parser
    quar_parser = subparsers.add_parser("quarantine", help="Backup, kill and delete a threat binary")
    quar_parser.add_argument("--file", required=True, help="Path to the threat file to delete")
    quar_parser.add_argument("--pid", type=int, default=0, help="PID of process to kill")
    quar_parser.add_argument("--backup-type", default="cloud", choices=["local", "network", "cloud"], help="Backup target type")
    quar_parser.add_argument("--backup-path", help="Absolute path for custom backup targets")
    quar_parser.add_argument("--encrypt", action="store_true", help="Enable client-side AES-256 encryption")
    quar_parser.add_argument("--passphrase", help="Passphrase for encryption/decryption")

    # API Server parser
    api_parser = subparsers.add_parser("api-server", help="Launch secure REST API micro-service")
    api_parser.add_argument("--host", default="127.0.0.1", help="Binding host IP")
    api_parser.add_argument("--port", type=int, default=8080, help="Port to bind API server")
    api_parser.add_argument("--token", required=True, help="Bearer token for request validation")

    # Bug Report parser
    bug_parser = subparsers.add_parser("bug-report", help="Generate local diagnostic bug report bundle")
    bug_parser.add_argument("--output", help="Custom JSON path to save diagnostics")

    # Store Check parser
    store_parser = subparsers.add_parser("store-check", help="Audit local files integrity against the store catalog")
    store_parser.add_argument("--catalog", help="Path to store_catalog.json")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        print("🔎 Scanning system directories...")
        results = run_scan()
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Saved scan metadata results to: {args.output}")
        if args.report:
            generate_markdown_report(results, args.report)
            print(f"📝 Saved markdown summary report to: {args.report}")
            
    elif args.command == "clean":
        cats = [c.strip().lower() for c in args.categories.split(",")]
        print(f"🧹 Commencing non-destructive cleanup for categories: {cats}...")
        perform_clean(args.input, cats, args.backup_type, args.backup_path, args.encrypt, args.passphrase, use_sudo=args.sudo)
        
    elif args.command == "av-scan":
        print("🛡️ Commencing modern AV threat audit...")
        av_results = run_av_scan(args.threat_db)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(av_results, f, indent=2)
        print(f"💾 Threat report successfully saved to: {args.output}")
        print(f"⚠️ Threats found: {av_results['summary']['total_threats']} | Suspicious items: {av_results['summary']['total_suspicious']}")
        
    elif args.command == "restore":
        perform_restore(args.date, args.path, args.backup_type, args.backup_path, args.passphrase)

    elif args.command == "rollback":
        perform_rollback(args.date, args.backup_type, args.backup_path, args.passphrase)

    elif args.command == "list-backups":
        results = run_list_backups(args.backup_type, args.backup_path)
        print(json.dumps(results, indent=2))

    elif args.command == "quarantine":
        perform_quarantine(args.file, args.pid, args.backup_type, args.backup_path, args.encrypt, args.passphrase)

    elif args.command == "api-server":
        run_api_server(args.host, args.port, args.token)

    elif args.command == "bug-report":
        print("📁 Packaging diagnostics bug report...")
        report = run_bug_report()
        out_path = args.output if args.output else os.path.join(os.getcwd(), "limpia_defensa_diagnostic.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"✅ Diagnostic bundle saved to: {out_path}")

    elif args.command == "store-check":
        print("📦 Commencing local Store Catalog integrity audit...")
        catalog_path = args.catalog if args.catalog else os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_catalog.json")
        report = run_store_check(catalog_path)
        print(f"Catalog Version: {report['catalog_version']} | Last Updated: {report['last_updated']}")
        print("--------------------------------------------------")
        for path, status in report["results"].items():
            color = GREEN_COLOR if status == "OK" else (RED_COLOR if status == "MISSING" else YELLOW_COLOR)
            print(f"{path:<40} -> {color}{status}{RESET_COLOR}")
        print("--------------------------------------------------")
        if report["integrity_passed"]:
            print(f"✅ {GREEN_COLOR}INTEGRITY AUDIT PASSED successfully.{RESET_COLOR}")
            sys.exit(0)
        else:
            print(f"❌ {RED_COLOR}INTEGRITY AUDIT FAILED. System modified or components missing.{RESET_COLOR}")
            sys.exit(1)

if __name__ == "__main__":
    main()
