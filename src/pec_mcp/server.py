"""Servidor FastMCP para execução standalone das tools clínicas."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ServerSettings, get_db_dsn, get_server_settings
from .db import get_connection
from .tools.atendimentos import listar_ultimos_atendimentos_soap
from .tools.condicoes import listar_condicoes_pacientes
from .tools.contar_pacientes import contar_pacientes
from .tools.medicoes import (
    listar_registros_antropometria,
    listar_registros_hgt,
    listar_registros_pa,
)
from .tools.exames import listar_resultados_hba1c
from .tools.gestantes import listar_gestantes
from .tools.obter_codigos_condicao_saude import obter_codigos_condicao_saude
from .tools.paciente import capturar_paciente
from .tools.prescricoes import listar_prescricoes_medicamentos
from .tools.unidades import listar_unidades_saude
from .tools.visitas_acs import listar_visitas_acs


STANDALONE_TOOLS = (
    capturar_paciente,
    obter_codigos_condicao_saude,
    listar_condicoes_pacientes,
    contar_pacientes,
    listar_unidades_saude,
    listar_ultimos_atendimentos_soap,
    listar_registros_antropometria,
    listar_registros_pa,
    listar_registros_hgt,
    listar_resultados_hba1c,
    listar_prescricoes_medicamentos,
    listar_visitas_acs,
    listar_gestantes,
)


def _build_lifespan(dsn: str | None):
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        connection = get_connection(dsn=dsn or get_db_dsn())
        connection.set_session(readonly=True, autocommit=True)
        try:
            yield {"db_conn": connection}
        finally:
            connection.close()

    return lifespan


def create_server(
    *,
    settings: ServerSettings | None = None,
    dsn: str | None = None,
) -> FastMCP:
    """Cria o servidor standalone; a conexão só é aberta no lifespan."""

    resolved_settings = settings or get_server_settings()

    server = FastMCP(
        "pec-mcp",
        host=resolved_settings.host,
        port=resolved_settings.port,
        lifespan=_build_lifespan(dsn),
    )
    for tool in STANDALONE_TOOLS:
        server.tool()(tool)
    return server


# Mantém um objeto importável para ASGI/composição e para clientes MCP.
mcp = create_server()


def main() -> None:
    """Inicia o processo standalone usando a configuração do ambiente."""

    settings = get_server_settings()
    server = create_server(settings=settings)
    server.run(transport=settings.transport)


if __name__ == "__main__":  # pragma: no cover - exercitado como processo
    main()


__all__ = ["STANDALONE_TOOLS", "create_server", "main", "mcp"]
