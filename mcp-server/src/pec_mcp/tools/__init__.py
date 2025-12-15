"""
Helpers compartilhados entre as tools MCP.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from ..db import get_connection

from mcp.server.fastmcp import Context

_GLOBAL_CONN = None  # Fallback para versões do FastMCP sem lifecycle


def get_db_conn(ctx: Context):
    """
    Obtém conexão de banco armazenada no estado do contexto.

    Se o FastMCP da runtime não suportar lifecycle (@lifespan), fazemos
    fallback para uma conexão global compartilhada para manter
    compatibilidade.
    """

    global _GLOBAL_CONN

    conn: Optional[object] = None
    state = getattr(ctx, "state", None)
    if isinstance(state, dict):
        conn = state.get("db_conn")

    if conn is None:
        if _GLOBAL_CONN is None or getattr(_GLOBAL_CONN, "closed", False):
            _GLOBAL_CONN = get_connection()
        conn = _GLOBAL_CONN
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
