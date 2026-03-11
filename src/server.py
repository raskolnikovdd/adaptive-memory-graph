"""MCP server for the Adaptive Memory Graph plugin.

Exposes graph operations as tools that Claude can call during conversations.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .graph import (
    Graph,
    Node,
    SessionLog,
    EngagementSignal,
    NewNodeSuggestion,
    ExplicitCorrection,
    _now,
)
from .storage import get_storage, REPORTS_DIR
from .update import update_graph as _update_graph

mcp = FastMCP(
    "adaptive-memory-graph",
    instructions="Intelligent persistent memory graph for Claude. "
    "Provides weighted, interconnected knowledge nodes that evolve "
    "through conversation. Use amg_load_index at session start for "
    "background awareness, amg_expand_branch when context warrants it, "
    "and amg_log_session silently at conversation end.",
)

_storage = get_storage()


def _load() -> Graph:
    return _storage.read_graph()


def _save(graph: Graph) -> None:
    _storage.write_graph(graph)


# ── Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def amg_load_index(session_context: str | None = None) -> str:
    """Load the lightweight memory graph index at session start.

    Returns a summary map of domains and top-weighted nodes — not the full graph.
    Use this at the start of every conversation for background awareness.

    Args:
        session_context: Optional domain filter (e.g. "health_and_safety")
            to focus the index on relevant domains.
    """
    graph = _load()
    index = graph.generate_index(session_context=session_context)
    return json.dumps(index, indent=2)


@mcp.tool()
def amg_expand_branch(node_id: str) -> str:
    """Fetch the full content of a memory node when contextually relevant.

    Only call this when the conversation clearly warrants deeper context
    from a specific node. Updates the node's last_accessed timestamp.

    Args:
        node_id: The ID of the node to expand (from the index).
    """
    graph = _load()
    node = graph.get_node(node_id)
    if not node:
        return json.dumps({"error": f"Node {node_id} not found"})
    node.touch()
    _save(graph)
    return json.dumps(node.to_dict(), indent=2)


@mcp.tool()
def amg_get_connected_nodes(node_id: str, min_weight: float = 0.5) -> str:
    """Get nodes connected to a given node above a minimum weight threshold.

    Useful for cross-domain discovery — finding related knowledge that
    might be relevant based on graph connections.

    Args:
        node_id: The node to find connections from.
        min_weight: Minimum connection weight to include (0.0-1.0).
    """
    graph = _load()
    node = graph.get_node(node_id)
    if not node:
        return json.dumps({"error": f"Node {node_id} not found"})

    connected = []
    for conn in node.connections:
        if conn.weight >= min_weight:
            target = graph.get_node(conn.node_id)
            if target and not target.archived:
                connected.append({
                    "id": target.id,
                    "title": target.title,
                    "domain": target.domain,
                    "summary": target.summary,
                    "weight": round(target.weight, 2),
                    "connection_weight": round(conn.weight, 2),
                    "connection_label": conn.label,
                })

    return json.dumps(connected, indent=2)


@mcp.tool()
def amg_log_session(
    interface: str = "text",
    branches_accessed: str = "[]",
    branches_expanded: str = "[]",
    engagement_signals: str = "[]",
    new_nodes_suggested: str = "[]",
    explicit_corrections: str = "[]",
) -> str:
    """Log session summary at the end of a conversation.

    Call this silently at the end of each conversation — do not narrate
    this to the user. Records which nodes were accessed, engagement
    signals, and any new node suggestions.

    Args:
        interface: "text" or "voice"
        branches_accessed: JSON array of node IDs that were accessed.
        branches_expanded: JSON array of node IDs that were fully expanded.
        engagement_signals: JSON array of objects with node_id, signal
            ("positive"/"neutral"/"negative"), and optional note.
        new_nodes_suggested: JSON array of objects with title, domain,
            summary, and optional connections_to array.
        explicit_corrections: JSON array of objects with node_id,
            correction text, and action ("decay"/"archive"/"update").
    """
    graph = _load()

    session_id = f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    log = SessionLog(
        session_id=session_id,
        timestamp=_now(),
        interface=interface,
        branches_accessed=json.loads(branches_accessed),
        branches_expanded=json.loads(branches_expanded),
        engagement_signals=[
            EngagementSignal.from_dict(s) for s in json.loads(engagement_signals)
        ],
        new_nodes_suggested=[
            NewNodeSuggestion.from_dict(s) for s in json.loads(new_nodes_suggested)
        ],
        explicit_corrections=[
            ExplicitCorrection.from_dict(c) for c in json.loads(explicit_corrections)
        ],
    )

    graph.add_session_log(log)
    _save(graph)

    return json.dumps({"status": "ok", "session_id": session_id})


@mcp.tool()
def amg_update_graph() -> str:
    """Process pending session logs and apply decay to the graph.

    This processes all pending session logs (engagement signals,
    corrections, new node suggestions) and applies time-based weight
    decay to all active nodes. Nodes that fall below 0.10 weight
    are archived.

    Typically called after each session or on a schedule.
    """
    graph = _load()
    summary = _update_graph(graph)
    _save(graph)
    return json.dumps(summary, indent=2)


@mcp.tool()
def amg_export_report(format: str = "markdown") -> str:
    """Generate a human-readable summary of the current graph state.

    Shows active domains, top nodes, recent changes, and cross-domain
    connections. Useful for periodic review of how the memory graph
    is evolving.

    Args:
        format: Output format — currently only "markdown" is supported.
    """
    graph = _load()
    active_nodes = graph.get_active_nodes()
    archived_nodes = [n for n in graph.nodes.values() if n.archived]
    domains = graph.get_domains()

    lines = [
        "# Adaptive Memory Graph — Report",
        f"**Generated:** {_now()}",
        f"**Schema Version:** {graph.schema_version}",
        f"**Total Nodes:** {len(graph.nodes)} ({len(active_nodes)} active, {len(archived_nodes)} archived)",
        f"**Session Logs:** {len(graph.session_logs)}",
        "",
        "---",
        "",
    ]

    # Domain summaries
    for domain in sorted(domains):
        domain_nodes = sorted(
            graph.get_nodes_by_domain(domain),
            key=lambda n: n.weight,
            reverse=True,
        )
        lines.append(f"## {domain.replace('_', ' ').title()}")
        lines.append(f"**Active nodes:** {len(domain_nodes)}")
        lines.append("")
        lines.append("| Node | Weight | Last Accessed | Tags |")
        lines.append("|------|--------|---------------|------|")
        for node in domain_nodes:
            tags = ", ".join(node.tags) if node.tags else "—"
            lines.append(
                f"| {node.title} | {node.weight:.2f} | {node.last_accessed[:10]} | {tags} |"
            )
        lines.append("")

    # Archived nodes
    if archived_nodes:
        lines.append("## Archived Nodes")
        lines.append("")
        for node in archived_nodes:
            lines.append(f"- **{node.title}** ({node.domain}) — weight: {node.weight:.2f}")
        lines.append("")

    # Cross-domain connections
    lines.append("## Cross-Domain Connections")
    lines.append("")
    found_cross = False
    for node in active_nodes:
        for conn in node.connections:
            target = graph.get_node(conn.node_id)
            if target and target.domain != node.domain and not target.archived:
                lines.append(
                    f"- {node.title} ({node.domain}) ↔ {target.title} ({target.domain}) "
                    f"— weight: {conn.weight:.2f}, label: {conn.label}"
                )
                found_cross = True
    if not found_cross:
        lines.append("_No cross-domain connections found._")
    lines.append("")

    report = "\n".join(lines)

    # Save report to file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"graph_report_{datetime.now(timezone.utc).strftime('%Y-%m')}.md"
    report_file.write_text(report, encoding="utf-8")

    return report


@mcp.tool()
def amg_manual_adjust(node_id: str, action: str, value: float | None = None) -> str:
    """Manually adjust a node's weight or status.

    Allows the user to directly control their memory graph.

    Args:
        node_id: The node to adjust.
        action: One of "boost", "decay", "archive", "delete".
        value: Optional weight delta for boost/decay (e.g. 0.1 to boost by 0.1).
            Defaults to 0.1 for boost, -0.1 for decay.
    """
    graph = _load()
    node = graph.get_node(node_id)
    if not node:
        return json.dumps({"error": f"Node {node_id} not found"})

    if action == "boost":
        delta = value if value is not None else 0.1
        node.weight = min(1.0, node.weight + delta)
        node.touch()
        result = {"status": "boosted", "new_weight": round(node.weight, 2)}
    elif action == "decay":
        delta = value if value is not None else 0.1
        node.weight = max(0.0, node.weight - delta)
        result = {"status": "decayed", "new_weight": round(node.weight, 2)}
    elif action == "archive":
        node.archived = True
        result = {"status": "archived"}
    elif action == "delete":
        graph.remove_node(node_id)
        # Clean up connections pointing to deleted node
        for other in graph.nodes.values():
            other.connections = [c for c in other.connections if c.node_id != node_id]
        result = {"status": "deleted"}
    elif action == "unarchive":
        node.archived = False
        node.weight = max(ARCHIVE_THRESHOLD_RESTORE, node.weight)
        node.touch()
        result = {"status": "unarchived", "new_weight": round(node.weight, 2)}
    else:
        return json.dumps({"error": f"Unknown action: {action}. Use boost, decay, archive, delete, or unarchive."})

    _save(graph)
    return json.dumps(result)


ARCHIVE_THRESHOLD_RESTORE = 0.15


@mcp.tool()
def amg_add_node(
    title: str,
    domain: str,
    summary: str,
    content: str = "",
    subdomain: str = "",
    tags: str = "[]",
    file_links: str = "[]",
    weight: float = 0.5,
    connect_to: str = "[]",
) -> str:
    """Manually add a new node to the memory graph.

    Args:
        title: Short title for the node.
        domain: Domain category (e.g. "health_and_safety", "personal", "ideas_and_projects", "general").
        summary: Brief summary used in the lightweight index.
        content: Full detailed content for the node.
        subdomain: Optional subcategory within the domain.
        tags: JSON array of string tags.
        file_links: JSON array of file path strings to link to this node.
        weight: Initial weight (0.0-1.0), defaults to 0.5.
        connect_to: JSON array of objects with node_id, weight, and label
            to create connections to existing nodes.
    """
    graph = _load()

    node = Node.create(
        title=title,
        domain=domain,
        summary=summary,
        content=content,
        subdomain=subdomain,
        tags=json.loads(tags),
        file_links=json.loads(file_links),
        weight=weight,
    )
    graph.add_node(node)

    # Create connections
    for conn_data in json.loads(connect_to):
        target_id = conn_data["node_id"]
        if graph.get_node(target_id):
            graph.add_connection(node.id, target_id, conn_data.get("weight", 0.5), conn_data.get("label", "related"))
            graph.add_connection(target_id, node.id, conn_data.get("weight", 0.5), conn_data.get("label", "related"))

    _save(graph)
    return json.dumps({"status": "created", "node_id": node.id, "title": title})


@mcp.tool()
def amg_search_nodes(query: str, domain: str | None = None, include_archived: bool = False) -> str:
    """Search for nodes by title, summary, tags, or content.

    Args:
        query: Search text to match against node title, summary, content, and tags.
        domain: Optional domain filter.
        include_archived: Whether to include archived nodes in results.
    """
    graph = _load()
    query_lower = query.lower()
    results = []

    for node in graph.nodes.values():
        if not include_archived and node.archived:
            continue
        if domain and node.domain != domain:
            continue

        # Search across title, summary, content, and tags
        searchable = f"{node.title} {node.summary} {node.content} {' '.join(node.tags)}".lower()
        if query_lower in searchable:
            results.append({
                "id": node.id,
                "title": node.title,
                "domain": node.domain,
                "summary": node.summary,
                "weight": round(node.weight, 2),
                "archived": node.archived,
                "tags": node.tags,
            })

    results.sort(key=lambda r: r["weight"], reverse=True)
    return json.dumps(results, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
