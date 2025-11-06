from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from .store import default_store_path, ensure_layout, alias_set, alias_get, load_manifest, manifest_path
from .store import commit_blob, commit_tree, blob_path, read_tree
from .runner import run_step_file
from .config import parse_keyval_list, load_config, merge_params
from .hashing import sha256_bytes, canonical_json
from .manifest import minimal_env_summary
from .util import prefer_link

def main(argv=None):
    parser = argparse.ArgumentParser(prog="repro", description="Reproducible CAS pipeline (stdlib skeleton)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run
    p_run = sub.add_parser("run", help="Run a step file")
    p_run.add_argument("step_file", help="Path to step Python file")
    p_run.add_argument("-c", "--config", help="TOML/JSON config file with params", default=None)
    p_run.add_argument("--param", action="append", default=[], help="KEY=VALUE (repeatable)")
    p_run.add_argument("--in", dest="in_kv", action="append", default=[], help="NAME=SPEC (repeatable) where SPEC is '@/path' or 'blob:sha256:..' or 'tree:sha256:..' or 'alias:name'")
    p_run.add_argument("--store", help="Path to repro store (default: .repro_store)", default=None)
    p_run.add_argument("--alias", help="Set alias to this run (e.g., runs/latest_cleaned)")
    p_run.add_argument("--env-prefix", default="REPRO_PARAM_", help="Env prefix for parameters (default: REPRO_PARAM_)")
    p_run.add_argument("--capture-packages", action="store_true", help="Capture installed packages into env summary (opt-in)")

    # adopt
    p_adopt = sub.add_parser("adopt", help="Adopt a file or directory into CAS")
    p_adopt.add_argument("path", help="Path to file or directory")
    p_adopt.add_argument("--alias", help="Create alias pointing to the adopted object")
    p_adopt.add_argument("--store", default=None, help="Path to repro store")

    # manifest show
    p_show = sub.add_parser("manifest", help="Show or view a manifest")
    sub_show = p_show.add_subparsers(dest="mcmd", required=True)
    p_m_show = sub_show.add_parser("show", help="Show manifest JSON")
    p_m_show.add_argument("run_id")
    p_m_view = sub_show.add_parser("view", help="Materialize outputs of a run to a directory")
    p_m_view.add_argument("run_id")
    p_m_view.add_argument("--into", required=True, help="Destination directory to create/overwrite")
    p_m_view.add_argument("--mode", choices=["symlink","hardlink","copy"], default=None,
                          help="Force a mode; default prefers symlink>hardlink>copy")
    p_m_view.add_argument("--store", default=None)

    # alias
    p_alias = sub.add_parser("alias", help="Set/get aliases")
    sub_alias = p_alias.add_subparsers(dest="acmd", required=True)
    p_a_set = sub_alias.add_parser("set")
    p_a_set.add_argument("name")
    p_a_set.add_argument("target", help="Target like 'run:sha256:..' or 'blob:sha256:..' or 'tree:sha256:..'")
    p_a_set.add_argument("--store", default=None)
    p_a_get = sub_alias.add_parser("get")
    p_a_get.add_argument("name")
    p_a_get.add_argument("--store", default=None)

    # who-built
    p_who = sub.add_parser("who-built", help="Find which run produced a blob/tree id")
    p_who.add_argument("typed_id", help="blob:sha256:.. or tree:sha256:..")
    p_who.add_argument("--store", default=None)

    # trace
    p_trace = sub.add_parser("trace", help="Trace lineage of a blob/tree id back to adopted sources")
    p_trace.add_argument("typed_id", help="blob:sha256:.. or tree:sha256:..")
    p_trace.add_argument("--store", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "run":
        store = Path(args.store).resolve() if args.store else default_store_path()
        ensure_layout(store)
        cfg = load_config(args.config)
        defaults = getattr(_load_defaults_from_step(args.step_file), "DEFAULTS", {})
        cli_params = parse_keyval_list(args.param)
        eff, prov = merge_params(defaults, cfg, args.env_prefix, cli_params)
        inputs = parse_keyval_list(getattr(args, "in_kv", []))
        run_id = run_step_file(
            step_path=args.step_file,
            store_path=str(store),
            params_eff=eff,
            params_prov=prov,
            input_specs=inputs,
            capture_packages=args.capture_packages,
            alias=args.alias,
        )
        print(run_id)

    elif args.cmd == "adopt":
        store = Path(args.store).resolve() if args.store else default_store_path()
        ensure_layout(store)
        p = Path(args.path).expanduser().resolve()
        if p.is_dir():
            tree_typed_id, _ = commit_tree(store, p)
            tid = tree_typed_id
        else:
            blob_id = commit_blob(store, p)
            tid = "blob:" + blob_id
        if args.alias:
            alias_set(store, args.alias, tid)
        print(tid)

    elif args.cmd == "manifest":
        store = default_store_path()
        if args.mcmd == "show":
            m = load_manifest(store, args.run_id)
            print(json.dumps(m, indent=2, ensure_ascii=False))
        elif args.mcmd == "view":
            m = load_manifest(store, args.run_id)
            dest = Path(args.into).resolve()
            if dest.exists():
                # overwrite for skeleton simplicity
                import shutil; shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            # For each output, materialize by preferred method
            for o in m.get("outputs", []):
                name = o["logical_name"]
                typ = o["type"]
                if typ == "file":
                    src = blob_path(store, "sha256:" + o["id"])
                    out = dest / name
                    method = prefer_link(src, out) if not args.mode else _force_link(src, out, args.mode)
                elif typ == "dir":
                    # Read and materialize tree
                    data = read_tree(store, "tree:sha256:" + o["id"])
                    outdir = dest / name
                    _materialize_tree(store, data, outdir, args.mode)
            print(str(dest))

    elif args.cmd == "alias":
        store = Path(args.store).resolve() if args.store else default_store_path()
        ensure_layout(store)
        if args.acmd == "set":
            alias_set(store, args.name, args.target)
        elif args.acmd == "get":
            v = alias_get(store, args.name)
            print(v or "")

    elif args.cmd == "who-built":
        store = Path(args.store).resolve() if args.store else default_store_path()
        run_id = _who_built_scan(store, args.typed_id)
        print(run_id or "")

    elif args.cmd == "trace":
        store = Path(args.store).resolve() if args.store else default_store_path()
        for line in _trace_to_sources(store, args.typed_id):
            print(line)

# ---- helpers ----
def _load_defaults_from_step(step_file: str):
    import importlib.util, types
    p = Path(step_file).resolve()
    spec = importlib.util.spec_from_file_location(f"repro_step_{abs(hash(p))}_defaults", p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

def _materialize_tree(store: Path, tree_data: dict, outdir: Path, mode: str | None):
    outdir.mkdir(parents=True, exist_ok=True)
    from .store import blob_path
    from .util import prefer_link
    import shutil
    for e in tree_data["entries"]:
        src = blob_path(store, e["blob"])
        dst = outdir / e["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode is None:
            prefer_link(src, dst)
        elif mode == "symlink":
            import os
            try:
                os.symlink(src, dst)
            except Exception:
                raise SystemExit("Symlinks not supported on this system for the selected mode")
        elif mode == "hardlink":
            import os
            if src.is_dir():
                raise SystemExit("Cannot hardlink a directory entry")
            os.link(src, dst)
        elif mode == "copy":
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

def _force_link(src: Path, dst: Path, mode: str):
    import os, shutil
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        os.symlink(src, dst); return "symlink"
    elif mode == "hardlink":
        if src.is_dir(): raise SystemExit("hardlink-dir-not-supported")
        os.link(src, dst); return "hardlink"
    elif mode == "copy":
        if src.is_dir(): shutil.copytree(src, dst)
        else: shutil.copy2(src, dst)
        return "copy"
    else:
        raise SystemExit("Unknown mode")

def _iter_manifests(store: Path):
    base = store / "manifests/sha256"
    if not base.exists():
        return
    for a in base.iterdir():
        for f in a.iterdir():
            if f.suffix == ".json":
                yield f

def _who_built_scan(store: Path, typed_id: str) -> str | None:
    lookup_id = None
    key = None
    if typed_id.startswith("blob:sha256:"):
        lookup_id = typed_id.split(":",2)[2]; key = "file"
    elif typed_id.startswith("tree:sha256:"):
        lookup_id = typed_id.split(":",2)[2]; key = "dir"
    else:
        raise SystemExit("typed_id must be blob:sha256:.. or tree:sha256:..")
    for mf in _iter_manifests(store):
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            for o in m.get("outputs", []):
                if o.get("type") == key and o.get("id") == lookup_id:
                    return m.get("run_id")
        except Exception:
            continue
    return None

def _trace_to_sources(store: Path, typed_id: str):
    """
    Simple DFS trace back to adopted sources.
    Yields lines of text. For a skeleton we keep output compact.
    """
    seen = set()
    stack = [(typed_id, 0)]
    while stack:
        tid, depth = stack.pop()
        indent = "  " * depth
        yield f"{indent}{tid}"
        if tid in seen:
            continue
        seen.add(tid)
        run_id = _who_built_scan(store, tid)
        if not run_id:
            yield f"{indent}  (no producing run; likely adopted source)"
            continue
        # Load manifest and enqueue its inputs
        from .store import load_manifest
        m = load_manifest(store, run_id)
        for inp in m.get("inputs", []):
            typ = inp["type"]
            child = ("blob:sha256:" if typ=="file" else "tree:sha256:") + inp["id"]
            stack.append((child, depth + 1))

if __name__ == "__main__":
    main()
