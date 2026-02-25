"""Tests for MCP server tool registration and auth middleware."""

import pytest

from zendesk_mcp.server import mcp, BearerAuthMiddleware


def test_tools_registered():
    """Verify all expected tools are registered on the MCP server."""
    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {"create_ticket", "get_ticket", "update_ticket", "add_comment", "search_tickets"}
    assert expected == tool_names


def test_summarize_ticket():
    from zendesk_mcp.server import _summarize_ticket

    raw = {
        "id": 42,
        "subject": "Test",
        "status": "open",
        "priority": "high",
        "type": "incident",
        "tags": ["billing"],
        "assignee_id": 1,
        "requester_id": 2,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
        "url": "https://test.zendesk.com/api/v2/tickets/42.json",
        "extra_field": "should be excluded",
    }
    result = _summarize_ticket(raw)
    assert result["id"] == 42
    assert result["subject"] == "Test"
    assert "extra_field" not in result


@pytest.mark.asyncio
async def test_auth_middleware_rejects_no_token():
    """Requests without a bearer token get 401."""
    responses = []

    async def mock_send(message):
        responses.append(message)

    middleware = BearerAuthMiddleware(app=None, token="secret123")
    scope = {"type": "http", "headers": []}

    await middleware(scope, None, mock_send)

    body = next(r for r in responses if r.get("type") == "http.response.body")
    assert b"Unauthorized" in body["body"]


@pytest.mark.asyncio
async def test_auth_middleware_rejects_wrong_token():
    """Requests with a wrong bearer token get 401."""
    responses = []

    async def mock_send(message):
        responses.append(message)

    middleware = BearerAuthMiddleware(app=None, token="secret123")
    scope = {
        "type": "http",
        "headers": [(b"authorization", b"Bearer wrong-token")],
    }

    await middleware(scope, None, mock_send)

    body = next(r for r in responses if r.get("type") == "http.response.body")
    assert b"Unauthorized" in body["body"]


@pytest.mark.asyncio
async def test_auth_middleware_passes_valid_token():
    """Requests with the correct bearer token pass through."""
    called = []

    async def mock_app(scope, receive, send):
        called.append(True)

    middleware = BearerAuthMiddleware(app=mock_app, token="secret123")
    scope = {
        "type": "http",
        "headers": [(b"authorization", b"Bearer secret123")],
    }

    await middleware(scope, None, None)
    assert called == [True]


@pytest.mark.asyncio
async def test_auth_middleware_skips_non_http():
    """Non-HTTP scopes (e.g. lifespan) pass through without auth check."""
    called = []

    async def mock_app(scope, receive, send):
        called.append(True)

    middleware = BearerAuthMiddleware(app=mock_app, token="secret123")
    scope = {"type": "lifespan"}

    await middleware(scope, None, None)
    assert called == [True]
