# Example step module showing the three-function API.
# This step reads a text file (input 'text'), uppercases it, and writes a directory
# of results with a file 'out.txt' in it.

from repro import load, core, save, RunContext

# Optional defaults for parameters, used by CLI precedence (defaults < config < ENV < CLI)
DEFAULTS = {
    "suffix": "!!!"
}

@load
def load_inputs(ctx: RunContext):
    # Read whole text into memory (simple skeleton)
    data = ctx.open_input("my_input", "r").read()
    return {"my_input": data}

@core
def core_logic(ctx: RunContext, inputs: dict):
    text = inputs["my_input"]
    transformed = (text.upper() + ctx.params.get("suffix", ""))
    return {"my_output": transformed}

@save
def save_outputs(ctx: RunContext, results: dict):
    # Write outputs under ctx.output_dir; top-level items are collected.
    out_dir = ctx.output_dir / "result_dir"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "out.txt", "w", encoding="utf-8") as f:
        f.write(results["my_output"])
