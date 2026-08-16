# MCP Applications for workspace_ops

**Last Updated**: 2025-11-19
**Purpose**: Analyze how Model Context Protocol could improve or replace current workspace_ops patterns and methodologies

---

## Executive Summary

The Model Context Protocol (MCP) offers significant opportunities to modernize and simplify workspace_ops patterns, particularly:

1. **Cross-LLM Agent Communication**: MCP provides a standardized way for Claude to work with other LLMs (Codex, Gemini, DeepSeek, etc.)
2. **Simplified Agent Contracts**: Replace custom TypeScript-style contracts with MCP's built-in resource/tool/prompt system
3. **Shared Knowledge Management**: Standardize how agents access and contribute to the knowledge base
4. **Reduced Maintenance**: One protocol instead of custom integration code for each LLM platform
5. **Enhanced Discoverability**: MCP servers self-describe their capabilities, reducing need for manual registry maintenance

---

## Current Architecture Analysis

### Existing Patterns in workspace_ops

#### 1. Agent Cooperation Conventions (`conventions/AGENT_COOPERATION.md`)

**Current Approach**:
- Custom TypeScript-style input/output contracts
- Four cooperation patterns: Sequential, Parallel, Handoff, Review Loop
- Manual context handoff via Task tool prompts
- File-based state sharing (`knowledge/`, `docs/agent-decisions/`, `.agent-state/`)

**Limitations**:
- Only works within Claude Code ecosystem
- Requires manual contract documentation
- No standardized way to invoke non-Claude agents (e.g., Codex)
- Context must be manually serialized into prompts

#### 2. Agent Registry (`conventions/AGENT_REGISTRY.md`)

**Current Approach**:
- Manually maintained markdown file listing all agents
- Tracks capabilities, locations, and when to use each agent
- Agent Registrar periodically scans and updates registry

**Limitations**:
- Manual updates required when agents change
- No runtime discovery mechanism
- Doesn't support agents from other LLM platforms
- Capabilities not queryable programmatically

#### 3. Multi-LLM Platform Support

**Current Approach**:
- Agent Registrar designed to support multiple LLMs (Claude, Codex, DeepSeek)
- Each platform has separate agent directories (`.claude/agents/`, `.codex/agents/`, etc.)
- No actual cross-LLM invocation mechanism

**Limitations**:
- **No way for Claude to invoke a Codex agent** or vice versa
- Each LLM exists in isolation
- No shared tooling or resources
- Duplication of similar agents across platforms

---

## MCP-Based Improvements

### 1. Cross-LLM Agent Communication

**Problem**: Currently, there's no standardized way for Claude to work with Codex or other LLMs.

**MCP Solution**: Each LLM platform can expose its agents as MCP servers.

#### Architecture

```
┌─────────────────────────────────────────────────┐
│         Claude Code (MCP Client)                │
│  - Main Assistant                               │
│  - Native Claude agents                         │
└────┬────────────────┬───────────────────────────┘
     │                │
     │                └────────────────┐
     ▼                                 ▼
┌────────────────┐            ┌──────────────────┐
│  Codex MCP     │            │  DeepSeek MCP    │
│  Server        │            │  Server          │
├────────────────┤            ├──────────────────┤
│ Tools:         │            │ Tools:           │
│ - code_codex   │            │ - deep_reason    │
│ - fix_codex    │            │ - analyze_deep   │
│                │            │                  │
│ Resources:     │            │ Resources:       │
│ - codex_docs   │            │ - model_insights │
│                │            │                  │
│ Prompts:       │            │ Prompts:         │
│ - refactor     │            │ - explain        │
└────────────────┘            └──────────────────┘
```

#### Implementation Example

