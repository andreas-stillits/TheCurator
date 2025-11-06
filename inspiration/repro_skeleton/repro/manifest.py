from __future__ import annotations
import json, platform, sys, os, datetime
from typing import Dict, List

def utc_now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def minimal_env_summary(capture_packages: bool = False) -> dict:
    """
    Minimal environment summary. Package capture is optional (off by default).
    """
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "env_vars": {k: os.environ.get(k, "") for k in ["TZ", "LANG", "LC_ALL", "PYTHONHASHSEED"]},
    }
    if capture_packages:
        try:
            import importlib.metadata as im
            pkgs = [{"name": d.metadata["Name"], "version": d.version} for d in im.distributions()]
            env["packages"] = sorted(pkgs, key=lambda x: x["name"].lower())
        except Exception:
            env["packages_error"] = "failed_to_capture"
    return env

def input_list_from_map(d: Dict[str, dict]) -> List[dict]:
    """
    Convert inputs dict {name: {type,id,size,origin}} to a sorted list for manifest.
    """
    items = []
    for name, v in d.items():
        item = {"logical_name": name}
        item.update(v)
        items.append(item)
    # Sort by logical_name for readability
    return sorted(items, key=lambda x: x["logical_name"])

def outputs_from_dir_scan(scan: dict) -> list:
    """
    Convert outputs scan {name: {...}} to sorted list.
    """
    items = []
    for name, v in scan.items():
        item = {"logical_name": name}
        item.update(v)
        items.append(item)
    return sorted(items, key=lambda x: x["logical_name"])
