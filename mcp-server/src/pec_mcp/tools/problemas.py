"""
Tool para listar problemas/comorbidades do paciente.
"""

from __future__ import annotations

from typing import List

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import ProblemaResult
from . import get_db_conn, to_iso_datetime

_SQL_PROBLEMAS = """
WITH ultima_evolucao AS (
    SELECT DISTINCT ON (e.co_unico_problema)
        e.co_unico_problema,
        e.dt_inicio_problema,
        e.dt_fim_problema,
        e.co_situacao_problema,
        e.ds_observacao
    FROM tb_problema_evolucao e
    ORDER BY e.co_unico_problema, e.dt_inicio_problema DESC NULLS LAST
)
SELECT
    p.co_seq_problema             AS problema_id,
    pr.co_cidadao                 AS paciente_id,
    cid.nu_cid10                  AS codigo_cid10,
    cid.no_cid10                  AS descricao_cid10,
    ue.dt_inicio_problema,
    ue.dt_fim_problema,
    ue.co_situacao_problema       AS situacao_id,
    ue.ds_observacao              AS observacao
FROM tb_problema p
JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
LEFT JOIN ultima_evolucao ue ON ue.co_unico_problema = p.co_unico_problema
LEFT JOIN tb_cid10 cid       ON cid.co_cid10 = p.co_cid10
WHERE pr.co_cidadao = %s
ORDER BY ue.dt_inicio_problema NULLS LAST, p.co_seq_problema;
"""


def listar_problemas_paciente(ctx: Context, paciente_id: int) -> List[ProblemaResult]:
    """
    Lista problemas (CID-10) do paciente considerando a última evolução.
    """

    conn = get_db_conn(ctx)
    rows = query_all(conn, _SQL_PROBLEMAS, (paciente_id,))

    results: List[ProblemaResult] = []
    for row in rows:
        results.append(
            ProblemaResult(
                problema_id=int(row["problema_id"]),
                paciente_id=int(row["paciente_id"]),
                codigo_cid10=str(row.get("codigo_cid10")) if row.get("codigo_cid10") is not None else None,
                descricao_cid10=str(row.get("descricao_cid10")) if row.get("descricao_cid10") is not None else None,
                dt_inicio_problema=to_iso_datetime(row.get("dt_inicio_problema")),
                dt_fim_problema=to_iso_datetime(row.get("dt_fim_problema")),
                situacao_id=str(row.get("situacao_id")) if row.get("situacao_id") is not None else None,
                observacao=str(row.get("observacao")) if row.get("observacao") is not None else None,
            )
        )
    return results


__all__ = ["listar_problemas_paciente"]
