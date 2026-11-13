"""MCP calls use the SDK; validate structured output at the portal boundary."""

import asyncio
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import ValidationError
from app.contracts import Document, SearchSnapshot, Tree


class KnowledgeUnavailable(RuntimeError):
    pass


class MCPClient:
    def __init__(self, url=None, token=None):
        self.url = url or os.getenv("MCP_URL", "http://kb-mcp:8000/mcp")
        self.token = token or os.environ["MCP_SERVICE_TOKEN"]

    async def call(self, name, arguments):
        try:
            async with asyncio.timeout(2):
                async with httpx.AsyncClient(
                    headers={"Authorization": "Bearer " + self.token},
                    timeout=2,
                    trust_env=False,
                ) as http:
                    async with streamable_http_client(self.url, http_client=http) as (
                        reader,
                        writer,
                        _,
                    ):
                        async with ClientSession(reader, writer) as session:
                            await session.initialize()
                            result = await session.call_tool(name, arguments)
        except Exception as error:
            raise KnowledgeUnavailable("Knowledge service unavailable") from error
        # Validate after exiting SDK task groups: a tool error is not a broken transport.
        if result.isError:
            raise ValueError("Knowledge tool rejected the arguments or revision")
        contract = {
            "get_doc": Document,
            "search_docs": SearchSnapshot,
            "list_sections": Tree,
        }[name]
        try:
            return contract.model_validate(result.structuredContent).model_dump()
        except ValidationError as error:
            raise KnowledgeUnavailable(
                "MCP returned invalid structured content"
            ) from error
