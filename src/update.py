"""Weight update, decay, and pruning logic for the AMG."""

from __future__ import annotations

from datetime import datetime, timezone

from .graph import Graph, Node, SessionLog, Connection

ARCHIVE_THRESHOLD = 0.10

ENGAGEMENT_WEIGHT_DELTAS = {
    "positive": 0.05,
    "neutral": 0.0,
    "negative": -0.10,
}

CORRECTION_ACTIONS = {
    "decay": -0.20,
    "archive": None,  # handled specially
    "update": 0.0,
}


def _days_since(iso_timestamp: str) -> float:
    """Calculate days elapsed since the given ISO timestamp."""
    then = datetime.fromisoformat(iso_timestamp)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max((now - then).total_seconds() / 86400.0, 0.0)


def apply_decay(graph: Graph) -> int:
    """Apply time-based decay to all active nodes. Returns count of newly archived nodes."""
    archived_count = 0
    for node in list(graph.nodes.values()):
        if node.archived:
            continue
        days = _days_since(node.last_accessed)
        if days > 0:
            node.weight = node.weight * ((1 - node.decay_rate) ** days)
        if node.weight < ARCHIVE_THRESHOLD:
            node.archived = True
            archived_count += 1
    return archived_count


def process_engagement(graph: Graph, log: SessionLog) -> None:
    """Process engagement signals from a session log to adjust node weights."""
    # Boost accessed nodes slightly (they were relevant enough to access)
    for node_id in log.branches_accessed:
        node = graph.get_node(node_id)
        if node:
            node.touch()

    # Expanded nodes get a bigger relevance bump
    for node_id in log.branches_expanded:
        node = graph.get_node(node_id)
        if node:
            node.weight = min(1.0, node.weight + 0.02)
            node.touch()

    # Apply engagement signals
    for signal in log.engagement_signals:
        node = graph.get_node(signal.node_id)
        if node:
            delta = ENGAGEMENT_WEIGHT_DELTAS.get(signal.signal, 0.0)
            node.weight = max(0.0, min(1.0, node.weight + delta))
            node.touch()


def process_corrections(graph: Graph, log: SessionLog) -> None:
    """Process explicit corrections from a session log."""
    for correction in log.explicit_corrections:
        node = graph.get_node(correction.node_id)
        if not node:
            continue
        if correction.action == "archive":
            node.archived = True
        else:
            delta = CORRECTION_ACTIONS.get(correction.action, 0.0)
            node.weight = max(0.0, min(1.0, node.weight + delta))


def process_new_node_suggestions(graph: Graph, log: SessionLog) -> list[str]:
    """Create new nodes from session suggestions. Returns list of created node IDs."""
    created = []
    for suggestion in log.new_nodes_suggested:
        node = Node.create(
            title=suggestion.title,
            domain=suggestion.domain,
            summary=suggestion.summary,
        )
        graph.add_node(node)
        # Create connections to specified nodes
        for target_id in suggestion.connections_to:
            if graph.get_node(target_id):
                graph.add_connection(node.id, target_id, 0.5, "suggested_link")
                graph.add_connection(target_id, node.id, 0.5, "suggested_link")
        created.append(node.id)
    return created


def update_graph(graph: Graph) -> dict:
    """Process all pending session logs, apply decay, and prune.

    Returns a summary of changes made.
    """
    summary = {
        "logs_processed": 0,
        "nodes_created": [],
        "nodes_archived": 0,
        "engagement_updates": 0,
        "corrections_applied": 0,
    }

    # Process pending session logs
    for log in graph.pending_logs:
        process_engagement(graph, log)
        summary["engagement_updates"] += len(log.engagement_signals)

        process_corrections(graph, log)
        summary["corrections_applied"] += len(log.explicit_corrections)

        created = process_new_node_suggestions(graph, log)
        summary["nodes_created"].extend(created)

        summary["logs_processed"] += 1

    # Clear pending logs after processing
    graph.pending_logs.clear()

    # Apply decay to all nodes
    summary["nodes_archived"] = apply_decay(graph)

    return summary
