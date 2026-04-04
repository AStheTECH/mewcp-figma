# Figma MCP Server

A Model Context Protocol (MCP) server that provides access to Figma API operations — files, nodes, images, comments, teams, projects, and components.

## Authentication

This server is **stateless and multi-tenant**. Every tenant-facing tool accepts an `access_token` on each call and authenticates per request — no session state is stored in memory.

Figma supports two token types:

| Type | How to obtain |
|------|---------------|
| **Personal Access Token (PAT)** | Figma → Account Settings → Personal access tokens |
| **OAuth2 Bearer Token** | Standard OAuth2 flow against `https://www.figma.com/oauth` |

Pass either token as `access_token` in every tool call. The server forwards it as the `X-Figma-Token` header to the Figma REST API.

Required Figma API scopes (OAuth2): `file_read`, `file_comments:write`

## Features

| Tool | Description |
|------|-------------|
| `health_check` | Check server readiness (no auth required) |
| `get_me` | Get authenticated user profile |
| `get_file` | Retrieve a Figma file document tree |
| `get_file_nodes` | Retrieve specific nodes from a file |
| `get_file_components` | List local components in a file |
| `get_file_styles` | List local styles in a file |
| `get_file_versions` | Retrieve version history of a file |
| `get_images` | Export nodes as rendered image URLs |
| `get_image_fills` | Get download URLs for image fills |
| `get_comments` | List all comments on a file |
| `post_comment` | Post a comment on a file |
| `get_team_projects` | List projects in a team |
| `get_project_files` | List files in a project |
| `get_team_components` | List published components in a team library |
| `get_component` | Get metadata for a specific published component |

## Setup

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
# stdio (default)
python server.py

# SSE
python server.py --transport sse --host 127.0.0.1 --port 8001

# Streamable HTTP
python server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

## Example Tool Calls

**Get a Figma file:**
```json
{
  "tool": "get_file",
  "arguments": {
    "access_token": "figd_...",
    "file_key": "abc123XYZ"
  }
}
```

**Export nodes as PNG images:**
```json
{
  "tool": "get_images",
  "arguments": {
    "access_token": "figd_...",
    "file_key": "abc123XYZ",
    "node_ids": "1:2,3:4",
    "format": "png",
    "scale": 2
  }
}
```

**Post a comment:**
```json
{
  "tool": "post_comment",
  "arguments": {
    "access_token": "figd_...",
    "file_key": "abc123XYZ",
    "message": "Looks great — ready for dev handoff."
  }
}
```

**List team projects:**
```json
{
  "tool": "get_team_projects",
  "arguments": {
    "access_token": "figd_...",
    "team_id": "123456789"
  }
}
```

## Project Structure

```text
cl-mcp-figma/
|-- server.py
|-- requirements.txt
|-- README.md
|-- .gitignore
`-- figma_mcp/
    |-- __init__.py
    |-- cli.py
    |-- config.py
    |-- schemas.py
    |-- service.py
    `-- tools.py
```

## Troubleshooting

- **401 Unauthorized** — token is invalid, expired, or missing required scopes.
- **403 Forbidden** — token lacks access to the requested file or team.
- **404 Not Found** — the file key, node ID, team ID, or component key does not exist.
- **429 Too Many Requests** — Figma rate limit hit; back off and retry.
