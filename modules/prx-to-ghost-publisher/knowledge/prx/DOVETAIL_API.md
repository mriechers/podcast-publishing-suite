# PRX Dovetail Podcasts API Documentation

> Source: https://gist.github.com/kookster/a7daaebc6b3df935c819a8ac13088bd8
> Retrieved: 2026-01-06

## Authentication

The Dovetail API uses OAuth2 Client Credentials flow.

### Environment Setup

```bash
export PRX_CLIENT_ID=[CLIENT_ID]
export PRX_CLIENT_SECRET=[CLIENT_SECRET]
```

### Obtain Access Token

```bash
curl -X POST \
  -d "grant_type=client_credentials&client_id=$PRX_CLIENT_ID&client_secret=$PRX_CLIENT_SECRET" \
  https://id.prx.org/token | jq
```

Response:
```json
{
  "access_token": "[TOKEN]",
  "token_type": "bearer"
}
```

## Base URLs

| Environment | ID Service | Podcasts API |
|---|---|---|
| Staging | https://id.staging.prx.tech | https://podcasts.dovetail.staging.prx.tech/api/v1 |
| Production | https://id.prx.org | https://podcasts.dovetail.prx.org/api/v1 |

## API Endpoints

### Authorization Root

```
GET /api/v1/authorization
```

Returns available operations and resource links for the authenticated account.

### List Podcasts

```
GET /api/v1/authorization/podcasts{?page,per,zoom,since}
```

Query parameters:
- `page`: Page number for pagination
- `per`: Items per page
- `zoom`: Include related resources
- `since`: Filter by modified date (ISO 8601)

### List Episodes

```
GET /api/v1/authorization/episodes{?page,per,zoom,since}
```

Query parameters:
- `page`: Page number for pagination
- `per`: Items per page
- `zoom`: Include related resources
- `since`: Filter by modified date (ISO 8601)

### Lookup Episode by GUID

```
GET /api/v1/podcasts/{podcast_id}/guids/{guid}
```

Look up a specific episode by its GUID within a podcast.

### Update Episode

```
PUT /api/v1/authorization/episodes/{id}
```

Update an existing episode's metadata.

### Create Episode

```
POST /api/v1/authorization/podcasts/{id}/episodes
```

Create a new episode within a podcast.

## Request Headers

All API requests require:

```
Authorization: Bearer $PRX_ACCESS_TOKEN
Content-Type: application/json
Accept: application/json
```

## Episode Payload Structure

```json
{
  "title": "string",
  "subtitle": "string",
  "description": "string",
  "itunesCategories": [
    {
      "name": "string",
      "subcategories": []
    }
  ],
  "media": [
    {
      "href": "https://example.com/audio.mp3"
    }
  ]
}
```

**Important Note:** The `media` array represents the complete file list. Sending a PUT request replaces all prior files unless URLs match existing entries.

## Response Format

Responses follow HAL+JSON format with embedded resources and links.

## Token Lifecycle

- Tokens are bearer tokens
- Token expiration is handled by the OAuth2 server
- Refresh by requesting a new token with client credentials
