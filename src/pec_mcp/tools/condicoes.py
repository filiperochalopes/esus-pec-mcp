"""
Tool para listar condicoes de saude (CID/CIAP) registradas em pacientes.
"""

from __future__ import annotations

import re
from typing import List, Optional

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import ConditionResult
from . import get_db_conn, to_iso_date
from .filters import build_condition_filters, build_patient_filters

_SQL_CONDICOES = """
WITH ultima_evolucao AS (
    SELECT DISTINCT ON (e.co_unico_problema)
        e.co_unico_problema,
        e.dt_inicio_problema,
        e.dt_fim_problema,
        e.co_situacao_problema,
        e.ds_observacao
    FROM tb_problema_evolucao e
    ORDER BY e.co_unico_problema, e.co_sequencial_evolucao DESC, e.dt_inicio_problema DESC NULLS LAST
)
SELECT
    pr.co_cidadao              AS paciente_id,
    c.no_cidadao               AS nome_paciente,
    c.dt_nascimento            AS data_nascimento,
    c.no_sexo                  AS sexo,
    p.co_seq_problema          AS condition_id,
    cid.nu_cid10               AS cid_code,
    cid.no_cid10               AS cid_description,
    ciap.co_ciap               AS ciap_code,
    ciap.ds_ciap               AS ciap_description,
    ue.dt_inicio_problema      AS dt_inicio_condicao,
    ue.dt_fim_problema         AS dt_fim_condicao,
    ue.co_situacao_problema    AS situacao_id,
    ue.ds_observacao           AS observacao
FROM tb_problema p
JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
JOIN tb_cidadao c ON c.co_seq_cidadao = pr.co_cidadao
LEFT JOIN ultima_evolucao ue ON ue.co_unico_problema = p.co_unico_problema
LEFT JOIN tb_cid10 cid ON cid.co_cid10 = p.co_cid10
LEFT JOIN tb_ciap ciap ON ciap.co_seq_ciap = p.co_ciap
{where_clause}
ORDER BY ue.dt_inicio_problema NULLS LAST, p.co_seq_problema
LIMIT %s;
"""


def _to_initials(full_name: Optional[str]) -> str:
    """
    Converte nome completo em iniciais (ex.: "Joao de Carvalho Lima" -> "JCL").
    """

    if not full_name:
        return "N/A"
    parts = re.split(r"\s+", str(full_name).strip())
    skip = {"de", "da", "do", "das", "dos"}
    initials = [p[0].upper() for p in parts if p and p.lower() not in skip]
    return "".join(initials) if initials else "N/A"


def listar_condicoes_pacientes(
    ctx: Context,
    paciente_id: Optional[int] = None,
    name_starts_with: Optional[str] = None,
    sex: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    unidade_saude_id: Optional[int] = None,
    equipe_id: Optional[int] = None,
    micro_area: Optional[str] = None,
    cid_code: Optional[str] = None,
    cid_codes: Optional[list[str]] = None,
    ciap_code: Optional[str] = None,
    ciap_codes: Optional[list[str]] = None,
    condition_text: Optional[str] = None,
    cid_logic: str = "OR",
    cid_ciap_logic: str = "OR",
    limite: int = 50,
) -> List[ConditionResult]:
    """
    Lista condicoes de saude (CID/CIAP) registradas em pacientes.

    Exige pelo menos um criterio para evitar varreduras amplas.
    Aceita filtro opcional de unidade de saude (atendimento ou vinculacao por CNES),
    equipe (co_seq_equipe) e microárea (nu_micro_area atual via cadastro individual).
    Nao use para descobrir codigos; para isso, use obter_codigos_condicao_saude.
    """

    patient_clauses, patient_params = build_patient_filters(
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
    condition_clauses, condition_params = build_condition_filters(
        cid_code=cid_code,
        cid_codes=cid_codes,
        ciap_code=ciap_code,
        ciap_codes=ciap_codes,
        condition_text=condition_text,
        cid_logic=cid_logic,
        cid_ciap_logic=cid_ciap_logic,
        allow_cid_and=False,
        patient_alias="c",
    )

    all_clauses = patient_clauses + condition_clauses
    all_params = patient_params + condition_params

    if not all_clauses:
        raise ValueError("Informe pelo menos um critério de paciente ou condição.")

    where_clause = "WHERE " + " AND ".join(all_clauses)
    safe_limit = max(1, min(limite, 200))
    sql = _SQL_CONDICOES.format(where_clause=where_clause)

    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, all_params + [safe_limit])

    results: List[ConditionResult] = []
    for row in rows:
        initials = _to_initials(row.get("nome_paciente"))
        birth_date = to_iso_date(row.get("data_nascimento"))
        dt_inicio = to_iso_date(row.get("dt_inicio_condicao"))
        dt_fim = to_iso_date(row.get("dt_fim_condicao"))
        sexo_val = str(row.get("sexo")) if row.get("sexo") is not None else None
        results.append(
            ConditionResult(
                paciente_id=int(row["paciente_id"]),
                paciente_initials=initials,
                birth_date=birth_date,
                sex=sexo_val,
                condition_id=int(row["condition_id"]),
                cid_code=str(row.get("cid_code")) if row.get("cid_code") is not None else None,
                cid_description=str(row.get("cid_description")) if row.get("cid_description") is not None else None,
                ciap_code=str(row.get("ciap_code")) if row.get("ciap_code") is not None else None,
                ciap_description=str(row.get("ciap_description")) if row.get("ciap_description") is not None else None,
                dt_inicio_condicao=dt_inicio,
                dt_fim_condicao=dt_fim,
                situacao_id=str(row.get("situacao_id")) if row.get("situacao_id") is not None else None,
                observacao=str(row.get("observacao")) if row.get("observacao") is not None else None,
            )
        )
    return results


__all__ = ["listar_condicoes_pacientes"]
