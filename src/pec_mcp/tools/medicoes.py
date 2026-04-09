"""
Tools para registros de medições clínicas (antropometria, PA, HGT).

Cada tool consolida dados de DUAS fontes distintas via UNION ALL:

1. **PEC (atendimento clínico)** — tabela `tl_medicao`
   Cadeia de joins: tl_medicao → tb_atend_prof → tb_atend → tb_prontuario → tb_cidadao
   Profissional via: tb_atend_prof → tb_lotacao → tb_prof (nome, co_seq_prof) + tb_cbo (CBO)
   Quem registra: médicos (CBO 225xxx), enfermeiros (CBO 2235xx), etc.

2. **Visita domiciliar (CDS)** — tabela `tb_fat_visita_domiciliar`
   Paciente via: tb_fat_cidadao_pec.co_cidadao (= tb_cidadao.co_seq_cidadao)
   Profissional via: tb_dim_profissional (nome, co_seq_dim_profissional) + tb_dim_cbo (CBO)
   Quem registra: ACS (CBO 515105), outros agentes de saúde

Ambas as fontes compartilham o mesmo namespace de paciente_id (co_seq_cidadao),
com overlap mínimo (~6 registros no dataset). O campo `origem` distingue a fonte.

O tipo de profissional é derivado do CBO:
  - 225xxx → "médico"
  - 2235xx → "enfermeiro"
  - 515105 → "ACS"
  - outros  → descrição CBO original
"""

from __future__ import annotations

from typing import List, Optional

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import AntropometriaResult, PAResult, HGTResult
from . import get_db_conn, to_iso_datetime


# ──────────────────────────────────────────────────────────────
# Classificação de profissional por CBO
# ──────────────────────────────────────────────────────────────

def _classify_professional(cbo_code: Optional[str], cbo_name: Optional[str]) -> str:
    """Deriva tipo de profissional legível a partir do código CBO."""
    if not cbo_code:
        return "não identificado"
    code = str(cbo_code).strip()
    if code.startswith("225"):
        return "médico"
    if code.startswith("2235"):
        return "enfermeiro"
    if code == "515105":
        return "ACS"
    if code.startswith("5151"):
        return "agente de saúde"
    if code.startswith("2232"):
        return "dentista"
    # Fallback: usa a descrição CBO se disponível
    return str(cbo_name).lower() if cbo_name else "outro"


# ──────────────────────────────────────────────────────────────
# Joins reutilizáveis
# ──────────────────────────────────────────────────────────────

# PEC: tl_medicao → paciente + profissional
_FROM_PEC = """
    FROM tl_medicao m
    JOIN tb_atend_prof ap  ON ap.co_seq_atend_prof = m.co_atend_prof
    JOIN tb_atend a        ON a.co_seq_atend       = ap.co_atend
    JOIN tb_prontuario pr  ON pr.co_seq_prontuario = a.co_prontuario
    JOIN tb_cidadao c      ON c.co_seq_cidadao     = pr.co_cidadao
    LEFT JOIN tb_lotacao l ON l.co_ator_papel      = ap.co_lotacao
    LEFT JOIN tb_prof p    ON p.co_seq_prof        = l.co_prof
    LEFT JOIN tb_cbo cb    ON cb.co_cbo            = l.co_cbo
"""

# Visita domiciliar: tb_fat_visita_domiciliar → paciente + profissional
_FROM_VISITA = """
    FROM tb_fat_visita_domiciliar v
    JOIN tb_fat_cidadao_pec cp     ON cp.co_seq_fat_cidadao_pec = v.co_fat_cidadao_pec
    JOIN tb_dim_tempo t            ON t.co_seq_dim_tempo = v.co_dim_tempo
    JOIN tb_dim_profissional dp    ON dp.co_seq_dim_profissional = v.co_dim_profissional
    JOIN tb_dim_cbo dcbo           ON dcbo.co_seq_dim_cbo = v.co_dim_cbo
"""


def _build_date_filter_pec(data_inicio, data_fim, params):
    """Adiciona filtros de data para a fonte PEC (tl_medicao.dt_medicao)."""
    clauses = []
    if data_inicio:
        clauses.append("m.dt_medicao >= %s::timestamp")
        params.append(data_inicio)
    if data_fim:
        clauses.append("m.dt_medicao <= %s::timestamp")
        params.append(data_fim)
    return " AND ".join(clauses) if clauses else ""


def _build_date_filter_visita(data_inicio, data_fim, params):
    """Adiciona filtros de data para a fonte visita (tb_dim_tempo.dt_registro)."""
    clauses = []
    if data_inicio:
        clauses.append("t.dt_registro >= %s::date")
        params.append(data_inicio)
    if data_fim:
        clauses.append("t.dt_registro <= %s::date")
        params.append(data_fim)
    return " AND ".join(clauses) if clauses else ""


