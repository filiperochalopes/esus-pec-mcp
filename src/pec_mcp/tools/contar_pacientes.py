"""
Tool para contar pacientes únicos aplicando filtros de paciente/condição.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import Context

from ..db import query_one
from ..models import CountResult
from . import get_db_conn
from .filters import build_condition_filters, build_patient_filters

_CTE_ULTIMA_EVOLUCAO = """
WITH ultima_evolucao AS (
    SELECT DISTINCT ON (e.co_unico_problema)
        e.co_unico_problema,
        e.ds_observacao
    FROM tb_problema_evolucao e
    ORDER BY e.co_unico_problema, e.co_sequencial_evolucao DESC, e.dt_inicio_problema DESC NULLS LAST
)
"""


def contar_pacientes(
    ctx: Context,
    paciente_id: Optional[int] = None,
    name_starts_with: Optional[str] = None,
    sex: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    unidade_saude_id: Optional[int] = None,
    cid_code: Optional[str] = None,
    cid_codes: Optional[list[str]] = None,
    ciap_code: Optional[str] = None,
    ciap_codes: Optional[list[str]] = None,
    condition_text: Optional[str] = None,
    cid_logic: str = "OR",
    cid_ciap_logic: str = "OR",
) -> CountResult:
    """
    Retorna apenas a contagem de pacientes distintos de acordo com filtros.
    Aceita filtro opcional de unidade de saúde (atendimento ou vinculação por CNES).
    """

    patient_clauses, patient_params = build_patient_filters(
        paciente_id,
        name_starts_with,
        sex,
        age_min,
        age_max,
        unidade_saude_id=unidade_saude_id,
        alias="c",
    )
    condition_clauses, condition_params = build_condition_filters(
        cid_code=cid_code,
        cid_codes=cid_codes,
        ciap_code=ciap_code,
        ciap_codes=ciap_codes,
        condition_text=condition_text,
        cid_logic=cid_logic,
        cid_ciap_logic=cid_ciap_logic,
        allow_cid_and=True,
        patient_alias="c",
    )

    clauses = patient_clauses + condition_clauses
    params = patient_params + condition_params

    if not clauses:
        raise ValueError("Informe pelo menos um critério de paciente ou condição.")

    where_sql = "WHERE " + " AND ".join(clauses)

    use_conditions = bool(condition_clauses)
    cte_sql = _CTE_ULTIMA_EVOLUCAO if use_conditions else ""
    condition_join = ""
    if use_conditions:
        condition_join = """
JOIN tb_problema p ON p.co_prontuario = pr.co_seq_prontuario
LEFT JOIN tb_cid10 cid ON cid.co_cid10 = p.co_cid10
LEFT JOIN tb_ciap ciap ON ciap.co_seq_ciap = p.co_ciap
LEFT JOIN ultima_evolucao ue ON ue.co_unico_problema = p.co_unico_problema
"""

    sql = f"""
{cte_sql}
SELECT COUNT(DISTINCT c.co_seq_cidadao) AS total
FROM tb_cidadao c
JOIN tb_prontuario pr ON pr.co_cidadao = c.co_seq_cidadao
{condition_join}
{where_sql};
"""

    conn = get_db_conn(ctx)
    row = query_one(conn, sql, params)
    total = int(row["total"]) if row and row.get("total") is not None else 0
    return CountResult(count=total)


__all__ = ["contar_pacientes"]
