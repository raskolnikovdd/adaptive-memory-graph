"""Schema migration for AMG graph version 1.0.

This is the initial schema — no migration needed, but the file
establishes the pattern for future migrations.
"""

from __future__ import annotations


def migrate(data: dict) -> dict:
    """Ensure a graph dict conforms to v1.0 schema."""
    data.setdefault("schema_version", "1.0")
    data.setdefault("nodes", [])
    data.setdefault("session_logs", [])
    data.setdefault("pending_logs", [])

    # Ensure each node has all required fields
    for node in data["nodes"]:
        node.setdefault("subdomain", "")
        node.setdefault("content", "")
        node.setdefault("weight", 0.5)
        node.setdefault("decay_rate", 0.03)
        node.setdefault("file_links", [])
        node.setdefault("connections", [])
        node.setdefault("tags", [])
        node.setdefault("archived", False)

    return data


MIGRATIONS = {
    "1.0": migrate,
}


def apply_migrations(data: dict, target_version: str = "1.0") -> dict:
    """Apply sequential migrations to bring data to target version."""
    current = data.get("schema_version", "1.0")
    if current == target_version:
        return MIGRATIONS[target_version](data)
    # For future versions, chain migrations here
    return MIGRATIONS[target_version](data)
