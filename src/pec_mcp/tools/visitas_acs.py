"""
Tool para listar visitas domiciliares de Agentes Comunitários de Saúde (ACS).

Fonte de dados: tabela fato desnormalizada `tb_fat_visita_domiciliar`,
que contém todas as visitas do CDS (Coleta de Dados Simplificada).

Dimensões utilizadas:
  - tb_dim_profissional: nome do ACS
  - tb_dim_tempo: data da visita (dt_registro)
  - tb_dim_cbo: CBO do profissional (515105 = ACS)
  - tb_dim_turno: turno da visita (Manhã/Tarde/Noite)
  - tb_dim_desfecho_visita: desfecho (Realizada/Recusada/Ausente)
  - tb_fat_cidadao_pec: vínculo com o paciente no PEC

Flags de motivo da visita (9 flags):
  - st_mot_vis_cad_att: cadastro/atualização
  - st_mot_vis_visita_periodica: visita periódica
  - st_mot_vis_busca_ativa: busca ativa
  - st_mot_vis_acompanhamento: acompanhamento de condicionalidade
  - st_mot_vis_egresso_internacao: egresso de internação
  - st_mot_vis_ctrl_ambnte_vetor: controle ambiental/vetorial
  - st_mot_vis_convte_atvidd_cltva: convite para atividade coletiva
  - st_mot_vis_orintacao_prevncao: orientação/prevenção
  - st_mot_vis_outros: outros motivos

Flags de acompanhamento por condição (23 flags):
  Ver _ACOMPANHAMENTO_MAP abaixo e docs/visita_domiciliar_flags.md.

Campos de aferição na visita:
  - nu_peso, nu_altura: peso e altura aferidos durante a visita
  - nu_medicao_pressao_arterial: PA (formato "PAS/PAD")
  - nu_medicao_glicemia: glicemia capilar (mg/dL)
  Os valores detalhados das aferições são retornados pelas tools de medição
  (medicoes.py), que consolidam PEC + visitas. Aqui expomos apenas presença
  (tem_peso_altura, tem_pa, tem_glicemia) para permitir contagens de cobertura.
"""

from __future__ import annotations

from typing import List, Optional, Union

from mcp.server.fastmcp import Context

from ..db import query_all, query_one
from ..domain.patient import to_initials
from ..models import VisitaACSResult, VisitaACSCountResult
from . import get_db_conn

# CBO do Agente Comunitário de Saúde
_CBO_ACS = "515105"

# ──────────────────────────────────────────────────────────────
# Flags de acompanhamento por condição
# ──────────────────────────────────────────────────────────────

_ACOMPANHAMENTO_MAP = {
    "gestante": "st_acomp_gestante",
    "puerpera": "st_acomp_puerpera",
    "recem_nascido": "st_acomp_recem_nascido",
    "crianca": "st_acomp_crianca",
    "desnutricao": "st_acomp_pessoa_desnutricao",
    "reabilitacao": "st_acomp_pessoa_reabil_deficie",
    "hipertensao": "st_acomp_pessoa_hipertensao",
    "diabetes": "st_acomp_pessoa_diabetes",
    "asma": "st_acomp_pessoa_asma",
    "dpoc": "st_acomp_pessoa_dpoc_enfisema",
    "cancer": "st_acomp_pessoa_cancer",
    "doenca_cronica": "st_acomp_pessoa_doenca_cronica",
    "hanseniase": "st_acomp_pessoa_hanseniase",
    "tuberculose": "st_acomp_pessoa_tuberculose",
    "sintomatico_respiratorio": "st_acomp_sintomaticos_respirat",
    "tabagista": "st_acomp_tabagista",
    "acamado": "st_acomp_domiciliados_acamados",
    "vulnerabilidade_social": "st_acomp_condi_vulnerab_social",
    "bolsa_familia": "st_acomp_condi_bolsa_familia",
    "saude_mental": "st_acomp_saude_mental",
    "alcool": "st_acomp_usuario_alcool",
    "drogas": "st_acomp_usuario_outras_drogra",
    "idoso": "st_acomp_pessoa_idosa",
}

# ──────────────────────────────────────────────────────────────
# Flags de motivo da visita
# ──────────────────────────────────────────────────────────────

_MOTIVO_MAP = {
    "cadastro": "st_mot_vis_cad_att",
    "periodica": "st_mot_vis_visita_periodica",
    "busca_ativa": "st_mot_vis_busca_ativa",
    "acompanhamento": "st_mot_vis_acompanhamento",
    "egresso_internacao": "st_mot_vis_egresso_internacao",
    "controle_ambiental": "st_mot_vis_ctrl_ambnte_vetor",
    "convite_atividade": "st_mot_vis_convte_atvidd_cltva",
    "orientacao_prevencao": "st_mot_vis_orintacao_prevncao",
    "outros": "st_mot_vis_outros",
}

