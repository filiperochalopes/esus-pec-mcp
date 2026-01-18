"""
Camada fina de acesso a dados usando psycopg2.

Mantenha aqui apenas o essencial para evitar complexidade desnecessária
e facilitar testes (princípios KISS e YAGNI).
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import get_db_dsn


def get_connection(dsn: Optional[str] = None):
    """
    Abre conexão com o PostgreSQL usando RealDictCursor para devolver dicts.

    Quem chama gerencia o ciclo de vida (abrir/fechar), permitindo reuso
    de conexão no lifespan do servidor MCP.
    """

    return psycopg2.connect(dsn=dsn or get_db_dsn(), cursor_factory=RealDictCursor)


def query_all(conn, sql: str, params: Optional[Sequence] = None) -> list[dict]:
    """
    Executa consulta de leitura e retorna lista de dicionários.

    Mantemos helper simples para evitar repetição de boilerplate.
    """

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        rows: Iterable[dict] = cur.fetchall()
    return list(rows)


def query_one(conn, sql: str, params: Optional[Sequence] = None) -> Optional[dict]:
    """
    Executa consulta de leitura e retorna um único registro ou None.
    """

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
    return row if row is not None else None


__all__ = ["get_connection", "query_all", "query_one"]
