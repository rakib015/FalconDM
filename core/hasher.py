import os
import hashlib
from typing import Dict, Optional, Callable

def compute_checksums(
    file_path: str,
    algorithms: Optional[list] = None,
    progress_cb: Optional[Callable[[float], None]] = None
) -> Dict[str, str]:
    """Computes MD5, SHA-1, SHA-256 hashes of a file efficiently with progress reporting."""
    if not os.path.isfile(file_path):
        return {}

    algorithms = algorithms or ['md5', 'sha1', 'sha256']
    hashers = {algo: getattr(hashlib, algo)() for algo in algorithms}

    total_size = os.path.getsize(file_path)
    processed = 0
    chunk_size = 128 * 1024  # 128 KB buffer

    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            for h in hashers.values():
                h.update(chunk)
            processed += len(chunk)
            if progress_cb and total_size > 0:
                progress_cb(processed / total_size)

    return {algo: h.hexdigest() for algo, h in hashers.items()}