def _validate_paciente_id(paciente_id):
    if paciente_id is None:
        raise ValueError("paciente_id é obrigatório.")
    pid = int(paciente_id)
    if pid <= 0:
        raise ValueError("paciente_id deve ser um inteiro positivo.")
    return pid


# ──────────────────────────────────────────────────────────────
# Tool: listar_registros_antropometria
# ──────────────────────────────────────────────────────────────


def listar_registros_antropometria(
    ctx: Context,
    paciente_id: int,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limite: int = 50,
) -> List[AntropometriaResult]:
    """
    Histórico de peso, altura e IMC de um paciente, consolidando dados
    de atendimentos clínicos (PEC) e visitas domiciliares (ACS).

    O IMC é calculado como peso(kg) / (altura(m))² sempre que peso e
    altura estiverem presentes. Os campos profissional_id/profissional_nome/
    tipo_profissional identificam quem registrou. O campo `origem` indica
    a fonte ("pec" ou "visita_domiciliar").
    """

    pid = _validate_paciente_id(paciente_id)
    safe_limit = max(1, min(int(limite), 200))

    # -- Fonte PEC --
    pec_params: list = [pid]
    pec_date = _build_date_filter_pec(data_inicio, data_fim, pec_params)
    pec_where = f"AND ({pec_date})" if pec_date else ""

    sql_pec = f"""
        SELECT
            c.co_seq_cidadao                          AS paciente_id,
            m.nu_medicao_peso::numeric                AS peso_kg,
            m.nu_medicao_altura::numeric              AS altura_cm,
            CASE
                WHEN m.nu_medicao_peso IS NOT NULL
                 AND m.nu_medicao_altura IS NOT NULL
                 AND m.nu_medicao_altura::numeric > 0
                THEN ROUND(
                    m.nu_medicao_peso::numeric
                    / ((m.nu_medicao_altura::numeric / 100.0) ^ 2), 2)
                ELSE NULL
            END                                       AS imc,
            m.dt_medicao                              AS data_medicao,
            p.co_seq_prof                             AS prof_id,
            p.no_social_profissional                  AS prof_nome,
            cb.co_cbo_2002                            AS cbo_codigo,
            cb.no_cbo                                 AS cbo_nome,
            'pec'                                     AS origem
        {_FROM_PEC}
        WHERE c.co_seq_cidadao = %s
          AND (m.nu_medicao_peso IS NOT NULL OR m.nu_medicao_altura IS NOT NULL)
          {pec_where}
    """

    # -- Fonte Visita --
    vis_params: list = [pid]
    vis_date = _build_date_filter_visita(data_inicio, data_fim, vis_params)
    vis_where = f"AND ({vis_date})" if vis_date else ""

    sql_vis = f"""
        SELECT
            cp.co_cidadao                             AS paciente_id,
            v.nu_peso                                 AS peso_kg,
            v.nu_altura                               AS altura_cm,
            CASE
                WHEN v.nu_peso IS NOT NULL AND v.nu_peso > 0
                 AND v.nu_altura IS NOT NULL AND v.nu_altura > 0
                THEN ROUND(
                    (v.nu_peso / ((v.nu_altura / 100.0) ^ 2))::numeric, 2)
                ELSE NULL
            END                                       AS imc,
            t.dt_registro::timestamp                  AS data_medicao,
            dp.co_seq_dim_profissional                AS prof_id,
            dp.no_profissional                        AS prof_nome,
            dcbo.nu_cbo                               AS cbo_codigo,
            dcbo.no_cbo                               AS cbo_nome,
            'visita_domiciliar'                       AS origem
        {_FROM_VISITA}
        WHERE cp.co_cidadao = %s
          AND (v.nu_peso IS NOT NULL AND v.nu_peso > 0
               OR v.nu_altura IS NOT NULL AND v.nu_altura > 0)
          {vis_where}
    """

    sql = f"""
        ({sql_pec})
        UNION ALL
        ({sql_vis})
        ORDER BY data_medicao DESC NULLS LAST
        LIMIT %s;
    """
    params = pec_params + vis_params + [safe_limit]

    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, tuple(params))

    results: List[AntropometriaResult] = []
    for row in rows:
        peso = float(row["peso_kg"]) if row.get("peso_kg") is not None else None
        altura = float(row["altura_cm"]) if row.get("altura_cm") is not None else None
        imc = float(row["imc"]) if row.get("imc") is not None else None
        results.append(
            AntropometriaResult(
                paciente_id=int(row["paciente_id"]),
                peso_kg=peso,
                altura_cm=altura,
                imc=imc,
                data_medicao=to_iso_datetime(row.get("data_medicao")),
                profissional_id=int(row["prof_id"]) if row.get("prof_id") else None,
                profissional_nome=row.get("prof_nome"),
                tipo_profissional=_classify_professional(
                    row.get("cbo_codigo"), row.get("cbo_nome")
                ),
                origem=row.get("origem", "pec"),
            )
        )
    return results


