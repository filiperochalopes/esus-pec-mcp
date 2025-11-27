"""
Tools analíticas para consultas epidemiológicas e pessoais.

Implementamos catálogo fechado de consultas para manter segurança e
previsibilidade (sem SQL arbitrário). As consultas usam o usuário de
somente leitura fornecido.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import EpidemiologiaComorbidadeResult, PessoalFiltroResult
from . import get_db_conn, to_iso_datetime

EpidemiologiaTipo = Literal["comorbidades_por_filtro"]

PessoalTipo = Literal[
    "sem_atendimento_ano",
    "gestante_sem_atendimento_mes",
    "hipertenso_sem_atendimento_6m",
    "hba1c_maior_8",
    "pa_maior_140_90",
]


def _age_filter_clause(alias: str = "c") -> str:
    """
    Retorna expressão de idade em anos para reuso nas consultas.
    """

    return f"DATE_PART('year', AGE(CURRENT_DATE, {alias}.dt_nascimento))"


def consulta_epidemiologia(
    ctx: Context,
    tipo: EpidemiologiaTipo = "comorbidades_por_filtro",
    sexo: Optional[str] = None,
    idade_min: Optional[int] = None,
    idade_max: Optional[int] = None,
    localidade_id: Optional[int] = None,
    limite: int = 50,
) -> List[EpidemiologiaComorbidadeResult]:
    """
    Consulta agregada para apoiar análises epidemiológicas.

    - comorbidades_por_filtro: conta pacientes com problemas (CID-10)
      aplicando filtros opcionais de sexo, faixa etária e localidade.
    """

    if tipo != "comorbidades_por_filtro":
        raise ValueError("Tipo de consulta epidemiológica não suportado")

    conn = get_db_conn(ctx)
    safe_limit = max(1, min(limite, 500))

    age_expr = _age_filter_clause("c")
    filters = [
        ("sexo", sexo, "c.no_sexo = %s"),
        ("idade_min", idade_min, f"{age_expr} >= %s"),
        ("idade_max", idade_max, f"{age_expr} <= %s"),
        ("localidade_id", localidade_id, "c.co_localidade_endereco = %s"),
    ]

    where_clauses = []
    params: list = []
    for _, value, clause in filters:
        if value is not None:
            where_clauses.append(clause)
            params.append(value)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
    WITH base AS (
        SELECT
            pr.co_cidadao,
            cid.nu_cid10      AS codigo_cid10,
            cid.no_cid10      AS descricao_cid10,
            c.no_sexo         AS sexo,
            c.co_localidade_endereco AS localidade_id,
            {_age_filter_clause("c")} AS idade
        FROM tb_problema p
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = p.co_prontuario
        JOIN tb_cidadao c ON c.co_seq_cidadao = pr.co_cidadao
        LEFT JOIN tb_cid10 cid ON cid.co_cid10 = p.co_cid10
    ),
    filtrado AS (
        SELECT * FROM base
        {where_sql}
    )
    SELECT
        codigo_cid10,
        descricao_cid10,
        sexo,
        CASE
            WHEN idade IS NULL THEN NULL
            WHEN idade < 12 THEN '0-11'
            WHEN idade BETWEEN 12 AND 17 THEN '12-17'
            WHEN idade BETWEEN 18 AND 39 THEN '18-39'
            WHEN idade BETWEEN 40 AND 59 THEN '40-59'
            ELSE '60+'
        END AS faixa_etaria,
        localidade_id,
        COUNT(DISTINCT co_cidadao) AS total_pacientes
    FROM filtrado
    GROUP BY codigo_cid10, descricao_cid10, sexo, faixa_etaria, localidade_id
    ORDER BY total_pacientes DESC NULLS LAST
    LIMIT %s;
    """

    rows = query_all(conn, sql, params + [safe_limit])
    results: List[EpidemiologiaComorbidadeResult] = []
    for row in rows:
        results.append(
            EpidemiologiaComorbidadeResult(
                codigo_cid10=row.get("codigo_cid10"),
                descricao_cid10=row.get("descricao_cid10"),
                sexo=row.get("sexo"),
                faixa_etaria=row.get("faixa_etaria"),
                localidade_id=row.get("localidade_id"),
                total_pacientes=int(row.get("total_pacientes", 0)),
            )
        )
    return results


