import os
from collections import defaultdict
from core.hasher import compute_hash


FILE_TYPES = {
    "Images": [".png", ".jpg", ".jpeg", ".gif"],
    "Videos": [".mp4", ".mkv", ".avi"],
    "Documents": [".pdf", ".docx", ".txt"],
}


def scan_for_duplicates(root_path, allowed_exts, include_others, progress_cb=None, stop_callback=None):
    files_map = defaultdict(list)
    EXCLUDED_DIRS = ["$RECYCLE.BIN", "System Volume Information", "Lib"]

    for root, dirs, files in os.walk(root_path):
        if stop_callback():
            return {}

        dirs[:] = [d for d in dirs
            if d not in EXCLUDED_DIRS
            and not d.startswith(".")
        ]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if allowed_exts and ext not in allowed_exts and not include_others:
                continue
            path = os.path.join(root, f)
            try:
                size = os.path.getsize(path)
                files_map[(f, size)].append(path)
            except Exception:
                continue


    hash_map = defaultdict(list)
    candidates = [v for v in files_map.values() if len(v) > 1]


    for i, group in enumerate(candidates, 1):
        for p in group:
            h = compute_hash(p)
            if h:
                hash_map[(h, os.path.basename(p), os.path.getsize(p))].append(p)
        if progress_cb:
            progress_cb(f"Hashed {i}/{len(candidates)} groups")


    return {k: v for k, v in hash_map.items() if len(v) > 1}