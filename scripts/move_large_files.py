#!/usr/bin/env python3
import os
import sys
import shutil
import datetime

USER_HOME = os.path.expanduser("~")

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

SEARCH_DIRECTORIES = [
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(USER_HOME, "Documents")
]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv"}
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024 # 50 MB

def log_message(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [INFO] {msg}\n"
    print(line, end="")
    
    # Append to LimpiaDefensa persistent logs
    logs_dir = os.path.join(USER_HOME, "Library/Logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "LimpiaDefensa.log")
    try:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line)
    except Exception:
        pass

def is_gdrive_active():
    return os.path.exists(GDRIVE_ROOT)

def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    import math
    size_name = ("B", "KB", "MB", "GB", "TB")
    p = int(math.floor(math.log(size_bytes, 1024)))
    s = round(size_bytes / math.pow(1024, p), 2)
    return f"{s} {size_name[p]}"

def main():
    log_message("=== Starting Large Files Migration to Google Drive ===")
    if not is_gdrive_active():
        log_message("❌ Error: Google Drive mount is inactive. Migration halted.")
        sys.exit(1)
        
    log_message(f"Resolved Google Drive root: {GDRIVE_ROOT}")
    
    candidates = []
    
    # Scan files
    for s_dir in SEARCH_DIRECTORIES:
        if not os.path.exists(s_dir):
            continue
        log_message(f"Scanning directory: {s_dir} ...")
        for root, _, files in os.walk(s_dir):
            # Exclude git repositories completely
            if ".git" in root.split(os.sep):
                continue
            # Exclude Library/CloudStorage paths
            if "Library/CloudStorage" in root:
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
                        candidates.append({
                            "name": f,
                            "path": path,
                            "size": size,
                            "rel_dir": os.path.relpath(root, USER_HOME)
                        })
                except Exception:
                    pass
                    
    log_message(f"Found {len(candidates)} migration candidates.")
    
    total_reclaimed = 0
    moved_count = 0
    failed_count = 0
    
    for item in candidates:
        src_path = item["path"]
        size_str = format_size(item["size"])
        log_message(f"Migrating: {src_path} ({size_str})")
        
        # Build destination structure under Google Drive/My Drive/ComradeCleanup_Backup/LargeFiles/Desktop/...
        dest_dir = os.path.join(GDRIVE_ROOT, BACKUP_FOLDER_NAME, LARGE_FILES_DIR, item["rel_dir"])
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, item["name"])
        
        FLASH_DRIVE_ROOT = "/Volumes/FLASH_DRIVE"
        use_flash_staging = os.path.exists(FLASH_DRIVE_ROOT) and item["size"] >= 500 * 1024 * 1024
        
        try:
            if use_flash_staging:
                # Stage to flash drive first
                flash_dir = os.path.join(FLASH_DRIVE_ROOT, "temp_migration", item["rel_dir"])
                os.makedirs(flash_dir, exist_ok=True)
                flash_path = os.path.join(flash_dir, item["name"])
                
                log_message(f"💾 Staging to flash drive first: {flash_path}")
                shutil.copy2(src_path, flash_path)
                
                if os.path.getsize(flash_path) == item["size"]:
                    # Free up space on local disk by removing original file
                    os.remove(src_path)
                    log_message(f"🗑️ Removed original file to free up local space: {src_path}")
                    
                    # Copy from flash drive to Google Drive
                    shutil.copy2(flash_path, dest_path)
                    
                    if os.path.getsize(dest_path) == item["size"]:
                        # Remove from flash drive
                        os.remove(flash_path)
                        total_reclaimed += item["size"]
                        moved_count += 1
                        log_message(f"✅ Successfully migrated {item['name']} via flash drive.")
                    else:
                        log_message(f"❌ Size verification failed on Google Drive for: {item['name']}. File remains on flash drive.")
                        failed_count += 1
                else:
                    log_message(f"❌ Size verification failed on flash drive for: {item['name']}. Kept local original.")
                    failed_count += 1
            else:
                # Copy file preserving metadata
                shutil.copy2(src_path, dest_path)
                
                # Verify file sizes match exactly
                if os.path.getsize(dest_path) == item["size"]:
                    # Safe to delete local file
                    os.remove(src_path)
                    total_reclaimed += item["size"]
                    moved_count += 1
                    log_message(f"✅ Successfully moved to Drive and deleted locally: {item['name']}")
                else:
                    log_message(f"❌ Size verification failed for copy: {item['name']}. Kept local file.")
                    failed_count += 1
        except Exception as e:
            log_message(f"❌ Migration failed for {item['name']}: {e}")
            failed_count += 1
            
    log_message(f"=== Migration complete. Moved: {moved_count}, Failed: {failed_count}, Reclaimed: {format_size(total_reclaimed)} ===")

if __name__ == "__main__":
    main()
