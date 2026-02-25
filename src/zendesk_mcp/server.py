"""Zendesk MCP server — exposes ticket management tools via the Model Context Protocol."""

import hmac
import os

from mcp.server.fastmcp import FastMCP

from zendesk_mcp.client import ZendeskClient

mcp = FastMCP("Zendesk")

_client: ZendeskClient | None = None


def _get_client() -> ZendeskClient:
    global _client
    if _client is None:
        _client = ZendeskClient()
    return _client


def _summarize_ticket(t: dict) -> dict:
    """Return a concise ticket representation for LLM consumption."""
    return {
        "id": t.get("id"),
        "subject": t.get("subject"),
        "status": t.get("status"),
        "priority": t.get("priority"),
        "type": t.get("type"),
        "tags": t.get("tags", []),
        "assignee_id": t.get("assignee_id"),
        "requester_id": t.get("requester_id"),
        "created_at": t.get("created_at"),
        "updated_at": t.get("updated_at"),
        "url": t.get("url"),
    }


@mcp.tool()
async def create_ticket(
    subject: str,
    description: str,
    priority: str = "normal",
    ticket_type: str | None = None,
    tags: list[str] | None = None,
    requester_email: str | None = None,
    assignee_email: str | None = None,
) -> dict:
    """Create a new Zendesk support ticket.

    Args:
        subject: Ticket subject/title.
        description: Ticket body text.
        priority: One of: low, normal, high, urgent. Defaults to normal.
        ticket_type: One of: problem, incident, question, task. Optional.
        tags: List of tags to apply.
        requester_email: Email of the person who requested the ticket.
        assignee_email: Email of the agent to assign the ticket to.
    """
    ticket = await _get_client().create_ticket(
        subject=subject,
        description=description,
        priority=priority,
        ticket_type=ticket_type,
        tags=tags,
        requester_email=requester_email,
        assignee_email=assignee_email,
    )
    return _summarize_ticket(ticket)


@mcp.tool()
async def get_ticket(ticket_id: int) -> dict:
    """Get details of a Zendesk ticket by its ID.

    Args:
        ticket_id: The numeric Zendesk ticket ID.
    """
    ticket = await _get_client().get_ticket(ticket_id)
    return _summarize_ticket(ticket)


@mcp.tool()
async def update_ticket(
    ticket_id: int,
    status: str | None = None,
    priority: str | None = None,
    assignee_email: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update fields on an existing Zendesk ticket.

    Args:
        ticket_id: The numeric Zendesk ticket ID.
        status: One of: new, open, pending, hold, solved, closed.
        priority: One of: low, normal, high, urgent.
        assignee_email: Email of the agent to reassign to.
        tags: Replace current tags with this list.
    """
    ticket = await _get_client().update_ticket(
        ticket_id=ticket_id,
        status=status,
        priority=priority,
        assignee_email=assignee_email,
        tags=tags,
    )
    return _summarize_ticket(ticket)


@mcp.tool()
async def add_comment(
    ticket_id: int,
    body: str,
    public: bool = True,
) -> dict:
    """Add a comment to a Zendesk ticket.

    Args:
        ticket_id: The numeric Zendesk ticket ID.
        body: The comment text.
        public: True for a public reply visible to the requester, False for an internal note.
    """
    ticket = await _get_client().add_comment(
        ticket_id=ticket_id,
        body=body,
        public=public,
    )
    return _summarize_ticket(ticket)


@mcp.tool()
async def search_tickets(
    query: str,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[dict]:
    """Search Zendesk tickets using Zendesk search syntax.

    Args:
        query: Search query using Zendesk syntax. Examples:
            - "status:open priority:high"
            - "assignee:me status:pending"
            - "tags:billing created>2024-01-01"
            - "subject:refund"
        sort_by: Field to sort by. Defaults to updated_at.
        sort_order: Sort direction — "asc" or "desc". Defaults to desc.
    """
    results = await _get_client().search_tickets(
        query=query,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [_summarize_ticket(t) for t in results]


class BearerAuthMiddleware:
    """ASGI middleware that requires a valid Bearer token on every HTTP request."""

    def __init__(self, app, token: str):
        self.app = app
        self._token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()

            valid = (
                auth_header.startswith("Bearer ")
                and hmac.compare_digest(auth_header[7:], self._token)
            )
            if not valid:
                from starlette.responses import JSONResponse

                response = JSONResponse(
                    {"error": "Unauthorized"}, status_code=401
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Zendesk MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="streamable-http",
        help="MCP transport (default: streamable-http)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable bearer token auth (NOT recommended for production)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    auth_token = os.environ.get("ZENDESK_MCP_AUTH_TOKEN")

    if not auth_token and not args.no_auth:
        print(
            "Error: ZENDESK_MCP_AUTH_TOKEN env var is required for HTTP transport.\n"
            "Set it to a secret bearer token, or pass --no-auth to disable "
            "(not recommended for production).",
            file=sys.stderr,
        )
        sys.exit(1)

    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if auth_token:
        import anyio
        import uvicorn

        async def _run_with_auth():
            app = mcp.streamable_http_app()
            app = BearerAuthMiddleware(app, auth_token)
            config = uvicorn.Config(app, host=args.host, port=args.port)
            server = uvicorn.Server(config)
            await server.serve()

        anyio.run(_run_with_auth)
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
