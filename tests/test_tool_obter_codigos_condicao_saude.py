from __future__ import annotations

import pytest

from pec_mcp.db import query_one
from pec_mcp.tools.obter_codigos_condicao_saude import obter_codigos_condicao_saude


def _find_any_cid_name(conn):
    row = query_one(
        conn,
        """
        SELECT no_cid10
        FROM tb_cid10
        WHERE no_cid10 IS NOT NULL
          AND length(no_cid10) BETWEEN 4 AND 80
        LIMIT 1;
        """,
    )
    if not row:
        return None
    return row["no_cid10"]


def test_obter_codigos_condicao_saude_preset(ctx):
    result = obter_codigos_condicao_saude(ctx, condicao="gravidez")
    assert result["source"] == "preset"
    assert "Z34.9" in result["cid_codes"]
    assert "W03" in result["ciap_codes"]


def test_obter_codigos_condicao_saude_busca_db(ctx):
    cid_name = _find_any_cid_name(ctx.state["db_conn"])
    if not cid_name:
        pytest.skip("Base sem CID-10 para testar")

    result = obter_codigos_condicao_saude(ctx, condicao=cid_name, limite=5)
    assert result["source"] == "database"
    assert result["cid_codes"]


def test_obter_codigos_condicao_saude_sem_condicao(ctx):
    with pytest.raises(ValueError):
        obter_codigos_condicao_saude(ctx, condicao=" ")