**Codex MCP Server** (conceptual):
```python
# codex_mcp_server.py
from mcp import Server, Tool, Resource, Prompt

server = Server("codex-agent-server")

@server.tool("generate_code")
async def generate_code(spec: str, language: str) -> str:
    """
    Invoke Codex to generate code from specification.
    Exposed as an MCP tool that Claude can call.
    """
    # Invoke Codex API
    result = await codex_api.generate(spec, language)
    return result.code

@server.resource("codex://best-practices/{language}")
async def get_best_practices(language: str) -> Resource:
    """
    Expose Codex's code style guidelines as resources.
    Claude can read these for context.
    """
    practices = await codex_api.get_best_practices(language)
    return Resource(
        uri=f"codex://best-practices/{language}",
        mimeType="text/markdown",
        text=practices
    )

@server.prompt("code_review")
async def code_review_prompt(file_path: str) -> Prompt:
    """
    Provide a standardized code review template.
    """
    return Prompt(
        name="Codex Code Review",
        description="Review code using Codex's patterns",
        messages=[
            {"role": "user", "content": f"Review {file_path} for..."}
        ]
    )

server.run()
```

**Usage from Claude**:
```typescript
// Claude invokes Codex via MCP
const result = await mcp.invoke_tool("codex-agent-server", "generate_code", {
    spec: "Create a REST API endpoint for user authentication",
    language: "python"
});

// Claude reads Codex's resources
const practices = await mcp.read_resource("codex://best-practices/python");
```

**Benefits**:
- Claude can invoke Codex for code generation tasks
- Codex can invoke Claude for reasoning tasks
- Shared resources across LLM platforms
- Standardized invocation instead of custom integration code

---

### 2. Simplified Agent Contracts

**Problem**: Current agent contracts are custom TypeScript-style schemas documented in markdown.

**MCP Solution**: MCP servers inherently define their contracts via tools, resources, and prompts.

#### Current Contract (AGENT_COOPERATION.md)

```typescript
// Current: Manual contract documentation
{
  "task_description": string,
  "agent_role": string,
  "prior_work": {
    "agent": string,
    "summary": string,
    "artifacts": string[],
    "decisions": object,
    "open_questions": string[]
  },
  // ... more fields
}
```

#### MCP-Based Contract

```python
# MCP: Self-describing contract
@server.tool("process_task")
async def process_task(
    task_description: str,
    prior_work: Optional[PriorWorkContext] = None,
    requirements: List[str] = [],
    constraints: List[str] = []
) -> TaskResult:
    """
    Process a task with optional prior work context.

    Args:
        task_description: What needs to be done
        prior_work: Context from previous agent
        requirements: Must-haves
        constraints: Limitations or boundaries

    Returns:
        TaskResult with summary, artifacts, and next steps
    """
    # Implementation
    pass
```

**MCP Advantages**:
- Contract is in the code, not separate documentation
- Type safety enforced automatically
- Clients can discover contracts at runtime via `tools/list`
- Changes to contract automatically reflected in all clients
- Validation built into the protocol

---

### 3. Enhanced Agent Registry

**Problem**: Manual registry maintenance, no runtime discovery.

**MCP Solution**: Dynamic discovery via MCP server capabilities.

#### MCP-Based Registry

```python
# agent_registry_mcp_server.py
from mcp import Server, Resource

server = Server("agent-registry")

@server.resource("registry://agents")
async def list_agents() -> Resource:
    """
    Dynamically discover all MCP servers (agents) available.
    """
    # Query all connected MCP servers
    servers = await mcp.discover_servers()

    agents = []
    for server in servers:
        # Get server capabilities
        tools = await server.list_tools()
        resources = await server.list_resources()
        prompts = await server.list_prompts()

        agents.append({
            "name": server.name,
            "capabilities": {
                "tools": [t.name for t in tools],
                "resources": [r.uri_template for r in resources],
                "prompts": [p.name for p in prompts]
            },
            "description": server.description,
            "status": "active"  # Based on ping/health check
        })

    return Resource(
        uri="registry://agents",
        mimeType="application/json",
        text=json.dumps(agents, indent=2)
    )

@server.tool("find_agent_for_task")
async def find_agent(task_description: str) -> List[str]:
    """
    Recommend agents based on task description.
    Uses semantic matching against agent capabilities.
    """
    agents = await list_agents()
    # AI-powered matching logic
    matches = semantic_match(task_description, agents)
    return [agent["name"] for agent in matches]
```

