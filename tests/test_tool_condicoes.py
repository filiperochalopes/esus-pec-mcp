from __future__ import annotations

import pytest

from pec_mcp.db import query_all
from pec_mcp.tools.condicoes import listar_condicoes_pacientes


def _find_paciente_com_condicao(conn):
    rows = query_all(
        conn,
        """
        SELECT pr.co_cidadao AS paciente_id
        FROM tb_problema p
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
        LIMIT 1;
        """,
    )
    if not rows:
        return None
    return rows[0]["paciente_id"]


def test_listar_condicoes_por_paciente(ctx):
    paciente_id = _find_paciente_com_condicao(ctx.state["db_conn"])
    if not paciente_id:
        pytest.skip("Base sem condições registradas para teste")

    results = listar_condicoes_pacientes(ctx, paciente_id=paciente_id, limite=5)
    assert isinstance(results, list)
    assert results, "Nenhuma condição retornada"

    row = results[0]
    assert row["paciente_id"] == paciente_id
    assert row["paciente_initials"]
    assert row["paciente_initials"].upper() == row["paciente_initials"]
    assert set(row.keys()) == {
        "paciente_id",
        "paciente_initials",
        "birth_date",
        "sex",
        "condition_id",
        "cid_code",
        "cid_description",
        "ciap_code",
        "ciap_description",
        "dt_inicio_condicao",
        "dt_fim_condicao",
        "situacao_id",
        "observacao",
    }


def test_listar_condicoes_sem_filtros(ctx):
    with pytest.raises(ValueError):
        listar_condicoes_pacientes(ctx)
