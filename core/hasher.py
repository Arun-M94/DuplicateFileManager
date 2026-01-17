import hashlib


CHUNK_SIZE = 8192




def compute_hash(path, algo='sha256'):
    h = hashlib.new(algo)
    try:
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
                return h.hexdigest()
    except Exception:
        return None