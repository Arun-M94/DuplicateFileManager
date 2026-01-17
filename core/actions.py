import os
import shutil
import stat
from core.logger import logger

def delete_file(path: str) -> bool:
    try:
        print(f"duplicate path: {path}")
        if not os.path.exists(path):
            logger.warning(f"File not found: {path}")
            return False

        # Handle read-only files (Windows)
        os.chmod(path, stat.S_IWRITE)

        os.remove(path)
        logger.info(f"Deleted file: {path}")
        return True

    except PermissionError as e:
        logger.exception(f"Permission denied while deleting: {path}")
    except FileNotFoundError:
        logger.warning(f"File already removed: {path}")
    except Exception as e:
        logger.exception(f"Unexpected error deleting file: {path}")

    return False

def safe_delete(paths):
    deleted, errors = [], []
    print(paths)
    for p in paths:
        try:
            # os.remove(p)
            if delete_file(p):
                deleted.append(p)
        except Exception as e:
            errors.append((p, str(e)))
    return deleted, errors


def safe_move(paths, destination):
    os.makedirs(destination, exist_ok=True)
    moved, errors = [], []
    for p in paths:
        try:
            dest = os.path.join(destination, os.path.basename(p))
            if os.path.exists(dest):
                os.remove(dest)
            shutil.move(p, dest)
            moved.append((p, dest))
        except Exception as e:
            errors.append((p, str(e)))
    return moved, errors