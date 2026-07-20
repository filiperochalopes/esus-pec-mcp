from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from pec_mcp.config import ServerSettings
from pec_mcp import server as server_module
from pec_mcp.server import STANDALONE_TOOLS, create_server
from pec_mcp.tools import get_db_conn


def test_saas_context_connection_is_still_supported():
    connection = object()
    ctx = SimpleNamespace(state={"db_conn": connection})
    assert get_db_conn(ctx) is connection


def test_fastmcp_lifespan_connection_is_supported():
    connection = object()
    ctx = SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context={"db_conn": connection})
    )
    assert get_db_conn(ctx) is connection


def test_missing_context_connection_has_clear_error():
    with pytest.raises(RuntimeError, match="Conexão clínica ausente"):
        get_db_conn(SimpleNamespace())


def test_standalone_lifespan_enforces_readonly_and_closes(monkeypatch):
    calls = []

    class FakeConnection:
        def set_session(self, **kwargs):
            calls.append(("set_session", kwargs))

        def close(self):
            calls.append(("close", None))

    connection = FakeConnection()
    monkeypatch.setattr(server_module, "get_connection", lambda dsn: connection)

    async def exercise_lifespan():
        lifespan = server_module._build_lifespan("test-dsn")
        async with lifespan(None) as state:
            assert state == {"db_conn": connection}

    asyncio.run(exercise_lifespan())
    assert calls == [
        ("set_session", {"readonly": True, "autocommit": True}),
        ("close", None),
    ]


def test_standalone_registers_the_clinical_tools_without_opening_database():
    server = create_server(
        settings=ServerSettings(),
        dsn="host=unused dbname=unused user=unused password=unused",
    )
    registered = {tool.name for tool in asyncio.run(server.list_tools())}
    expected = {tool.__name__ for tool in STANDALONE_TOOLS}
    assert registered == expected
    assert "obter_codigos_condicao_saude" in registered


def test_condition_code_tool_describes_aggregate_query_workflow():
    server = create_server(
        settings=ServerSettings(),
        dsn="host=unused dbname=unused user=unused password=unused",
    )
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    description = tools["obter_codigos_condicao_saude"].description

    assert "dados agregados" in description
    assert "informe" in description
    assert "codigos foram usados" in description
