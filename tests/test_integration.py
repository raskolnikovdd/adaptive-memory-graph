"""Integration tests — exercise the full plugin API through actual function calls."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph import Graph, Node
from src.storage import LocalStorageBackend
from src.crypto import encrypt, decrypt, NONCE_LENGTH


def test_crypto_roundtrip():
    """Test encrypt/decrypt without touching Keychain."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = AESGCM.generate_key(bit_length=256)
    data = {"test": "hello", "nodes": [1, 2, 3]}
    blob = encrypt(data, key)
    assert len(blob) > NONCE_LENGTH
    result = decrypt(blob, key)
    assert result == data


def test_storage_roundtrip():
    """Test full storage write/read cycle with a temp file."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = AESGCM.generate_key(bit_length=256)

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph.json.enc"
        backend = LocalStorageBackend(graph_path=graph_path)
        backend._key = key  # Bypass Keychain for testing

        # Write a graph
        graph = Graph()
        node = Node.create(
            title="Test Node",
            domain="health_and_safety",
            summary="Integration test node",
            content="Full content for testing.",
            tags=["test", "integration"],
        )
        graph.add_node(node)
        backend.write_graph(graph)

        # Read it back
        loaded = backend.read_graph()
        assert len(loaded.nodes) == 1
        loaded_node = list(loaded.nodes.values())[0]
        assert loaded_node.title == "Test Node"
        assert loaded_node.content == "Full content for testing."
        assert loaded_node.tags == ["test", "integration"]


def test_full_workflow():
    """Test the complete workflow: create graph, add nodes, generate index, update."""
    from src.update import update_graph
    from src.graph import SessionLog, EngagementSignal, NewNodeSuggestion

    graph = Graph()

    # Add some nodes across domains
    n1 = Node.create(title="Confined Space — Site C", domain="health_and_safety",
                     summary="Confined space work at Site C", weight=0.85)
    n2 = Node.create(title="AI Construction Talk", domain="ideas_and_projects",
                     summary="Talk about AI in construction", weight=0.90)
    n3 = Node.create(title="Family", domain="personal",
                     summary="Family information", weight=0.60)
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)

    # Create connections
    graph.add_connection(n1.id, n2.id, 0.5, "related_project")

    # Generate index
    index = graph.generate_index()
    assert len(index["domains"]) == 3

    # Generate scoped index
    hs_index = graph.generate_index(session_context="health_and_safety")
    domain_names = [d["domain"] for d in hs_index["domains"]]
    assert "health_and_safety" in domain_names

    # Log a session
    log = SessionLog(
        session_id="int_test_001",
        timestamp="2026-03-10T10:00:00Z",
        interface="text",
        branches_accessed=[n1.id, n2.id],
        branches_expanded=[n2.id],
        engagement_signals=[
            EngagementSignal(node_id=n2.id, signal="positive", note="User engaged deeply"),
            EngagementSignal(node_id=n1.id, signal="neutral"),
        ],
        new_nodes_suggested=[
            NewNodeSuggestion(
                title="AMG Plugin Project",
                domain="ideas_and_projects",
                summary="Building the memory graph plugin",
                connections_to=[n2.id],
            ),
        ],
    )
    graph.add_session_log(log)

    # Run update
    summary = update_graph(graph)
    assert summary["logs_processed"] == 1
    assert len(summary["nodes_created"]) == 1
    assert len(graph.nodes) == 4  # 3 original + 1 suggested

    # Verify the new node was created and connected
    new_id = summary["nodes_created"][0]
    new_node = graph.get_node(new_id)
    assert new_node.title == "AMG Plugin Project"
    assert len(new_node.connections) == 1

    # Verify engagement boosted n2
    assert n2.weight > 0.90

    print("Full workflow test PASSED")


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
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
