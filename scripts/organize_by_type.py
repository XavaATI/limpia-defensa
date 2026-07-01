#!/usr/bin/env python3
import os
import shutil

USER_HOME = os.path.expanduser("~")
TARGET_DIRS = [
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(USER_HOME, "Documents")
]

# Map file extensions to category subfolders
CATEGORY_MAP = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".heic", ".bmp", ".tiff", ".svg", ".webp", ".eps", ".psd"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md", ".rtf", ".odt", ".pages", ".key", ".numbers"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv", ".3gp"},
    "Archives": {".zip", ".tar", ".gz", ".tgz", ".rar", ".7z", ".bz2", ".xz"},
    "Installers": {".dmg", ".pkg", ".iso", ".app", ".exe"}
}

def get_category(ext):
    ext = ext.lower()
    for cat, exts in CATEGORY_MAP.items():
        if ext in exts:
            return cat
    return None

def organize_folder(folder_path):
    if not os.path.exists(folder_path):
        return
    print(f"Organizing loose files directly in: {folder_path}")
    
    moved_count = 0
    # List files directly in the root of target folder (non-recursive for safety)
    try:
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            
            # Skip directories, hidden files, and scripts
            if os.path.isdir(item_path) or item.startswith("."):
                continue
                
            ext = os.path.splitext(item)[1]
            category = get_category(ext)
            
            if category:
                dest_dir = os.path.join(folder_path, category)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, item)
                
                # Handle file name collision
                if os.path.exists(dest_path):
                    base, ext_part = os.path.splitext(item)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext_part}")
                        counter += 1
                        
                try:
                    shutil.move(item_path, dest_path)
                    print(f"  ➡️ Moved: {item} -> {category}/")
                    moved_count += 1
                except Exception as e:
                    print(f"  ❌ Error moving {item}: {e}")
    except Exception as e:
        print(f"Error reading directory {folder_path}: {e}")
        
    print(f"Finished organizing {folder_path}. Total loose files moved: {moved_count}")

def main():
    print("=== Starting Folder Organization by Type ===")
    for d in TARGET_DIRS:
        organize_folder(d)
    print("=== Folder Organization Complete ===")

if __name__ == "__main__":
    main()
