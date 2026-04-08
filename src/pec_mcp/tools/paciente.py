"""
Tool minimalista para capturar dados de pacientes de forma anonimizada.
"""

from __future__ import annotations

from typing import List, Optional

from mcp.server.fastmcp import Context

from ..db import query_all
from ..domain.patient import compute_age_display, to_initials
from ..models import PatientCaptureResult
from . import get_db_conn
from .filters import build_patient_filters

_SQL_BASE = """
SELECT
    c.co_seq_cidadao AS paciente_id,
    c.no_cidadao     AS nome_paciente,
    c.dt_nascimento  AS data_nascimento,
    c.no_sexo        AS sexo
FROM tb_cidadao c
{where_clause}
ORDER BY c.co_seq_cidadao
LIMIT %s;
"""


def capturar_paciente(
    ctx: Context,
    paciente_id: Optional[int] = None,
    name_starts_with: Optional[str] = None,
    sex: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    unidade_saude_id: Optional[int] = None,
    equipe_id: Optional[int] = None,
    micro_area: Optional[str] = None,
    limite: int = 50,
) -> List[PatientCaptureResult]:
    """
    Retorna dados mínimos de pacientes sem identificadores diretos (somente leitura).

    Exige ao menos um critério (id, prefixo de nome, sexo ou faixa etária) para evitar varreduras amplas.
    Aceita filtro opcional de unidade de saúde (atendimento ou vinculação por CNES),
    equipe (co_seq_equipe) e microárea (nu_micro_area atual via cadastro individual).
    """

    safe_limit = max(1, min(limite, 200))
    clauses, params = build_patient_filters(
        paciente_id,
        name_starts_with,
        sex,
        age_min,
        age_max,
        unidade_saude_id=unidade_saude_id,
        equipe_id=equipe_id,
        micro_area=micro_area,
        alias="c",
    )
    if not clauses:
        raise ValueError("Informe pelo menos um critério (id, prefixo de nome, sexo ou idade).")

    where_clause = "WHERE " + " AND ".join(clauses)
    sql = _SQL_BASE.format(where_clause=where_clause)
    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, params + [safe_limit])

    results: List[PatientCaptureResult] = []
    for row in rows:
        sexo_val = str(row.get("sexo")) if row.get("sexo") is not None else None
        results.append(
            PatientCaptureResult(
                paciente_id=int(row["paciente_id"]),
                name=to_initials(row.get("nome_paciente")),
                age=compute_age_display(row.get("data_nascimento")),
                sex=sexo_val,
            )
        )
    return results


__all__ = ["capturar_paciente"]
