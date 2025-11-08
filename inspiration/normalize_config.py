# Save human readible .toml and machine friendly .json
# Normalization should accout for: types (e.g. Path -> str), order, explicit defaults (remove all not step related)
# maybe even fix precision types on floats, ints, etc.

def deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def normalize_config(cfg):
    from pathlib import Path
    import numpy as np
    def norm(x):
        if isinstance(x, dict):
            return {k: norm(x[k]) for k in sorted(x)}   # sort keys
        if isinstance(x, (list, tuple, set)):
            return [norm(i) for i in x]                 # stable sequence
        if isinstance(x, Path):
            return str(x)
        if isinstance(x, (np.integer,)):  return int(x)
        if isinstance(x, (np.floating,)): return float(x)
        return x
    return norm(cfg)

def extract_step_relevant(cfg: dict, step: str) -> dict:
	step_cfg = cfg.get("steps", {}).get(step, {})
	# e.g.	
	return {
		"step": step,
		"step_cfg", step_cfg,
	}

# precedence: CLI > file > defaults
resolved = deep_merge(defaults, file_cfg)
resolved = deep_merge(resolved, cli_cfg)
canonical = normalize_config(resolved)

# Save both:
(Path(run_prov)/"config.toml").write_text(original_toml_text)
(Path(run_prov)/"config.json").write_text(json.dumps(canonical, sort_keys=True, separators=(",",":")))

# --- EXAMPLE CONFIG --- 
# [paths]
# data_root = "./data/"
#
# [globals]
# log_level = "INFO"
# quiet = false 
#
# [steps.name1]
# ...
#
# [steps.name2]
# ...
	 
