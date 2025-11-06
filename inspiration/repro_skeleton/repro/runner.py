from __future__ import annotations
import importlib.util, types, inspect, json, os, tempfile, shutil
from pathlib import Path
from .context import RunContext
from .decorators import load as deco_load, core as deco_core, save as deco_save
from .hashing import code_hash_ast, canonical_json, combine_hashes, sha256_bytes
from .hashing import sha256_file
from .store import default_store_path, ensure_layout, commit_blob, commit_tree, blob_path
from .store import write_manifest, manifest_path, read_tree, alias_get, alias_set
from .manifest import minimal_env_summary, utc_now_iso, input_list_from_map, outputs_from_dir_scan
from .util import prefer_link

# ---- Discover decorated functions in a step module ----
def discover_functions(mod: types.ModuleType):
    load_fn = core_fn = save_fn = None
    for name, obj in vars(mod).items():
        role = getattr(obj, "__repro_role__", None)
        if role == "load": load_fn = obj
        elif role == "core": core_fn = obj
        elif role == "save": save_fn = obj
    if not (load_fn and core_fn and save_fn):
        raise SystemExit("Step module must define three decorated functions: @load, @core, @save")
    return load_fn, core_fn, save_fn

def import_step_module(path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(f"repro_step_{abs(hash(path))}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

# ---- Input spec parsing ----
# Supported sources:
#   '@/path' (file or dir) -> adopt into CAS on the fly
#   'blob:sha256:...'       -> file blob id
#   'tree:sha256:...'       -> directory tree id
#   'alias:name'            -> resolves to typed id string from store/aliases/name
def resolve_input_spec(store: Path, spec: str) -> tuple[str, dict]:
    origin = "derived"
    if spec.startswith("@"):
        # Adopt a path (file or directory) on the fly
        p = Path(spec[1:]).expanduser().resolve()
        if p.is_dir():
            tree_typed_id, _ = commit_tree(store, p)
            return tree_typed_id, {"type": "dir", "id": tree_typed_id.split(":",1)[1], "origin": "adopted"}
        else:
            blob_id = commit_blob(store, p)
            return "blob:" + blob_id, {"type": "file", "id": blob_id.split(":",1)[1], "origin": "adopted"}
    elif spec.startswith("alias:"):
        target = alias_get(store, spec.split(":",1)[1])
        if not target:
            raise SystemExit(f"Alias not found: {spec}")
        return resolve_input_spec(store, target)
    elif spec.startswith("blob:sha256:"):
        return spec, {"type": "file", "id": spec.split(":",2)[2], "origin": origin}
    elif spec.startswith("tree:sha256:"):
        return spec, {"type": "dir", "id": spec.split(":",2)[2], "origin": origin}
    else:
        raise SystemExit(f"Unsupported input spec: {spec!r}")

def materialize_input(store: Path, typed_id: str, dst: Path) -> str:
    """
    Materialize a typed id into path dst.
    Returns the method used ('symlink'|'hardlink'|'copy').
    """
    if typed_id.startswith("blob:sha256:"):
        blob = typed_id.split(":",2)[2]
        src = blob_path(store, "sha256:" + blob)
        return prefer_link(src, dst)
    elif typed_id.startswith("tree:sha256:"):
        data = read_tree(store, typed_id)
        # Create files by linking each blob to the right path
        # We materialize under dst (a directory)
        dst.mkdir(parents=True, exist_ok=True)
        used = None
        for e in data["entries"]:
            src = blob_path(store, e["blob"])
            out = dst / e["path"]
            out.parent.mkdir(parents=True, exist_ok=True)
            used = prefer_link(src, out) if used is None else used or prefer_link(src, out)
        return used or "copy"
    else:
        raise SystemExit(f"Cannot materialize id: {typed_id}")

def scan_outputs_and_commit(store: Path, out_dir: Path) -> dict:
    """
    Scan top-level items under out_dir and commit them.
    Returns mapping {logical_name: {type,id,size,mime?}} (size optional for dirs).
    """
    outputs = {}
    for entry in sorted(out_dir.iterdir() if out_dir.exists() else []):
        name = entry.name
        if entry.is_dir():
            tree_typed_id, entries = commit_tree(store, entry)
            total = sum(int(e.get("size", 0)) for e in entries)
            outputs[name] = {"type":"dir","id": tree_typed_id.split(":",1)[1], "size": int(total)}
        elif entry.is_file():
            blob_id = commit_blob(store, entry)
            size = entry.stat().st_size
            outputs[name] = {"type":"file","id": blob_id.split(":",1)[1], "size": int(size)}
    return outputs

# ---- Main run function ----
def run_step_file(
    step_path: str,
    store_path: str | None,
    params_eff: dict,
    params_prov: dict,
    input_specs: dict[str, str],
    capture_packages: bool = False,
    alias: str | None = None,
) -> str:
    """
    Execute a step file with already-resolved params and input specs.
    Returns the run_id.
    """
    step_path = str(step_path)
    store = Path(store_path).resolve() if store_path else default_store_path()
    ensure_layout(store)

    mod = import_step_module(Path(step_path))
    load_fn, core_fn, save_fn = discover_functions(mod)
    code_h = code_hash_ast(Path(step_path))

    # Resolve and materialize inputs
    # Map logical name -> typed id and manifest entry
    inputs_map = {}
    materialization = {}
    in_temp = Path(tempfile.mkdtemp(prefix="repro_in_"))
    for name, spec in input_specs.items():
        typed_id, entry = resolve_input_spec(store, spec)
        inputs_map[name] = entry
        dst = in_temp / name
        # For directories ensure dst is a dir; for files, a file path
        if typed_id.startswith("tree:"):
            materialize_input(store, typed_id, dst)  # materializes inside dst dir
        else:
            materialize_input(store, typed_id, dst)  # materializes as a file
        materialization[name] = str(dst)

    # Compute input_hash (name + type + id, sorted by name)
    triples = [(n, v["type"], v["id"]) for n, v in sorted(inputs_map.items())]
    from .hashing import canonical_json, sha256_bytes
    input_hash = sha256_bytes(canonical_json(triples))

    # Env fingerprint
    env_summary = minimal_env_summary(capture_packages=capture_packages)
    env_hash = sha256_bytes(canonical_json(env_summary))

    # Params hash
    params_hash = sha256_bytes(canonical_json(params_eff))

    # Run id
    run_id = combine_hashes(code_h, input_hash, params_hash, env_hash)

    # Create run working dir
    run_dir = store / "tmp" / ("run-" + run_id.split(":")[1])
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "in").mkdir(parents=True, exist_ok=True)
    (run_dir / "out").mkdir(parents=True, exist_ok=True)

    # Link materialized inputs into run_dir/in by name
    for name, src in materialization.items():
        src_p = Path(src)
        dst_p = run_dir / "in" / name
        if src_p.is_dir():
            # copytree for simplicity in working dir (inputs are read-only in CAS)
            shutil.copytree(src_p, dst_p)
        else:
            dst_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_p, dst_p)

    # Build context and execute user code
    ctx = RunContext(run_dir=run_dir, input_dir=run_dir/"in", output_dir=run_dir/"out",
                     params=params_eff, env=env_summary)
    loaded = load_fn(ctx)
    results = core_fn(ctx, loaded)
    save_fn(ctx, results)

    # Commit outputs to CAS
    outputs_map = scan_outputs_and_commit(store, ctx.output_dir)

    # Assemble manifest
    manifest = {
        "manifest_version": 1,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "step": {"name": Path(step_path).stem, "path": str(Path(step_path).resolve()), "code_hash": code_h},
        "parameters": {"effective": params_eff, "provenance": params_prov, "hash": params_hash},
        "environment": {"summary": env_summary, "hash": env_hash},
        "inputs": [{"logical_name": n, **v} for n, v in sorted(inputs_map.items())],
        "outputs": [{"logical_name": n, **v} for n, v in sorted(outputs_map.items())],
        "io_summary": {},
        "host": {},
        "tool": {"name":"repro-skeleton","version":"0.1.0"},
    }
    write_manifest(store, run_id, manifest)

    # Optionally set alias to this run
    if alias:
        alias_set(store, alias, "run:" + run_id)

    # Cleanup temp materialization
    try:
        shutil.rmtree(in_temp)
        shutil.rmtree(run_dir)
    except Exception:
        pass

    return run_id
