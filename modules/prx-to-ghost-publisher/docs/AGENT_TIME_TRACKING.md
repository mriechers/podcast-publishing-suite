# Agent Time Tracking & Contribution Metrics

## Overview

Tracking AI agent work hours presents unique challenges since agents don't work in "real time" the same way humans do. However, there are several approaches to estimate and track AI contribution for client billing, project management, and transparency.

## The Challenge

**AI agents are not direct human-hour equivalents:**
- Agent may "work" for 30 seconds but accomplish 2 hours of human work
- Agent may iterate through 10 approaches in minutes (would take human hours)
- Token usage doesn't directly correlate to value delivered
- Some tasks are trivial for AI but complex for humans (and vice versa)

**What we can track:**
- ✅ Session duration (wall-clock time)
- ✅ Number of tool calls / operations performed
- ✅ Tokens consumed (input + output)
- ✅ Lines of code written/modified
- ✅ Documents created
- ✅ Tasks completed
- ❌ "Equivalent human hours" (subjective)

## Tracking Approaches

### Approach 1: Session-Based Tracking (Simplest)

Track each AI session as a billable unit:

```markdown
## Agent Sessions Log

| Date | Agent | Duration | Tasks Completed | Deliverables | Bill As |
|------|-------|----------|-----------------|--------------|---------|
| 2025-11-14 | Main Assistant | 2h 15m | Research & Design | Ghost docs, PRX analysis, Architecture doc, 8 scripts | 8 hours |
| 2025-11-15 | Implementation | 45m | Core publisher script | publish_new_episodes.py, tests | 3 hours |
| 2025-11-16 | Testing | 30m | Bug fixes, validation | 12 commits, workflow file | 1.5 hours |
```

**Billing Rationale:**
- **Research session (2h 15m wall time)** = estimate 8 human hours because:
  - Comprehensive API documentation review
  - Competitive analysis of implementation options
  - Detailed design document creation
  - Multiple scripts/tools created
  - Would take human 6-8 hours to produce same quality

**Pros:**
- ✅ Simple to track
- ✅ Easy for client to understand
- ✅ Focuses on value delivered vs. time spent

**Cons:**
- ⚠️ Subjective estimation of "human equivalent"
- ⚠️ May over/under-value AI work

---

### Approach 2: Deliverable-Based Tracking (Recommended)

Track what was delivered, not time spent:

```markdown
## Deliverables Log

### 2025-11-14: Initial Research & Design
**Agent:** Main Assistant
**Wall Time:** 2h 15m

Deliverables:
- [x] Ghost API documentation (8 files, ~62KB)
- [x] PRX feed structure analysis (comprehensive, 15+ pages)
- [x] Automation architecture design (20+ pages, 4 options evaluated)
- [x] Documentation update strategy
- [x] Project summary and handoff guide
- [x] 4 Python scripts for documentation/feed management
- [x] Complete cost analysis and risk assessment

**Estimated Human Effort:** 8-10 hours
**Bill As:** [Client decision - suggest 6-8 hours as fair middle ground]
```

**Billing Formula:**
```
Value = (Complexity + Quality + Completeness) × Market Rate

Example:
- Architecture doc (high complexity, high quality, complete) = 3-4 hours
- Feed analysis (medium complexity, complete) = 2 hours
- Scripts (medium complexity, functional) = 2-3 hours
Total: 7-9 hours (from 2h15m wall time)
```

**Pros:**
- ✅ Focuses on value, not time
- ✅ Easier to justify to client
- ✅ Aligns with output-based work

**Cons:**
- ⚠️ Requires upfront agreement on deliverable values

---

### Approach 3: Hybrid Metrics Tracking (Most Comprehensive)

Track multiple metrics for transparency:

