from __future__ import annotations
import hashlib, json, os, ast
from pathlib import Path

CHUNK = 1024 * 1024 * 8  # 8MB streaming chunks

def sha256_file(path: Path) -> str:
    """
    Stream a file and return 'sha256:<hex>'.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return "sha256:" + h.hexdigest()

def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

def canonical_json(obj) -> bytes:
    """
    Canonical JSON for hashing: UTF-8, sorted keys, no whitespace.
    Note: for learning simplicity we leave values as provided (strings/numbers).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def combine_hashes(*ids: str) -> str:
    """
    Combine multiple 'sha256:...' strings deterministically.
    """
    prefix_free = "|".join(ids).encode("utf-8")
    return sha256_bytes(prefix_free)

# ---- Code hashing (ignore whitespace and comments) ----
def code_hash_ast(path: Path) -> str:
    """
    Hash the AST of a Python file (ignores whitespace/comments/formatting).
    This is a simple normalization and not a perfect semantic hash.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    # Dump without attributes to reduce noise
    dumped = ast.dump(tree, annotate_fields=False, include_attributes=False)
    return sha256_bytes(dumped.encode("utf-8"))

# ---- Directory hashing (Merkle-like) ----
def iter_files(root: Path):
    """
    Yield relative file paths (as POSIX strings) under root, sorted.
    Follows symlinks for simplicity; skips non-regular files.
    """
    files = []
    for base, dirs, filenames in os.walk(root, followlinks=True):
        base_p = Path(base)
        for name in filenames:
            fp = base_p / name
            try:
                if not fp.is_file():
                    continue
            except OSError:
                continue
            rel = fp.relative_to(root).as_posix()
            files.append(rel)
    for rel in sorted(files):
        yield rel

def tree_snapshot(root: Path):
    """
    Compute snapshot entries for a directory: list of {path, blob, size}.
    The tree id is sha256 over canonical JSON of [(path, blob_id)].
    """
    entries = []
    pairs = []
    for rel in iter_files(root):
        blob_id = sha256_file(root / rel)
        size = (root / rel).stat().st_size
        entries.append({"path": rel, "blob": blob_id, "size": int(size)})
        pairs.append([rel, blob_id])
    tree_id = sha256_bytes(canonical_json(pairs))
    return tree_id, entries
