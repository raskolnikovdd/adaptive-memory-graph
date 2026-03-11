# Adaptive Memory Graph — Runtime Instructions

This project is an MCP server plugin that provides Claude with persistent, intelligent memory across sessions via a weighted graph of interconnected knowledge nodes.

## Runtime Behaviour

At the start of each conversation, call `amg_load_index()` to receive a lightweight map of the user's memory graph. Use this map as background awareness only — do not reference it unless contextually relevant.

If the conversation touches a domain or topic that clearly warrants deeper context, call `amg_expand_branch()` for the relevant node. Be conservative: only expand when it would genuinely improve your response.

Do not surface personal nodes during professional work sessions, and vice versa, unless explicitly relevant.

At the end of each conversation, call `amg_log_session()` with a summary of which branches were accessed, which were engaged with, and any suggested new nodes. Do this silently — do not narrate this process to the user.

If the user explicitly corrects a memory ("that's not relevant" / "stop bringing that up"), record this as an explicit correction in the session log.

## Available Tools

- `amg_load_index` — Load lightweight index at session start
- `amg_expand_branch` — Fetch full node content when contextually relevant
- `amg_get_connected_nodes` — Find related nodes across domains
- `amg_log_session` — Log session summary at conversation end
- `amg_update_graph` — Process pending logs and apply decay
- `amg_export_report` — Generate human-readable graph summary
- `amg_manual_adjust` — Boost, decay, archive, or delete nodes
- `amg_add_node` — Manually add new nodes to the graph
- `amg_search_nodes` — Search nodes by title, summary, tags, or content

## Project Structure

- `src/graph.py` — Core graph data model (Node, Graph, SessionLog)
- `src/crypto.py` — AES-256-GCM encryption with macOS Keychain key storage
- `src/storage.py` — Storage abstraction (LocalStorageBackend)
- `src/update.py` — Weight update, decay, and pruning logic
- `src/server.py` — MCP server entry point with all tool definitions
- `migrations/v1_0.py` — Schema migration scripts
- `tests/test_graph.py` — Test suite
