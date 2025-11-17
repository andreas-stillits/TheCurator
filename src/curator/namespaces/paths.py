"""

Module for managing the naming of paths within the Curator system.

"""

from __future__ import annotations
from pathlib import Path

class CuratorPaths:
    """ Class to manage Curator system paths. """

    def __init__(self, storage_root: Path) -> None:
        """ Initialize with the storage root path. """
        self.storage_root = storage_root 
        self.TREASURY = self.storage_root / ".treasury"
        self.ARTIFACTS = self.TREASURY / "artifacts"
        self.COLLECTIONS = self.TREASURY / "collections"
        self.MANIFESTS = self.TREASURY / "manifests"
        self.LOGS = self.TREASURY / "logs"
        self.ALIASES = self.storage_root / "aliases"
        self.VIEWS = self.storage_root / "views"
        self.TMP = self.storage_root / "tmp"

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
            self.TMP,
        ]:
            path.mkdir(parents=True, exist_ok=True)
