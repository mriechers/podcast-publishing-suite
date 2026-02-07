# MCP Safety Notes (OpenAI Docs)

**Last Updated**: 2025-12-05  
**Source**: OpenAI MCP documentation (https://platform.openai.com/docs/mcp)

These notes capture safety considerations highlighted in the OpenAI MCP docs, with quick mitigations for building and operating MCP servers or clients.

## Why It Matters
- MCP lets models call tools and read resources across transports; unsafe exposure can lead to data exfiltration, misuse of authority, or model manipulation.
- Hosts may auto-start servers defined in config files, so misconfigured entries can silently grant capabilities.
- Resources are model-visible context; unsafe or unreviewed content can steer outputs (prompt injection, leakage).

## Primary Risk Areas
- **Tool authority**: Destructive or high-impact tools (file writes, package installs, network mutations) can cause damage if granted broadly. Prefer read-only defaults; require explicit confirmation for writes or external calls.
- **Resource exposure**: Files, logs, or API responses may contain secrets or PII. Scope roots narrowly, redact sensitive fields, and avoid exposing tokens in plain text.
- **Prompt injection/data poisoning**: Untrusted resources (web pages, issue bodies) can instruct the model to take unintended actions. Sanitize inputs and add guardrails in prompts and server responses.
- **Server authenticity**: Remote or third-party servers might lie about capabilities or return manipulated content. Pin to trusted sources, review configs before enabling, and avoid embedding secrets in server args/env unless required.
- **Transport + network reach**: HTTP transports can be used for SSRF or lateral movement if endpoints are not restricted. Lock allowed outbound hosts and prefer localhost transports for sensitive data.
- **File system safety**: Tools that accept paths can be abused for traversal. Normalize and enforce allowed roots; reject absolute paths outside declared roots.
- **Denial of service**: Large resources or unbounded tool calls can exhaust context or system resources. Add size caps, rate limits, and timeouts.

## Mitigations and Good Practices
- **Capability minimization**: Expose only the resources/roots required; separate read and write tools; default to read-only.
- **Confirmation + logging**: Require human confirmation for high-risk tools; log tool invocations and resource reads for auditability.
- **Validation**: Schema-validate tool inputs; clamp parameters (paths, URLs, counts); reject ambiguous or empty arguments.
- **Content hygiene**: Strip secrets before returning resources; add warning headers to untrusted content; chunk large responses with clear metadata.
- **Config hygiene**: Treat MCP config files as sensitive; review before launching hosts; avoid storing API keys inline—use env vars or secret managers.
- **Isolation**: Run servers with the least privilege (limited FS access, separate service accounts); prefer local loopback; disable unnecessary network egress.
- **Testing**: Dry-run tools, add unit tests around argument validation, and exercise error paths; use inspector tools to verify capability exposure.

## Operational Checklist (quick)
- Roots scoped to the minimum needed paths; traversal prevented.
- High-risk tools require confirmation and are rate-limited/time-bounded.
- Resources redacted for secrets/PII; size capped before return.
- MCP configs reviewed; servers pinned to trusted code; environment secrets stored out-of-band.
- Logs captured for tool calls and resource fetches; alerts on failures or unexpected capability changes.