# ──────────────────────────────────────────────────────────────
# Tool: listar_registros_pa
# ──────────────────────────────────────────────────────────────


def listar_registros_pa(
    ctx: Context,
    paciente_id: int,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limite: int = 50,
) -> List[PAResult]:
    """
    Histórico de pressão arterial (PAS/PAD) de um paciente, consolidando
    dados de atendimentos clínicos (PEC) e visitas domiciliares (ACS).

    A PA é armazenada como "PAS/PAD" (ex.: "130/80") e é decomposta em
    valores separados. Os campos profissional_id/profissional_nome/
    tipo_profissional identificam quem aferiu.
    """

    pid = _validate_paciente_id(paciente_id)
    safe_limit = max(1, min(int(limite), 200))

    # -- Fonte PEC --
    pec_params: list = [pid]
    pec_date = _build_date_filter_pec(data_inicio, data_fim, pec_params)
    pec_where = f"AND ({pec_date})" if pec_date else ""

    sql_pec = f"""
        SELECT
            c.co_seq_cidadao                                     AS paciente_id,
            SPLIT_PART(m.nu_medicao_pressao_arterial, '/', 1)    AS pas_str,
            SPLIT_PART(m.nu_medicao_pressao_arterial, '/', 2)    AS pad_str,
            m.nu_medicao_pressao_arterial                        AS pressao_raw,
            m.dt_medicao                                         AS data_medicao,
            p.co_seq_prof                                        AS prof_id,
            p.no_social_profissional                             AS prof_nome,
            cb.co_cbo_2002                                       AS cbo_codigo,
            cb.no_cbo                                            AS cbo_nome,
            'pec'                                                AS origem
        {_FROM_PEC}
        WHERE c.co_seq_cidadao = %s
          AND m.nu_medicao_pressao_arterial IS NOT NULL
          {pec_where}
    """

    # -- Fonte Visita --
    vis_params: list = [pid]
    vis_date = _build_date_filter_visita(data_inicio, data_fim, vis_params)
    vis_where = f"AND ({vis_date})" if vis_date else ""

    sql_vis = f"""
        SELECT
            cp.co_cidadao                                        AS paciente_id,
            SPLIT_PART(v.nu_medicao_pressao_arterial, '/', 1)    AS pas_str,
            SPLIT_PART(v.nu_medicao_pressao_arterial, '/', 2)    AS pad_str,
            v.nu_medicao_pressao_arterial                        AS pressao_raw,
            t.dt_registro::timestamp                             AS data_medicao,
            dp.co_seq_dim_profissional                           AS prof_id,
            dp.no_profissional                                   AS prof_nome,
            dcbo.nu_cbo                                          AS cbo_codigo,
            dcbo.no_cbo                                          AS cbo_nome,
            'visita_domiciliar'                                  AS origem
        {_FROM_VISITA}
        WHERE cp.co_cidadao = %s
          AND v.nu_medicao_pressao_arterial IS NOT NULL
          {vis_where}
    """

    sql = f"""
        ({sql_pec})
        UNION ALL
        ({sql_vis})
        ORDER BY data_medicao DESC NULLS LAST
        LIMIT %s;
    """
    params = pec_params + vis_params + [safe_limit]

    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, tuple(params))

    results: List[PAResult] = []
    for row in rows:
        pas_str = row.get("pas_str")
        pad_str = row.get("pad_str")
        pas = int(pas_str) if pas_str and pas_str.strip().isdigit() else None
        pad = int(pad_str) if pad_str and pad_str.strip().isdigit() else None
        results.append(
            PAResult(
                paciente_id=int(row["paciente_id"]),
                pas=pas,
                pad=pad,
                pressao_raw=row.get("pressao_raw"),
                data_medicao=to_iso_datetime(row.get("data_medicao")),
                profissional_id=int(row["prof_id"]) if row.get("prof_id") else None,
                profissional_nome=row.get("prof_nome"),
                tipo_profissional=_classify_professional(
                    row.get("cbo_codigo"), row.get("cbo_nome")
                ),
                origem=row.get("origem", "pec"),
            )
        )
    return results


# ──────────────────────────────────────────────────────────────
# Tool: listar_registros_hgt
# ──────────────────────────────────────────────────────────────

# Mapeamento tp_glicemia → texto legível (espelha tb_dim_tipo_glicemia)
_GLICEMIA_TIPO = {
    0: "Jejum",
    1: "Pós-prandial",
    2: "Pré-prandial",
    3: "Não especificado",
}

_MOMENTO_FILTER = {
    "jejum": 0,
    "pos_prandial": 1,
    "pre_prandial": 2,
}


