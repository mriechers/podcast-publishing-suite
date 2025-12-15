# Anthropic Agent SDK - Executive Summary

Generated: 2025-12-02
Source: `/Users/mriechers/Developer/workspace_ops/knowledge/claude/raw/anthropic_agent_sdk_overview.raw.md` (332KB)
Original URL: https://platform.claude.com/docs/en/agent-sdk/overview

## Overview

The Anthropic Agent SDK provides event-driven infrastructure for building long-running Claude agents with tool integration, session management, and cost tracking.

## Core Architecture

### Event-Driven Model
- **System Events**: Tool availability, configuration, MCP server lifecycle
- **User Events**: Messages, tool results, user interactions
- **Agent Events**: Responses, tool calls, intermediate states
- Clear separation between system-level and user-level operations

### Session Management
- **State Tracking**: Maintains conversation context across turns
- **Compaction**: Automatic or manual context summarization
- **Persistence**: Save/restore sessions for long-running workflows
- **Cost Accounting**: Per-session token usage and API cost tracking

### Tool Integration
- **Native Tools**: Built-in capabilities (code execution, file operations)
- **Custom Tools**: User-defined functions via Python decorators
- **MCP Tools**: Model Context Protocol server integration
- **Tool Chaining**: Sequential tool use with intermediate results

## MCP Integration

### MCP Server Support
- **Local Servers**: Connect to MCP servers on localhost
- **Remote Servers**: Access cloud-hosted MCP services
- **Discovery**: Automatic tool enumeration from MCP servers
- **Lifecycle**: Server startup, shutdown, reconnection handling

### Tool Registration
- Tools exposed via MCP automatically available to Claude
- Slash commands from MCP servers become agent commands
- Prompts from MCP servers inject into system context
- Resource access (files, databases) via MCP resource providers

### Configuration
```python
from anthropic import Agent

agent = Agent(
    mcp_servers=[
        {"name": "browser", "command": "npx", "args": ["@playwright/mcp"]},
        {"name": "taskdb", "uri": "https://tasks.example.com/mcp"}
    ]
)
```

## Session State and Compaction

### State Management
- **Automatic Compaction**: SDK triggers compaction at token thresholds
- **Manual Compaction**: Developer-controlled summarization
- **State Preservation**: Keep critical context during compaction
- **Incremental Updates**: Append new context efficiently

### Compaction Strategies
1. **Summarization**: Condense conversation history to key points
2. **Selective Retention**: Keep recent messages, compress old ones
3. **Structured State**: Maintain JSON state separately from chat history
4. **Checkpoint/Resume**: Save snapshots for multi-session workflows

## Cost Tracking

### Usage Monitoring
- **Token Counts**: Input, output, cached tokens per turn
- **API Costs**: Dollar amounts based on model pricing
- **Session Totals**: Cumulative usage across all turns
- **Tool Costs**: Separate tracking for expensive tool calls

### Budget Controls
- Set per-session spending limits
- Halt execution when budget exceeded
- Alert on threshold violations
- Export usage data for analysis

## Hosting Guidance

### Development
- Local testing with file-based MCP servers
- Hot reload for rapid iteration
- Debug logging for tool calls and state changes

### Production
- Container deployment (Docker/Kubernetes)
- Environment-based configuration (API keys, MCP endpoints)
- Health checks for MCP server connectivity
- Monitoring for session state size and compaction frequency

### Scaling Considerations
- Stateless design for horizontal scaling
- External session storage (Redis, database)
- MCP server connection pooling
- Rate limiting and backpressure handling

## Workspace Integration Opportunities

### Align with SDK Patterns
- **Session State**: Mirror SDK's session management in our harness scripts
- **Cost Logging**: Implement per-agent cost tracking using SDK methods
- **MCP Registration**: Centralize MCP server config in workspace conventions

### Bootstrap Script Integration
- Reference SDK hosting guidance in `forerunner_setup.sh`
- Include SDK installation in Python environment setup
- Provide MCP server templates for common workspace tools

### Convention Alignment
- **Tool Naming**: Follow SDK conventions for tool definitions
- **Error Handling**: Match SDK patterns for graceful degradation
- **Logging**: Use SDK-compatible log formats

### Testing Infrastructure
- Local MCP server testing before deployment
- Session replay for debugging long-running agents
- Cost analysis for different prompt strategies

## Key Takeaways

1. **Event-Driven**: All interactions flow through event handlers
2. **MCP-First**: Prefer MCP servers over custom tool implementations
3. **State Management**: Explicit compaction is essential for long sessions
4. **Cost Awareness**: Track usage proactively, not retroactively
5. **Hosting Ready**: SDK designed for production deployment

## References

- Full document: `raw/anthropic_agent_sdk_overview.raw.md`
- Related: `claude_4_summary.md` - Prompting best practices
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/mcp_overview.md` - MCP protocol details
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/agents/long_running_agents_summary.md` - Harness patterns
