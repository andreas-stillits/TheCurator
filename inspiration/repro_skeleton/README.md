# repro-skeleton (stdlib-only)

A small, heavily-commented, stdlib-first skeleton that turns any Python script
into a reproducible, content-addressed step with manifests and lineage.

## Install / Run locally (no dependencies)

```bash
# No install needed; just run the module in-place
python -m repro --help
```

## Store layout

By default a `.repro_store/` folder is created in your CWD:

```
.repro_store/
  blobs/sha256/<fanout>/...     # file blobs
  trees/sha256/<fanout>/...     # directory snapshots (JSON)
  manifests/sha256/<fanout>/... # run manifests
  aliases/...                   # aliases (plain text files)
  tmp/...                       # temp working paths
```

You can override the location with `REPRO_STORE=/some/path` or `--store` in CLI.

## Writing a step

Create a file `step_example.py` (or see `examples/step_example.py`) with three
decorated functions:

```python
from repro import load, core, save, RunContext

DEFAULTS = {"suffix": "!!!"}  # optional

@load
def load_inputs(ctx: RunContext):
    data = ctx.open_input("text", "r").read()
    return {"text": data}

@core
def core_logic(ctx: RunContext, inputs):
    return {"text": inputs["text"].upper() + ctx.params.get("suffix","")}

@save
def save_outputs(ctx: RunContext, results):
    out_dir = ctx.output_dir / "result_dir"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "out.txt").write_text(results["text"], encoding="utf-8")
```

## Running a step

Prepare an input file and adopt it (optional), or pass with '@' to adopt on the fly:

```bash
echo "hello" > /tmp/hello.txt

# Run with inline adoption. The logical input name is 'text' (used in load_inputs).
python -m repro run examples/step_example.py --in text=@/tmp/hello.txt --param suffix="!!!"
# prints the run_id (sha256:...)
```

Materialize outputs of that run:

```bash
python -m repro manifest view <run_id> --into ./artifacts
tree ./artifacts
# artifacts/
#   result_dir/
#     out.txt
```

## Parameters (precedence)

Parameters follow **CLI > ENV > config > defaults**. Environment variables are
discovered using an uppercased key with the prefix `REPRO_PARAM_` by default.

Example:

```bash
export REPRO_PARAM_SUFFIX="??"
python -m repro run examples/step_example.py --in text=@/tmp/hello.txt
# suffix comes from ENV
```

To use a config file, pass `-c config.toml` (top-level flat keys).

## Aliases

```bash
# Set alias to a run
python -m repro run examples/step_example.py --in text=@/tmp/hello.txt --alias runs/demo
python -m repro alias get runs/demo
# -> run:sha256:...

# Adopt and alias a directory
python -m repro adopt ./some_dir --alias data/some_dir
python -m repro alias get data/some_dir
# -> tree:sha256:...
```

## Who built / Trace

```bash
# Given a typed id (blob:sha256:... or tree:sha256:...), find producer run
python -m repro who-built blob:sha256:deadbeef...

# Trace back to adopted sources
python -m repro trace tree:sha256:deadbeef...
```

## Notes & limits

- Code hash uses the Python AST of the step file, ignoring whitespace/comments.
- Directories are hashed as a Merkle-like snapshot of file paths + file content hashes.
- The skeleton is filesystem-only for lineage queries (scans manifests) and keeps
  an intentionally simple contract so you can study and extend it.
- Link preference for materialization and views is: symlink > hardlink > copy.
- Package capture is opt-in via `--capture-packages`.
- No Git awareness or non-file connectors in v1 (by design).
```
