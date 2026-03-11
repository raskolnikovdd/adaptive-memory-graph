"""Storage abstraction layer for the Adaptive Memory Graph.

Phase 1: LocalStorageBackend — encrypted JSON file on disk.
Phase 2: APIStorageBackend — REST API to multi-user backend (future).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from .crypto import get_or_create_key, encrypt, decrypt
from .graph import Graph

AMG_DIR = Path.home() / ".amg"
GRAPH_FILE = AMG_DIR / "graph.json.enc"
REPORTS_DIR = AMG_DIR / "reports"


class StorageBackend(ABC):
    @abstractmethod
    def read_graph(self, user_id: str = "default") -> Graph:
        ...

    @abstractmethod
    def write_graph(self, graph: Graph, user_id: str = "default") -> None:
        ...


class LocalStorageBackend(StorageBackend):
    """Encrypted local JSON file storage."""

    def __init__(self, graph_path: Path | None = None):
        self.graph_path = graph_path or GRAPH_FILE
        self._key: bytes | None = None

    def _ensure_dirs(self) -> None:
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_key(self) -> bytes:
        if self._key is None:
            self._key = get_or_create_key()
        return self._key

    def read_graph(self, user_id: str = "default") -> Graph:
        self._ensure_dirs()
        if not self.graph_path.exists():
            return Graph()
        blob = self.graph_path.read_bytes()
        data = decrypt(blob, self._get_key())
        return Graph.from_dict(data)

    def write_graph(self, graph: Graph, user_id: str = "default") -> None:
        self._ensure_dirs()
        data = graph.to_dict()
        blob = encrypt(data, self._get_key())
        # Atomic write: write to temp file then rename
        tmp_path = self.graph_path.with_suffix(".tmp")
        tmp_path.write_bytes(blob)
        tmp_path.rename(self.graph_path)


def get_storage() -> StorageBackend:
    """Return the configured storage backend."""
    return LocalStorageBackend()
