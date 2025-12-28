"""
Servidor MCP FastMCP para consultas clínicas no PEC.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .db import get_connection

# Instância global do servidor MCP.
mcp = FastMCP("pec-mcp")


if hasattr(mcp, "lifespan"):
    @mcp.lifespan
    async def lifespan(ctx: Context):
        """
        Abre conexão única com o banco durante o ciclo de vida do servidor.

        Mantemos a conexão no estado do contexto para ser reutilizada pelas tools,
        reduzindo overhead de abertura/fechamento (DRY/KISS).
        """

        conn = get_connection()
        ctx.state["db_conn"] = conn
        try:
            yield
        finally:
            # Garante fechamento limpo ao encerrar o servidor MCP.
            conn.close()
else:
    # Fallback para versões antigas do FastMCP sem suporte a @lifespan.
    # As tools farão fallback para uma conexão global compartilhada.
    pass


# Importações tardias para evitar ciclos antes da instância do MCP existir.
from .tools.paciente import capturar_paciente
from .tools.obter_codigos_condicao_saude import obter_codigos_condicao_saude
from .tools.condicoes import listar_condicoes_pacientes
from .tools.contar_pacientes import contar_pacientes
from .tools.unidades import listar_unidades_saude
from .tools.atendimentos import listar_ultimos_atendimentos_soap
from .tools.sem_consulta import contar_pacientes_sem_consulta, listar_pacientes_sem_consulta

# Registro das tools no MCP.
mcp.tool()(capturar_paciente)
mcp.tool()(obter_codigos_condicao_saude)
mcp.tool()(listar_condicoes_pacientes)
mcp.tool()(contar_pacientes)
mcp.tool()(listar_unidades_saude)
mcp.tool()(listar_ultimos_atendimentos_soap)
mcp.tool()(contar_pacientes_sem_consulta)
mcp.tool()(listar_pacientes_sem_consulta)


def main() -> Any:
    """
    Ponto de entrada do servidor MCP.
    """

    # O transporte "streamable-http" é adequado para execução local via mcp-cli.
    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_HTTP_PORT", "5174"))

    # Ajusta host/port diretamente nas settings do FastMCP (API pública).
    mcp.settings.host = host
    mcp.settings.port = port

    print(f"[pec-mcp] Iniciando Streamable HTTP em http://{host}:{port}")
    return mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
