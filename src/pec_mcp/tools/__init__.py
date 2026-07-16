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

    A conexão deve ser injetada pelo contexto autenticado da instalação.
    """

    conn: Optional[object] = None
    # O SaaS usa um contexto mínimo com ``state`` para injetar a conexão.
    state = getattr(ctx, "state", None)
    if isinstance(state, dict):
        conn = state.get("db_conn")

    # O servidor FastMCP standalone entrega o valor produzido pelo lifespan
    # por meio do request_context.
    if conn is None:
        try:
            request_context = ctx.request_context
        except (AttributeError, ValueError):
            request_context = None
        lifespan_context = getattr(request_context, "lifespan_context", None)
        if isinstance(lifespan_context, dict):
            conn = lifespan_context.get("db_conn")

    if conn is None:
        raise RuntimeError("Conexão clínica ausente no contexto da tool.")
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


def to_iso_date(value) -> Optional[str]:
    """
    Converte date/datetime para string ISO (apenas data) ou retorna None.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


__all__ = ["get_db_conn", "to_iso_datetime", "to_iso_date"]
