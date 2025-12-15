# MCP Quick Reference Guide

**Version**: 1.0
**Last Updated**: 2025-12-03
**For**: MCP server developers and integrators

This cheatsheet provides quick answers for common MCP development operations. For comprehensive details, see `mcp_overview.md` or the full specification archive.

---

## Component Types: What to Expose

### Resources (Read-Only Data)
**When to use**: Expose data the AI should read and reference
**Examples**: Files, documentation, API responses, database records

```python
@server.resource("file://{path}")
async def read_file(path: str) -> Resource:
    return Resource(
        uri=f"file://{path}",
        mimeType="text/plain",
        text=read_file_content(path)
    )
```

### Tools (Actions)
**When to use**: Expose operations the AI can execute
**Examples**: API calls, file writes, database queries, service actions

```python
@server.tool("send_email")
async def send_email(to: str, subject: str, body: str) -> str:
    email_service.send(to, subject, body)
    return f"Email sent to {to}"
```

### Prompts (Templates)
**When to use**: Provide reusable instructions or workflows
**Examples**: Code review templates, analysis patterns, multi-step procedures

```python
@server.prompt("code_review")
async def code_review_prompt() -> Prompt:
    return Prompt(
        messages=[
            {"role": "user", "content": "Review this code for:\n1. Security issues\n2. Performance\n3. Best practices"}
        ]
    )
```

### Roots (Scope Boundaries)
**When to use**: Define entry points and navigation boundaries
**Examples**: Project directories, repository roots, database schemas

```python
@server.list_roots()
async def list_roots() -> list[Root]:
    return [
        Root(uri="file:///project1", name="Project 1"),
        Root(uri="file:///project2", name="Project 2")
    ]
```

---

## Server Configuration

### Claude Desktop (macOS)
**Config Location**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "python",
      "args": ["/path/to/your/server.py"],
      "env": {
        "API_KEY": "your-key-here"
      }
    }
  }
}
```

### Claude Desktop (Windows)
**Config Location**: `%APPDATA%/Claude/claude_desktop_config.json`

### Development Server
```json
{
  "mcpServers": {
    "dev-server": {
      "command": "node",
      "args": ["dist/index.js"],
      "cwd": "/path/to/project"
    }
  }
}
```

---

## Common Patterns

### File System Server
```python
from mcp import Server, Resource, Tool

server = Server("filesystem")

@server.resource("file://{path}")
async def read_file(path: str) -> Resource:
    with open(path, 'r') as f:
        return Resource(uri=f"file://{path}", text=f.read())

@server.tool("write_file")
async def write_file(path: str, content: str) -> str:
    with open(path, 'w') as f:
        f.write(content)
    return f"Wrote {len(content)} bytes"
```

### Database Server
```python
@server.resource("db://query/{query_id}")
async def get_query_result(query_id: str) -> Resource:
    result = db.execute_saved_query(query_id)
    return Resource(
        uri=f"db://query/{query_id}",
        mimeType="application/json",
        text=json.dumps(result)
    )

@server.tool("execute_query")
async def execute_query(sql: str) -> str:
    result = db.execute(sql)
    return json.dumps(result)
```

### API Integration Server
```python
@server.tool("api_call")
async def api_call(endpoint: str, method: str, body: dict = None) -> str:
    response = requests.request(method, f"{API_BASE}/{endpoint}", json=body)
    return response.text

@server.resource("api://{endpoint}")
async def get_api_data(endpoint: str) -> Resource:
    data = requests.get(f"{API_BASE}/{endpoint}").json()
    return Resource(uri=f"api://{endpoint}", text=json.dumps(data))
```

### Task Management Server
```python
@server.tool("create_task")
async def create_task(title: str, description: str) -> str:
    task_id = task_db.create(title, description)
    return f"Created task {task_id}"

@server.tool("list_tasks")
async def list_tasks(status: str = "open") -> str:
    tasks = task_db.list(status=status)
    return json.dumps(tasks)

@server.resource("task://{task_id}")
async def get_task(task_id: str) -> Resource:
    task = task_db.get(task_id)
    return Resource(uri=f"task://{task_id}", text=json.dumps(task))
