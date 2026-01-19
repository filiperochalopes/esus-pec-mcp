"""
Tool para listar gestações em acompanhamento pré-natal.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import GestanteResult
from . import get_db_conn, to_iso_datetime

# Consulta baseada no enunciado. Se o schema real divergir, ajustar aqui.
_SQL_GESTANTES = """
WITH g AS (
    SELECT
        pn.co_seq_pre_natal          AS gestacao_id,
        pr.co_cidadao                AS paciente_id,
        c.no_cidadao                 AS nome_paciente,
        pn.dt_ultima_menstruacao,
        pn.dt_desfecho,
        pn.tp_gravidez,
        pn.st_alto_risco,
        ex.dt_provavel_parto_eco,
        (CURRENT_DATE - pn.dt_ultima_menstruacao::date) AS gest_days
    FROM tb_pre_natal pn
    JOIN tb_prontuario pr ON pr.co_seq_prontuario = pn.co_prontuario
    JOIN tb_cidadao   c  ON c.co_seq_cidadao     = pr.co_cidadao
    LEFT JOIN tb_exame_prenatal ex ON ex.co_exame_requisitado = pn.co_seq_pre_natal
    WHERE pn.dt_desfecho IS NULL
)
SELECT
    g.gestacao_id,
    g.paciente_id,
    g.nome_paciente,
    COALESCE(
        g.dt_provavel_parto_eco,
        (g.dt_ultima_menstruacao::date + INTERVAL '280 days')::date
    )                                            AS dpp,
    (g.gest_days / 7)                            AS idade_gestacional_semanas,
    (g.gest_days %% 7)                           AS idade_gestacional_dias,
    (g.gest_days / 7)::text
      || 's' ||
    (g.gest_days %% 7)::text
      || 'd'                                     AS idade_gestacional_str,
    g.tp_gravidez,
    g.st_alto_risco,
    'ativa'                                      AS situacao
FROM g
WHERE
    g.gest_days BETWEEN %s AND %s   -- 1s a 42s
    {trimestre_clause}
ORDER BY dpp
LIMIT %s;
"""

_TRIMESTRE_RANGE = {
    "primeiro": (1, 12),
    "1": (1, 12),
    "1o": (1, 12),
    "segundo": (13, 26),
    "2": (13, 26),
    "2o": (13, 26),
    "terceiro": (27, 42),
    "3": (27, 42),
    "3o": (27, 42),
}


def _resolve_trimestre(trimestre: Optional[str]) -> Optional[Tuple[int, int]]:
    if trimestre is None:
        return None
    value = str(trimestre).strip().lower()
    if not value:
        return None
    if value in _TRIMESTRE_RANGE:
        return _TRIMESTRE_RANGE[value]
    raise ValueError("trimestre inválido. Use: primeiro, segundo ou terceiro.")


def listar_gestantes(
    ctx: Context,
    limite: int = 50,
    trimestre: Optional[str] = None,
) -> List[GestanteResult]:
    """
    Lista gestações ativas entre 1 e 42 semanas de acompanhamento.
    """

    # Limitamos para evitar consultas excessivas em contextos de LLM.
    safe_limit = max(1, min(limite, 200))
    trimestre_range = _resolve_trimestre(trimestre)
    trimestre_clause = ""
    params: List = [7, 294]
    if trimestre_range is not None:
        trimestre_clause = "AND (g.gest_days / 7) BETWEEN %s AND %s"
        params.extend(list(trimestre_range))
    params.append(safe_limit)
    sql = _SQL_GESTANTES.format(trimestre_clause=trimestre_clause)
    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, params)

    results: List[GestanteResult] = []
    for row in rows:
        dpp_iso = to_iso_datetime(row.get("dpp"))
        semanas = row.get("idade_gestacional_semanas")
        dias = row.get("idade_gestacional_dias")
        results.append(
            GestanteResult(
                gestacao_id=int(row["gestacao_id"]),
                paciente_id=int(row["paciente_id"]),
                nome_paciente=str(row["nome_paciente"]),
                dpp=dpp_iso,
                idade_gestacional_semanas=int(semanas) if semanas is not None else None,
                idade_gestacional_dias=int(dias) if dias is not None else None,
                idade_gestacional_str=str(row.get("idade_gestacional_str"))
                if row.get("idade_gestacional_str") is not None
                else None,
                tp_gravidez=str(row.get("tp_gravidez")) if row.get("tp_gravidez") is not None else None,
                st_alto_risco=str(row.get("st_alto_risco")) if row.get("st_alto_risco") is not None else None,
                situacao=str(row.get("situacao", "ativa")),
            )
        )
    return results


__all__ = ["listar_gestantes"]
