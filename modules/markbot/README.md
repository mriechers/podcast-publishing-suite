# Your Helpful MarkBot!

Centralized Slack bot for alerts, updates and nudges. Gathers up saved items and stray conversations for other LLM-driven apps, and gives LLM applications a simple Slack notifier. 

## Quick Start

```bash
pip install -r requirements.txt
export SLACK_BOT_TOKEN=xoxb-your-token

# Test with dry run (no token needed)
python3 markbot.py --dry-run transcribe-start --episode "Test" --channel X
```

## Setup

See [docs/SETUP.md](docs/SETUP.md) for Slack App creation and configuration.

## Commands

- **`transcribe-start`** — "Working on a transcript" notification (prints `thread_ts`)
- **`transcribe-ready`** — "Transcript ready to edit" with Google Doc link
- **`schedule-alert`** — Release readiness alerts (missing / drafted / scheduled)
- **`ghost-import`** — Import lifecycle notifications (start, draft ready, scheduled, failed)
- **`post`** — Generic Block Kit poster for custom payloads

## Use cases
- Used as centralized alert system in the [podcast-publishing-suite](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite).
