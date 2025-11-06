#!/usr/bin/env python3
from __future__ import annotations

"""
aggregate_view.py  —  Build a by-sample view from multiple runs (stdlib-only)

This is a stand-alone helper that understands the on-disk layout of the
repro skeleton's store (blobs/trees/manifests/aliases) and creates a
human-readable directory structure like:

DEST/
  <sample_id>/
    <logical_output_1>
    <logical_output_2>/...
  <sample_id_2>/
    ...

You can choose a flat layout (default) or group outputs under a run subdir.
It links files with preference: symlink > hardlink > copy (same as the skeleton).

USAGE EXAMPLES
--------------
# 1) Using a JSON mapping (sample -> run/alias)
# samples.json:
# {
#   "sampleA": "run:sha256:...",
#   "sampleB": "runs/clean_latest"  # alias name stored in store/aliases
# }
python aggregate_view.py \
  --store .repro_store \
  --into ./artifacts/by-sample \
  --map-file samples.json \
  --select "*"

# 2) Direct --map entries (repeatable)
python aggregate_view.py \
  --store .repro_store \
  --into ./artifacts/by-sample \
  --map sampleA=run:sha256:abc... \
  --map sampleB=runs/clean_latest \
  --select "result_dir/**"

# 3) Group under run subfolders to avoid name clashes
python aggregate_view.py \
  --store .repro_store \
  --into ./artifacts/by-sample \
  --map-file samples.json \
  --layout by-run

MAPPING VALUES
--------------
- "run:sha256:..."  -> exact run id
- "sha256:..."      -> treated as a run id
- "alias:<name>"    -> resolve via store/aliases/<name>
- "<name>"          -> same as alias:<name>

SELECT PATTERNS
---------------
Use --select with glob(s) over logical output names.
- For file outputs: match the logical name exactly (e.g., 'out.csv' or 'result_*')
- For directory outputs (trees): a pattern ending with '/**' means 'include the whole dir'
  and otherwise we treat the directory as a whole object.
If no --select is given, all outputs are included.

LAYOUT
------
- flat (default):   DEST/<sample>/<logical_output_name>
- by-run:           DEST/<sample>/<run_short>/<logical_output_name>
"""

import json, os, shutil, argparse, fnmatch
from pathlib import Path