```

---

## Transport Protocols

### stdio (Default, Recommended)
**Use for**: Local servers, command-line tools
**Pros**: Simple, secure, no network exposure
**Cons**: Local only, can't share across network

```python
# Server automatically uses stdio when run directly
server.run()
```

### HTTP + SSE (Server-Sent Events)
**Use for**: Remote servers, web-based clients
**Pros**: Network accessible, standard HTTP
**Cons**: Requires more security consideration

```python
server.run_http(host="localhost", port=8080)
```

---

## Error Handling

### Tool Errors
```python
@server.tool("risky_operation")
async def risky_operation(param: str) -> str:
    try:
        result = perform_operation(param)
        return f"Success: {result}"
    except ValueError as e:
        raise MCPError(f"Invalid parameter: {e}")
    except PermissionError:
        raise MCPError("Permission denied")
```

### Resource Errors
```python
@server.resource("data://{id}")
async def get_data(id: str) -> Resource:
    if not data_exists(id):
        raise ResourceNotFoundError(f"No data with id: {id}")

    return Resource(uri=f"data://{id}", text=load_data(id))
```

---

## Testing

### Manual Testing with MCP Inspector
```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Test your server
mcp-inspector python /path/to/server.py
```

### Unit Testing
```python
import pytest
from your_server import server

@pytest.mark.asyncio
async def test_tool_invocation():
    result = await server.call_tool("create_task", {
        "title": "Test Task",
        "description": "Test description"
    })
    assert "Created task" in result
```

### Integration Testing with Claude Desktop
1. Add server to `claude_desktop_config.json`
2. Restart Claude Desktop
3. Check logs: `~/Library/Logs/Claude/mcp-server-*.log` (macOS)
4. Test with prompts that should trigger your server

---

## Security Best Practices

### 1. Input Validation
```python
@server.tool("delete_file")
async def delete_file(path: str) -> str:
    # Validate path is within allowed directory
    if not is_safe_path(path):
        raise MCPError("Path outside allowed directory")

    os.remove(path)
    return f"Deleted {path}"
```

### 2. Environment Variables for Secrets
```python
import os

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

### 3. Rate Limiting
```python
from functools import lru_cache
import time

@server.tool("expensive_api_call")
@rate_limit(calls=10, period=60)  # 10 calls per minute
async def expensive_api_call(query: str) -> str:
    return await external_api.call(query)
```

### 4. Scope Restrictions
```python
ALLOWED_PATHS = ["/home/user/projects", "/home/user/docs"]

@server.resource("file://{path}")
async def read_file(path: str) -> Resource:
    if not any(path.startswith(p) for p in ALLOWED_PATHS):
        raise MCPError("Access denied")

    return Resource(uri=f"file://{path}", text=read_file(path))
```

---

## Common Issues & Solutions

### Issue: Server not appearing in Claude Desktop
**Solutions**:
1. Check config JSON syntax: `python -m json.tool < claude_desktop_config.json`
2. Verify absolute paths in `command` and `args`
3. Restart Claude Desktop completely
4. Check logs in `~/Library/Logs/Claude/`

### Issue: Server crashes on startup
**Solutions**:
1. Test server independently: `python your_server.py`
2. Check environment variables are set
3. Verify dependencies are installed
4. Review logs for error messages

### Issue: Tools not executing
**Solutions**:
1. Verify tool names match registration
2. Check parameter types match schema
3. Add logging to tool functions
4. Test with MCP Inspector first

### Issue: Resources not loading
**Solutions**:
1. Verify URI patterns match usage
2. Check mimeType is correct
3. Ensure async/await used properly
4. Test resource handlers directly

---

## Performance Tips

### 1. Cache Expensive Operations
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def load_expensive_data(id: str):
    return database.query_complex(id)

@server.resource("data://{id}")
async def get_data(id: str) -> Resource:
    data = load_expensive_data(id)
    return Resource(uri=f"data://{id}", text=data)
