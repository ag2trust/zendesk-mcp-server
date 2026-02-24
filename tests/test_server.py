"""Tests for MCP server tool registration."""

from zendesk_mcp.server import mcp


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