**Benefits**:
- Registry updates automatically when agents start/stop
- No manual maintenance required
- Runtime capability discovery
- Semantic search for "which agent can do X?"
- Works across all LLM platforms

---

### 4. Standardized Knowledge Management

**Problem**: Current approach uses file-based knowledge sharing (`knowledge/`, `docs/agent-decisions/`).

**MCP Solution**: Knowledge base as MCP resources with versioning and access control.

#### MCP Knowledge Server

```python
# knowledge_mcp_server.py
from mcp import Server, Resource, Tool

server = Server("workspace-knowledge")

@server.resource("knowledge://{topic}")
async def get_knowledge(topic: str) -> Resource:
    """
    Access knowledge base articles by topic.
    """
    # Read from knowledge/ directory
    file_path = f"/Users/mriechers/Developer/workspace-ops/knowledge/{topic}.md"

    with open(file_path, 'r') as f:
        content = f.read()

    return Resource(
        uri=f"knowledge://{topic}",
        mimeType="text/markdown",
        text=content,
        metadata={
            "last_updated": get_file_mtime(file_path),
            "contributors": get_git_contributors(file_path)
        }
    )

@server.tool("add_knowledge")
async def add_knowledge(
    topic: str,
    content: str,
    tags: List[str] = [],
    agent: str = None
) -> str:
    """
    Add or update knowledge base article.
    Automatically tracked via git with agent attribution.
    """
    file_path = f"knowledge/{topic}.md"

    # Write content
    with open(file_path, 'w') as f:
        f.write(content)

    # Git commit with agent attribution
    await git_commit(
        file_path,
        message=f"docs: Add knowledge article on {topic}\n\n[Agent: {agent}]",
        tags=tags
    )

    return f"Added knowledge article: {topic}"

@server.resource("knowledge://search?q={query}")
async def search_knowledge(query: str) -> Resource:
    """
    Search knowledge base.
    """
    results = await vector_search(query, "knowledge/")

    return Resource(
        uri=f"knowledge://search?q={query}",
        mimeType="application/json",
        text=json.dumps(results)
    )
```

**Usage**:
```python
# Any agent (Claude, Codex, etc.) can access knowledge
practices = await mcp.read_resource("knowledge://mcp_overview")

# Any agent can contribute
await mcp.invoke_tool("workspace-knowledge", "add_knowledge", {
    "topic": "deployment_procedures",
    "content": "...",
    "agent": "obsidian-extension-developer"
})

# Any agent can search
results = await mcp.read_resource("knowledge://search?q=obsidian+api")
```

**Benefits**:
- Unified knowledge access across all LLMs
- Automatic versioning via git
- Agent attribution preserved
- Search capabilities
- Access control (read-only vs. write)

---

### 5. Improved Agent Cooperation Patterns

**Problem**: Sequential, Parallel, Handoff, and Review Loop patterns require manual orchestration.

**MCP Solution**: Standardized workflow composition with explicit dependencies.

#### MCP Workflow Server

```python
# workflow_mcp_server.py
from mcp import Server, Tool

server = Server("agent-workflows")

@server.tool("execute_workflow")
async def execute_workflow(
    workflow_type: str,  # "sequential", "parallel", "handoff", "review_loop"
    agents: List[str],
    task: dict,
    context: dict = {}
) -> dict:
    """
    Execute multi-agent workflow with standardized patterns.
    """
    if workflow_type == "sequential":
        return await sequential_workflow(agents, task, context)
    elif workflow_type == "parallel":
        return await parallel_workflow(agents, task, context)
    elif workflow_type == "handoff":
        return await handoff_workflow(agents, task, context)
    elif workflow_type == "review_loop":
        return await review_loop_workflow(agents, task, context)

async def sequential_workflow(agents, task, context):
    """Sequential: agent1 → agent2 → agent3"""
    result = context

    for agent_name in agents:
        # Invoke agent via MCP
        agent_result = await mcp.invoke_tool(
            agent_name,
            "process_task",
            {
                "task_description": task["description"],
                "prior_work": result,
                "requirements": task.get("requirements", [])
            }
        )

        # Accumulate context for next agent
        result = {
            **result,
            "agent": agent_name,
            "summary": agent_result["summary"],
            "artifacts": result.get("artifacts", []) + agent_result["artifacts"],
            "decisions": {**result.get("decisions", {}), **agent_result["decisions"]}
        }

    return result

async def parallel_workflow(agents, task, context):
    """Parallel: agent1, agent2, agent3 all execute concurrently"""
    # Execute all agents in parallel
    tasks = [
        mcp.invoke_tool(agent, "process_task", {
            "task_description": task["description"],
            "context": context
        })
        for agent in agents
    ]

    results = await asyncio.gather(*tasks)

    # Merge results
    merged = merge_parallel_results(results)
    return merged
```

