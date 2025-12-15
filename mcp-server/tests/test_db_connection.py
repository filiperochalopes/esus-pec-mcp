from __future__ import annotations

import pytest

from pec_mcp.db import query_all


def test_can_connect_and_select(db_conn):
    row = query_all(db_conn, "SELECT 1 AS ok;")[0]
    assert row["ok"] == 1


def test_can_read_cidadao_table(db_conn):
    """
    Verifica se a tabela de cidadãos está acessível.
    """

    rows = query_all(db_conn, "SELECT co_seq_cidadao FROM tb_cidadao LIMIT 1;")
    if not rows:
        pytest.skip("Base sem registros em tb_cidadao para validar leitura")
    assert "co_seq_cidadao" in rows[0]
