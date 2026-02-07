# Model Context Protocol (MCP) Resources

This directory contains documentation and resources for the Model Context Protocol, which enables tool integration and resource access for Claude agents.

## Contents

### Documentation Files

**mcp_overview.md** (16KB)
- Protocol fundamentals and architecture
- Client-server model
- Tool, prompt, and resource capabilities
- Transport mechanisms (stdio, HTTP)

**mcp_safety_notes.md** (4KB)
- Safety risks from OpenAI MCP docs
- Authority limits and scoping practices
- Prompt-injection and resource hygiene mitigations
- Operational checklist for secure deployments

**mcp_workspace_applications.md** (28KB)
- Workspace-specific MCP server ideas
- Repository health monitoring
- Convention validation
- Documentation search and retrieval
- Task management integration

**docs/model_context_protocol_docs-*.tar.gz** (16MB)
- Complete protocol specification
- TypeScript/Python SDK documentation
- Server implementation examples

**docs_archive/openai_mcp_docs_2025-12-05.md** (27KB)
- Raw capture of OpenAI MCP guide via jina.ai mirror
- Building remote servers and connectors
- Risks/safety guidance and example FastMCP server

## Key Concepts

### MCP Architecture
- **Client**: Claude or other LLM requesting capabilities
- **Server**: Provides tools, prompts, or resources
- **Transport**: stdio (local) or HTTP (remote)
- **Lifecycle**: Initialize → capabilities exchange → requests → shutdown

### Capability Types

**Tools**
- Functions Claude can call
- Defined with JSON schema for parameters
- Return structured results
- Examples: file operations, API calls, database queries

**Prompts**
- Reusable prompt templates
- Inject context into conversations
- Dynamic arguments
- Examples: code review templates, analysis frameworks

**Resources**
- Read-only data access
- File contents, database records, API responses
- URI-based addressing
- Examples: repository files, configuration data

### Transport Mechanisms

**Stdio (Local Servers)**
- Server runs as subprocess
- Bidirectional communication via stdin/stdout
- Launched on-demand by client
- Ideal for development and local tools

**HTTP (Remote Servers)**
- Server runs as web service
- RESTful API over HTTPS
- Always-available, shareable
- Ideal for production and team tools

## Workspace MCP Servers

### Existing Servers

**claude-chat-export**
- Location: `/Users/mriechers/Developer/workspace_ops/mcp-servers/claude-chat-export/`
- Purpose: Search personal Claude conversation history
- Tools: search_conversations, get_conversation
- Resources: Conversation transcripts

### Potential Workspace Servers

**repository-health**
- Monitor all repos in workspace manifest
- Check branch sync, uncommitted changes, stale repos
- Provide health metrics for Librarian

**convention-validator**
- Verify CLAUDE.md compliance
- Check agent attribution in commits
- Validate git hook setup

**documentation-search**
- Index all workspace documentation
- Semantic search across conventions, READMEs, knowledge base
- Return relevant snippets with context

**task-manager**
- Feature list management (feature_list.json)
- Progress log aggregation
- Task dependency tracking

## MCP in Agent Workflows

### Tool Integration
Agents automatically get access to MCP tools:
```python
# MCP server provides these tools
agent.tools = [
    "search_repositories",
    "validate_conventions",
    "get_health_report"
]
```

### Resource Access
Agents can read data via MCP resources:
```
mcp://repo-health/workspace_ops/status
mcp://docs/conventions/COMMIT_CONVENTIONS.md
mcp://tasks/feature_list.json
```

### Prompt Templates
MCP servers provide reusable prompts:
```
# Code review prompt from MCP
Use template: mcp://prompts/code_review
With context: {file_path, changes}
```

## Development Workflow

### Creating MCP Server
1. Choose transport (stdio for local, HTTP for remote)
2. Define capabilities (tools/prompts/resources)
3. Implement server using SDK
4. Test with MCP Inspector tool
5. Register in Claude config

### Testing MCP Server
```bash
# Use MCP Inspector
npx @modelcontextprotocol/inspector path/to/server

# Test with curl (HTTP servers)
curl http://localhost:3000/mcp/v1/tools
```

### Registering in Workspace
Add to Claude config or environment:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "node",
      "args": ["path/to/server.js"]
    }
  }
}
```

## Best Practices

### Server Design
- Single responsibility per server
- Clear tool/resource naming
- Comprehensive error handling
- Rate limiting for expensive operations
- Logging for debugging

### Security
- Validate all inputs
- Sandbox dangerous operations
- Use authentication for HTTP servers
- Limit file system access scope
- Never expose credentials

### Performance
- Cache expensive computations
- Stream large responses
- Implement timeouts
- Handle concurrent requests
- Monitor resource usage

## Related Resources

- `/Users/mriechers/Developer/workspace_ops/knowledge/claude/agent_sdk_summary.md` - SDK MCP integration
- `/Users/mriechers/Developer/workspace_ops/mcp-servers/` - Workspace MCP server implementations
- Official MCP docs: https://modelcontextprotocol.io

## Adding New Content

When adding MCP resources:
1. Official spec updates: Extract to `docs/`
2. Workspace applications: Add to `mcp_workspace_applications.md`
3. Server implementations: Place in `/mcp-servers/` directory
4. Cross-reference with agent patterns that use MCP