**Usage from Claude**:
```python
# Execute a sequential workflow
result = await mcp.invoke_tool("agent-workflows", "execute_workflow", {
    "workflow_type": "sequential",
    "agents": [
        "obsidian-docs-curator",  # Claude agent
        "codex-agent-server"      # Codex agent (via MCP)
    ],
    "task": {
        "description": "Research Obsidian API and generate implementation",
        "requirements": ["TypeScript", "Plugin API v1.0"]
    }
})
```

**Benefits**:
- Workflows work across different LLM platforms
- Standardized execution and context passing
- Error handling and retry logic centralized
- Observable workflow execution
- Easy to extend with new patterns

---

## Migration Strategy

### Phase 1: Foundation (Month 1)

**Goal**: Establish MCP infrastructure without breaking existing patterns.

**Tasks**:
1. Create `mcp-servers/` directory in workspace_ops
2. Implement basic MCP servers:
   - `knowledge-server.py` - Expose knowledge/ directory as resources
   - `registry-server.py` - Dynamic agent discovery
3. Configure Claude Desktop to connect to local MCP servers
4. Test resource access from Claude
5. Document MCP setup in workspace_ops/README.md

**Deliverables**:
- Working MCP servers running locally
- Claude can read knowledge base via MCP
- Documentation for adding new servers

**Effort**: 10-15 hours

---

### Phase 2: Cross-LLM Bridge (Month 2)

**Goal**: Enable Claude to invoke Codex (or other LLMs) via MCP.

**Tasks**:
1. Set up Codex API access (if not already configured)
2. Create `codex-mcp-server.py`:
   - Tools for code generation, refactoring, review
   - Resources for Codex documentation and best practices
   - Prompts for common Codex workflows
3. Configure Claude to connect to Codex MCP server
4. Test cross-LLM invocation:
   - Claude invokes Codex for code generation
   - Results returned to Claude via MCP
5. Document usage patterns in workspace_ops/knowledge/

**Deliverables**:
- Claude can invoke Codex via standardized MCP interface
- Example workflows demonstrating cross-LLM cooperation
- Documentation of capabilities and limitations

**Effort**: 15-20 hours

---

### Phase 3: Agent Migration (Month 3-4)

**Goal**: Migrate existing agents to MCP-based contracts.

**Tasks**:
1. Create MCP server templates for common agent patterns
2. Migrate one agent per domain to MCP:
   - `obsidian-extension-developer-mcp-server.py`
   - `home-assistant-guardian-mcp-server.py`
   - `librarian-mcp-server.py`
3. Update agent registry to include MCP capabilities
4. Test existing workflows with MCP-based agents
5. Validate that MCP versions provide same functionality
6. Document migration process for remaining agents

**Deliverables**:
- 3-5 agents running as MCP servers
- Side-by-side comparison (old vs. MCP)
- Migration playbook for other agents

**Effort**: 25-30 hours

---

### Phase 4: Workflow Orchestration (Month 5)

**Goal**: Implement standardized workflow patterns via MCP.

**Tasks**:
1. Create `workflow-mcp-server.py`
2. Implement four cooperation patterns (Sequential, Parallel, Handoff, Review Loop)
3. Create workflow definitions for common scenarios:
   - Documentation → Implementation (Sequential)
   - Multi-domain analysis (Parallel)
   - Safety handoffs (Handoff)
   - Code review cycles (Review Loop)