_ALL_FLAG_COLUMNS = list(_ACOMPANHAMENTO_MAP.values())
_FLAG_LABEL_BY_COL = {v: k for k, v in _ACOMPANHAMENTO_MAP.items()}

_ALL_MOTIVO_COLUMNS = list(_MOTIVO_MAP.values())
_MOTIVO_LABEL_BY_COL = {v: k for k, v in _MOTIVO_MAP.items()}


def _build_flag_list(row: dict) -> list:
    """Retorna lista de labels de acompanhamento ativos (flag=1) na visita."""
    return [
        _FLAG_LABEL_BY_COL[col]
        for col in _ALL_FLAG_COLUMNS
        if row.get(col) == 1
    ]


def _build_motivo_list(row: dict) -> list:
    """Retorna lista de labels de motivo da visita ativos (flag=1)."""
    return [
        _MOTIVO_LABEL_BY_COL[col]
        for col in _ALL_MOTIVO_COLUMNS
        if row.get(col) == 1
    ]


def listar_visitas_acs(
    ctx: Context,
    profissional_id: Optional[int] = None,
    nome_profissional: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    ultimos_dias: Optional[int] = None,
    acompanhamento: Optional[str] = None,
    motivo: Optional[str] = None,
    unidade_saude_id: Optional[int] = None,
    com_peso_altura: Optional[bool] = None,
    com_pa: Optional[bool] = None,
    com_glicemia: Optional[bool] = None,
    apenas_contagem: bool = False,
    limite: int = 200,
) -> Union[List[VisitaACSResult], VisitaACSCountResult]:
    """
    Lista ou conta visitas domiciliares de Agentes Comunitários de Saúde (ACS).

    Permite filtrar por profissional, período, tipo de acompanhamento,
    motivo da visita, unidade de saúde e presença de aferições.

    Exemplos de uso pela LM:
    - "Quantas visitas a gestantes o ACS Maria fez nos últimos 2 meses?"
      → nome_profissional="Maria", acompanhamento="gestante", ultimos_dias=60, apenas_contagem=true
    - "Dos hipertensos, quantos tiveram PA aferida esse mês?"
      → acompanhamento="hipertensao", com_pa=true, data_inicio="2026-04-01", apenas_contagem=true
    - "Listar visitas periódicas do ACS X em março"
      → nome_profissional="X", motivo="periodica", data_inicio/fim de março

    Filtros de acompanhamento: gestante, puerpera, crianca, hipertensao, diabetes,
    tuberculose, hanseniase, cancer, acamado, saude_mental, idoso, etc.

    Filtros de motivo: cadastro, periodica, busca_ativa, acompanhamento,
    egresso_internacao, controle_ambiental, convite_atividade, orientacao_prevencao.
    """

    clauses = ["cbo.nu_cbo = %s"]
    params: list = [_CBO_ACS]

    if profissional_id is not None:
        clauses.append("v.co_dim_profissional = %s")
        params.append(int(profissional_id))

    if nome_profissional:
        clauses.append("p.no_profissional ILIKE %s")
        params.append(f"%{nome_profissional}%")

    if ultimos_dias is not None:
        dias = max(1, min(int(ultimos_dias), 730))
        clauses.append("t.dt_registro >= (CURRENT_DATE - %s * INTERVAL '1 day')")
        params.append(dias)
    else:
        if data_inicio:
            clauses.append("t.dt_registro >= %s::date")
            params.append(data_inicio)
        if data_fim:
            clauses.append("t.dt_registro <= %s::date")
            params.append(data_fim)

    if acompanhamento:
        acomp_key = acompanhamento.strip().lower()
        if acomp_key not in _ACOMPANHAMENTO_MAP:
            validos = ", ".join(sorted(_ACOMPANHAMENTO_MAP.keys()))
            raise ValueError(
                f"acompanhamento inválido: '{acompanhamento}'. "
                f"Valores válidos: {validos}"
            )
        clauses.append(f"v.{_ACOMPANHAMENTO_MAP[acomp_key]} = 1")

    if motivo:
        motivo_key = motivo.strip().lower()
        if motivo_key not in _MOTIVO_MAP:
            validos = ", ".join(sorted(_MOTIVO_MAP.keys()))
            raise ValueError(
                f"motivo inválido: '{motivo}'. Valores válidos: {validos}"
            )
        clauses.append(f"v.{_MOTIVO_MAP[motivo_key]} = 1")

    if unidade_saude_id is not None:
        clauses.append("v.co_dim_unidade_saude = %s")
        params.append(int(unidade_saude_id))

    # Filtros de presença de aferição
    if com_peso_altura is True:
        clauses.append("v.nu_peso IS NOT NULL AND v.nu_peso > 0 AND v.nu_altura IS NOT NULL AND v.nu_altura > 0")
    if com_pa is True:
        clauses.append("v.nu_medicao_pressao_arterial IS NOT NULL")
    if com_glicemia is True:
        clauses.append("v.nu_medicao_glicemia IS NOT NULL")

    where = "WHERE " + " AND ".join(clauses)
    conn = get_db_conn(ctx)

    # ── Modo contagem ──
    if apenas_contagem:
        sql_count = f"""
            SELECT COUNT(*) AS count
            FROM tb_fat_visita_domiciliar v
            JOIN tb_dim_cbo cbo          ON cbo.co_seq_dim_cbo = v.co_dim_cbo
            JOIN tb_dim_tempo t          ON t.co_seq_dim_tempo = v.co_dim_tempo
            JOIN tb_dim_profissional p   ON p.co_seq_dim_profissional = v.co_dim_profissional
            {where};
        """
        row = query_one(conn, sql_count, tuple(params))
        return VisitaACSCountResult(count=int(row["count"]) if row else 0)

    # ── Modo listagem ──
    safe_limit = max(1, min(int(limite), 500))
    flag_cols = ", ".join(f"v.{col}" for col in _ALL_FLAG_COLUMNS)
    motivo_cols = ", ".join(f"v.{col}" for col in _ALL_MOTIVO_COLUMNS)

    sql_list = f"""
        SELECT
            v.co_seq_fat_visita_domiciliar AS visita_id,
            p.no_profissional              AS profissional,
            t.dt_registro                  AS data_visita,
            v.co_fat_cidadao_pec           AS paciente_pec_id,
            cp.no_cidadao                  AS paciente_nome,
            turno.ds_turno                 AS turno,
            desf.ds_desfecho_visita        AS desfecho,
            -- Presença de aferições
            CASE WHEN v.nu_peso IS NOT NULL AND v.nu_peso > 0
                  AND v.nu_altura IS NOT NULL AND v.nu_altura > 0
                 THEN true ELSE false END  AS tem_peso_altura,
            CASE WHEN v.nu_medicao_pressao_arterial IS NOT NULL
                 THEN true ELSE false END  AS tem_pa,
            CASE WHEN v.nu_medicao_glicemia IS NOT NULL
                 THEN true ELSE false END  AS tem_glicemia,
            {flag_cols},
            {motivo_cols}
        FROM tb_fat_visita_domiciliar v
        JOIN tb_dim_cbo cbo              ON cbo.co_seq_dim_cbo = v.co_dim_cbo
        JOIN tb_dim_tempo t              ON t.co_seq_dim_tempo = v.co_dim_tempo
        JOIN tb_dim_profissional p       ON p.co_seq_dim_profissional = v.co_dim_profissional
        LEFT JOIN tb_dim_turno turno     ON turno.co_seq_dim_turno = v.co_dim_turno
        LEFT JOIN tb_dim_desfecho_visita desf ON desf.co_seq_dim_desfecho_visita = v.co_dim_desfecho_visita
        LEFT JOIN tb_fat_cidadao_pec cp  ON cp.co_seq_fat_cidadao_pec = v.co_fat_cidadao_pec
        {where}
        ORDER BY t.dt_registro DESC, v.co_seq_fat_visita_domiciliar DESC
        LIMIT %s;
    """
    params.append(safe_limit)

    rows = query_all(conn, sql_list, tuple(params))

    results: List[VisitaACSResult] = []
    for row in rows:
        # Anonimiza o nome do paciente com a única implementação de iniciais do
        # projeto (domain/patient.py). A versão inline que existia aqui não
        # ignorava a conjunção "e", divergindo de to_initials().
        nome_raw = row.get("paciente_nome")
        iniciais = to_initials(nome_raw) if nome_raw else None

        data_str = None
        dt_val = row.get("data_visita")
        if dt_val is not None:
            data_str = str(dt_val) if not hasattr(dt_val, "isoformat") else dt_val.isoformat()

        results.append(
            VisitaACSResult(
                visita_id=int(row["visita_id"]),
                profissional=row.get("profissional"),
                data_visita=data_str,
                paciente_id=int(row["paciente_pec_id"]) if row.get("paciente_pec_id") else None,
                paciente_nome=iniciais,
                turno=row.get("turno"),
                desfecho=row.get("desfecho"),
                motivo_visita=_build_motivo_list(row),
                acompanhamentos=_build_flag_list(row),
                tem_peso_altura=bool(row.get("tem_peso_altura")),
                tem_pa=bool(row.get("tem_pa")),
                tem_glicemia=bool(row.get("tem_glicemia")),
            )
        )
    return results


__all__ = ["listar_visitas_acs"]
