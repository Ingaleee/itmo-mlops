"""Independent SDK acceptance, emitting metadata only (never document bodies)."""

import asyncio
import json
import os
from pathlib import Path
import sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.mcp_client import MCPClient


async def main():
    url = os.environ["MCP_URL"]
    headers = {"Authorization": "Bearer " + os.environ["MCP_SERVICE_TOKEN"]}
    async with httpx.AsyncClient(headers=headers, timeout=10, trust_env=False) as http:
        async with streamable_http_client(url, http_client=http) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                initialized = await session.initialize()
                tools = (await session.list_tools()).tools
                assert {tool.name for tool in tools} == {
                    "list_sections",
                    "get_doc",
                    "search_docs",
                }
                get = next(tool for tool in tools if tool.name == "get_doc")
                assert set(get.inputSchema["required"]) == {"doc_id", "version"}
                doc = await session.call_tool(
                    "get_doc", {"doc_id": "M-05", "version": "1.1"}
                )
                assert not doc.isError and doc.structuredContent["status"] == "Архив"
                absent = await session.call_tool(
                    "get_doc", {"doc_id": "M-05", "version": "9.9"}
                )
                assert absent.isError
    client = MCPClient()
    try:
        await client.call("get_doc", {"doc_id": "M-05", "version": "9.9"})
    except ValueError:
        pass
    else:
        raise AssertionError("Missing revision was not a tool error")
    cases = json.loads(Path("control-questions.json").read_text(encoding="utf-8"))
    report = []
    for case in cases:
        result = await client.call(
            "search_docs", {"query": case["question"], "statuses": case["statuses"]}
        )
        pairs = [card["id"] + "@" + card["version"] for card in result["cards"]]
        assert set(case.get("required_documents", [])) <= set(pairs), case["id"]
        assert not case.get("any_of_documents") or set(case["any_of_documents"]) & set(
            pairs
        ), case["id"]
        report.append(
            {"id": case["id"], "documents": pairs, "generation": result["generation"]}
        )
    output = {
        "status": "passed",
        "transport": "streamable-http",
        "protocol": initialized.protocolVersion,
        "tools": [tool.model_dump(mode="json") for tool in tools],
        "missing_revision": "tool_error",
        "controls": report,
    }
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/mcp.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": "passed", "tools": len(tools), "control_questions": len(report)}
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
