"""

Module for managing the naming of paths within the Curator system.

NB: the term "storage_root" must be used in settings.toml

"""

from __future__ import annotations
from pathlib import Path

STORAGE_ROOT_NAME = "storage_root"
SETTINGS_PATH = Path( "./settings.toml")


class CuratorPaths:
    """ Class to manage Curator system paths. """

    def __init__(self, storage_root: Path | None = None, settings_path: Path | None = None) -> None:
        """ Initialize with the storage root path. """
        self.settings_path = settings_path if settings_path is not None else SETTINGS_PATH
        self.storage_root = storage_root 
        if self.storage_root is None:
            # derive from settings.toml 
            try:
                import tomllib
            except Exception:
                raise ImportError("tomllib is required to read settings.toml (default in Python >= 3.11)")
            with open(self.settings_path, "rb") as settings_file:
                settings = tomllib.load(settings_file)
            storage_root_str = settings.get("paths", {}).get(STORAGE_ROOT_NAME, ".") # if not found, use current directory "." as default
            self.storage_root = Path(storage_root_str).expanduser().resolve()

        self.TREASURY = self.storage_root / ".treasury"
        self.ARTIFACTS = self.TREASURY / "artifacts"
        self.COLLECTIONS = self.TREASURY / "collections"
        self.MANIFESTS = self.TREASURY / "manifests"
        self.LOGS = self.TREASURY / "logs"
        self.ALIASES = self.TREASURY / "aliases"
        self.VIEWS = self.TREASURY / "views"

    def ensure_existence(self) -> None:
        """ Ensure all necessary directories exist. """
        for path in [
            self.TREASURY,
            self.ARTIFACTS,
            self.COLLECTIONS,
            self.MANIFESTS,
            self.LOGS,
            self.ALIASES,
            self.VIEWS,
        ]:
            path.mkdir(parents=True, exist_ok=True)