def listar_registros_hgt(
    ctx: Context,
    paciente_id: int,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    momento: Optional[str] = None,
    limite: int = 50,
) -> List[HGTResult]:
    """
    Histórico de glicemia capilar (HGT) de um paciente, consolidando
    dados de atendimentos clínicos (PEC) e visitas domiciliares (ACS).

    Retorna o valor em mg/dL e o momento da aferição em texto legível
    (Jejum, Pós-prandial, Pré-prandial). Os campos profissional_id/
    profissional_nome/tipo_profissional identificam quem aferiu.
    Filtro opcional `momento` aceita: "jejum", "pos_prandial", "pre_prandial".
    """

    pid = _validate_paciente_id(paciente_id)
    safe_limit = max(1, min(int(limite), 200))

    momento_tp = None
    if momento:
        momento_key = momento.strip().lower()
        if momento_key not in _MOMENTO_FILTER:
            raise ValueError(
                f"momento inválido: '{momento}'. Use: jejum, pos_prandial, pre_prandial."
            )
        momento_tp = _MOMENTO_FILTER[momento_key]

    # -- Fonte PEC --
    pec_params: list = [pid]
    pec_date = _build_date_filter_pec(data_inicio, data_fim, pec_params)
    pec_extra = f"AND ({pec_date})" if pec_date else ""
    if momento_tp is not None:
        pec_extra += " AND m.tp_glicemia = %s"
        pec_params.append(momento_tp)

    sql_pec = f"""
        SELECT
            c.co_seq_cidadao            AS paciente_id,
            m.nu_medicao_glicemia       AS valor_str,
            m.tp_glicemia               AS tp_glicemia,
            m.dt_medicao                AS data_medicao,
            p.co_seq_prof               AS prof_id,
            p.no_social_profissional    AS prof_nome,
            cb.co_cbo_2002              AS cbo_codigo,
            cb.no_cbo                   AS cbo_nome,
            'pec'                       AS origem
        {_FROM_PEC}
        WHERE c.co_seq_cidadao = %s
          AND m.nu_medicao_glicemia IS NOT NULL
          {pec_extra}
    """

    # -- Fonte Visita --
    vis_params: list = [pid]
    vis_date = _build_date_filter_visita(data_inicio, data_fim, vis_params)
    vis_extra = f"AND ({vis_date})" if vis_date else ""
    if momento_tp is not None:
        vis_extra += " AND dtg.nu_identificador::text = %s::text"
        vis_params.append(momento_tp)

    sql_vis = f"""
        SELECT
            cp.co_cidadao               AS paciente_id,
            v.nu_medicao_glicemia       AS valor_str,
            dtg.co_ordem                AS tp_glicemia,
            t.dt_registro::timestamp    AS data_medicao,
            dp.co_seq_dim_profissional  AS prof_id,
            dp.no_profissional          AS prof_nome,
            dcbo.nu_cbo                 AS cbo_codigo,
            dcbo.no_cbo                 AS cbo_nome,
            'visita_domiciliar'         AS origem
        {_FROM_VISITA}
        LEFT JOIN tb_dim_tipo_glicemia dtg ON dtg.co_seq_dim_tipo_glicemia = v.co_dim_tipo_glicemia
        WHERE cp.co_cidadao = %s
          AND v.nu_medicao_glicemia IS NOT NULL
          {vis_extra}
    """

    sql = f"""
        ({sql_pec})
        UNION ALL
        ({sql_vis})
        ORDER BY data_medicao DESC NULLS LAST
        LIMIT %s;
    """
    params = pec_params + vis_params + [safe_limit]

    conn = get_db_conn(ctx)
    rows = query_all(conn, sql, tuple(params))

    results: List[HGTResult] = []
    for row in rows:
        valor_str = row.get("valor_str")
        valor = None
        if valor_str is not None:
            try:
                valor = float(valor_str)
            except (ValueError, TypeError):
                pass

        tp = row.get("tp_glicemia")
        momento_texto = _GLICEMIA_TIPO.get(
            int(tp) if tp is not None else -1,
            "Não informado",
        )

        results.append(
            HGTResult(
                paciente_id=int(row["paciente_id"]),
                valor_mg_dl=valor,
                momento_afericao=momento_texto,
                data_medicao=to_iso_datetime(row.get("data_medicao")),
                profissional_id=int(row["prof_id"]) if row.get("prof_id") else None,
                profissional_nome=row.get("prof_nome"),
                tipo_profissional=_classify_professional(
                    row.get("cbo_codigo"), row.get("cbo_nome")
                ),
                origem=row.get("origem", "pec"),
            )
        )
    return results


__all__ = [
    "listar_registros_antropometria",
    "listar_registros_pa",
    "listar_registros_hgt",
]
