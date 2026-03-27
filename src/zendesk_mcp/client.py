"""Async Zendesk API client."""

import base64
import os
import re

import httpx

# Zendesk subdomains: alphanumeric and hyphens only
_SUBDOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")

VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"new", "open", "pending", "hold", "solved", "closed"}
VALID_TICKET_TYPES = {"problem", "incident", "question", "task"}


class ZendeskError(Exception):
    """Raised when a Zendesk API call fails."""


class ZendeskClient:
    """Lightweight async client for the Zendesk REST API v2."""

    def __init__(
        self,
        subdomain: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        auth_mode: str = "basic",
        access_token: str | None = None,
    ):
        if auth_mode not in ("basic", "bearer"):
            raise ValueError(f"auth_mode must be 'basic' or 'bearer', got {auth_mode!r}")

        self.subdomain = (subdomain or "").strip() or os.environ.get("ZENDESK_SUBDOMAIN", "")
        if not self.subdomain:
            raise ValueError("subdomain is required (via argument or ZENDESK_SUBDOMAIN env var)")

        if not _SUBDOMAIN_RE.match(self.subdomain):
            raise ValueError(
                f"Invalid Zendesk subdomain: {self.subdomain!r}. "
                "Must contain only alphanumeric characters and hyphens."
            )

        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
        self._auth_mode = auth_mode

        if auth_mode == "bearer":
            if not access_token:
                raise ValueError("access_token is required when auth_mode='bearer'")
            self._headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        else:
            email = (email or "").strip() or os.environ["ZENDESK_EMAIL"]
            api_token = (api_token or "").strip() or os.environ["ZENDESK_API_TOKEN"]
            creds = base64.b64encode(f"{email}/token:{api_token}".encode()).decode()
            self._headers = {
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
            }

        self._http_client: httpx.AsyncClient | None = None

    def __repr__(self) -> str:
        return f"ZendeskClient(subdomain={self.subdomain!r})"

    _ALLOWED_METHODS = {"get", "post", "put", "delete"}

    def __init_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=30.0,
        )

    @property
    def _http(self) -> httpx.AsyncClient:
        """Lazy-initialized persistent HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = self.__init_http_client()
        return self._http_client

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    @staticmethod
    def _validate_ticket_id(ticket_id: int) -> int:
        """Ensure ticket_id is a positive integer to prevent path traversal."""
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            raise ValueError(f"ticket_id must be a positive integer, got {ticket_id!r}")
        return ticket_id

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an API request with safe error handling."""
        if method not in self._ALLOWED_METHODS:
            raise ValueError(f"HTTP method {method!r} not allowed")
        resp = await getattr(self._http, method)(path, **kwargs)
        if resp.is_error:
            raise ZendeskError(
                f"Zendesk API error: {resp.status_code} on {method.upper()} {path}"
            )
        return resp

    async def create_ticket(
        self,
        subject: str,
        description: str,
        priority: str | None = None,
        ticket_type: str | None = None,
        tags: list[str] | None = None,
        requester_email: str | None = None,
        assignee_email: str | None = None,
        custom_fields: list[dict] | None = None,
    ) -> dict:
        """Create a new Zendesk ticket."""
        if priority and priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority {priority!r}. Must be one of: {VALID_PRIORITIES}")
        if ticket_type and ticket_type not in VALID_TICKET_TYPES:
            raise ValueError(f"Invalid ticket_type {ticket_type!r}. Must be one of: {VALID_TICKET_TYPES}")

        comment = {"body": description}
        ticket: dict = {"subject": subject, "comment": comment}

        if priority:
            ticket["priority"] = priority
        if ticket_type:
            ticket["type"] = ticket_type
        if tags:
            ticket["tags"] = tags
        if requester_email:
            ticket["requester"] = {"email": requester_email}
        if assignee_email:
            ticket["assignee_email"] = assignee_email
        if custom_fields:
            ticket["custom_fields"] = custom_fields

        resp = await self._request("post", "/tickets.json", json={"ticket": ticket})
        return resp.json()["ticket"]

    async def get_ticket(self, ticket_id: int) -> dict:
        """Get a ticket by ID."""
        self._validate_ticket_id(ticket_id)
        resp = await self._request("get", f"/tickets/{ticket_id}.json")
        return resp.json()["ticket"]

    async def update_ticket(
        self,
        ticket_id: int,
        status: str | None = None,
        priority: str | None = None,
        assignee_email: str | None = None,
        tags: list[str] | None = None,
        custom_fields: list[dict] | None = None,
    ) -> dict:
        """Update an existing ticket's fields."""
        self._validate_ticket_id(ticket_id)
        if status and status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {status!r}. Must be one of: {VALID_STATUSES}")
        if priority and priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority {priority!r}. Must be one of: {VALID_PRIORITIES}")

        ticket: dict = {}

        if status:
            ticket["status"] = status
        if priority:
            ticket["priority"] = priority
        if assignee_email:
            ticket["assignee_email"] = assignee_email
        if tags:
            ticket["tags"] = tags
        if custom_fields:
            ticket["custom_fields"] = custom_fields

        resp = await self._request(
            "put", f"/tickets/{ticket_id}.json", json={"ticket": ticket}
        )
        return resp.json()["ticket"]

    async def add_comment(
        self,
        ticket_id: int,
        body: str,
        public: bool = True,
    ) -> dict:
        """Add a comment to a ticket. Set public=False for an internal note."""
        self._validate_ticket_id(ticket_id)
        ticket = {"comment": {"body": body, "public": public}}

        resp = await self._request(
            "put", f"/tickets/{ticket_id}.json", json={"ticket": ticket}
        )
        return resp.json()["ticket"]

    async def search_tickets(
        self,
        query: str,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> list[dict]:
        """Search tickets using Zendesk search syntax.

        Example queries:
            - "status:open priority:high"
            - "assignee:me status:pending"
            - "tags:billing created>2024-01-01"
        """
        params = {
            "query": f"type:ticket {query}",
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        resp = await self._request("get", "/search.json", params=params)
        return resp.json()["results"]
