# Your Helpful MarkBot! Setup Guide

**Your Helpful MarkBot!** is a Slack bot that posts producer-friendly notifications to the Wonder Cabinet Productions workspace. It handles transcription notifications, release schedule alerts, and other pipeline updates as a single bot identity.

## Step 1: Create the Slack App

A manifest file is included at `slack-app-manifest.yaml` that pre-configures everything — name, scopes, bot identity, and branding color.

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From an app manifest**
3. Select the Wonder Cabinet Productions workspace
4. Paste the contents of `slack-app-manifest.yaml` (switch the editor to YAML mode if it defaults to JSON)
5. Review the summary — it should show:
   - App name: Your Helpful MarkBot!
   - Bot scopes: `chat:write`, `chat:write.public`
   - Bot display name: Your Helpful MarkBot!
6. Click **Create**

<details>
<summary>Manual setup (if not using the manifest)</summary>

1. Click **Create New App** > **From scratch**
2. App Name: `Your Helpful MarkBot!`, Workspace: Wonder Cabinet Productions
3. Go to **OAuth & Permissions** > **Bot Token Scopes**, add:
   - `chat:write` — post messages
   - `chat:write.public` — post to channels the bot hasn't been invited to

</details>

## Step 2: Install to Workspace

1. In the app settings sidebar, go to **OAuth & Permissions**
2. Click **Install to Workspace**
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Step 3: Set the Bot Token

Add the token to a `.env` file in this repo:

```bash
cp .env.example .env
# Edit .env and paste your xoxb- token as SLACK_BOT_TOKEN
```

Or export it directly in your shell:

```bash
export SLACK_BOT_TOKEN=xoxb-your-token-here
```

The `markbot.py` script reads `SLACK_BOT_TOKEN` from the environment.

## Step 4: Upload the Bot Icon

The manifest sets the name, description, and background color automatically. The only thing it can't set is the icon image (no `icon_url` field in the manifest spec).

1. Download the WC logo: [logo-primary-dark-bg-800w.png](https://wondercabinetproductions.com/content/images/2026/01/logo-primary-dark-bg-800w.png)
2. In the app settings sidebar, go to **Basic Information**
3. Scroll to **Display Information**
4. Upload the logo as the **App icon**
5. Click **Save Changes**

## Step 5: Install the `slack-sdk` Dependency

```bash
pip install -r requirements.txt
# or directly:
pip install slack-sdk>=3.27.0
```

## Step 6: Test

### Dry run (no Slack token needed)

```bash
# Transcription start
python3 markbot.py --dry-run transcribe-start \
  --episode "005 - Renee Bergland" \
  --channel C09QUBVE0DR

# Transcription ready
python3 markbot.py --dry-run transcribe-ready \
  --episode "005 - Renee Bergland" \
  --doc-url "https://docs.google.com/document/d/test" \
  --channel C09QUBVE0DR \
  --thread-ts "1234567890.123456"

# Schedule alert
python3 markbot.py --dry-run schedule-alert \
  --state missing --show "Wonder Cabinet" \
  --slot "Podcast Episode" \
  --release-time "Saturday, March 7 at 6:00 AM CST (12h from now)" \
  --channel C09QUBVE0DR

# Generic post
echo '{"blocks":[{"type":"section","text":{"type":"mrkdwn","text":"Hello"}}]}' | \
  python3 markbot.py --dry-run post --blocks-json - --channel C09QUBVE0DR
```

### Live test (requires token)

Post to a test channel first. Create `#markbot-testing` and use its channel ID:

```bash
# 1. Post start message — capture thread_ts
THREAD_TS=$(python3 markbot.py transcribe-start \
  --episode "005 - Renee Bergland" \
  --channel YOUR_TEST_CHANNEL_ID)

echo "Thread TS: $THREAD_TS"

# 2. Post ready message in that thread
python3 markbot.py transcribe-ready \
  --episode "005 - Renee Bergland" \
  --doc-url "https://docs.google.com/document/d/test" \
  --speaker-note "Some speaker labels in Part 2 may be swapped" \
  --channel YOUR_TEST_CHANNEL_ID \
  --thread-ts "$THREAD_TS"
```

### Verify

- [ ] Bot appears as "Your Helpful MarkBot!" (not Mark)
- [ ] Start message shows episode name and ETA
- [ ] Ready message has the Google Doc link prominent and clickable
- [ ] Speaker note appears when provided, absent when omitted
- [ ] Ready message broadcasts to channel from thread (visible outside the thread)

## Architecture

```
wc-transcribe skill ─────────► markbot.py transcribe-start / transcribe-ready
airtable-automations ─────────► markbot.py schedule-alert / post
any future caller ────────────► markbot.py schedule-alert / post
```

The script is a standalone CLI tool using `slack_sdk.WebClient`. It reads:
- `SLACK_BOT_TOKEN` from the environment
- Chapter and transcript files from disk (via `--chapters-file` and `--transcript-file`)

## Channel Reference

| Channel | ID | Purpose |
|---------|----|---------|
| #all-wonder-cabinet-productions | `C09QUBVE0DR` | Production channel (default) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `SLACK_BOT_TOKEN environment variable not set` | Export the token or add it to `.env` |
| `not_in_channel` error | Add `chat:write.public` scope, or invite the bot to the channel |
| Message posts as plain text (no formatting) | Ensure both `blocks` and `text` are in the API call (the script handles this) |
| Ready message doesn't appear in channel | Check that `reply_broadcast=True` is set (it is by default in the script) |
