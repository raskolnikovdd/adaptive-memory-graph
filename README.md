# Adaptive Memory Graph

<!-- mcp-name: io.github.raskolnikovdd/adaptive-memory-graph -->

An MCP server plugin that gives Claude persistent, intelligent memory across sessions. It stores knowledge as weighted, interconnected nodes in a graph that evolves through conversation — nodes that get used gain weight, unused ones decay and eventually archive.

Works with **Claude Code** and **Claude Desktop**.

## Features

- **Weighted memory nodes** — Important memories stay prominent; stale ones fade
- **Cross-domain connections** — Link related knowledge across topics
- **Time-based decay** — Graph self-prunes so only relevant memories persist
- **Encrypted storage** — AES-256-GCM encryption with macOS Keychain key storage
- **Session logging** — Tracks which memories were accessed and how they were received
- **Domain organization** — Nodes organized by domain (e.g. health_and_safety, personal, ideas_and_projects)
- **Chat history ingestion** — Review and extract knowledge from past Claude Code sessions

## Installation

```bash
pip install adaptive-memory-graph
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install adaptive-memory-graph
```

## Setup

### Claude Code

```bash
claude mcp add adaptive-memory-graph -s user -- amg-server
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "adaptive-memory-graph": {
      "command": "amg-server"
    }
  }
}
```

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Tools

| Tool | Description |
|------|-------------|
| `amg_load_index` | Load lightweight graph index at session start |
| `amg_expand_branch` | Fetch full node content when contextually relevant |
| `amg_get_connected_nodes` | Find related nodes across domains |
| `amg_log_session` | Log session summary at conversation end |
| `amg_update_graph` | Process pending logs and apply weight decay |
| `amg_export_report` | Generate human-readable graph summary |
| `amg_manual_adjust` | Boost, decay, archive, or delete nodes |
| `amg_add_node` | Add new nodes to the graph |
| `amg_search_nodes` | Search nodes by title, summary, tags, or content |
| `amg_list_chat_sessions` | List available Claude Code chat sessions for review |
| `amg_read_chat_session` | Read a chat session's conversation content |

## How It Works

1. **Session start** — Claude calls `amg_load_index` to get a lightweight summary of your memory graph
2. **During conversation** — If a topic is relevant, Claude expands specific nodes for deeper context
3. **Session end** — Claude silently logs which nodes were accessed and suggests new ones
4. **Between sessions** — Weight decay runs, archiving memories that haven't been useful

Nodes are stored as encrypted JSON on disk (`~/.amg/graph.json.enc`). The encryption key is stored in your macOS Keychain.

## Requirements

- Python 3.10+
- macOS (for Keychain-based encryption key storage)

## License

MIT
