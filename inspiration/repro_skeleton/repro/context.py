from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class RunContext:
    """
    Simple container passed to user functions.
    - run_dir: working folder for this run (contains 'in' and 'out')
    - input_dir: where inputs are materialized
    - output_dir: where user writes outputs; top-level items are collected as outputs
    - params: dict of effective parameters
    - env: minimal environment summary dictionary
    """
    run_dir: Path
    input_dir: Path
    output_dir: Path
    params: dict
    env: dict

    def output_path(self, logical_name: str) -> Path:
        """
        Helper: return a path inside output_dir for the given logical name.
        Creates parents as needed.
        """
        p = self.output_dir / logical_name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def open_input(self, logical_name: str, mode: str = "rb"):
        """
        Helper: open a file inside input_dir by logical name.
        """
        return open(self.input_dir / logical_name, mode)

    def input_path(self, logical_name: str) -> Path:
        """
        Helper: return a path inside input_dir for the given logical name.
        Useful for directory inputs.
        """
        return self.input_dir / logical_name
