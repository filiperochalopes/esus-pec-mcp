"""
Tools para contar e listar pacientes sem consulta recente.
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional, Tuple

from mcp.server.fastmcp import Context

from ..db import query_all, query_one
from ..models import CountResult, PacienteSemConsultaResult
from . import get_db_conn, to_iso_date
from .filters import build_patient_filters

SemConsultaTipo = Literal["hipertensao", "diabetes", "gestante"]

_DEFAULT_DIAS = {
    "hipertensao": 180,  # ~6 meses
    "diabetes": 180,     # ~6 meses
    "gestante": 60,      # 60 dias
}

_HIPERTENSAO_CID = ["I10%", "I11%", "I12%", "I13%", "I15%"]
_HIPERTENSAO_CIAP = ["K86", "K87"]
_DIABETES_CID = ["E10%", "E11%", "E12%", "E13%", "E14%"]
_DIABETES_CIAP = ["T89", "T90"]

_CBO_MED_ENF = "(cb.co_cbo_2002 LIKE '225%%' OR cb.co_cbo_2002 LIKE '2235%%')"


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


def _normalize_tipo(tipo: SemConsultaTipo) -> str:
    if not tipo:
        raise ValueError("tipo é obrigatório.")
    normalized = str(tipo).strip().lower()
    if normalized not in _DEFAULT_DIAS:
        raise ValueError("tipo inválido. Use: hipertensao, diabetes ou gestante.")
    return normalized


def _resolve_dias(tipo: str, dias_sem_consulta: Optional[int]) -> int:
    if dias_sem_consulta is None:
        return _DEFAULT_DIAS[tipo]
    dias = int(dias_sem_consulta)
    if dias <= 0:
        raise ValueError("dias_sem_consulta deve ser um inteiro positivo.")
    return dias


def _build_base_sql(tipo: str) -> Tuple[str, List]:
    if tipo == "gestante":
        sql = """
        SELECT DISTINCT pr.co_cidadao AS paciente_id
        FROM tb_pre_natal pn
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = pn.co_prontuario
        WHERE pn.dt_desfecho IS NULL
          AND (CURRENT_DATE - pn.dt_ultima_menstruacao::date) BETWEEN 7 AND 294
        """
        return sql, []

    if tipo == "hipertensao":
        cid_patterns = _HIPERTENSAO_CID
        ciap_patterns = _HIPERTENSAO_CIAP
    elif tipo == "diabetes":
        cid_patterns = _DIABETES_CID
        ciap_patterns = _DIABETES_CIAP
    else:
        raise ValueError("tipo inválido.")

    sql = """
    SELECT DISTINCT pr.co_cidadao AS paciente_id
    FROM tb_problema p
    JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
    LEFT JOIN tb_cid10 cid ON cid.co_cid10 = p.co_cid10
    LEFT JOIN tb_ciap ciap ON ciap.co_seq_ciap = p.co_ciap
    WHERE (cid.nu_cid10 ILIKE ANY(%s) OR ciap.co_ciap ILIKE ANY(%s))
    """
    return sql, [cid_patterns, ciap_patterns]


def _build_sem_consulta_sql(
    tipo: str,
    unidade_saude_id: Optional[int],
    equipe_id: Optional[int],
    micro_area: Optional[str],
    dias_sem_consulta: int,
    select_sql: str,
    order_sql: str = "",
    limit_offset_sql: str = "",
) -> Tuple[str, List]:
    base_sql, base_params = _build_base_sql(tipo)

    ult_where = _CBO_MED_ENF
    ult_params: List = []
    unit_id = None
    if unidade_saude_id is not None:
        unit_id = int(unidade_saude_id)
        if unit_id <= 0:
            raise ValueError("unidade_saude_id deve ser um inteiro positivo.")
        ult_where += " AND a.co_unidade_saude = %s"
        ult_params.append(unit_id)

    patient_clauses, patient_params = build_patient_filters(
        paciente_id=None,
        name_prefix=None,
        sex=None,
        age_min=None,
        age_max=None,
        unidade_saude_id=unit_id,
        equipe_id=equipe_id,
        micro_area=micro_area,
        alias="c",
    )

    where_clauses = [
        "(ult.ultima_consulta IS NULL OR ult.ultima_consulta < CURRENT_DATE - INTERVAL %s)"
    ]
    where_clauses.extend(patient_clauses)
    where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
    WITH base_pacientes AS (
        {base_sql}
    ),
    ultima_consulta AS (
        SELECT
            pr.co_cidadao AS paciente_id,
            MAX(a.dt_inicio)::date AS ultima_consulta
        FROM tb_atend_prof ap
        JOIN tb_atend a ON a.co_seq_atend = ap.co_atend
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = a.co_prontuario
        LEFT JOIN tb_lotacao l ON l.co_ator_papel = ap.co_lotacao
        LEFT JOIN tb_cbo cb ON cb.co_cbo = l.co_cbo
        WHERE {ult_where}
        GROUP BY pr.co_cidadao
    )
    SELECT
        {select_sql}
    FROM base_pacientes bp
    JOIN tb_cidadao c ON c.co_seq_cidadao = bp.paciente_id
    LEFT JOIN ultima_consulta ult ON ult.paciente_id = bp.paciente_id
    {where_sql}
    {order_sql}
    {limit_offset_sql}
    """

    params = base_params + ult_params + [f"{dias_sem_consulta} days"] + patient_params
    return sql, params


