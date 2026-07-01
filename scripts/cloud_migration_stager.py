#!/usr/bin/env python3
import os
import sys
import shutil
import time
import json
import datetime

USER_HOME = os.path.expanduser("~")
CHECKPOINT_DIR = "/Users/xavasena/.gemini/antigravity/brain/03b32843-046a-40fd-80f0-62b75d080f4e/scratch"
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "migration_checkpoint.json")
PAUSE_FLAG_PATH = "/Users/xavasena/collectivo/limpiada/pause.flag"
FLASH_DRIVE_ROOT = "/Volumes/FLASH_DRIVE"

# Cloud Storage Destination
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
LARGE_FILES_DIR = "LargeFiles"

# Scan Config
SEARCH_ROOTS = [USER_HOME, "/Users/Shared"]
EXCLUDE_DIRS = {
    "Library", "CloudStorage", "Google Drive", ".npm", ".cache", ".gemini", 
    ".cargo", ".vscode", "node_modules", "System", "Volumes", "dev", 
    "proc", "sys", "private", "Applications"
}

# Exclude all active git repositories to avoid breaking local environments
SAFE_REPOS = [
    os.path.join(USER_HOME, "queztl-core"),
    os.path.join(USER_HOME, "git"),
    os.path.join(USER_HOME, "NMSocilalistas"),
    os.path.join(USER_HOME, "collectivo"),
    os.path.join(USER_HOME, "collective"),
    os.path.join(USER_HOME, "chuco-site"),
    os.path.join(USER_HOME, "aws-coding-copilot"),
    os.path.join(USER_HOME, "hive"),
    os.path.join(USER_HOME, "merc-mercado"),
    os.path.join(USER_HOME, "securesign")
]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv", ".mov"}
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB
FLASH_STAGING_THRESHOLD = 500 * 1024 * 1024  # 500 MB

