from __future__ import annotations
import shutil, os
from pathlib import Path

def prefer_link(src: Path, dst: Path) -> str:
    """
    Try symlink > hardlink > copy. Returns the method used.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    # If destination exists, remove it (simple behavior for skeleton)
    if dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    # Symlink
    try:
        os.symlink(src, dst)
        return "symlink"
    except Exception:
        pass
    # Hardlink
    try:
        if src.is_dir():
            raise OSError("hardlink-dir-not-supported")
        os.link(src, dst)
        return "hardlink"
    except Exception:
        pass
    # Copy (file or directory)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return "copy"
