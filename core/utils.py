import os


def human_readable_size(n):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024


def choose_original(paths):
    try:
        sorted_paths = sorted(paths, key=lambda p: (os.path.getctime(p), p))
    except Exception:
        sorted_paths = sorted(paths)
    return sorted_paths[0], sorted_paths[1:]