```markdown
## Agent Work Metrics: 2025-11-14 Session

### Session Overview
- **Duration:** 2h 15m (8,100 seconds)
- **Agent:** Main Assistant
- **Model:** Claude Sonnet 4.5
- **Purpose:** Initial research and design

### Resource Consumption
- **Tokens Used:** 57,280 tokens
  - Input: ~20,000 tokens (reading docs, context)
  - Output: ~37,000 tokens (writing docs, code)
- **Cost:** ~$1.72 (at API rates)
- **Tool Calls:** 47 total
  - WebFetch: 5
  - Bash: 18
  - Write: 12
  - Read: 8
  - Edit: 4

### Output Metrics
- **Code Written:** 847 lines (Python)
  - Scripts: 4 new files
  - Tests: 0 (pending)
- **Documentation:** 4,115 lines (Markdown)
  - API docs: 8 files
  - Design docs: 3 files
  - Guides: 2 files
- **Git Operations:**
  - Commits: 1
  - Files changed: 53
  - Insertions: 4,115

### Tasks Completed
1. ✅ Set up Crawl4AI environment
2. ✅ Scraped Ghost documentation (8 sources)
3. ✅ Created Ghost docs update plan
4. ✅ Analyzed PRX feed structure (documented expected structure)
5. ✅ Designed automation architecture (4 options)
6. ✅ Wrote comprehensive project summary
7. ✅ Created handoff documentation
8. ✅ Committed and pushed to feature branch

### Estimated Human Equivalent
**Conservative:** 6 hours (efficiency multiplier: ~2.7x)
**Standard:** 8 hours (efficiency multiplier: ~3.5x)
**Generous:** 10 hours (efficiency multiplier: ~4.4x)

### Recommendation
Bill as: **7-8 hours** (middle ground, accounts for quality and comprehensiveness)
```

**Pros:**
- ✅ Highly transparent
- ✅ Shows value of AI acceleration
- ✅ Data-driven billing justification
- ✅ Useful for improving estimates over time

**Cons:**
- ⚠️ More complex to track
- ⚠️ Clients may not understand all metrics

---

## Automated Tracking Implementation

### Git Commit Metrics (No Code Changes Needed)

Extract metrics from git history:

```bash
#!/bin/bash
# scripts/extract_agent_metrics.sh

echo "Agent Contribution Metrics"
echo "=========================="
echo

# Commits by agent (from commit messages)
echo "Commits per Agent:"
git log --all --format="%an | %s" | grep -i "\[Agent:" | cut -d'[' -f2 | cut -d']' -f1 | sort | uniq -c

# Lines added/removed per agent
echo
echo "Code Changes per Agent:"
git log --all --numstat --format="%an | %s" --author="Claude" | awk '{added+=$1; removed+=$2} END {print "Added:", added, "Removed:", removed}'

# Files created by agents
echo
echo "Files Created by Agents:"
git log --all --diff-filter=A --format="%an | %s" --name-only | grep -A1 "\[Agent:" | grep -v "\[Agent:" | grep -v "^--$" | sort | uniq | wc -l

# Session count
echo
echo "Total Agent Sessions:"
git log --all --format="%s" | grep -i "\[Agent:" | wc -l
```

**Output Example:**
```
Agent Contribution Metrics
==========================

Commits per Agent:
  8 Agent: Main Assistant
  3 Agent: Implementation Agent
  2 Agent: Testing Agent

Code Changes per Agent:
Added: 4115 Removed: 0

Files Created by Agents:
53

Total Agent Sessions:
13
```

---

### Token Usage Tracking (Requires Code Addition)

Add to automation script:

```python
# scripts/publish_new_episodes.py

import time
from datetime import datetime
from pathlib import Path
import json

class AgentMetrics:
    def __init__(self, agent_name="Publisher Agent"):
        self.agent_name = agent_name
        self.start_time = time.time()
        self.metrics = {
            "agent": agent_name,
            "started_at": datetime.utcnow().isoformat(),
            "operations": [],
            "tokens_estimated": 0,  # Rough estimate based on content
            "tasks_completed": [],
        }

    def log_operation(self, operation_type, details=None):
        """Log an operation performed."""
        self.metrics["operations"].append({
            "type": operation_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        })

    def log_task(self, task_name, status="completed"):
        """Log a completed task."""
        self.metrics["tasks_completed"].append({
            "task": task_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        })

    def save(self):
        """Save metrics to file."""
        self.metrics["ended_at"] = datetime.utcnow().isoformat()
        self.metrics["duration_seconds"] = time.time() - self.start_time

        metrics_dir = Path("data/agent_metrics")
        metrics_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        metrics_file = metrics_dir / f"session_{timestamp}.json"

        metrics_file.write_text(json.dumps(self.metrics, indent=2))
        return metrics_file


# Usage in script:
metrics = AgentMetrics("Episode Publisher")

metrics.log_operation("fetch_feed", {"url": feed_url})
# ... do work ...

metrics.log_task("Check for new episodes")
metrics.log_task("Publish 3 episodes")

metrics.save()
```

