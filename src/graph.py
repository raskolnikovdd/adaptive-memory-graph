"""Core graph data model for the Adaptive Memory Graph."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


DEFAULT_DECAY_RATES = {
    "health_and_safety": 0.01,
    "ideas_and_projects": 0.02,
    "personal": 0.015,
    "general": 0.03,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"node_{uuid.uuid4().hex[:12]}"


@dataclass
class Connection:
    node_id: str
    weight: float
    label: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Connection:
        return cls(
            node_id=data["node_id"],
            weight=data["weight"],
            label=data["label"],
        )


@dataclass
class Node:
    id: str
    title: str
    domain: str
    subdomain: str
    summary: str
    content: str
    weight: float
    last_accessed: str
    created: str
    decay_rate: float
    file_links: list[str] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    archived: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["connections"] = [c.to_dict() for c in self.connections]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Node:
        connections = [Connection.from_dict(c) for c in data.get("connections", [])]
        return cls(
            id=data["id"],
            title=data["title"],
            domain=data["domain"],
            subdomain=data.get("subdomain", ""),
            summary=data["summary"],
            content=data.get("content", ""),
            weight=data.get("weight", 0.5),
            last_accessed=data.get("last_accessed", _now()),
            created=data.get("created", _now()),
            decay_rate=data.get("decay_rate", DEFAULT_DECAY_RATES.get(data.get("domain", "general"), 0.03)),
            file_links=data.get("file_links", []),
            connections=connections,
            tags=data.get("tags", []),
            archived=data.get("archived", False),
        )

    @classmethod
    def create(
        cls,
        title: str,
        domain: str,
        summary: str,
        content: str = "",
        subdomain: str = "",
        file_links: list[str] | None = None,
        tags: list[str] | None = None,
        weight: float = 0.5,
    ) -> Node:
        now = _now()
        decay_rate = DEFAULT_DECAY_RATES.get(domain, 0.03)
        return cls(
            id=_new_id(),
            title=title,
            domain=domain,
            subdomain=subdomain,
            summary=summary,
            content=content,
            weight=weight,
            last_accessed=now,
            created=now,
            decay_rate=decay_rate,
            file_links=file_links or [],
            connections=[],
            tags=tags or [],
        )

    def touch(self) -> None:
        self.last_accessed = _now()


@dataclass
class EngagementSignal:
    node_id: str
    signal: str  # "positive", "neutral", "negative"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> EngagementSignal:
        return cls(
            node_id=data["node_id"],
            signal=data["signal"],
            note=data.get("note", ""),
        )


@dataclass
class NewNodeSuggestion:
    title: str
    domain: str
    summary: str
    connections_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NewNodeSuggestion:
        return cls(
            title=data["title"],
            domain=data["domain"],
            summary=data["summary"],
            connections_to=data.get("connections_to", []),
        )


@dataclass
class ExplicitCorrection:
    node_id: str
    correction: str
    action: str = "decay"  # "decay", "archive", "update"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExplicitCorrection:
        return cls(
            node_id=data["node_id"],
            correction=data["correction"],
            action=data.get("action", "decay"),
        )


@dataclass
class SessionLog:
    session_id: str
    timestamp: str
    interface: str  # "text" or "voice"
    branches_accessed: list[str] = field(default_factory=list)
    branches_expanded: list[str] = field(default_factory=list)
    engagement_signals: list[EngagementSignal] = field(default_factory=list)
    new_nodes_suggested: list[NewNodeSuggestion] = field(default_factory=list)
    explicit_corrections: list[ExplicitCorrection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "interface": self.interface,
            "branches_accessed": self.branches_accessed,
            "branches_expanded": self.branches_expanded,
            "engagement_signals": [e.to_dict() for e in self.engagement_signals],
            "new_nodes_suggested": [n.to_dict() for n in self.new_nodes_suggested],
            "explicit_corrections": [c.to_dict() for c in self.explicit_corrections],
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionLog:
        return cls(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            interface=data.get("interface", "text"),
            branches_accessed=data.get("branches_accessed", []),
            branches_expanded=data.get("branches_expanded", []),
            engagement_signals=[EngagementSignal.from_dict(e) for e in data.get("engagement_signals", [])],
            new_nodes_suggested=[NewNodeSuggestion.from_dict(n) for n in data.get("new_nodes_suggested", [])],
            explicit_corrections=[ExplicitCorrection.from_dict(c) for c in data.get("explicit_corrections", [])],
        )


@dataclass
class Graph:
    schema_version: str = "1.0"
    nodes: dict[str, Node] = field(default_factory=dict)
    session_logs: list[SessionLog] = field(default_factory=list)
    pending_logs: list[SessionLog] = field(default_factory=list)
    last_updated: str = field(default_factory=_now)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        self.last_updated = _now()

    def remove_node(self, node_id: str) -> Optional[Node]:
        self.last_updated = _now()
        return self.nodes.pop(node_id, None)

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_active_nodes(self) -> list[Node]:
        return [n for n in self.nodes.values() if not n.archived]

    def get_nodes_by_domain(self, domain: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.domain == domain and not n.archived]

    def get_domains(self) -> list[str]:
        return list({n.domain for n in self.nodes.values() if not n.archived})

    def add_connection(self, from_id: str, to_id: str, weight: float, label: str) -> None:
        from_node = self.nodes.get(from_id)
        to_node = self.nodes.get(to_id)
        if not from_node or not to_node:
            return
        # Update existing or add new
        for conn in from_node.connections:
            if conn.node_id == to_id:
                conn.weight = weight
                conn.label = label
                return
        from_node.connections.append(Connection(node_id=to_id, weight=weight, label=label))
        self.last_updated = _now()

    def add_session_log(self, log: SessionLog) -> None:
        self.pending_logs.append(log)
        self.session_logs.append(log)
        self.last_updated = _now()

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "session_logs": [s.to_dict() for s in self.session_logs],
            "pending_logs": [s.to_dict() for s in self.pending_logs],
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Graph:
        graph = cls(
            schema_version=data.get("schema_version", "1.0"),
            last_updated=data.get("last_updated", _now()),
        )
        for node_data in data.get("nodes", []):
            node = Node.from_dict(node_data)
            graph.nodes[node.id] = node
        graph.session_logs = [SessionLog.from_dict(s) for s in data.get("session_logs", [])]
        graph.pending_logs = [SessionLog.from_dict(s) for s in data.get("pending_logs", [])]
        return graph

    def generate_index(self, session_context: Optional[str] = None, top_n: int = 5) -> dict:
        """Generate the lightweight index that Claude receives at session start."""
        domains: dict[str, list[Node]] = {}
        for node in self.get_active_nodes():
            domains.setdefault(node.domain, []).append(node)

        # Filter by session context if provided
        if session_context:
            # Include the requested domain and any domains with high-weight nodes
            filtered = {}
            for domain, nodes in domains.items():
                if domain == session_context:
                    filtered[domain] = nodes
                else:
                    high_weight = [n for n in nodes if n.weight >= 0.7]
                    if high_weight:
                        filtered[domain] = high_weight
            domains = filtered

        index_domains = []
        for domain, nodes in sorted(domains.items()):
            sorted_nodes = sorted(nodes, key=lambda n: n.weight, reverse=True)[:top_n]
            index_domains.append({
                "domain": domain,
                "node_count": len(nodes),
                "top_nodes": [
                    {"id": n.id, "title": n.title, "weight": round(n.weight, 2)}
                    for n in sorted_nodes
                ],
            })

        return {
            "generated": _now(),
            "session_context_hint": session_context,
            "domains": index_domains,
        }