def prefer_link(src: Path, dst: Path) -> str:
    """Try symlink > hardlink > copy. Returns the method used."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    try:
        os.symlink(src, dst)
        return "symlink"
    except Exception:
        pass
    try:
        if src.is_dir():
            raise OSError("hardlink-dir-not-supported")
        os.link(src, dst)
        return "hardlink"
    except Exception:
        pass
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return "copy"

def _store_paths(store: Path):
    return {
        "blobs": store / "blobs" / "sha256",
        "trees": store / "trees" / "sha256",
        "manifests": store / "manifests" / "sha256",
        "aliases": store / "aliases",
    }

def _manifest_file_for_run(store: Path, run_id: str) -> Path:
    assert run_id.startswith("sha256:"), "run_id must be sha256:..."
    fan = run_id.split(':', 1)[1]
    return _store_paths(store)["manifests"] / fan[:2] / (fan + ".json")

def _read_manifest(store: Path, run_id: str) -> dict:
    p = _manifest_file_for_run(store, run_id)
    return json.loads(p.read_text(encoding="utf-8"))

def _blob_path(store: Path, blob_id: str) -> Path:
    assert blob_id.startswith("sha256:"), "blob id must be sha256:..."
    fan = blob_id.split(':', 1)[1]
    return _store_paths(store)["blobs"] / fan[:2] / fan

def _read_tree(store: Path, tree_typed_id: str) -> dict:
    assert tree_typed_id.startswith("tree:sha256:"), "expected typed tree id"
    digest = tree_typed_id.split(':', 2)[2]
    p = _store_paths(store)["trees"] / digest[:2] / digest
    return json.loads(p.read_text(encoding="utf-8"))

def _resolve_alias(store: Path, name: str) -> str | None:
    p = _store_paths(store)["aliases"] / name
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip()

def _resolve_run_identifier(store: Path, value: str) -> str:
    """Return a bare run_id "sha256:..." from a variety of hints."""
    if value.startswith("run:sha256:"):
        return value.split(':', 1)[1]
    if value.startswith("sha256:"):
        return value
    if value.startswith("alias:"):
        target = _resolve_alias(store, value.split(':', 1)[1])
        if not target:
            raise SystemExit(f'Alias not found: {value}')
        return _resolve_run_identifier(store, target)
    target = _resolve_alias(store, value)
    if not target:
        raise SystemExit(f'Alias not found: {value}')
    return _resolve_run_identifier(store, target)

def _iter_selected_outputs(manifest: dict, selects: list[str] | None):
    """Yield (logical_name, type, id) for outputs matching the selection patterns."""
    outs = manifest.get('outputs', [])
    if not selects:
        for o in outs:
            yield o['logical_name'], o['type'], o['id']
        return
    for o in outs:
        name = o['logical_name']
        for pat in selects:
            if pat.endswith('/**'):
                base = pat[:-3]
                if fnmatch.fnmatch(name, base):
                    yield name, o['type'], o['id']
                    break
            else:
                if fnmatch.fnmatch(name, pat):
                    yield name, o['type'], o['id']
                    break

def _short_run(run_id: str, n: int = 12) -> str:
    return run_id.split(':', 1)[1][:n]

def aggregate(store: Path, mapping: dict[str, str], dest: Path, selects: list[str] | None,
              layout: str = 'flat', clear: bool = False) -> None:
    if clear and dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    for sample, ref in mapping.items():
        run_id = _resolve_run_identifier(store, ref)
        m = _read_manifest(store, run_id)

        # destination base for this sample
        if layout == 'by-run':
            base = dest / sample / _short_run(run_id)
        else:
            base = dest / sample
        base.mkdir(parents=True, exist_ok=True)

        # place outputs
        for name, typ, _id in _iter_selected_outputs(m, selects):
            target = base / name
            if typ == 'file':
                src = _blob_path(store, 'sha256:' + _id)
                prefer_link(src, target)
            elif typ == 'dir':
                target.mkdir(parents=True, exist_ok=True)
                tree = _read_tree(store, 'tree:sha256:' + _id)
                for e in tree['entries']:
                    src = _blob_path(store, e['blob'])
                    out = target / e['path']
                    out.parent.mkdir(parents=True, exist_ok=True)
                    prefer_link(src, out)
            else:
                raise SystemExit(f'Unknown output type: {typ}')

def _parse_map_args(items: list[str]) -> dict[str, str]:
    out = {}
    for it in items or []:
        if '=' not in it:
            raise SystemExit(f"--map expects sample=run_or_alias, got: {it!r}")
        k, v = it.split('=', 1)
        out[k] = v
    return out

def _load_map_file(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise SystemExit(f'Map file not found: {p}')
    if p.suffix.lower() == '.json':
        data = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise SystemExit('JSON map must be an object {sample: run_or_alias}')
        return {str(k): str(v) for k, v in data.items()}
    elif p.suffix.lower() in {'.csv', '.tsv'}:
        import csv
        delim = ',' if p.suffix.lower() == '.csv' else '\t'
        res = {}
        with open(p, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f, delimiter=delim):
                res[row['sample']] = row['run']
        return res
    else:
        raise SystemExit('Unsupported map file format (use .json, .csv, or .tsv)')

def main(argv=None):
    ap = argparse.ArgumentParser(description='Build a by-sample aggregate view from multiple runs')
    ap.add_argument('--store', default='.repro_store', help='Path to repro store (default: .repro_store)')
    ap.add_argument('--into', required=True, help='Destination directory to create/overwrite')
    ap.add_argument('--map', action='append', default=[], help="Mapping 'sample=run_or_alias' (repeatable)")
    ap.add_argument('--map-file', default=None, help='JSON/CSV/TSV mapping file')
    ap.add_argument('--select', action='append', default=[], help='Glob over logical output names (repeatable). If omitted, include all.')
    ap.add_argument('--layout', choices=['flat','by-run'], default='flat', help='Directory layout (default: flat)')
    ap.add_argument('--clear', action='store_true', help='Delete destination directory before writing')
    args = ap.parse_args(argv)

    store = Path(args.store).resolve()
    dest = Path(args.into).resolve()

    # merge mapping sources (map-file < map) so explicit flags win
    mapping = _load_map_file(args.map_file)
    mapping.update(_parse_map_args(args.map))

    if not mapping:
        raise SystemExit('No samples provided. Use --map or --map-file.')

    aggregate(store, mapping, dest, args.select or None, layout=args.layout, clear=args.clear)
    print(str(dest))

if __name__ == '__main__':
    main()