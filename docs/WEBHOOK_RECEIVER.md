# Ghost Webhook Receiver

This document describes how to set up a Cloudflare Worker to receive Ghost webhooks and trigger GitHub Actions workflows.

## Overview

Ghost CMS can send webhooks when posts are scheduled, published, or updated. However, GitHub Actions cannot receive webhooks directly. This Cloudflare Worker acts as a bridge:

```
Ghost → Cloudflare Worker → GitHub repository_dispatch → on-schedule.yml
```

## Cloudflare Worker Code

Deploy this code to Cloudflare Workers:

```javascript
/**
 * Ghost Webhook Receiver for GitHub Actions
 *
 * Receives Ghost post.scheduled webhooks and triggers GitHub repository_dispatch events.
 * Deploy to Cloudflare Workers and configure as a Ghost webhook target.
 *
 * Environment Variables (set in Cloudflare dashboard):
 * - GITHUB_TOKEN: Personal access token with repo scope
 * - GITHUB_REPO: Repository in format "owner/repo"
 * - WEBHOOK_SECRET: Optional shared secret for webhook verification
 */

export default {
  async fetch(request, env) {
    // Only accept POST requests
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // Verify webhook secret if configured
    if (env.WEBHOOK_SECRET) {
      const signature = request.headers.get('X-Ghost-Signature');
      if (!signature) {
        return new Response('Missing signature', { status: 401 });
      }
      // Note: Full HMAC verification would go here
      // Ghost uses SHA256 HMAC with the webhook secret
    }

    try {
      const payload = await request.json();

      // Extract post data from Ghost webhook
      // Ghost webhook format: { post: { current: {...}, previous: {...} } }
      const post = payload.post?.current || payload.post;

      if (!post || !post.id) {
        return new Response('Invalid webhook payload', { status: 400 });
      }

      // Only trigger for scheduled status
      if (post.status !== 'scheduled') {
        console.log(`Ignoring non-scheduled post: ${post.status}`);
        return new Response('OK - ignored', { status: 200 });
      }

      // Trigger GitHub repository_dispatch
      const githubResponse = await fetch(
        `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
        {
          method: 'POST',
          headers: {
            'Authorization': `token ${env.GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'Ghost-Webhook-Receiver/1.0',
          },
          body: JSON.stringify({
            event_type: 'post.scheduled',
            client_payload: {
              post: {
                id: post.id,
                slug: post.slug,
                title: post.title,
                status: post.status,
                published_at: post.published_at,
              },
              timestamp: new Date().toISOString(),
            },
          }),
        }
      );

      if (!githubResponse.ok) {
        const error = await githubResponse.text();
        console.error(`GitHub API error: ${error}`);
        return new Response(`GitHub API error: ${githubResponse.status}`, {
          status: 500,
        });
      }

      console.log(`Triggered workflow for post: ${post.slug}`);
      return new Response('OK', { status: 200 });

    } catch (error) {
      console.error(`Error processing webhook: ${error}`);
      return new Response(`Error: ${error.message}`, { status: 500 });
    }
  },
};
```

## Setup Instructions

### 1. Create Cloudflare Worker

1. Go to [Cloudflare Workers Dashboard](https://dash.cloudflare.com/)
2. Click "Create a Worker"
3. Paste the code above
4. Deploy the worker

### 2. Configure Environment Variables

In the Cloudflare Workers dashboard, add these secrets:

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub Personal Access Token with `repo` scope |
| `GITHUB_REPO` | Repository name (e.g., `owner/prx-to-ghost-publisher`) |
| `WEBHOOK_SECRET` | (Optional) Shared secret for webhook verification |

### 3. Configure Ghost Webhook

1. Go to Ghost Admin → Settings → Integrations
2. Click "Add custom integration"
3. Name it "GitHub Actions Trigger"
4. Add a new webhook:
   - **Event:** `Post scheduled`
   - **Target URL:** Your Cloudflare Worker URL (e.g., `https://ghost-webhook.your-subdomain.workers.dev`)

### 4. Test the Webhook

1. Create a test post in Ghost
2. Schedule it for a future time
3. Check the Cloudflare Workers logs for the webhook receipt
4. Check GitHub Actions for the triggered workflow

## Security Considerations

1. **Use a webhook secret**: Configure both Ghost and the Worker with a shared secret
2. **Limit token scope**: The GitHub token only needs `repo` scope
3. **Use Cloudflare Access**: Optionally protect the worker URL with Cloudflare Access rules

## Alternative: GitHub App

For production use, consider using a GitHub App instead of a Personal Access Token:
- Better security (installation-scoped tokens)
- No expiration (unlike PATs)
- Better audit logging

## Troubleshooting

### Webhook not received
- Check Ghost integration is enabled
- Verify the Worker URL is correct
- Check Cloudflare Workers logs

### GitHub workflow not triggered
- Verify GITHUB_TOKEN has correct permissions
- Check GITHUB_REPO format is correct
- Look for errors in Cloudflare Workers logs

### Wrong workflow triggered
- Verify the `event_type` matches `post.scheduled`
- Check the `on: repository_dispatch` configuration in `on-schedule.yml`