**Generates:**
```json
{
  "agent": "Episode Publisher",
  "started_at": "2025-11-14T12:00:00.000Z",
  "ended_at": "2025-11-14T12:02:15.000Z",
  "duration_seconds": 135,
  "operations": [
    {
      "type": "fetch_feed",
      "timestamp": "2025-11-14T12:00:05.000Z",
      "details": {"url": "https://f.prxu.org/3329/feed-rss.xml"}
    },
    {
      "type": "create_post",
      "timestamp": "2025-11-14T12:01:30.000Z",
      "details": {"post_id": "abc123", "title": "Episode 5"}
    }
  ],
  "tasks_completed": [
    {"task": "Check for new episodes", "status": "completed", "timestamp": "2025-11-14T12:00:10.000Z"},
    {"task": "Publish 3 episodes", "status": "completed", "timestamp": "2025-11-14T12:02:00.000Z"}
  ]
}
```

---

### Visualization Script

Generate HTML report from metrics:

```python
#!/usr/bin/env python3.11
"""Generate agent contribution report."""

import json
from pathlib import Path
from datetime import datetime

def generate_report():
    metrics_dir = Path("data/agent_metrics")
    if not metrics_dir.exists():
        print("No metrics found")
        return

    sessions = []
    for metrics_file in metrics_dir.glob("session_*.json"):
        sessions.append(json.loads(metrics_file.read_text()))

    # Calculate totals
    total_sessions = len(sessions)
    total_duration = sum(s.get("duration_seconds", 0) for s in sessions)
    total_tasks = sum(len(s.get("tasks_completed", [])) for s in sessions)
    total_operations = sum(len(s.get("operations", [])) for s in sessions)

    # Generate report
    html = f"""
    <html>
    <head><title>Agent Contribution Report</title></head>
    <body>
        <h1>Agent Contribution Report</h1>
        <h2>Summary</h2>
        <ul>
            <li>Total Sessions: {total_sessions}</li>
            <li>Total Runtime: {total_duration/3600:.2f} hours</li>
            <li>Tasks Completed: {total_tasks}</li>
            <li>Operations: {total_operations}</li>
        </ul>

        <h2>Sessions</h2>
        <table border="1">
            <tr>
                <th>Date</th>
                <th>Agent</th>
                <th>Duration</th>
                <th>Tasks</th>
                <th>Operations</th>
            </tr>
    """

    for session in sorted(sessions, key=lambda s: s["started_at"]):
        date = datetime.fromisoformat(session["started_at"]).strftime("%Y-%m-%d %H:%M")
        duration = session.get("duration_seconds", 0)
        html += f"""
            <tr>
                <td>{date}</td>
                <td>{session.get("agent", "Unknown")}</td>
                <td>{duration:.0f}s</td>
                <td>{len(session.get("tasks_completed", []))}</td>
                <td>{len(session.get("operations", []))}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    Path("data/agent_report.html").write_text(html)
    print("✓ Report generated: data/agent_report.html")

if __name__ == "__main__":
    generate_report()
```

---

## Client Communication

### Sample Invoice Line Item

**Option A: Time-Based**
```
AI-Assisted Development (Session 2025-11-14)
  Initial research and design phase
  Duration: 2h 15m wall time
  Deliverables: See attached summary
  Billed as: 7.5 hours @ $[rate]/hr
```

