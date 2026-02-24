# Zendesk MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that lets AI agents manage Zendesk Support tickets. Built from scratch in Python 3.12 using the official MCP SDK.

> **Disclaimer:** This project was built from scratch by AI agents. It is **not** affiliated with, endorsed by, or associated with Zendesk, Inc. "Zendesk" is a trademark of Zendesk, Inc. This is an independent, open-source integration that uses the publicly available Zendesk REST API.

## Tools

| Tool | Description |
|------|-------------|
| `create_ticket` | Create a new support ticket |
| `get_ticket` | Get ticket details by ID |
| `update_ticket` | Update status, priority, assignee, or tags |
| `add_comment` | Add a public reply or internal note |
| `search_tickets` | Search tickets using Zendesk query syntax |

## Setup

### Prerequisites

- Python 3.12+
- A Zendesk account with API access enabled

### Zendesk credentials

You need three things from your Zendesk account:

1. **Subdomain** — the `acme` part of `acme.zendesk.com`
2. **Email** — the email address of a Zendesk agent or admin
3. **API token** — generated in Zendesk Admin Center → Apps and integrations → APIs → Zendesk API

### Install

```bash
pip install .
```

Or with uv:

```bash
uv pip install .
```

### Run

Set your credentials as environment variables and start the server:

```bash
export ZENDESK_SUBDOMAIN=acme
export ZENDESK_EMAIL=agent@acme.com
export ZENDESK_API_TOKEN=your_api_token

# HTTP server (default) — for use with MCP gateways and remote clients
zendesk-mcp

# stdio mode — for local use with Claude Desktop, Cursor, etc.
zendesk-mcp --transport stdio
```

Options:

```
--transport    stdio | streamable-http (default: streamable-http)
--host         Host to bind to (default: 0.0.0.0)
--port         Port to bind to (default: 8000)
```

### Docker

```bash
docker build -t zendesk-mcp-server .

docker run -p 8000:8000 \
  -e ZENDESK_SUBDOMAIN=acme \
  -e ZENDESK_EMAIL=agent@acme.com \
  -e ZENDESK_API_TOKEN=your_api_token \
  zendesk-mcp-server
```

The server will be available at `http://localhost:8000/mcp`.

## MCP client configuration

### Remote / HTTP clients

Point your MCP client at the server URL:

```
http://your-host:8000/mcp
```

### Local / stdio clients (Claude Desktop, Cursor, etc.)

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "zendesk-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "ZENDESK_SUBDOMAIN": "acme",
        "ZENDESK_EMAIL": "agent@acme.com",
        "ZENDESK_API_TOKEN": "your_api_token"
      }
    }
  }
}
```

## Tool details

### create_ticket

```
subject (required): Ticket subject
description (required): Ticket body text
priority: low | normal | high | urgent (default: normal)
ticket_type: problem | incident | question | task
tags: list of tags
requester_email: email of the requester
assignee_email: email of the assigned agent
```

### get_ticket

```
ticket_id (required): Numeric Zendesk ticket ID
```

### update_ticket

```
ticket_id (required): Numeric Zendesk ticket ID
status: new | open | pending | hold | solved | closed
priority: low | normal | high | urgent
assignee_email: email of the agent to reassign to
tags: replace current tags with this list
```

### add_comment

```
ticket_id (required): Numeric Zendesk ticket ID
body (required): Comment text
public: true for public reply, false for internal note (default: true)
```

### search_tickets

Uses [Zendesk search syntax](https://support.zendesk.com/hc/en-us/articles/4408886879258):

```
query (required): e.g. "status:open priority:high", "tags:billing", "assignee:me"
sort_by: field to sort by (default: updated_at)
sort_order: asc | desc (default: desc)
```

## Security

This server communicates over plain HTTP by default. **For production deployments, we strongly recommend placing it behind a TLS-terminating reverse proxy** (e.g., Nginx, Caddy, or a cloud load balancer) so that all traffic — including Zendesk API credentials — is encrypted in transit. Do not expose the server directly to the public internet without TLS.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