```

### 2. Lazy Loading
```python
@server.resource("large_dataset://{id}")
async def get_dataset(id: str) -> Resource:
    # Return metadata first, not full dataset
    metadata = get_dataset_metadata(id)
    return Resource(
        uri=f"large_dataset://{id}",
        text=json.dumps(metadata),
        links=[f"large_dataset://{id}/full"]  # Link to full data
    )
```

### 3. Batch Operations
```python
@server.tool("batch_process")
async def batch_process(items: list[str]) -> str:
    # Process multiple items in one call
    results = await asyncio.gather(*[process_item(i) for i in items])
    return json.dumps(results)
```

---

## Debugging

### Enable Verbose Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

@server.tool("debug_tool")
async def debug_tool(param: str) -> str:
    logging.debug(f"Tool called with: {param}")
    result = process(param)
    logging.debug(f"Result: {result}")
    return result
```

### Log to File
```python
import logging

logging.basicConfig(
    filename='/tmp/mcp_server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### Inspect Messages
```python
@server.on_message
async def log_message(message):
    print(f"Received: {message}")
    # Process message normally
```

---

## Quick Start Checklist

Building a new MCP server? Follow these steps:

- [ ] **1. Choose SDK**: Python or TypeScript
- [ ] **2. Define components**: What resources/tools do you need?
- [ ] **3. Create server**: `Server("your-name")`
- [ ] **4. Implement handlers**: Resources, tools, prompts
- [ ] **5. Add validation**: Input checking, error handling
- [ ] **6. Test locally**: Run server standalone first
- [ ] **7. Test with Inspector**: `mcp-inspector python server.py`
- [ ] **8. Configure Claude**: Add to `claude_desktop_config.json`
- [ ] **9. Integration test**: Try with Claude Desktop
- [ ] **10. Document**: Usage, examples, limitations

---

## Example: Complete Minimal Server

```python
#!/usr/bin/env python3
"""
Minimal MCP Server Example
Exposes a note-taking system via MCP
"""

import json
from mcp import Server, Resource, Tool

# Initialize server
server = Server("notes")

# In-memory storage
notes = {}

@server.resource("note://{note_id}")
async def get_note(note_id: str) -> Resource:
    """Expose notes as resources"""
    if note_id not in notes:
        raise ResourceNotFoundError(f"Note {note_id} not found")

    return Resource(
        uri=f"note://{note_id}",
        mimeType="text/plain",
        text=notes[note_id]
    )

@server.tool("create_note")
async def create_note(content: str) -> str:
    """Create a new note"""
    note_id = str(len(notes) + 1)
    notes[note_id] = content
    return f"Created note {note_id}"

@server.tool("list_notes")
async def list_notes() -> str:
    """List all notes"""
    if not notes:
        return "No notes found"

    return json.dumps({
        "count": len(notes),
        "notes": [{"id": k, "preview": v[:50]} for k, v in notes.items()]
    })

@server.prompt("note_template")
async def note_template() -> Prompt:
    """Provide a note-taking template"""
    return Prompt(
        messages=[{
            "role": "user",
            "content": "Create a structured note with:\n- Title\n- Date\n- Content\n- Tags"
        }]
    )

if __name__ == "__main__":
    server.run()
```

**To use**:
1. Save as `notes_server.py`
2. Add to Claude config:
   ```json
   {
     "mcpServers": {
       "notes": {
         "command": "python",
         "args": ["/path/to/notes_server.py"]
       }
     }
   }
   ```
3. Restart Claude Desktop
4. Ask: "Create a note about MCP servers"

---

## Resources

- **Full Documentation**: `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/mcp_overview.md`
- **Workspace Applications**: `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/mcp_workspace_applications.md`
- **Full Spec Archive**: `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/docs_archive/`
- **Official Site**: https://modelcontextprotocol.io
- **GitHub**: https://github.com/anthropics/mcp

---

**Quick Tips**:
- Start with stdio transport (simpler, more secure)
- Test tools independently before MCP integration
- Use descriptive URIs for resources (`file://`, `db://`, `api://`)
- Log everything during development
- Validate inputs rigorously
- Cache expensive operations
- Document expected behavior and limitations