def contar_pacientes_sem_consulta(
    ctx: Context,
    tipo: SemConsultaTipo,
    unidade_saude_id: Optional[int] = None,
    equipe_id: Optional[int] = None,
    micro_area: Optional[str] = None,
    dias_sem_consulta: Optional[int] = None,
) -> CountResult:
    """
    Conta pacientes sem consulta recente por perfil clínico.
    Aceita filtros opcionais de unidade, equipe e microárea.
    """

    tipo_norm = _normalize_tipo(tipo)
    dias = _resolve_dias(tipo_norm, dias_sem_consulta)

    sql, params = _build_sem_consulta_sql(
        tipo=tipo_norm,
        unidade_saude_id=unidade_saude_id,
        equipe_id=equipe_id,
        micro_area=micro_area,
        dias_sem_consulta=dias,
        select_sql="COUNT(DISTINCT bp.paciente_id) AS total",
    )

    conn = get_db_conn(ctx)
    row = query_one(conn, sql, params)
    total = int(row["total"]) if row and row.get("total") is not None else 0
    return CountResult(count=total)


def listar_pacientes_sem_consulta(
    ctx: Context,
    tipo: SemConsultaTipo,
    unidade_saude_id: Optional[int] = None,
    equipe_id: Optional[int] = None,
    micro_area: Optional[str] = None,
    dias_sem_consulta: Optional[int] = None,
    limite: int = 50,
    offset: int = 0,
) -> List[PacienteSemConsultaResult]:
    """
    Lista pacientes sem consulta recente por perfil clínico (com paginação).
    Aceita filtros opcionais de unidade, equipe e microárea.
    """

    tipo_norm = _normalize_tipo(tipo)
    dias = _resolve_dias(tipo_norm, dias_sem_consulta)

    safe_limit = max(1, min(int(limite), 200))
    safe_offset = max(0, int(offset))

    select_sql = """
        bp.paciente_id AS paciente_id,
        c.no_cidadao AS nome_paciente,
        c.dt_nascimento AS data_nascimento,
        c.no_sexo AS sexo,
        ult.ultima_consulta AS ultima_consulta,
        CASE
            WHEN ult.ultima_consulta IS NULL THEN NULL
            ELSE (CURRENT_DATE - ult.ultima_consulta)
        END AS dias_sem_consulta
    """

    sql, params = _build_sem_consulta_sql(
        tipo=tipo_norm,
        unidade_saude_id=unidade_saude_id,
        equipe_id=equipe_id,
        micro_area=micro_area,
        dias_sem_consulta=dias,
        select_sql=select_sql,
        order_sql="ORDER BY ult.ultima_consulta NULLS FIRST, bp.paciente_id",
        limit_offset_sql="LIMIT %s OFFSET %s",
    )
    params = params + [safe_limit, safe_offset]

    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, params)

    results: List[PacienteSemConsultaResult] = []
    for row in rows:
        initials = _to_initials(row.get("nome_paciente"))
        birth_date = to_iso_date(row.get("data_nascimento"))
        sexo_val = str(row.get("sexo")) if row.get("sexo") is not None else None
        ultima = to_iso_date(row.get("ultima_consulta"))
        dias_val = row.get("dias_sem_consulta")
        results.append(
            PacienteSemConsultaResult(
                paciente_id=int(row["paciente_id"]),
                paciente_initials=initials,
                birth_date=birth_date,
                sex=sexo_val,
                ultima_consulta=ultima,
                dias_sem_consulta=int(dias_val) if dias_val is not None else None,
            )
        )
    return results


__all__ = ["contar_pacientes_sem_consulta", "listar_pacientes_sem_consulta"]
