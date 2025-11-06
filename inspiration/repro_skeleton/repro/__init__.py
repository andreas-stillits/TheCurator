"""
Minimal, stdlib-only skeleton for a reproducible, content-addressed pipeline layer.
See README.md for an overview. This package is intentionally simple for learning.
"""
from .context import RunContext
from .decorators import load, core, save
from .runner import run_step_file
__all__ = ["RunContext", "load", "core", "save", "run_step_file"]
__version__ = "0.1.0-skeleton"
