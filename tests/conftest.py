"""
Fixtures compartilhadas para testes das tools MCP.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Garante que o pacote pec_mcp seja encontrado adicionando mcp-server/src ao sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../mcp-server
SERVER_SRC = PROJECT_ROOT / "src"
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))

from pec_mcp.db import get_connection, query_all


def _connect_or_skip():
    """
    Tenta abrir conexão; se indisponível, pula os testes dependentes.
    """

    try:
        conn = get_connection()
    except Exception as exc:  # pragma: no cover - depende do ambiente local
        pytest.skip(f"Banco indisponível para testes: {exc}")
    return conn


@pytest.fixture()
def db_conn():
    conn = _connect_or_skip()
    try:
        yield conn
    finally:
        conn.close()


class DummyContext:
    """
    Contexto mínimo para invocar tools fora do runtime MCP.
    """

    def __init__(self, conn):
        self.state = {"db_conn": conn}


@pytest.fixture()
def ctx(db_conn):
    return DummyContext(db_conn)
__all__ = ["db_conn", "ctx", "query_all"]
