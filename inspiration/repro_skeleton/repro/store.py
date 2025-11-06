from __future__ import annotations
from pathlib import Path
import os, json, tempfile, shutil, time
from .hashing import sha256_file, sha256_bytes, canonical_json, tree_snapshot

"""
Content Addressed Storage (CAS) and simple layout:

store/
  blobs/sha256/ab/abcdef...     # file blobs
  trees/sha256/ab/abcdef...     # JSON snapshot for directories
  manifests/sha256/..           # run manifests (JSON)
  aliases/                      # alias files (text with 'blob:...' or 'tree:...' or 'run:...')
"""

def default_store_path() -> Path:
    # Allow override via environment, else .repro_store in cwd
    p = os.environ.get("REPRO_STORE", ".repro_store")
    return Path(p).resolve()

def ensure_layout(store: Path) -> None:
    (store / "blobs/sha256").mkdir(parents=True, exist_ok=True)
    (store / "trees/sha256").mkdir(parents=True, exist_ok=True)
    (store / "manifests/sha256").mkdir(parents=True, exist_ok=True)
    (store / "aliases").mkdir(parents=True, exist_ok=True)
    (store / "tmp").mkdir(parents=True, exist_ok=True)

def _fanout_dir(store: Path, kind: str, digest_hex: str) -> Path:
    return store / f"{kind}/sha256" / digest_hex[:2] / digest_hex[2:]

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp-" + str(time.time_ns()))
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

# ---- Blobs (files) ----
def commit_blob(store: Path, src: Path) -> str:
    """
    Copy/commit a file into CAS under blobs/ by its sha256 id.
    Returns id like 'sha256:abcdef...'.
    """
    blob_id = sha256_file(src)
    digest_hex = blob_id.split(":", 1)[1]
    dst = _fanout_dir(store, "blobs", digest_hex)
    if dst.exists():
        return blob_id
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically: copy to tmp then rename
    tmp = dst.with_suffix(".tmp")
    with open(src, "rb") as fsrc, open(tmp, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=1024 * 1024 * 8)
        fdst.flush()
        os.fsync(fdst.fileno())
    os.replace(tmp, dst)
    return blob_id

def blob_path(store: Path, blob_id: str) -> Path:
    assert blob_id.startswith("sha256:"), "blob id must be 'sha256:...'"
    digest_hex = blob_id.split(":", 1)[1]
    return _fanout_dir(store, "blobs", digest_hex)

# ---- Trees (directories) ----
def commit_tree(store: Path, src_dir: Path):
    """
    Commit a directory snapshot. Each file becomes a blob; the tree is a JSON snapshot.
    Returns ('tree:sha256:...', entries)
    """
    tree_id, entries = tree_snapshot(src_dir)
    digest_hex = tree_id.split(":", 1)[1]
    tree_file = _fanout_dir(store, "trees", digest_hex)
    if not tree_file.exists():
        # Ensure all blobs exist first
        for e in entries:
            commit_blob(store, src_dir / e["path"])
        data = {"version": 1, "entries": entries}
        _atomic_write_bytes(tree_file, json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return "tree:" + tree_id, entries

def read_tree(store: Path, tree_typed_id: str):
    """
    Read the tree JSON and return {'version':1,'entries':[...]}.
    """
    prefix = "tree:sha256:"
    assert tree_typed_id.startswith(prefix), "expected typed tree id"
    digest_hex = tree_typed_id[len(prefix):]
    p = _fanout_dir(store, "trees", digest_hex)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data

# ---- Manifests ----
def manifest_path(store: Path, run_id: str) -> Path:
    assert run_id.startswith("sha256:"), "run_id must be 'sha256:...'"
    digest_hex = run_id.split(":", 1)[1]
    return _fanout_dir(store, "manifests", digest_hex).with_suffix(".json")

def write_manifest(store: Path, run_id: str, manifest: dict) -> None:
    p = manifest_path(store, run_id)
    _atomic_write_bytes(p, json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))

def load_manifest(store: Path, run_id: str) -> dict:
    p = manifest_path(store, run_id)
    return json.loads(p.read_text(encoding="utf-8"))

# ---- Aliases ----
def alias_path(store: Path, name: str) -> Path:
    return (store / "aliases" / name).resolve()

def alias_set(store: Path, name: str, target: str) -> None:
    p = alias_path(store, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(p, (target + "\n").encode("utf-8"))

def alias_get(store: Path, name: str) -> str | None:
    p = alias_path(store, name)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip()
