"""
Helpers compartilhados entre as tools MCP.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from mcp.server.fastmcp import Context


def get_db_conn(ctx: Context):
    """
    Obtém conexão de banco armazenada no estado do contexto.

    Preferimos lançar erro claro caso o lifespan não tenha provisionado
    a conexão para evitar falhas silenciosas.
    """

    conn = ctx.state.get("db_conn")
    if conn is None:
        raise RuntimeError("Conexão do banco não encontrada no contexto MCP")
    return conn


def to_iso_datetime(value) -> Optional[str]:
    """
    Converte date/datetime para string ISO 8601 ou retorna None.
    """

    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    # Mantemos str(value) como fallback, útil para tipos como Decimal.
    return str(value)


__all__ = ["get_db_conn", "to_iso_datetime"]
