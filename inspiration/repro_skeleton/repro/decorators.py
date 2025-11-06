"""
Very small marker decorators so the runner can discover which functions
in a user's step module correspond to load/core/save.
"""
def load(fn):
    fn.__repro_role__ = "load"
    return fn

def core(fn):
    fn.__repro_role__ = "core"
    return fn

def save(fn):
    fn.__repro_role__ = "save"
    return fn
