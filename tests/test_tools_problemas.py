from __future__ import annotations

import pytest

from pec_mcp.db import query_all
from pec_mcp.tools.problemas import listar_problemas_paciente


def _find_paciente_com_problema(conn) -> int | None:
    rows = query_all(
        conn,
        """
        SELECT DISTINCT pr.co_cidadao AS paciente_id
        FROM tb_problema p
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
        LIMIT 1;
        """,
    )
    if not rows:
        return None
    return rows[0]["paciente_id"]


def test_listar_problemas_paciente(ctx, db_conn):
    paciente_id = _find_paciente_com_problema(db_conn)
    if paciente_id is None:
        pytest.skip("Nenhum paciente com problemas cadastrado para testar")

    resultados = listar_problemas_paciente(ctx, paciente_id=paciente_id)
    assert isinstance(resultados, list)
    if not resultados:
        pytest.skip("Paciente não retornou problemas para validar campos")

    ids = set()
    for item in resultados:
        assert item["problema_id"] not in ids
        ids.add(item["problema_id"])
        assert "codigo_cid10" in item
        assert "descricao_cid10" in item
        assert item["paciente_id"] == paciente_id