**Option B: Deliverable-Based**
```
Project Setup & Architecture Design
  - Ghost API documentation capture and analysis
  - PRX feed integration research
  - Automation architecture design (4 options evaluated)
  - Implementation planning and cost analysis
  - Knowledge base setup with update procedures

  Fixed price: $[amount] (based on scope, not time)
```

**Option C: Transparent Hybrid**
```
AI-Assisted Development (Main Assistant)
  Date: 2025-11-14
  Session Duration: 2h 15m
  Deliverables Completed: 8/8

  Output:
  - 847 lines of code (4 Python scripts)
  - 4,115 lines of documentation
  - Complete architecture design
  - Cost analysis and implementation plan

  Human-equivalent effort: ~8 hours
  Billed at: 6 hours @ $[rate]/hr

  Note: AI acceleration factor of ~3.5x allows us to deliver
  high-quality work faster while maintaining affordable rates.
```

---

## Recommendations

### For This Project

**Recommended Approach:** Deliverable-Based with Transparency

1. **Track git commits** with `[Agent: Name]` tags (already doing this ✅)
2. **Log major sessions** in a simple markdown file:

```markdown
# Agent Work Log

## Session: 2025-11-14 (Initial Research & Design)
**Agent:** Main Assistant
**Duration:** 2h 15m
**Branch:** claude/build-out-project-015VXWGFN7bW6fy1fEE5n7gc
**Commit:** f0391fd

### Deliverables
- Ghost API documentation (8 files)
- PRX feed analysis
- Automation architecture design
- GitHub org handoff guide
- Feed access solutions documentation

### Estimated Value
**Human equivalent:** 7-8 hours
**Bill as:** [Client decision]

---

## Session: 2025-11-15 (Implementation)
...
```

3. **Review with client** at milestones
4. **Bill based on value delivered**, not AI processing time

### Best Practice

**Don't:**
- ❌ Bill AI execution time 1:1 as human hours
- ❌ Hide that AI was used
- ❌ Over-inflate hours to match traditional estimates

**Do:**
- ✅ Be transparent about AI assistance
- ✅ Focus on value and quality of deliverables
- ✅ Pass savings to client (competitive rates)
- ✅ Track sessions for project management
- ✅ Show efficiency gains as a feature, not a bug

---

## Future Enhancements

### GitHub Action for Automatic Tracking

```yaml
# .github/workflows/track-agent-metrics.yml
name: Track Agent Metrics

on:
  push:
    branches: ['claude/**']

jobs:
  track:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Extract metrics from commit
        run: |
          # Extract agent name from commit message
          AGENT=$(git log -1 --format=%B | grep -o '\[Agent: [^]]*\]' | sed 's/\[Agent: \(.*\)\]/\1/')

          # Count changes
          FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD | wc -l)
          LINES_ADDED=$(git diff-tree --no-commit-id --numstat -r HEAD | awk '{sum+=$1} END {print sum}')

          echo "Agent: $AGENT"
          echo "Files: $FILES_CHANGED"
          echo "Lines: $LINES_ADDED"

          # Save to metrics file (append)
          echo "$(date -Iseconds),$AGENT,$FILES_CHANGED,$LINES_ADDED" >> data/agent_metrics.csv

      - name: Commit metrics
        run: |
          git add data/agent_metrics.csv
          git commit -m "chore: update agent metrics [skip ci]" || exit 0
          git push
```

---

## Summary

**For Client Billing:**
- Track sessions with clear deliverables
- Bill based on value, not execution time
- Be transparent about AI assistance
- Show efficiency as a benefit

**For Project Management:**
- Log major sessions in markdown
- Track git commits with agent tags
- Review metrics at milestones
- Use data to improve estimates

**For Transparency:**
- Commit metrics to git
- Generate periodic reports
- Share efficiency gains with client
- Maintain clear communication

**Recommended Setup Time:** 30 minutes to add basic tracking
**Value:** Clear project records + fair client billing + accountability

---

**Status:** Guidance provided, implementation optional
**Last Updated:** 2025-11-14
**Applies To:** All AI-assisted development projects
