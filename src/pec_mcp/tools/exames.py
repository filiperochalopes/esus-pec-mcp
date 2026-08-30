"""Tools de resultados laboratoriais estruturados úteis ao seguimento longitudinal."""

from __future__ import annotations

from typing import List

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import HbA1cResult
from . import get_db_conn, to_iso_datetime

_SQL_HBA1C = """
WITH grupos_paciente AS (
    SELECT DISTINCT COALESCE(pr.co_prontuario_grupo, pr.co_seq_prontuario) AS grupo_id
    FROM tb_prontuario pr
    WHERE pr.co_cidadao = %s
)
SELECT
    hg.vl_hemoglobina_glicada AS valor_percentual,
    er.dt_realizacao,
    er.dt_resultado
FROM tb_exame_hemoglobina_glicada hg
JOIN tb_exame_requisitado er
  ON er.co_seq_exame_requisitado = hg.co_exame_requisitado
JOIN tb_prontuario pr ON pr.co_seq_prontuario = er.co_prontuario
JOIN grupos_paciente gp
  ON gp.grupo_id = COALESCE(pr.co_prontuario_grupo, pr.co_seq_prontuario)
WHERE (%s IS NULL OR COALESCE(er.dt_resultado, er.dt_realizacao) >= %s::timestamp)
  AND (%s IS NULL OR COALESCE(er.dt_resultado, er.dt_realizacao) <= %s::timestamp)
ORDER BY COALESCE(er.dt_resultado, er.dt_realizacao) DESC NULLS LAST,
         er.co_seq_exame_requisitado DESC
LIMIT %s
"""


def listar_resultados_hba1c(
    ctx: Context,
    paciente_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    limite: int = 50,
) -> List[HbA1cResult]:
    """Lista o histórico de hemoglobina glicada (HbA1c) do paciente."""

    paciente_id_int = int(paciente_id)
    if paciente_id_int <= 0:
        raise ValueError("paciente_id deve ser um inteiro positivo.")
    safe_limit = max(1, min(int(limite), 200))
    params = (
        paciente_id_int,
        data_inicio,
        data_inicio,
        data_fim,
        data_fim,
        safe_limit,
    )
    rows = query_all(get_db_conn(ctx), _SQL_HBA1C, params)
    return [
        HbA1cResult(
            paciente_id=paciente_id_int,
            valor_percentual=float(row["valor_percentual"])
            if row.get("valor_percentual") is not None
            else None,
            data_realizacao=to_iso_datetime(row.get("dt_realizacao")),
            data_resultado=to_iso_datetime(row.get("dt_resultado")),
        )
        for row in rows
    ]


__all__ = ["listar_resultados_hba1c"]
