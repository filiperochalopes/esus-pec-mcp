"""
Fixtures compartilhadas para testes das tools MCP.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Garante que o pacote pec_mcp seja encontrado mesmo após mover o código
# para a raiz de mcp-server sem depender de PYTHONPATH externo.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "mcp-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

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


# Consulta simples para obter um paciente elegível para atendimentos,
# reaproveitada em múltiplos testes.
def find_paciente_com_atendimento(conn):
    rows = query_all(
        conn,
        """
        SELECT DISTINCT pr.co_cidadao AS paciente_id
        FROM tb_atend_prof ap
        JOIN tb_atend       a   ON a.co_seq_atend       = ap.co_atend
        JOIN tb_prontuario  pr  ON pr.co_seq_prontuario = a.co_prontuario
        LEFT JOIN tb_lotacao l  ON l.co_ator_papel      = ap.co_lotacao
        LEFT JOIN tb_cbo     cb ON cb.co_cbo            = l.co_cbo
        WHERE cb.co_cbo_2002 LIKE '225%%'
           OR cb.co_cbo_2002 LIKE '2235%%'
        LIMIT 1;
        """,
    )
    if not rows:
        return None
    return rows[0]["paciente_id"]


__all__ = ["db_conn", "ctx", "query_all"]
