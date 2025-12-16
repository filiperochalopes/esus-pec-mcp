from __future__ import annotations

import pytest

from pec_mcp.db import query_one
from pec_mcp.tools.contar_pacientes import contar_pacientes


def _find_any_cid_code(conn):
    row = query_one(conn, "SELECT nu_cid10 FROM tb_cid10 LIMIT 1;")
    if not row:
        return None
    return row["nu_cid10"]


def test_contar_pacientes_por_cid(ctx):
    cid_code = _find_any_cid_code(ctx.state["db_conn"])
    if not cid_code:
        pytest.skip("Base sem CID-10 para testar")

    result = contar_pacientes(ctx, cid_code=cid_code)
    assert isinstance(result, dict)
    assert "count" in result
    assert isinstance(result["count"], int)


def test_contar_pacientes_por_lista_cid(ctx):
    cid_code = _find_any_cid_code(ctx.state["db_conn"])
    if not cid_code:
        pytest.skip("Base sem CID-10 para testar")

    result = contar_pacientes(ctx, cid_codes=[cid_code], cid_logic="OR")
    assert isinstance(result, dict)
    assert "count" in result
    assert isinstance(result["count"], int)


def test_contar_pacientes_sem_filtro(ctx):
    with pytest.raises(ValueError):
        contar_pacientes(ctx)
