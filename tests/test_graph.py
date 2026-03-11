"""Tests for the Adaptive Memory Graph core logic."""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph import (
    Graph,
    Node,
    Connection,
    SessionLog,
    EngagementSignal,
    NewNodeSuggestion,
    ExplicitCorrection,
    DEFAULT_DECAY_RATES,
)
from src.update import apply_decay, update_graph, process_engagement


# ── Node Tests ─────────────────────────────────────────────────────────


def test_node_create():
    node = Node.create(
        title="Test Node",
        domain="health_and_safety",
        summary="A test node",
        content="Full test content",
        tags=["test", "demo"],
    )
    assert node.title == "Test Node"
    assert node.domain == "health_and_safety"
    assert node.weight == 0.5
    assert node.decay_rate == DEFAULT_DECAY_RATES["health_and_safety"]
    assert node.id.startswith("node_")
    assert not node.archived
    assert node.tags == ["test", "demo"]


def test_node_serialization():
    node = Node.create(title="Roundtrip", domain="general", summary="Test")
    node.connections.append(Connection(node_id="node_other", weight=0.7, label="related"))
    d = node.to_dict()
    restored = Node.from_dict(d)
    assert restored.id == node.id
    assert restored.title == "Roundtrip"
    assert len(restored.connections) == 1
    assert restored.connections[0].node_id == "node_other"


def test_node_touch():
    node = Node.create(title="Touch Test", domain="general", summary="Test")
    old_accessed = node.last_accessed
    node.touch()
    assert node.last_accessed >= old_accessed


# ── Graph Tests ────────────────────────────────────────────────────────


def test_graph_add_and_get():
    graph = Graph()
    node = Node.create(title="Graph Node", domain="personal", summary="Test")
    graph.add_node(node)
    assert graph.get_node(node.id) is node
    assert len(graph.get_active_nodes()) == 1


def test_graph_remove():
    graph = Graph()
    node = Node.create(title="To Remove", domain="general", summary="Test")
    graph.add_node(node)
    removed = graph.remove_node(node.id)
    assert removed is node
    assert graph.get_node(node.id) is None


def test_graph_domains():
    graph = Graph()
    graph.add_node(Node.create(title="A", domain="personal", summary="T"))
    graph.add_node(Node.create(title="B", domain="health_and_safety", summary="T"))
    graph.add_node(Node.create(title="C", domain="personal", summary="T"))
    domains = graph.get_domains()
    assert "personal" in domains
    assert "health_and_safety" in domains
    assert len(graph.get_nodes_by_domain("personal")) == 2


def test_graph_connections():
    graph = Graph()
    n1 = Node.create(title="Node 1", domain="general", summary="T")
    n2 = Node.create(title="Node 2", domain="general", summary="T")
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_connection(n1.id, n2.id, 0.8, "related")
    assert len(n1.connections) == 1
    assert n1.connections[0].node_id == n2.id
    assert n1.connections[0].weight == 0.8


def test_graph_serialization():
    graph = Graph()
    graph.add_node(Node.create(title="Serialize Me", domain="general", summary="T"))
    d = graph.to_dict()
    restored = Graph.from_dict(d)
    assert len(restored.nodes) == 1
    assert list(restored.nodes.values())[0].title == "Serialize Me"


# ── Index Tests ────────────────────────────────────────────────────────


def test_index_generation():
    graph = Graph()
    graph.add_node(Node.create(title="HS Node", domain="health_and_safety", summary="T"))
    graph.add_node(Node.create(title="Personal Node", domain="personal", summary="T"))
    index = graph.generate_index()
    assert index["session_context_hint"] is None
    assert len(index["domains"]) == 2


def test_index_with_context():
    graph = Graph()
    n1 = Node.create(title="HS Node", domain="health_and_safety", summary="T")
    n1.weight = 0.9
    graph.add_node(n1)
    n2 = Node.create(title="Personal Node", domain="personal", summary="T")
    n2.weight = 0.3
    graph.add_node(n2)
    index = graph.generate_index(session_context="health_and_safety")
    assert index["session_context_hint"] == "health_and_safety"
    domain_names = [d["domain"] for d in index["domains"]]
    assert "health_and_safety" in domain_names
    # Personal node has low weight so should be filtered out
    assert "personal" not in domain_names


