"""
Servidor MCP FastMCP para consultas clínicas no PEC.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .db import get_connection

# Instância global do servidor MCP.
mcp = FastMCP("pec-mcp")


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


# Importações tardias para evitar ciclos antes da instância do MCP existir.
from .tools.gestantes import listar_gestantes
from .tools.problemas import listar_problemas_paciente
from .tools.atendimentos import listar_ultimos_atendimentos_soap
from .tools.analytics import consulta_epidemiologia, consulta_pessoal

# Registro das tools no MCP.
mcp.tool()(listar_gestantes)
mcp.tool()(listar_problemas_paciente)
mcp.tool()(listar_ultimos_atendimentos_soap)
mcp.tool()(consulta_epidemiologia)
mcp.tool()(consulta_pessoal)


def main() -> Any:
    """
    Ponto de entrada do servidor MCP.
    """

    # O transporte "streamable-http" é adequado para execução local via mcp-cli.
    return mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
