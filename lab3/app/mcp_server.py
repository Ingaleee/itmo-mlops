"""Independent MCP deployment using the official SDK and Streamable HTTP."""

import hmac
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.knowledge import Knowledge, build
from app.contracts import Document, SearchSnapshot, Tree


def create_app():
    database = Path(os.getenv("KB_DATABASE", "artifacts/knowledge.db"))
    corpus = os.getenv("KB_CORPUS")
    if corpus:
        build(Path(corpus), database)
    store = Knowledge(database)
    store.metadata()
    token = os.environ["MCP_SERVICE_TOKEN"]
    if len(token) < 24:
        raise RuntimeError("MCP service token must contain at least 24 characters")
    server = FastMCP(
        "liratech-knowledge",
        host="0.0.0.0",
        port=8000,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "kb-mcp:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
        ),
    )

    @server.tool()
    def list_sections() -> Tree:
        """List the hierarchy, document IDs, exact revisions and statuses."""
        return Tree.model_validate(store.tree())

    @server.tool()
    def get_doc(doc_id: str, version: str) -> Document:
        """Read one exact document revision, including original sections."""
        return Document.model_validate(store.get(doc_id, version))

    @server.tool()
    def search_docs(
        query: str,
        limit: int = 5,
        path: list[str] | None = None,
        statuses: list[str] | None = None,
        doc_id: str | None = None,
        version: str | None = None,
    ) -> SearchSnapshot:
        """Search filtered sections and return unique revision cards and source anchors."""
        return SearchSnapshot.model_validate(
            store.search(query, limit, path, statuses, doc_id, version)
        )

    @server.custom_route("/livez", methods=["GET"])
    async def live(_: Request):
        return JSONResponse({"status": "alive"})

    @server.custom_route("/readyz", methods=["GET"])
    async def ready(_: Request):
        return JSONResponse({"status": "ready", **store.metadata()})

    application = server.streamable_http_app()

    class ServiceToken:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope["path"].startswith("/mcp"):
                headers = dict(scope["headers"])
                supplied = headers.get(b"authorization", b"")
                if not hmac.compare_digest(supplied, ("Bearer " + token).encode()):
                    await JSONResponse(
                        {"detail": "MCP authentication required"}, status_code=401
                    )(scope, receive, send)
                    return
            await self.app(scope, receive, send)

    return ServiceToken(application)
