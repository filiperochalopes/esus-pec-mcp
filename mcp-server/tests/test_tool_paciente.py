from __future__ import annotations

import pytest

from pec_mcp.db import query_all
from pec_mcp.tools.paciente import capturar_paciente


def _find_any_paciente(conn):
    rows = query_all(conn, "SELECT co_seq_cidadao AS paciente_id FROM tb_cidadao LIMIT 1;")
    if not rows:
        return None
    return rows[0]["paciente_id"]


def test_capturar_paciente_por_id(ctx):
    paciente_id = _find_any_paciente(ctx.state["db_conn"])
    if not paciente_id:
        pytest.skip("Base sem pacientes disponíveis para teste")

    result = capturar_paciente(ctx, paciente_id=paciente_id, limite=1)
    assert isinstance(result, list)
    assert result, "Nenhum paciente retornado por ID"
    row = result[0]
    assert set(row.keys()) == {"name", "birth_date", "sex", "gender"}
    assert row["name"]
    assert row["name"].upper() == row["name"]


def test_capturar_paciente_por_filtros(ctx):
    results = capturar_paciente(ctx, name_starts_with="A", sex="MASCULINO", age_min=40, limite=5)
    if not results:
        pytest.skip("Nenhum paciente encontrado com prefixo A, sexo MASCULINO e idade >= 40")
    for row in results:
        assert row["name"]
        assert row["name"].upper() == row["name"]


def test_capturar_paciente_sem_filtros(ctx):
    with pytest.raises(ValueError):
        capturar_paciente(ctx)


def test_capturar_paciente_sexo_invalido(ctx):
    with pytest.raises(ValueError):
        capturar_paciente(ctx, sex="XYZ")