def log_message(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [MIGRATION] {msg}\n"
    print(line, end="", flush=True)
    
    logs_dir = os.path.join(USER_HOME, "Library/Logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "LimpiaDefensa.log")
    try:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line)
    except Exception:
        pass

def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_message(f"Warning: Failed to load checkpoint file: {e}")
    return {}

def save_checkpoint(checkpoint):
    try:
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
    except Exception as e:
        log_message(f"Warning: Failed to save checkpoint file: {e}")

def check_pause():
    while os.path.exists(PAUSE_FLAG_PATH):
        log_message("⏸️ Migration paused by pause.flag. Sleeping for 10 seconds...")
        time.sleep(10)

def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    import math
    size_name = ("B", "KB", "MB", "GB", "TB")
    p = int(math.floor(math.log(size_bytes, 1024)))
    s = round(size_bytes / math.pow(1024, p), 2)
    return f"{s} {size_name[p]}"

def is_repo_path(path):
    for repo in SAFE_REPOS:
        if path.startswith(repo):
            return True
    return False

def scan_candidates():
    candidates = []
    log_message("Scanning system for migration candidates...")
    for root_dir in SEARCH_ROOTS:
        if not os.path.exists(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            # Exclude directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            
            # Skip if inside an active git repository path
            if is_repo_path(root):
                continue
                
            for f in files:
                if f.startswith("."):
                    continue
                path = os.path.join(root, f)
                try:
                    size = os.path.getsize(path)
                    ext = os.path.splitext(f)[1].lower()
                    is_large = size >= LARGE_FILE_THRESHOLD
                    is_video = ext in VIDEO_EXTENSIONS
                    
                    if is_large or is_video:
                        # Find base dir for relative path structuring
                        if root.startswith(USER_HOME):
                            rel_dir = os.path.relpath(root, USER_HOME)
                        else:
                            rel_dir = os.path.relpath(root, "/")
                            
                        candidates.append({
                            "name": f,
                            "path": path,
                            "size": size,
                            "rel_dir": rel_dir
                        })
                except Exception:
                    pass
    log_message(f"Found {len(candidates)} migration candidates.")
    return candidates

def migrate_file(item, checkpoint):
    src_path = item["path"]
    size = item["size"]
    size_str = format_size(size)
    
    # Destination in Google Drive
    dest_dir = os.path.join(GDRIVE_ROOT, BACKUP_FOLDER_NAME, LARGE_FILES_DIR, item["rel_dir"])
    dest_path = os.path.join(dest_dir, item["name"])
    
    # Check if already completed in checkpoint
    if src_path in checkpoint and checkpoint[src_path].get("status") == "completed":
        if os.path.exists(dest_path) and os.path.getsize(dest_path) == size:
            log_message(f"⏭️ File already migrated and verified: {item['name']}")
            if os.path.exists(src_path):
                os.remove(src_path)
                log_message(f"🗑️ Cleaned up leftover original: {src_path}")
            return True
            
    log_message(f"Migrating: {src_path} ({size_str})")
    os.makedirs(dest_dir, exist_ok=True)
    
    use_flash = os.path.exists(FLASH_DRIVE_ROOT) and size >= FLASH_STAGING_THRESHOLD
    
    try:
        check_pause()
        
        if use_flash:
            # 1. Stage to Flash Drive
            flash_dir = os.path.join(FLASH_DRIVE_ROOT, "temp_migration", item["rel_dir"])
            os.makedirs(flash_dir, exist_ok=True)
            flash_path = os.path.join(flash_dir, item["name"])
            
            log_message(f"💾 Staging to flash drive: {flash_path}")
            shutil.copy2(src_path, flash_path)
            
            if os.path.getsize(flash_path) == size:
                # Delete local original immediately to free up space
                os.remove(src_path)
                log_message(f"🗑️ Removed original local file to free space: {src_path}")
                
                check_pause()
                
                # Copy from Flash Drive to Google Drive
                log_message(f"☁️ Uploading from flash drive to Google Drive: {dest_path}")
                shutil.copy2(flash_path, dest_path)
                
                if os.path.getsize(dest_path) == size:
                    os.remove(flash_path)
                    checkpoint[src_path] = {
                        "status": "completed",
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "size": size
                    }
                    save_checkpoint(checkpoint)
                    log_message(f"✅ Successfully migrated {item['name']} via flash staging.")
                    return True
                else:
                    log_message(f"❌ Size verification failed on Google Drive for: {item['name']}.")
                    return False
            else:
                log_message(f"❌ Size verification failed on flash drive for: {item['name']}.")
                return False
        else:
            # Direct Copy
            log_message(f"☁️ Direct copying to Google Drive: {dest_path}")
            shutil.copy2(src_path, dest_path)
            
            if os.path.getsize(dest_path) == size:
                os.remove(src_path)
                checkpoint[src_path] = {
                    "status": "completed",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "size": size
                }
                save_checkpoint(checkpoint)
                log_message(f"✅ Successfully migrated {item['name']} directly.")
                return True
            else:
                log_message(f"❌ Size verification failed on Google Drive for: {item['name']}.")
                return False
                
    except Exception as e:
        log_message(f"❌ Error migrating {item['name']}: {e}")
        return False

def main():
    log_message("=== Starting Staged Cloud Migration ===")
    if not os.path.exists(GDRIVE_ROOT):
        log_message("❌ Error: Google Drive mount is inactive. Migration aborted.")
        sys.exit(1)
        
    checkpoint = load_checkpoint()
    candidates = scan_candidates()
    
    success_count = 0
    fail_count = 0
    total_reclaimed = 0
    
    for item in candidates:
        check_pause()
        if migrate_file(item, checkpoint):
            success_count += 1
            total_reclaimed += item["size"]
        else:
            fail_count += 1
            
    log_message(f"=== Migration Finished. Successful: {success_count}, Failed: {fail_count}, Reclaimed: {format_size(total_reclaimed)} ===")

if __name__ == "__main__":
    main()