def test_index_excludes_archived():
    graph = Graph()
    n1 = Node.create(title="Active", domain="general", summary="T")
    n2 = Node.create(title="Archived", domain="general", summary="T")
    n2.archived = True
    graph.add_node(n1)
    graph.add_node(n2)
    index = graph.generate_index()
    total_in_index = sum(d["node_count"] for d in index["domains"])
    assert total_in_index == 1


# ── Decay Tests ────────────────────────────────────────────────────────


def test_decay_reduces_weight():
    graph = Graph()
    node = Node.create(title="Decaying", domain="general", summary="T")
    node.weight = 0.5
    node.last_accessed = "2025-01-01T00:00:00+00:00"  # Long ago
    graph.add_node(node)
    apply_decay(graph)
    assert node.weight < 0.5


def test_decay_archives_low_weight():
    graph = Graph()
    node = Node.create(title="Low Weight", domain="general", summary="T")
    node.weight = 0.05
    node.last_accessed = "2025-01-01T00:00:00+00:00"
    graph.add_node(node)
    archived = apply_decay(graph)
    assert archived == 1
    assert node.archived is True


# ── Session Log Tests ──────────────────────────────────────────────────


def test_session_log_serialization():
    log = SessionLog(
        session_id="test_001",
        timestamp="2026-03-10T10:00:00Z",
        interface="text",
        branches_accessed=["node_1"],
        engagement_signals=[
            EngagementSignal(node_id="node_1", signal="positive", note="Good stuff"),
        ],
        new_nodes_suggested=[
            NewNodeSuggestion(title="New Idea", domain="ideas_and_projects", summary="A new idea"),
        ],
    )
    d = log.to_dict()
    restored = SessionLog.from_dict(d)
    assert restored.session_id == "test_001"
    assert len(restored.engagement_signals) == 1
    assert restored.engagement_signals[0].signal == "positive"


# ── Update Graph Tests ─────────────────────────────────────────────────


def test_update_processes_engagement():
    graph = Graph()
    node = Node.create(title="Engaged Node", domain="general", summary="T")
    node.weight = 0.5
    graph.add_node(node)

    log = SessionLog(
        session_id="test_002",
        timestamp="2026-03-10T10:00:00Z",
        interface="text",
        engagement_signals=[
            EngagementSignal(node_id=node.id, signal="positive"),
        ],
    )
    graph.add_session_log(log)
    summary = update_graph(graph)
    assert summary["logs_processed"] == 1
    assert node.weight > 0.5  # Boosted by positive engagement


def test_update_creates_suggested_nodes():
    graph = Graph()
    existing = Node.create(title="Existing", domain="general", summary="T")
    graph.add_node(existing)

    log = SessionLog(
        session_id="test_003",
        timestamp="2026-03-10T10:00:00Z",
        interface="text",
        new_nodes_suggested=[
            NewNodeSuggestion(
                title="Suggested Node",
                domain="ideas_and_projects",
                summary="Auto-created",
                connections_to=[existing.id],
            ),
        ],
    )
    graph.add_session_log(log)
    summary = update_graph(graph)
    assert len(summary["nodes_created"]) == 1
    assert len(graph.nodes) == 2  # existing + new


def test_update_processes_corrections():
    graph = Graph()
    node = Node.create(title="To Correct", domain="general", summary="T")
    node.weight = 0.8
    graph.add_node(node)

    log = SessionLog(
        session_id="test_004",
        timestamp="2026-03-10T10:00:00Z",
        interface="text",
        explicit_corrections=[
            ExplicitCorrection(node_id=node.id, correction="Not relevant", action="archive"),
        ],
    )
    graph.add_session_log(log)
    summary = update_graph(graph)
    assert summary["corrections_applied"] == 1
    assert node.archived is True


if __name__ == "__main__":
    test_funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"  PASS  {func.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {func.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