4. Test workflows with both native Claude and MCP-based agents
5. Monitor and optimize performance

**Deliverables**:
- Workflow orchestration server
- Pre-defined workflows for common tasks
- Performance benchmarks

**Effort**: 20-25 hours

---

### Phase 5: Ecosystem Expansion (Ongoing)

**Goal**: Expand MCP ecosystem and retire legacy patterns.

**Tasks**:
1. Migrate remaining agents to MCP
2. Integrate additional LLM platforms (Gemini, DeepSeek, etc.)
3. Create shared resource pools (documentation, best practices)
4. Develop MCP-based monitoring and analytics
5. Contribute MCP servers back to community
6. Deprecate custom contract system in favor of MCP

**Deliverables**:
- Fully MCP-based agent ecosystem
- Multi-LLM workspace with standardized communication
- Community contributions and feedback

**Effort**: Ongoing maintenance (~5 hours/month)

---

## Comparison: Current vs. MCP-Based

| Aspect | Current Approach | MCP-Based Approach |
|--------|-----------------|-------------------|
| **Cross-LLM Communication** | ❌ Not possible | ✅ Standardized protocol |
| **Agent Contracts** | Manual documentation in markdown | Self-describing via MCP tools |
| **Registry Maintenance** | Manual updates via Agent Registrar | Automatic discovery |
| **Knowledge Access** | File-based, LLM-specific | Unified resources across LLMs |
| **Workflow Orchestration** | Custom patterns per LLM | Standardized workflow server |
| **Discoverability** | Grep agent definitions | Runtime capability query |
| **Versioning** | Git commits on definition files | Protocol versioning |
| **Testing** | Manual invocation | MCP testing tools |
| **Documentation** | Separate markdown files | Inline with code |
| **Extensibility** | Fork and modify agents | Compose MCP servers |
| **Community** | Internal only | Leverage public MCP servers |
| **Maintenance Burden** | High (manual registry, docs) | Low (auto-discovery, self-docs) |

---

## Recommendations

### High Priority

1. **Start with Knowledge Management** (Phase 1)
   - Low risk, high value
   - Immediate benefits for all agents
   - Foundation for future work

2. **Cross-LLM Bridge** (Phase 2)
   - Addresses your specific pain point (Claude ↔ Codex)
   - Demonstrates core MCP value
   - Enables new workflows not possible today

### Medium Priority

3. **Agent Migration** (Phase 3)
   - Gradual migration reduces risk
   - Start with agents that benefit most from cross-LLM
   - Keep existing agents working during transition

4. **Workflow Orchestration** (Phase 4)
   - Builds on migrated agents
   - Standardizes cooperation patterns
   - Reduces custom orchestration code

### Long Term

5. **Full Ecosystem Migration** (Phase 5)
   - Complete when majority of agents migrated
   - Deprecate custom contract system
   - Contribute learnings back to MCP community

---

## Risks and Mitigation

### Risk 1: MCP Maturity
**Risk**: Protocol is young (launched Nov 2024), may have breaking changes.

**Mitigation**:
- Pin to specific MCP SDK versions
- Monitor MCP changelog and community
- Keep legacy system running during transition
- Build abstraction layer for easy migration

### Risk 2: Performance Overhead
**Risk**: MCP adds network/serialization overhead vs. native invocation.

**Mitigation**:
- Run MCP servers locally (stdio transport)
- Benchmark critical paths
- Cache MCP resource reads
- Use streaming for large responses

### Risk 3: Tool Availability
**Risk**: Not all Claude Code tools available in MCP yet.

**Mitigation**:
- Implement hybrid agents (native tools + MCP interface)
- Contribute missing tool types to MCP spec
- Use MCP for coordination, native tools for execution

### Risk 4: Learning Curve
**Risk**: Team needs to learn MCP concepts and implementation.

**Mitigation**:
- Start with simple servers (knowledge, registry)
- Use official MCP templates and examples
- Document workspace-specific patterns
- Gradual migration allows learning in phases

