"""Tests for MCP server tool registration and auth middleware."""

import pytest

from zendesk_mcp.server import mcp, BearerAuthMiddleware, _extract_request_credentials


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


# --- Per-request credential extraction ---


def test_extract_credentials_from_headers():
    """X-Zendesk-Token and X-Zendesk-Subdomain headers are extracted."""
    headers = [
        (b"x-zendesk-token", b"oauth-tok-123"),
        (b"x-zendesk-subdomain", b"acme"),
    ]
    creds = _extract_request_credentials(headers)
    assert creds == {"access_token": "oauth-tok-123", "subdomain": "acme"}


def test_extract_credentials_missing_headers_returns_none():
    """Returns None when neither credential header is present."""
    headers = [(b"authorization", b"Bearer transport-token")]
    creds = _extract_request_credentials(headers)
    assert creds is None


def test_extract_credentials_partial_headers_returns_none():
    """Both headers required — partial returns None."""
    headers = [(b"x-zendesk-token", b"tok")]
    creds = _extract_request_credentials(headers)
    assert creds is None


def test_extract_credentials_validates_subdomain():
    """Invalid subdomain in header is rejected."""
    headers = [
        (b"x-zendesk-token", b"tok"),
        (b"x-zendesk-subdomain", b"evil.com"),
    ]
    with pytest.raises(ValueError, match="Invalid Zendesk subdomain"):
        _extract_request_credentials(headers)


def test_extract_credentials_token_not_logged(caplog):
    """Tokens from headers must not appear in log output."""
    import logging

    with caplog.at_level(logging.DEBUG):
        headers = [
            (b"x-zendesk-token", b"super-secret-oauth-token"),
            (b"x-zendesk-subdomain", b"acme"),
        ]
        _extract_request_credentials(headers)
    assert "super-secret-oauth-token" not in caplog.text
