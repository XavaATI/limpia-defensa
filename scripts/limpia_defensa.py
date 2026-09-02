#!/usr/bin/env python3
import os
import time
import sys
import json
import hashlib
import shutil
import datetime
import argparse
import subprocess
import platform
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
            "developer_caches": [],
            "ai_model_caches": [],
            "trash": [],
            "browser_caches": [],
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
    
    # 1. System & App Caches Scan
    cache_dirs = [
        (os.path.join(USER_HOME, "Library/Caches"), "User Cache"),
        ("/Library/Caches", "System Cache")
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

    # 2. Developer Build & Package Caches
    dev_cache_dirs = [
        (os.path.join(USER_HOME, ".npm"), "NPM Package Cache"),
        (os.path.join(USER_HOME, ".gradle/caches"), "Gradle Daemon Caches"),
        (os.path.join(USER_HOME, ".cargo/registry/cache"), "Rust Cargo Crate Cache"),
        (os.path.join(USER_HOME, ".bun/install/cache"), "Bun Package Cache"),
        (os.path.join(USER_HOME, ".pnpm-store"), "pnpm Store Cache"),
        (os.path.join(USER_HOME, "Library/Developer/Xcode/DerivedData"), "Xcode DerivedData"),
        (os.path.join(USER_HOME, "Library/Developer/Xcode/Archives"), "Xcode Build Archives"),
        (os.path.join(USER_HOME, "Library/Developer/CoreSimulator/Caches"), "iOS CoreSimulator Cache"),
        (os.path.join(USER_HOME, "Library/Caches/CocoaPods"), "CocoaPods Cache"),
        (os.path.join(USER_HOME, "Library/Caches/Homebrew"), "Homebrew Download Cache")
    ]
    for path, label in dev_cache_dirs:
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
                results["categories"]["developer_caches"].append({
                    "name": label,
                    "path": path,
                    "size": size,
                    "size_str": format_size(size),
                    "files_count": file_count
                })

    # 3. AI & Machine Learning Model Caches
    ai_cache_dirs = [
        (os.path.join(USER_HOME, ".cache/huggingface"), "HuggingFace Transformers Cache"),
        (os.path.join(USER_HOME, ".cache/codex-runtimes"), "Codex Runtime Cache"),
        (os.path.join(USER_HOME, ".ollama/models"), "Ollama Local LLM Blobs"),
        (os.path.join(USER_HOME, ".cache/torch"), "PyTorch Hub & Kernel Cache")
    ]
    for path, label in ai_cache_dirs:
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
                results["categories"]["ai_model_caches"].append({
                    "name": label,
                    "path": path,
                    "size": size,
                    "size_str": format_size(size),
                    "files_count": file_count
                })

    # 4. User Trash Bin
    trash_dir = os.path.join(USER_HOME, ".Trash")
    if os.path.exists(trash_dir):
        size = 0
        file_count = 0
        for root, _, files in os.walk(trash_dir):
            for f in files:
                try:
                    size += os.path.getsize(os.path.join(root, f))
                    file_count += 1
                except Exception:
                    pass
        if size > 0:
            results["categories"]["trash"].append({
                "name": "User Trash Bin",
                "path": trash_dir,
                "size": size,
                "size_str": format_size(size),
                "files_count": file_count
            })

    # 5. Dedicated Browser Caches
    browser_dirs = [
        (os.path.join(USER_HOME, "Library/Caches/Google/Chrome"), "Google Chrome Cache"),
        (os.path.join(USER_HOME, "Library/Caches/com.apple.Safari"), "Safari Cache"),
        (os.path.join(USER_HOME, "Library/Caches/Firefox"), "Mozilla Firefox Cache"),
        (os.path.join(USER_HOME, "Library/Caches/BraveSoftware/Brave-Browser"), "Brave Browser Cache"),
        (os.path.join(USER_HOME, "Library/Caches/company.thebrowser.Arc"), "Arc Browser Cache"),
        (os.path.join(USER_HOME, "Library/Caches/Microsoft Edge"), "Microsoft Edge Cache")
    ]
    for path, label in browser_dirs:
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
                results["categories"]["browser_caches"].append({
                    "name": label,
                    "path": path,
                    "size": size,
                    "size_str": format_size(size),
                    "files_count": file_count
                })

    # 6. Logs Scan
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

    # 7. Installers Scan
    for s_dir in [os.path.join(USER_HOME, "Downloads"), os.path.join(USER_HOME, "Desktop")]:
        if os.path.exists(s_dir):
            try:
                for item in os.listdir(s_dir):
                    item_path = os.path.join(s_dir, item)
                    if os.path.isfile(item_path) and item.lower().endswith((".dmg", ".pkg", ".iso")):
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

    # 8. Media Scan
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
                        elif ext in photo_exts and ("screenshot" in f.lower() or size >= 5 * 1024 * 1024):
                            results["categories"]["photos"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                        elif ext in archive_exts and size >= 10 * 1024 * 1024:
                            results["categories"]["archives"].append({
                                "name": f,
                                "path": filepath,
                                "size": size,
                                "size_str": format_size(size)
                            })
                    except Exception:
                        pass

    # 9. Duplicates Scan (Files >= 1MB)
    files_by_size = defaultdict(list)
    for s_dir in SCAN_DIRECTORIES:
        if os.path.exists(s_dir):
            for root, _, files in os.walk(s_dir):
                if any(part.startswith('.') for part in root.split(os.sep)):
                    continue
                for f in files:
                    if f.startswith('.'):
                        continue
                    filepath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(filepath)
                        if size >= 1024 * 1024:
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

    # 10. Orphans Scan
    results["categories"]["orphans"] = find_orphans()

    # Calculate Totals
    total_reclaimable = 0
    for cat, list_val in results["categories"].items():
        if cat == "duplicates":
            for group in list_val:
                total_reclaimable += group["size"] * (len(group["paths"]) - 1)
        else:
            for entry in list_val:
                total_reclaimable += entry["size"]
                
    results["summary"]["reclaimable_size"] = total_reclaimable
    results["summary"]["reclaimable_str"] = format_size(total_reclaimable)
    return results

def generate_markdown_report(results, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ✊ Limpia-Defensa System Optimization Report\n\n")
        f.write(f"**Scan Executed At**: `{results['timestamp']}`  \n")
        f.write(f"**Google Drive Cloud Connection**: `{'CONNECTED (Active Staging Enabled)' if results['gdrive_connected'] else 'DISCONNECTED (Backup Dry-Run Only)'}`  \n")
        f.write(f"**Total Reclaimable SSD Space**: **{results['summary']['reclaimable_str']}**\n\n")
        
        f.write("## 🧹 Cleanup Categories Breakdown\n\n")
        
        # Caches
        f.write("### 🗄️ System & Application Caches\n")
        caches = results["categories"].get("caches", [])
        if not caches:
            f.write("No major caches indexed.\n")
        else:
            f.write("| Cache Type | Path | File Count | Reclaimable Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for c in caches:
                f.write(f"| {c['name']} | `{c['path']}` | {c['files_count']} | **{c['size_str']}** |\n")
        f.write("\n")

        # Developer Caches
        f.write("### 🛠️ Developer & Package Caches\n")
        dev_caches = results["categories"].get("developer_caches", [])
        if not dev_caches:
            f.write("No developer build caches found.\n")
        else:
            f.write("| Cache Target | Path | File Count | Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for dc in dev_caches:
                f.write(f"| {dc['name']} | `{dc['path']}` | {dc['files_count']} | **{dc['size_str']}** |\n")
        f.write("\n")

        # AI Model Caches
        f.write("### 🤖 AI & Machine Learning Model Caches\n")
        ai_caches = results["categories"].get("ai_model_caches", [])
        if not ai_caches:
            f.write("No local AI model caches found.\n")
        else:
            f.write("| Model Framework | Path | File Count | Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for ac in ai_caches:
                f.write(f"| {ac['name']} | `{ac['path']}` | {ac['files_count']} | **{ac['size_str']}** |\n")
        f.write("\n")

        # Trash
        f.write("### 🗑️ User Trash Bin\n")
        trash_items = results["categories"].get("trash", [])
        if not trash_items:
            f.write("Trash is empty.\n")
        else:
            for t in trash_items:
                f.write(f"- Size: **{t['size_str']}** ({t['files_count']} files) in `{t['path']}`\n")
        f.write("\n")

        # Browser Caches
        f.write("### 🌐 Browser Caches\n")
        browsers = results["categories"].get("browser_caches", [])
        if not browsers:
            f.write("No separate browser caches found.\n")
        else:
            f.write("| Browser | Path | File Count | Space |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for b in browsers:
                f.write(f"| {b['name']} | `{b['path']}` | {b['files_count']} | **{b['size_str']}** |\n")
        f.write("\n")
        
        # Logs
        f.write("### 📝 System Log Buffers\n")
        logs = results["categories"].get("logs", [])
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
        installers = results["categories"].get("installers", [])
        if not installers:
            f.write("No leftover installers found.\n")
        else:
            f.write("| Installer Name | Path | File Size |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for inst in installers:
                f.write(f"| {inst['name']} | `{inst['path']}` | **{inst['size_str']}** |\n")
        f.write("\n")

        # Orphans
        f.write("### 📱 Orphaned App Support Folders\n")
        orphans = results["categories"].get("orphans", [])
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
        dupes = results["categories"].get("duplicates", [])
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
        
        # Disposable cache categories skip expensive zip compression
        if category in ["caches", "developer_caches", "ai_model_caches", "browser_caches", "trash", "logs"]:
            if manifest is not None:
                manifest["files"][hashed_key] = {
                    "original_path": source_path,
                    "type": "directory" if os.path.isdir(source_path) else "file",
                    "checksum": "disposable-cache",
                    "size": 0,
                    "category": category
                }
            return True

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

    for category in [
        "caches", "developer_caches", "ai_model_caches", "trash", "browser_caches",
        "logs", "installers", "orphans", "vms", "videos", "photos", "archives"
    ]:
        if category in categories_list:
            for entry in results["categories"].get(category, []):
                path = entry["path"]
                if not os.path.exists(path):
                    continue
                is_system_path = path.startswith(("/Library", "/var/log"))
                if is_system_path and not use_sudo:
                    print(f"⏭️ Skipping system-level path (run with --sudo to clean): {path}")
                    continue
                    
                print(f"📦 Staging to backup: {path}")
                if stage_file_to_backup(path, category, run_date, backup_type, backup_path, encrypt, passphrase, manifest):
                    try:
                        if os.path.isdir(path):
                            if category in ["caches", "developer_caches", "ai_model_caches", "trash", "browser_caches"]:
                                # Prune contents inside the cache/trash directory to preserve directory mount
                                if use_sudo and is_system_path:
                                    subprocess.run(f"sudo rm -rf '{path}'/* '{path}'/.[!.]* 2>/dev/null || true", shell=True, check=False)
                                else:
                                    for child in os.listdir(path):
                                        child_path = os.path.join(path, child)
                                        try:
                                            if os.path.isdir(child_path):
                                                shutil.rmtree(child_path, ignore_errors=True)
                                            else:
                                                os.remove(child_path)
                                        except Exception:
                                            pass
                            else:
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
        "vectors_scanned": [
            "Process Memory & Disguised Daemons",
            "Reverse Shells & Remote Sockets",
            "LaunchAgents & LaunchDaemons Persistence",
            "Shell Startup Profiles & Injections",
            "Cron & Periodic Tasks",
            "Keychain & Stealer Heuristics",
            "Network Listeners & Open Ports",
            "Unsigned Binaries in Staging Dirs",
            "Cryptominer Signatures"
        ],
        "threats_found": [],
        "suspicious_items": [],
        "summary": {
            "total_threats": 0,
            "total_suspicious": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0
        }
    }

    # --------------------------------------------------------------------------
    # VECTOR 1: ACTIVE PROCESS MEMORY & BEHAVIORAL SWEEPS
    # --------------------------------------------------------------------------
    try:
        ps_proc = subprocess.run(
            ["ps", "-eo", "pid,ppid,%cpu,%mem,comm,args"],
            capture_output=True,
            text=True
        )
        if ps_proc.returncode == 0:
            lines = ps_proc.stdout.strip().split("\n")
            header = lines[0] if lines else ""
            for line in lines[1:]:
                parts = line.strip().split(None, 5)
                if len(parts) < 6:
                    continue
                pid_str, ppid_str, cpu_str, mem_str, comm, args = parts
                pid = int(pid_str) if pid_str.isdigit() else 0
                if pid <= 1:
                    continue

                args_lower = args.lower()
                comm_lower = comm.lower()

                # A. Reverse Shell Heuristic
                rev_shell_patterns = [
                    "import socket,subprocess,os;s=socket.socket",
                    "socket.socket(socket.af_inet",
                    "nc -e /bin/",
                    "ncat -e /bin/",
                    "bash -i >& /dev/tcp/",
                    "zsh -i >& /dev/tcp/",
                    "/bin/sh -i >& /dev/tcp/",
                    "base64 -d | sh",
                    "base64 -d | bash",
                    "base64 -d | zsh"
                ]
                for pat in rev_shell_patterns:
                    if pat in args:
                        av_results["threats_found"].append({
                            "name": os.path.basename(comm),
                            "path": comm,
                            "pid": pid,
                            "type": "Interactive Reverse Shell Execution",
                            "severity": "CRITICAL",
                            "sha256": get_file_sha256(comm) or "N/A",
                            "reason": f"Active process PID {pid} is running reverse shell payload: '{pat}'"
                        })

                # B. Masquerading Daemon Names
                disguised_names = ["launchd", "windowserver", "kernel_task", "mdworker", "syslogd", "opendirectoryd"]
                base_comm = os.path.basename(comm)
                if base_comm in disguised_names:
                    # Valid system daemons live in /System, /usr/libexec, /usr/sbin, /sbin
                    if not comm.startswith(("/System", "/usr/libexec", "/usr/sbin", "/sbin", "/usr/bin")):
                        av_results["threats_found"].append({
                            "name": base_comm,
                            "path": comm,
                            "pid": pid,
                            "type": "Disguised System Daemon Masquerade",
                            "severity": "CRITICAL",
                            "sha256": get_file_sha256(comm) or "N/A",
                            "reason": f"Process {base_comm} running from non-system location '{comm}'"
                        })

                # C. Execution from Temp or Staging Directories
                if comm.startswith(("/tmp/", "/var/tmp/", "/dev/shm/")):
                    sha256 = get_file_sha256(comm)
                    av_results["threats_found"].append({
                        "name": base_comm,
                        "path": comm,
                        "pid": pid,
                        "type": "Active Binary in Volatile Temp Directory",
                        "severity": "HIGH",
                        "sha256": sha256 or "N/A",
                        "reason": f"Active process PID {pid} is executing binary located inside volatile directory '{comm}'"
                    })

                # D. Cryptominer Signatures
                miner_keywords = ["xmrig", "stratum+tcp://", "stratum+ssl://", "minergate", "hashvault.pro", "cryptonight", "moneroocean"]
                for mk in miner_keywords:
                    if mk in args_lower:
                        av_results["threats_found"].append({
                            "name": base_comm,
                            "path": comm,
                            "pid": pid,
                            "type": "Cryptocurrency Mining Process",
                            "severity": "CRITICAL",
                            "sha256": get_file_sha256(comm) or "N/A",
                            "reason": f"Process PID {pid} contains mining connection argument: '{mk}'"
                        })
    except Exception as e:
        print(f"Process memory audit exception: {e}")

    # --------------------------------------------------------------------------
    # VECTOR 2: LAUNCH AGENTS & LAUNCH DAEMONS PERSISTENCE
    # --------------------------------------------------------------------------
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
                        is_threat = False
                        is_suspicious = False
                        reasons = []
                        severity = "LOW"
                        
                        try:
                            # 1. Hash audit against threat DB
                            sha256 = get_file_sha256(item_path)
                            if sha256 and sha256 in threat_hashes:
                                is_threat = True
                                severity = "CRITICAL"
                                reasons.append("Matches known hash signature in threat database")

                            # 2. Parse plist content
                            with open(item_path, "rb") as pf:
                                try:
                                    import plistlib
                                    plist_data = plistlib.load(pf)
                                    prog_args = plist_data.get("ProgramArguments", [])
                                    prog = plist_data.get("Program", "")
                                    all_cmd_strings = [str(prog)] + [str(a) for a in prog_args]
                                    joined_cmd = " ".join(all_cmd_strings)
                                except Exception:
                                    pf.seek(0)
                                    joined_cmd = pf.read().decode("utf-8", errors="ignore")

                            # Suspicious command checks with word boundaries
                            if any(re_kw in joined_cmd for re_kw in ["curl ", "wget ", "base64 -d", "base64 --decode", "nc -e", "/tmp/"]):
                                if "base64" in joined_cmd or "/tmp/" in joined_cmd:
                                    is_threat = True
                                    severity = "HIGH"
                                    reasons.append(f"Persistence script executes suspicious commands from tmp/base64: {joined_cmd[:100]}")
                                else:
                                    is_suspicious = True
                                    severity = "MEDIUM"
                                    reasons.append(f"Persistence script downloads/executes network scripts: {joined_cmd[:100]}")
                                    
                            if "security find-generic-password" in joined_cmd or "security dump-keychain" in joined_cmd:
                                is_threat = True
                                severity = "CRITICAL"
                                reasons.append("Attempts to harvest Keychain credentials via security command")

                            if is_threat:
                                av_results["threats_found"].append({
                                    "name": item,
                                    "path": item_path,
                                    "type": "Malicious Launch Persistence Daemon",
                                    "severity": severity,
                                    "sha256": sha256 or "Unknown",
                                    "reason": "; ".join(reasons)
                                })
                            elif is_suspicious:
                                av_results["suspicious_items"].append({
                                    "name": item,
                                    "path": item_path,
                                    "type": "Suspicious Launch Persistence Item",
                                    "severity": severity,
                                    "sha256": sha256 or "Unknown",
                                    "reason": "; ".join(reasons)
                                })
                        except Exception:
                            pass
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # VECTOR 3: SHELL STARTUP PROFILES & INJECTIONS
    # --------------------------------------------------------------------------
    shell_rc_files = [
        os.path.join(USER_HOME, ".zshrc"),
        os.path.join(USER_HOME, ".zshenv"),
        os.path.join(USER_HOME, ".zprofile"),
        os.path.join(USER_HOME, ".bashrc"),
        os.path.join(USER_HOME, ".bash_profile"),
        os.path.join(USER_HOME, ".profile"),
        "/etc/zshrc",
        "/etc/zprofile",
        "/etc/profile",
        "/etc/bashrc"
    ]
    for rc in shell_rc_files:
        if os.path.exists(rc):
            try:
                with open(rc, "r", encoding="utf-8", errors="ignore") as rf:
                    lines = rf.readlines()
                for idx, line in enumerate(lines):
                    line_str = line.strip()
                    if not line_str or line_str.startswith("#"):
                        continue
                    
                    # Heuristics for malicious shell injections
                    if "curl " in line_str and ("| sh" in line_str or "| bash" in line_str or "| zsh" in line_str):
                        av_results["threats_found"].append({
                            "name": f"{os.path.basename(rc)} (Line {idx+1})",
                            "path": rc,
                            "type": "Shell Profile Piped Network Execution Hook",
                            "severity": "HIGH",
                            "sha256": get_file_sha256(rc) or "N/A",
                            "reason": f"Auto-executes remote script: {line_str[:120]}"
                        })
                    elif "base64 -d" in line_str and ("sh" in line_str or "eval" in line_str):
                        av_results["threats_found"].append({
                            "name": f"{os.path.basename(rc)} (Line {idx+1})",
                            "path": rc,
                            "type": "Obfuscated Base64 Shell Hook",
                            "severity": "CRITICAL",
                            "sha256": get_file_sha256(rc) or "N/A",
                            "reason": f"Contains obfuscated evaluation command: {line_str[:120]}"
                        })
                    elif "DYLD_INSERT_LIBRARIES" in line_str or "DYLD_LIBRARY_PATH" in line_str:
                        av_results["suspicious_items"].append({
                            "name": f"{os.path.basename(rc)} (Line {idx+1})",
                            "path": rc,
                            "type": "Dynamic Library (DYLD) Injection Variable",
                            "severity": "HIGH",
                            "sha256": get_file_sha256(rc) or "N/A",
                            "reason": f"Overrides macOS dynamic linker: {line_str[:120]}"
                        })
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # VECTOR 4: CRON & PERIODIC SYSTEM TASKS
    # --------------------------------------------------------------------------
    try:
        cron_proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if cron_proc.returncode == 0 and cron_proc.stdout.strip():
            cron_lines = cron_proc.stdout.strip().split("\n")
            for idx, line in enumerate(cron_lines):
                line_clean = line.strip()
                if line_clean and not line_clean.startswith("#"):
                    if any(kw in line_clean for kw in ["curl", "wget", "base64", "sh", "bash", "python", "/tmp"]):
                        av_results["suspicious_items"].append({
                            "name": f"User Crontab Task {idx+1}",
                            "path": "crontab",
                            "type": "Automated Cron Task",
                            "severity": "MEDIUM",
                            "sha256": "N/A",
                            "reason": f"Active execution command: {line_clean}"
                        })
    except Exception:
        pass

    periodic_dirs = ["/etc/periodic/daily", "/etc/periodic/weekly", "/etc/periodic/monthly"]
    for pdir in periodic_dirs:
        if os.path.exists(pdir):
            try:
                for item in os.listdir(pdir):
                    p_path = os.path.join(pdir, item)
                    if os.path.isfile(p_path) and not item.startswith("."):
                        # Check if non-standard system periodic task
                        standard_tasks = ["100.clean-logs", "130.clean-rwho", "140.clean-httpd", "199.clean-fax", "300.biweekly", "400.status-disks"]
                        if item not in standard_tasks:
                            av_results["suspicious_items"].append({
                                "name": item,
                                "path": p_path,
                                "type": "Custom Periodic Maintenance Script",
                                "severity": "LOW",
                                "sha256": get_file_sha256(p_path) or "N/A",
                                "reason": f"Non-default periodic script located in '{pdir}'"
                            })
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # VECTOR 5: NETWORK LISTENERS & OPEN PORTS
    # --------------------------------------------------------------------------
    try:
        lsof_proc = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"],
            capture_output=True,
            text=True
        )
        if lsof_proc.returncode == 0:
            lines = lsof_proc.stdout.strip().split("\n")
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 9:
                    comm_name = parts[0]
                    pid_str = parts[1]
                    user_str = parts[2]
                    port_str = parts[8]
                    pid = int(pid_str) if pid_str.isdigit() else 0
                    
                    # Flag listeners running from /tmp or volatile paths
                    try:
                        bin_proc = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
                        bin_path = bin_proc.stdout.strip()
                        if bin_path.startswith(("/tmp/", "/var/tmp/", "/Users/")):
                            # Check if signed
                            cs = subprocess.run(["codesign", "-v", bin_path], capture_output=True)
                            if cs.returncode != 0 and not bin_path.endswith(("/node", "/python3", "/limpia-defensa-gui")):
                                av_results["suspicious_items"].append({
                                    "name": f"{comm_name} (Port {port_str})",
                                    "path": bin_path,
                                    "pid": pid,
                                    "type": "Unsigned User-Space Network Listener",
                                    "severity": "HIGH",
                                    "sha256": get_file_sha256(bin_path) or "N/A",
                                    "reason": f"Unsigned binary listening on port {port_str} executed by {user_str}"
                                })
                    except Exception:
                        pass
    except Exception:
        pass

    # --------------------------------------------------------------------------
    # VECTOR 6: HIGH-RISK ENTRY DIRECTORIES & CODE SIGNATURES
    # --------------------------------------------------------------------------
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
                        try:
                            stat_info = os.stat(item_path)
                            is_executable = (stat_info.st_mode & 0o111) != 0
                            
                            is_script = False
                            if not is_executable:
                                with open(item_path, "rb") as f:
                                    header = f.read(2)
                                    if header == b"#!":
                                        is_script = True
                                        
                            if is_executable or is_script:
                                is_signed = False
                                try:
                                    cs_proc = subprocess.run(["codesign", "-v", item_path], capture_output=True)
                                    if cs_proc.returncode == 0:
                                        is_signed = True
                                except Exception:
                                    pass
                                    
                                sha256 = get_file_sha256(item_path)
                                if sha256 and sha256 in threat_hashes:
                                    av_results["threats_found"].append({
                                        "name": item,
                                        "path": item_path,
                                        "type": "Known Malicious Signature Binary",
                                        "severity": "CRITICAL",
                                        "sha256": sha256,
                                        "reason": "Matches known signature in threat database"
                                    })
                                elif not is_signed and not item_path.endswith((".py", ".sh", ".swift")):
                                    av_results["suspicious_items"].append({
                                        "name": item,
                                        "path": item_path,
                                        "type": "Unsigned Executable in High-Risk Folder",
                                        "severity": "LOW",
                                        "sha256": sha256 or "Unknown",
                                        "reason": "Unsigned binary file with execution privileges in staging folder"
                                    })
                        except Exception:
                            pass
            except Exception:
                pass

    # Summarize severities
    av_results["summary"]["total_threats"] = len(av_results["threats_found"])
    av_results["summary"]["total_suspicious"] = len(av_results["suspicious_items"])
    for t in av_results["threats_found"] + av_results["suspicious_items"]:
        sev = t.get("severity", "LOW")
        if sev == "CRITICAL":
            av_results["summary"]["critical_count"] += 1
        elif sev == "HIGH":
            av_results["summary"]["high_count"] += 1
        elif sev == "MEDIUM":
            av_results["summary"]["medium_count"] += 1

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

    # 2. Unload LaunchAgent/Daemon if applicable
    if filepath.endswith(".plist") and ("LaunchAgents" in filepath or "LaunchDaemons" in filepath):
        print(f"🛑 Unloading Launch Daemon/Agent: {filepath}")
        try:
            subprocess.run(["launchctl", "unload", filepath], capture_output=True)
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", filepath], capture_output=True)
            print(f"✅ Unloaded launchd service: {filepath}")
        except Exception as e:
            print(f"⚠️ launchctl unload note: {e}")

    # 3. Terminate PID
    if pid > 0:
        print(f"🛑 Terminating process PID {pid}...")
        terminated = False
        try:
            os.kill(pid, 9)
            print(f"✅ Sent SIGKILL to process {pid}")
            terminated = True
        except ProcessLookupError:
            print(f"ℹ️ Process {pid} already dead.")
            terminated = True
        except PermissionError:
            print(f"⚠️ Permission denied. Retrying with sudo...")
            try:
                subprocess.run(["sudo", "kill", "-9", str(pid)], check=True)
                print(f"✅ Terminated process {pid} via sudo")
                terminated = True
            except Exception as e:
                print(f"❌ Failed to terminate process {pid} via sudo: {e}")
        except Exception as e:
            print(f"❌ Failed to terminate process {pid}: {e}")

        if terminated:
            print(f"⏳ Waiting for process {pid} to terminate completely...")
            max_retries = 30  # 3 seconds max
            for i in range(max_retries):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    print(f"ℹ️ Process {pid} has exited.")
                    break
                except PermissionError:
                    time.sleep(0.1)
            else:
                print(f"⚠️ Process {pid} did not exit within 3 seconds.")

    # 4. Delete binary from disk
    if os.path.exists(filepath):
        print(f"🗑️ Deleting file from disk: {filepath}")
        delete_success = False
        for attempt in range(5):
            try:
                os.remove(filepath)
                print(f"✅ Deleted threat binary: {filepath}")
                delete_success = True
                break
            except PermissionError:
                print(f"⚠️ Permission denied deleting file. Retrying with sudo...")
                try:
                    subprocess.run(["sudo", "rm", "-f", filepath], check=True)
                    print(f"✅ Deleted threat binary via sudo: {filepath}")
                    delete_success = True
                    break
                except Exception as e:
                    print(f"❌ Failed to delete file via sudo (attempt {attempt + 1}/5): {e}")
            except Exception as e:
                print(f"❌ Failed to delete file (attempt {attempt + 1}/5): {e}")
            
            time.sleep(0.2)
            
        if not delete_success:
            print(f"❌ Permanent failure: Could not delete threat binary {filepath}")

# ==============================================================================
# ENTERPRISE REST API & DIAGNOSTICS ENGINES
# ==============================================================================
import http.server
import socketserver
import threading
import urllib.parse
import traceback
import tempfile

def get_doctor_report():
    issues = []
    
    # 1. Python Environment
    py_ver = sys.version.split()[0]
    py_ok = sys.version_info >= (3, 10)
    if not py_ok:
        issues.append("Upgrade Python to 3.10 or higher")

    # 2. Operating System & Architecture
    arch = platform.machine()
    sw_vers = "macOS"
    try:
        sw_proc = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
        if sw_proc.returncode == 0:
            sw_vers = f"macOS {sw_proc.stdout.strip()}"
    except Exception:
        pass
    
    # 3. Swift Compiler
    swiftc_ok = False
    v_line = "Not Found"
    try:
        sc_proc = subprocess.run(["swiftc", "--version"], capture_output=True, text=True)
        if sc_proc.returncode == 0:
            v_line = sc_proc.stdout.split("\n")[0]
            swiftc_ok = True
    except Exception:
        pass
    if not swiftc_ok:
        issues.append("Install Xcode Command Line Tools: xcode-select --install")
        
    # 4. Binary Code Signatures
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    gui_candidates = [
        os.path.join(script_dir, "limpia-defensa-gui"),
        os.path.join(workspace_root, "bin", "limpia-defensa-gui"),
        shutil.which("limpia-defensa-gui")
    ]
    gui_binary = next((g for g in gui_candidates if g and os.path.exists(g)), os.path.join(script_dir, "limpia-defensa-gui"))
    app_bundle = os.path.join(workspace_root, "LimpiaDefensa.app")
    
    gui_status = "MISSING"
    if os.path.exists(gui_binary):
        cs = subprocess.run(["codesign", "-v", gui_binary], capture_output=True)
        gui_status = "SIGNED" if cs.returncode == 0 else "UNSIGNED_OR_MODIFIED"
        if cs.returncode != 0:
            issues.append("Re-sign GUI binary via 'python3 scripts/limpia_defensa.py patch-release'")
    else:
        issues.append("Compile GUI binary: 'python3 scripts/limpia_defensa.py patch-release'")
        
    app_status = "NOT_ASSEMBLED"
    if os.path.exists(app_bundle):
        app_cs = subprocess.run(["codesign", "-v", app_bundle], capture_output=True)
        app_status = "SIGNED" if app_cs.returncode == 0 else "UNSIGNED"

    # 5. Store Catalog Integrity
    catalog_path = find_catalog_path()
    chk = run_store_check(catalog_path)
    if not chk.get("integrity_passed", False):
        issues.append("Run 'python3 scripts/limpia_defensa.py patch-release' to synchronize catalog hashes")
        
    # 6. LaunchAgent Background Daemon
    daemon_active = False
    try:
        la_proc = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        if "com.limpiadefensa.agent" in la_proc.stdout:
            daemon_active = True
    except Exception:
        pass
        
    # 7. Disk Health
    disk_avail = "Unknown"
    disk_cap = "Unknown"
    try:
        df_proc = subprocess.run(["df", "-h", "/System/Volumes/Data"], capture_output=True, text=True)
        if df_proc.returncode == 0:
            lines = df_proc.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                disk_avail, disk_cap = parts[3], parts[4]
    except Exception:
        pass

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "healthy": len(issues) == 0,
        "issues": issues,
        "python": {"version": py_ver, "status": "OK" if py_ok else "DEPRECATED"},
        "os": {"version": sw_vers, "arch": arch, "status": "OK"},
        "swift": {"version": v_line, "status": "OK" if swiftc_ok else "NOT_FOUND"},
        "signatures": {
            "gui_binary": gui_status,
            "app_bundle": app_status
        },
        "catalog": {
            "version": chk.get("catalog_version", "0.0.0"),
            "status": "OK" if chk.get("integrity_passed", False) else "MODIFIED"
        },
        "daemon": {
            "label": "com.limpiadefensa.agent",
            "status": "ACTIVE" if daemon_active else "INACTIVE"
        },
        "disk": {
            "available": disk_avail,
            "capacity": disk_cap,
            "status": "OK"
        }
    }

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class EnterpriseAPIRequestHandler(http.server.BaseHTTPRequestHandler):
    server_token = ""
    server_start_time = time.time()
    request_counter = 0
    _lock = threading.Lock()
    
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Server", "LimpiaDefensa-Enterprise/1.3.4")
        self.end_headers()
        self.wfile.write(b'{"cors":"enabled"}')

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
        with EnterpriseAPIRequestHandler._lock:
            EnterpriseAPIRequestHandler.request_counter += 1
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept")
        self.send_header("Server", "LimpiaDefensa-Enterprise/1.3.4")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def send_unauthorized(self):
        self.send_json(401, {"error": "Unauthorized. Missing or invalid Bearer Token."})

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Unauthenticated liveness probe
        if path == "/healthz":
            uptime = round(time.time() - EnterpriseAPIRequestHandler.server_start_time, 2)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            catalog_path = os.path.join(script_dir, "store_catalog.json")
            cat_ver = "1.3.4"
            if os.path.exists(catalog_path):
                try:
                    with open(catalog_path, "r", encoding="utf-8") as f:
                        cat_ver = json.load(f).get("version", cat_ver)
                except Exception:
                    pass
            self.send_json(200, {
                "status": "healthy",
                "service": "Limpia-Defensa Enterprise API",
                "version": cat_ver,
                "uptime_seconds": uptime,
                "arch": platform.machine(),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            return
            
        if not self.check_auth():
            self.send_unauthorized()
            return
            
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Server", "LimpiaDefensa-Enterprise/1.3.4")
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
                script_dir = os.path.dirname(os.path.abspath(__file__))
                catalog_path = os.path.join(script_dir, "store_catalog.json")
                report = run_store_check(catalog_path)
                self.send_json(200, report)
            except Exception as e:
                self.send_json(500, {"error": f"Store catalog audit failed: {e}", "trace": traceback.format_exc()})
                
        elif path == "/api/doctor":
            try:
                doc = get_doctor_report()
                self.send_json(200, doc)
            except Exception as e:
                self.send_json(500, {"error": f"Doctor audit failed: {e}", "trace": traceback.format_exc()})

        elif path == "/api/metrics":
            uptime = round(time.time() - EnterpriseAPIRequestHandler.server_start_time, 2)
            self.send_json(200, {
                "service": "Limpia-Defensa Enterprise API",
                "uptime_seconds": uptime,
                "total_requests": EnterpriseAPIRequestHandler.request_counter,
                "python_version": sys.version.split()[0],
                "active_threads": threading.active_count(),
                "pid": os.getpid()
            })

        elif path == "/api/backups":
            try:
                backups = run_list_backups("cloud", None)
                self.send_json(200, backups)
            except Exception as e:
                self.send_json(500, {"error": f"Backups list failed: {e}", "trace": traceback.format_exc()})
                
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
(deny file-write* (subpath "/usr"))
(deny file-write* (subpath "/bin"))
(deny file-write* (subpath "/sbin"))
(deny file-write* (subpath "/private/var/root"))
"""
            elif profile_type == "read-only":
                clean_cwd = os.getcwd().replace('\\', '\\\\').replace('"', '\\"')
                sb_profile = f"""(version 1)
(deny default)
(allow process*)
(allow file-read*)
(allow file-write* (subpath "{clean_cwd}"))
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

        elif path == "/api/patch-release":
            bump = body.get("bump", "patch")
            dry_run = body.get("dry_run", False)
            skip_tests = body.get("skip_tests", False)
            pipeline_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_pipeline.py")
            cmd = [sys.executable, pipeline_script, "--bump", bump]
            if dry_run:
                cmd.append("--dry-run")
            if skip_tests:
                cmd.append("--skip-tests")
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.send_json(200 if res.returncode == 0 else 500, {
                "status": "success" if res.returncode == 0 else "failed",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
                
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

def find_catalog_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    candidates = [
        os.path.join(script_dir, "store_catalog.json"),
        os.path.join(workspace_root, "scripts", "store_catalog.json"),
        os.path.join(workspace_root, "store_catalog.json"),
        os.path.join(os.path.dirname(workspace_root), "scripts", "store_catalog.json"),
        "/opt/homebrew/opt/limpia-defensa/scripts/store_catalog.json"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

def run_store_check(catalog_path=None):
    if not catalog_path:
        catalog_path = find_catalog_path()

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
            base_filename = os.path.basename(path)
            candidate_paths = [
                os.path.abspath(os.path.join(workspace_root, path)),
                os.path.abspath(os.path.join(workspace_root, "bin", base_filename)),
                os.path.abspath(os.path.join(workspace_root, "scripts", base_filename)),
                os.path.abspath(os.path.join(script_dir, base_filename)),
            ]
            abs_path = next((cp for cp in candidate_paths if os.path.exists(cp)), candidate_paths[0])
            
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
    EnterpriseAPIRequestHandler.server_start_time = time.time()
    server = ThreadedHTTPServer((host, port), EnterpriseAPIRequestHandler)
    print(f"🚀 Limpia-Defensa Enterprise Multi-Threaded API Server running at http://{host}:{port}/")
    print(f"🔒 Secure Bearer Token: {token}")
    print(f"🩺 Liveness Health Probe: http://{host}:{port}/healthz")
    print(f"📊 System Metrics Telemetry: http://{host}:{port}/api/metrics")
    print(f"🩺 Remote System Diagnostics: http://{host}:{port}/api/doctor")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server...")
        server.server_close()

def run_doctor():
    doc = get_doctor_report()
    print(f"\n{GREEN_COLOR}======================================================{RESET_COLOR}")
    print(f"{GREEN_COLOR}🩺 LIMPIA-DEFENSA SOLO-OPERATOR SYSTEM DOCTOR{RESET_COLOR}")
    print(f"{GREEN_COLOR}======================================================{RESET_COLOR}")
    
    py = doc["python"]
    py_col = GREEN_COLOR if py["status"] == "OK" else RED_COLOR
    print(f"  [+] Python Runtime: {py['version']} ({py_col}{py['status']}{RESET_COLOR})")
    
    os_info = doc["os"]
    print(f"  [+] OS Architecture: {os_info['version']} ({os_info['arch']}) ({GREEN_COLOR}OK{RESET_COLOR})")
    
    sw = doc["swift"]
    sw_col = GREEN_COLOR if sw["status"] == "OK" else RED_COLOR
    print(f"  [+] Swift Compiler: {sw['version']} ({sw_col}{sw['status']}{RESET_COLOR})")
    
    sig = doc["signatures"]
    gui_sig_col = GREEN_COLOR if sig["gui_binary"] == "SIGNED" else RED_COLOR
    print(f"  [+] GUI Binary Signature: {sig['gui_binary']} ({gui_sig_col}{sig['gui_binary']}{RESET_COLOR})")
    app_sig_col = GREEN_COLOR if sig["app_bundle"] == "SIGNED" else YELLOW_COLOR
    print(f"  [+] App Bundle Signature: {sig['app_bundle']} ({app_sig_col}{sig['app_bundle']}{RESET_COLOR})")
    
    cat = doc["catalog"]
    cat_col = GREEN_COLOR if cat["status"] == "OK" else RED_COLOR
    print(f"  [+] Store Catalog Integrity: Version {cat['version']} ({cat_col}{cat['status']}{RESET_COLOR})")
    
    daemon = doc["daemon"]
    daemon_col = GREEN_COLOR if daemon["status"] == "ACTIVE" else YELLOW_COLOR
    print(f"  [+] Background Daemon: {daemon['label']} ({daemon_col}{daemon['status']}{RESET_COLOR})")
    
    disk = doc["disk"]
    print(f"  [+] Disk Health: {disk['available']} available ({disk['capacity']} capacity) ({GREEN_COLOR}OK{RESET_COLOR})")
    
    print(f"\n{GREEN_COLOR}------------------------------------------------------{RESET_COLOR}")
    if doc["healthy"]:
        print(f"🎉 {GREEN_COLOR}ALL DOCTOR CHECKS PASSED! System is in prime operating state.{RESET_COLOR}\n")
        return 0
    else:
        print(f"⚠️ {YELLOW_COLOR}{len(doc['issues'])} action item(s) recommended:{RESET_COLOR}")
        for idx, item in enumerate(doc["issues"]):
            print(f"   {idx+1}. {item}")
        print()
        return 1

def install_daemon(port=8989, token="test-enterprise-token"):
    user_home = os.path.expanduser("~")
    launch_agents_dir = os.path.join(user_home, "Library", "LaunchAgents")
    os.makedirs(launch_agents_dir, exist_ok=True)
    
    plist_path = os.path.join(launch_agents_dir, "com.limpiadefensa.agent.plist")
    script_path = os.path.abspath(__file__)
    python_bin = sys.executable
    log_dir = os.path.join(user_home, "Library", "Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "LimpiaDefensaAPI.log")
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.limpiadefensa.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{script_path}</string>
        <string>api-server</string>
        <string>--port</string>
        <string>{port}</string>
        <string>--token</string>
        <string>{token}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{os.path.dirname(script_path)}</string>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""
    subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
    
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist_content)
        
    res = subprocess.run(["launchctl", "load", plist_path], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✅ LaunchAgent deployed and loaded successfully at: {plist_path}")
        print(f"📡 API Server running on port {port} with token '{token}'")
        return True
    else:
        print(f"⚠️ Failed to load LaunchAgent: {res.stderr}")
        return False

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
    clean_parser.add_argument("--categories", required=True, help="Comma-separated categories to clean (caches,developer_caches,ai_model_caches,trash,browser_caches,logs,installers,duplicates,orphans,vms,videos,photos,archives)")
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

    # Doctor parser
    doc_parser = subparsers.add_parser("doctor", help="Run solo-operator system environment and health audit")

    # Install Daemon parser
    daemon_parser = subparsers.add_parser("install-daemon", help="Generate and deploy LaunchAgent background service")
    daemon_parser.add_argument("--port", type=int, default=8989, help="Port to bind API server (default: 8989)")
    daemon_parser.add_argument("--token", default="test-enterprise-token", help="Bearer authentication token")

    # Patch Release parser
    patch_parser = subparsers.add_parser("patch-release", help="Execute automated solo-operator release and patch pipeline")
    patch_parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch", help="Semver level to bump (default: patch)")
    patch_parser.add_argument("--version", help="Explicit version override (e.g. 1.3.1)")
    patch_parser.add_argument("--skip-tests", action="store_true", help="Skip running Kali test suite")
    patch_parser.add_argument("--publish", action="store_true", help="Publish release to GitHub and push formula to homebrew-colectivo")
    patch_parser.add_argument("--dry-run", action="store_true", help="Preview actions without modifying files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "doctor":
        exit_code = run_doctor()
        sys.exit(exit_code)

    elif args.command == "install-daemon":
        success = install_daemon(port=args.port, token=args.token)
        sys.exit(0 if success else 1)

    elif args.command == "patch-release":
        pipeline_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_pipeline.py")
        cmd = [sys.executable, pipeline_script, "--bump", args.bump]
        if args.version:
            cmd.extend(["--version", args.version])
        if args.skip_tests:
            cmd.append("--skip-tests")
        if args.publish:
            cmd.append("--publish")
        if args.dry_run:
            cmd.append("--dry-run")
        res = subprocess.run(cmd)
        sys.exit(res.returncode)

    elif args.command == "scan":
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
        catalog_path = args.catalog if args.catalog else find_catalog_path()
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