def _consulta_sem_atendimento(conn, dias: int, apenas_gestantes: bool = False, cid_filtro: Optional[str] = None, limite: int = 50) -> List[PessoalFiltroResult]:
    """
    Consulta pessoas sem atendimento em X dias, com filtros opcionais.
    """

    gestante_join = ""
    gestante_where = ""
    if apenas_gestantes:
        gestante_join = """
        JOIN tb_pre_natal pn ON pn.co_prontuario = pr.co_seq_prontuario
        """
        gestante_where = "AND pn.dt_desfecho IS NULL"

    cid_join = ""
    cid_where = ""
    if cid_filtro:
        cid_join = "JOIN tb_problema p ON p.co_prontuario = pr.co_seq_prontuario JOIN tb_cid10 cid ON cid.co_cid10 = p.co_cid10"
        cid_where = "AND cid.nu_cid10 LIKE %s"

    sql = f"""
    WITH ult AS (
        SELECT
            pr.co_cidadao,
            MAX(a.dt_inicio)::date AS ultima_data
        FROM tb_atend a
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = a.co_prontuario
        {cid_join}
        GROUP BY pr.co_cidadao
    )
    SELECT
        c.co_seq_cidadao AS paciente_id,
        c.no_cidadao     AS nome_paciente,
        ult.ultima_data  AS data_referencia
    FROM ult
    JOIN tb_cidadao c ON c.co_seq_cidadao = ult.co_cidadao
    JOIN tb_prontuario pr ON pr.co_cidadao = c.co_seq_cidadao
    {gestante_join}
    WHERE (ult.ultima_data IS NULL OR ult.ultima_data < CURRENT_DATE - INTERVAL %s)
    {gestante_where}
    {cid_where}
    ORDER BY ult.ultima_data NULLS FIRST
    LIMIT %s;
    """

    params: list = [f"{dias} days"]
    if cid_filtro:
        params.append(cid_filtro)
    params.append(limite)
    rows = query_all(conn, sql, params)
    results: List[PessoalFiltroResult] = []
    for row in rows:
        results.append(
            PessoalFiltroResult(
                paciente_id=int(row["paciente_id"]),
                nome_paciente=row.get("nome_paciente"),
                data_referencia=to_iso_datetime(row.get("data_referencia")),
                detalhe=None,
                metrica=None,
            )
        )
    return results


def _consulta_hba1c_maior_8(conn, limite: int = 50) -> List[PessoalFiltroResult]:
    sql = """
    WITH ex AS (
        SELECT
            pr.co_cidadao AS paciente_id,
            er.dt_realizacao,
            er.dt_resultado,
            hg.vl_hemoglobina_glicada,
            ROW_NUMBER() OVER (
                PARTITION BY pr.co_cidadao
                ORDER BY COALESCE(er.dt_resultado, er.dt_realizacao) DESC NULLS LAST, er.co_seq_exame_requisitado DESC
            ) AS rn
        FROM tb_exame_hemoglobina_glicada hg
        JOIN tb_exame_requisitado er ON er.co_seq_exame_requisitado = hg.co_exame_requisitado
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = er.co_prontuario
    )
    SELECT * FROM ex
    WHERE rn = 1 AND vl_hemoglobina_glicada > 8
    ORDER BY COALESCE(dt_resultado, dt_realizacao) DESC NULLS LAST
    LIMIT %s;
    """
    rows = query_all(conn, sql, (limite,))
    results: List[PessoalFiltroResult] = []
    for row in rows:
        data_ref = row.get("dt_resultado") or row.get("dt_realizacao")
        results.append(
            PessoalFiltroResult(
                paciente_id=int(row["paciente_id"]),
                nome_paciente=None,
                data_referencia=to_iso_datetime(data_ref),
                detalhe="HbA1c",
                metrica=str(row.get("vl_hemoglobina_glicada")) if row.get("vl_hemoglobina_glicada") is not None else None,
            )
        )
    return results


