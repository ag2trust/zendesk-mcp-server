"""Tests for the Zendesk API client."""

import base64

import pytest

from zendesk_mcp.client import ZendeskClient


def test_client_init_from_args():
    client = ZendeskClient(
        subdomain="test",
        email="user@test.com",
        api_token="tok123",
    )
    assert client.base_url == "https://test.zendesk.com/api/v2"

    expected_creds = base64.b64encode(b"user@test.com/token:tok123").decode()
    assert client._headers["Authorization"] == f"Basic {expected_creds}"


def test_client_init_from_env(monkeypatch):
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "envtest")
    monkeypatch.setenv("ZENDESK_EMAIL", "env@test.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "envtok")

    client = ZendeskClient()
    assert client.base_url == "https://envtest.zendesk.com/api/v2"


def test_client_init_missing_env_raises():
    with pytest.raises((KeyError, ValueError)):
        ZendeskClient()


def test_repr_does_not_leak_credentials():
    client = ZendeskClient(subdomain="test", email="u@t.com", api_token="secret")
    r = repr(client)
    assert "secret" not in r
    assert "test" in r


@pytest.mark.parametrize("bad_subdomain", [
    "evil.com",
    "foo/bar",
    "sub domain",
    "../etc",
    "acme.zendesk.com",
    "-startwithhyphen",
])
def test_invalid_subdomain_rejected(bad_subdomain):
    with pytest.raises(ValueError, match="Invalid Zendesk subdomain"):
        ZendeskClient(subdomain=bad_subdomain, email="u@t.com", api_token="tok")


@pytest.mark.parametrize("good_subdomain", [
    "acme",
    "my-company",
    "test123",
    "A1",
])
def test_valid_subdomain_accepted(good_subdomain):
    client = ZendeskClient(subdomain=good_subdomain, email="u@t.com", api_token="tok")
    assert good_subdomain in client.base_url


def test_empty_string_args_fall_through_to_env(monkeypatch):
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "fromenv")
    monkeypatch.setenv("ZENDESK_EMAIL", "env@t.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "envtok")

    client = ZendeskClient(subdomain="", email="", api_token="")
    assert client.subdomain == "fromenv"


def test_validate_ticket_id_rejects_bad_values():
    with pytest.raises(ValueError):
        ZendeskClient._validate_ticket_id("../users")
    with pytest.raises(ValueError):
        ZendeskClient._validate_ticket_id(-1)
    with pytest.raises(ValueError):
        ZendeskClient._validate_ticket_id(0)


def test_validate_ticket_id_accepts_positive_int():
    assert ZendeskClient._validate_ticket_id(42) == 42


def test_persistent_http_client():
    """HTTP client is reused across property accesses."""
    client = ZendeskClient(subdomain="test", email="u@t.com", api_token="tok")
    http1 = client._http
    http2 = client._http
    assert http1 is http2


def test_disallowed_http_method():
    """Only get/post/put/delete are allowed."""
    client = ZendeskClient(subdomain="test", email="u@t.com", api_token="tok")
    with pytest.raises(ValueError, match="not allowed"):
        import asyncio
        asyncio.run(client._request("patch", "/foo"))


# --- Bearer auth mode ---


def test_bearer_auth_mode():
    """Bearer mode uses Authorization: Bearer header, no email required."""
    client = ZendeskClient(
        subdomain="test",
        auth_mode="bearer",
        access_token="oauth-token-123",
    )
    assert client.base_url == "https://test.zendesk.com/api/v2"
    assert client._headers["Authorization"] == "Bearer oauth-token-123"


def test_bearer_auth_mode_missing_token_raises():
    """Bearer mode requires access_token."""
    with pytest.raises(ValueError, match="access_token.*required"):
        ZendeskClient(subdomain="test", auth_mode="bearer")


def test_bearer_auth_mode_no_email_required():
    """Bearer mode does not require email or api_token."""
    client = ZendeskClient(
        subdomain="test",
        auth_mode="bearer",
        access_token="tok",
    )
    assert "Basic" not in client._headers["Authorization"]


def test_bearer_repr_does_not_leak_token():
    """Bearer token must not appear in repr."""
    client = ZendeskClient(
        subdomain="test",
        auth_mode="bearer",
        access_token="super-secret-token",
    )
    r = repr(client)
    assert "super-secret-token" not in r
    assert "test" in r


def test_invalid_auth_mode_raises():
    """Only 'basic' and 'bearer' are valid auth modes."""
    with pytest.raises(ValueError, match="auth_mode"):
        ZendeskClient(
            subdomain="test",
            email="u@t.com",
            api_token="tok",
            auth_mode="digest",
        )


def test_basic_auth_mode_is_default():
    """Default auth_mode is 'basic', preserving backward compat."""
    client = ZendeskClient(subdomain="test", email="u@t.com", api_token="tok")
    assert client._headers["Authorization"].startswith("Basic ")
