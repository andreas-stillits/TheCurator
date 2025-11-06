from __future__ import annotations
from pathlib import Path
import os, json
try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - skeleton only
    tomllib = None

def parse_keyval_list(items: list[str]) -> dict:
    """
    Parse ['k=v', 'x=y'] into {'k':'v','x':'y'}.
    Values are kept as strings in the skeleton for simplicity.
    """
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"Expected KEY=VALUE, got: {it!r}")
        k, v = it.split("=", 1)
        out[k] = v
    return out

def load_config(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Config file not found: {p}")
    if p.suffix.lower() in {".toml", ".tml"}:
        if tomllib is None:
            raise SystemExit("tomllib not available for TOML parsing")
        return tomllib.loads(p.read_text(encoding='utf-8'))
    elif p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    else:
        raise SystemExit("Unsupported config format (use TOML or JSON)")

def merge_params(defaults: dict, config: dict, env_prefix: str, cli: dict):
    """
    Produce effective params and a provenance map per key following:
    CLI > ENV > config > defaults
    - env variables are matched as f'{env_prefix}{KEY.upper()}'
    - config is expected to be a flat dict (skeleton simplicity)
    """
    keys = set(defaults) | set(config) | set(cli)
    eff, prov = {}, {}
    for k in keys:
        env_key = f"{env_prefix}{k.upper()}"
        if k in cli:
            eff[k] = cli[k]; prov[k] = "CLI"
        elif env_key in os.environ:
            eff[k] = os.environ[env_key]; prov[k] = "ENV"
        elif k in config:
            eff[k] = config[k]; prov[k] = "CONFIG"
        else:
            eff[k] = defaults.get(k); prov[k] = "DEFAULT"
    return eff, prov