def _consulta_pa_maior_140_90(conn, limite: int = 50) -> List[PessoalFiltroResult]:
    sql = """
    WITH pa AS (
        SELECT
            pr.co_cidadao AS paciente_id,
            m.dt_medicao,
            m.nu_medicao_pressao_arterial,
            NULLIF(split_part(m.nu_medicao_pressao_arterial, '/', 1), '')::int AS sistolica,
            NULLIF(split_part(m.nu_medicao_pressao_arterial, '/', 2), '')::int AS diastolica,
            ROW_NUMBER() OVER (PARTITION BY pr.co_cidadao ORDER BY m.dt_medicao DESC NULLS LAST, m.co_seq_medicao DESC) AS rn
        FROM tb_medicao m
        JOIN tb_atend_prof ap ON ap.co_seq_atend_prof = m.co_atend_prof
        JOIN tb_atend a ON a.co_seq_atend = ap.co_atend
        JOIN tb_prontuario pr ON pr.co_seq_prontuario = a.co_prontuario
        WHERE m.nu_medicao_pressao_arterial IS NOT NULL
    )
    SELECT * FROM pa
    WHERE rn = 1 AND (
        (sistolica IS NOT NULL AND sistolica > 140) OR
        (diastolica IS NOT NULL AND diastolica > 90)
    )
    ORDER BY dt_medicao DESC NULLS LAST
    LIMIT %s;
    """
    rows = query_all(conn, sql, (limite,))
    results: List[PessoalFiltroResult] = []
    for row in rows:
        results.append(
            PessoalFiltroResult(
                paciente_id=int(row["paciente_id"]),
                nome_paciente=None,
                data_referencia=to_iso_datetime(row.get("dt_medicao")),
                detalhe="PA",
                metrica=row.get("nu_medicao_pressao_arterial"),
            )
        )
    return results


def consulta_pessoal(
    ctx: Context,
    tipo: PessoalTipo,
    limite: int = 50,
) -> List[PessoalFiltroResult]:
    """
    Consulta pacientes que atendem a filtros pré-definidos.

    Tipos:
    - sem_atendimento_ano: último atendimento há > 365 dias
    - gestante_sem_atendimento_mes: gestante ativa sem atendimento há > 30 dias
    - hipertenso_sem_atendimento_6m: paciente com CID-10 hipertensivo e última consulta há > 180 dias
    - hba1c_maior_8: último exame de HbA1c > 8%
    - pa_maior_140_90: última PA registrada > 140/90
    """

    conn = get_db_conn(ctx)
    safe_limit = max(1, min(limite, 500))

    if tipo == "sem_atendimento_ano":
        return _consulta_sem_atendimento(conn, dias=365, limite=safe_limit)
    if tipo == "gestante_sem_atendimento_mes":
        return _consulta_sem_atendimento(conn, dias=30, apenas_gestantes=True, limite=safe_limit)
    if tipo == "hipertenso_sem_atendimento_6m":
        # CID-10 hipertensão primária costuma ser I10 (prefixo I10)
        return _consulta_sem_atendimento(conn, dias=180, cid_filtro="I10%%", limite=safe_limit)
    if tipo == "hba1c_maior_8":
        return _consulta_hba1c_maior_8(conn, limite=safe_limit)
    if tipo == "pa_maior_140_90":
        return _consulta_pa_maior_140_90(conn, limite=safe_limit)

    raise ValueError("Tipo de consulta pessoal não suportado")


__all__ = ["consulta_epidemiologia", "consulta_pessoal"]