---

## Conclusion

**MCP offers transformative potential for workspace_ops**, particularly in enabling Claude to work seamlessly with other LLMs like Codex. The migration path is clear:

1. ✅ **Immediate value**: Knowledge management and cross-LLM communication
2. ✅ **Medium-term gains**: Simplified agent contracts and automatic registry
3. ✅ **Long-term vision**: Fully standardized, multi-LLM agent ecosystem

**The biggest win** is moving from isolated LLM silos to an interoperable agent mesh where Claude, Codex, Gemini, and future LLMs collaborate via a standard protocol.

**Recommended next step**: Implement Phase 1 (knowledge MCP server) as a proof of concept, then evaluate Phase 2 (Codex bridge) based on results.

---

## Review Notes from Codex (2025-02-14)

1. **Tie MCP rollout into existing operational tracks**: Each migration phase defines new servers and docs but never mentions how they get folded into Forerunner bootstrap runs or Librarian audits. Please extend the phase checklists so new MCP services are added to `forerunner_setup.sh`, `workspace_manifest.yaml`, and the Librarian reports. That ensures fresh machines get the servers automatically and ongoing audits confirm they are still healthy.
2. **Secrets and permissioning for the Codex bridge**: Phase 2 introduces a Codex MCP server but doesn’t specify how API keys or OAuth tokens will be sourced, rotated, and scoped. Document whether secrets live in Keychain, 1Password CLI, or env vars, and describe how MCP transports authenticate requests so credentials never end up in repo history or logs.
3. **Write-governance for the knowledge MCP server**: The sample server writes directly to `knowledge/*.md` and commits immediately, which bypasses human review and risks agents clobbering each other. Consider adding a staging branch, moderation queue, or locking strategy plus pre-commit validation so automated updates still respect Librarian quality standards.
4. **Testing and observability for workflow orchestration**: The workflow server centralizes fan-out/fan-in logic but there’s no requirement for integration tests, logging, or rollback plans. Augment Phase 4 so promotion is blocked until there are synthetic workflow tests, health metrics, and retry/failure-handling policies documented.

---

## Review Notes from Gemini (2025-11-20)

1.  **Explicit Gemini Integration**: The analysis focuses heavily on bridging Claude and Codex. Phase 2 and 5 should explicitly include integrating Gemini agents via MCP. This presents an opportunity to leverage Gemini's distinct capabilities (e.g., advanced reasoning, multi-modal understanding) within the same standardized workflow, creating a truly multi-vendor, multi-capability agent mesh.
2.  **Enhanced Discovery Services**: The proposed `agent-registry` is a good start, but its utility could be amplified. I recommend extending the registry service to also index the specific `tools` and `resources` each agent provides. This would enable a more powerful, dynamic discovery model where an orchestrator can find not just *an* agent, but the *right tool* for a specific sub-task, regardless of which agent hosts it.
3.  **Robust Security Model for Secrets**: The Codex notes rightly point out the need for secrets management. I recommend against using local solutions like Keychain or environment variables for a production-grade system. Instead, the architecture should incorporate a dedicated secrets management service (e.g., HashiCorp Vault, AWS/GCP Secrets Manager). MCP servers should authenticate to this service to fetch API keys and other credentials at runtime, ensuring secrets are never stored on disk and can be centrally managed and rotated.
4.  **Transactional Knowledge Base Updates**: The write-governance point from Codex is critical. To build on it, the `knowledge-mcp-server` should implement a transactional update mechanism. When multiple agents attempt to write to the knowledge base simultaneously, a locking or queueing system (like a Redis-based queue) should be used to prevent race conditions and ensure that updates are applied atomically, preserving data integrity.
5.  **Developer Experience and End-User Impact**: The document is highly technical and agent-focused. I suggest adding a section that outlines the direct benefits and workflow changes for the human developer. How does this MCP-powered ecosystem make their daily work faster, easier, or more powerful? Highlighting the end-user value (e.g., "seamlessly ask a question and get a researched, coded, and tested answer from a team of specialized AI agents") will be crucial for team adoption and buy-in.
