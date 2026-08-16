# Model Context Protocol Documentation Snapshot

This folder hosts an offline copy of the full Model Context Protocol (MCP) documentation so agents can work without hitting the public site.

- Source: https://github.com/modelcontextprotocol/modelcontextprotocol
- Commit: f075d163d840afbd925b3668c480aa8a0ab742d1
- Snapshot date: 2025-11-20
- Archive: `model_context_protocol_docs-f075d16-2025-11-20.tar.gz` (contains the repo's entire `docs/` tree, which backs https://modelcontextprotocol.io)

## How to use

1. Extract the archive next to this README when you need the raw files:
   ```bash
   tar -xzf model_context_protocol_docs-f075d16-2025-11-20.tar.gz
   ```
2. The extracted `docs/` directory contains every Mintlify page (MDX) as well as supporting metadata such as `docs.json` and schemas.
3. Open any of the `.mdx` files directly or feed them into your preferred tooling.

For updates, rerun `update_mcp_docs.sh` (optionally passing a commit SHA or tag) to refresh the archive and propagate it across repos.
