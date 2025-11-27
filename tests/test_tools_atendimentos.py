from __future__ import annotations

import pytest

from pec_mcp.db import query_all
from pec_mcp.tools.atendimentos import listar_ultimos_atendimentos_soap


def _find_paciente_com_atendimento(conn) -> int | None:
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


def test_listar_ultimos_atendimentos(ctx, db_conn):
    paciente_id = _find_paciente_com_atendimento(db_conn)
    if paciente_id is None:
        pytest.fail("Nenhum paciente com atendimento elegível encontrado (CBO 225xx/2235x)")

    limite = 5
    resultados = listar_ultimos_atendimentos_soap(ctx, paciente_id=paciente_id, limite=limite)
    assert isinstance(resultados, list)
    assert len(resultados) > 0, "Esperava ao menos um atendimento elegível"
    assert len(resultados) <= limite

    esperado = {
        "atendimento_id",
        "paciente_id",
        "data_hora",
        "cbo_codigo",
        "cbo_descricao",
        "profissional",
        "tipo_profissional_id",
        "tipo_atendimento_id",
        "soap_s",
        "soap_o",
        "soap_a",
        "soap_p",
    }
    for item in resultados:
        assert esperado.issubset(item.keys())
        codigo = item.get("cbo_codigo") or ""
        assert codigo.startswith("225") or codigo.startswith("2235")
        assert item["paciente_id"] == paciente_id
