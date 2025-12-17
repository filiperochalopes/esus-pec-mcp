"""
Tool para listar os últimos atendimentos SOAP de um paciente.
"""

from __future__ import annotations

from typing import List

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import AtendimentoSOAPResult
from . import get_db_conn, to_iso_datetime

_SQL_ATENDIMENTOS_BASE = """
SELECT
    ap.co_seq_atend_prof          AS atendimento_id,
    pr.co_cidadao                 AS paciente_id,
    a.dt_inicio                   AS data_hora,
    cb.co_cbo_2002                AS cbo_codigo,
    cb.no_cbo                     AS cbo_descricao,
    p.no_social_profissional      AS profissional,
    ap.tp_atend_prof              AS tipo_profissional_id,
    ap.tp_atend                   AS tipo_atendimento_id,
    es.ds_subjetivo               AS soap_s,
    eo.ds_objetivo                AS soap_o,
    ea.ds_avaliacao               AS soap_a,
    ep.ds_plano                   AS soap_p,
    COALESCE(cond.condicoes, '[]') AS condicoes
FROM tb_atend_prof ap
JOIN tb_atend       a   ON a.co_seq_atend       = ap.co_atend
JOIN tb_prontuario  pr  ON pr.co_seq_prontuario = a.co_prontuario
LEFT JOIN tb_lotacao l  ON l.co_ator_papel      = ap.co_lotacao
LEFT JOIN tb_prof    p  ON p.co_seq_prof        = l.co_prof
LEFT JOIN tb_cbo     cb ON cb.co_cbo            = l.co_cbo
LEFT JOIN tb_evolucao_subjetivo es ON es.co_atend_prof = ap.co_seq_atend_prof
LEFT JOIN tb_evolucao_objetivo  eo ON eo.co_atend_prof = ap.co_seq_atend_prof
LEFT JOIN tb_evolucao_avaliacao ea ON ea.co_atend_prof = ap.co_seq_atend_prof
LEFT JOIN tb_evolucao_plano     ep ON ep.co_atend_prof = ap.co_seq_atend_prof
LEFT JOIN LATERAL (
    SELECT json_agg(
        jsonb_build_object(
            'condition_id', p2.co_seq_problema,
            'cid_code', cid2.nu_cid10,
            'cid_description', cid2.no_cid10,
            'ciap_code', ciap2.co_ciap,
            'ciap_description', ciap2.ds_ciap,
            'observacao', pe2.ds_observacao,
            'dt_inicio_condicao', pe2.dt_inicio_problema,
            'dt_fim_condicao', pe2.dt_fim_problema,
            'situacao_id', pe2.co_situacao_problema
        )
        ORDER BY pe2.dt_inicio_problema DESC NULLS LAST, p2.co_seq_problema
    ) AS condicoes
    FROM tb_problema_evolucao pe2
    JOIN tb_problema p2 ON p2.co_unico_problema = pe2.co_unico_problema
    LEFT JOIN tb_cid10 cid2 ON cid2.co_cid10 = p2.co_cid10
    LEFT JOIN tb_ciap ciap2 ON ciap2.co_seq_ciap = p2.co_ciap
    WHERE pe2.co_atend_prof = ap.co_seq_atend_prof
) cond ON TRUE
WHERE pr.co_cidadao = %s
  AND (
        cb.co_cbo_2002 LIKE '225%%'   -- médicos
     OR cb.co_cbo_2002 LIKE '2235%%'  -- enfermeiros
     -- OR cb.co_cbo_2002 LIKE '2232%%'  -- dentistas (opcional)
      )
ORDER BY a.dt_inicio DESC NULLS LAST
"""


def listar_ultimos_atendimentos_soap(
    ctx: Context, paciente_id: int, limite: int | None = None
) -> List[AtendimentoSOAPResult]:
    """
    Recupera últimos atendimentos SOAP do paciente (médicos e enfermeiros).
    """

    if paciente_id is None:
        raise ValueError("paciente_id é obrigatório para consultar histórico de atendimento.")

    paciente_id_int = int(paciente_id)
    if paciente_id_int <= 0:
        raise ValueError("paciente_id deve ser um inteiro positivo.")

    safe_limit = None
    if limite is not None:
        safe_limit = max(1, min(int(limite), 1000))

    conn = get_db_conn(ctx)
    sql = _SQL_ATENDIMENTOS_BASE
    params = [paciente_id_int]
    if safe_limit is not None:
        sql = f"{sql} LIMIT %s"
        params.append(safe_limit)

    rows = query_all(conn, sql, tuple(params))

    results: List[AtendimentoSOAPResult] = []
    for row in rows:
        results.append(
            AtendimentoSOAPResult(
                atendimento_id=int(row["atendimento_id"]),
                paciente_id=int(row["paciente_id"]),
                data_hora=to_iso_datetime(row.get("data_hora")),
                cbo_codigo=str(row.get("cbo_codigo")) if row.get("cbo_codigo") is not None else None,
                cbo_descricao=str(row.get("cbo_descricao")) if row.get("cbo_descricao") is not None else None,
                profissional=str(row.get("profissional")) if row.get("profissional") is not None else None,
                tipo_profissional_id=str(row.get("tipo_profissional_id"))
                if row.get("tipo_profissional_id") is not None
                else None,
                tipo_atendimento_id=str(row.get("tipo_atendimento_id"))
                if row.get("tipo_atendimento_id") is not None
                else None,
                soap_s=str(row.get("soap_s")) if row.get("soap_s") is not None else None,
                soap_o=str(row.get("soap_o")) if row.get("soap_o") is not None else None,
                soap_a=str(row.get("soap_a")) if row.get("soap_a") is not None else None,
                soap_p=str(row.get("soap_p")) if row.get("soap_p") is not None else None,
                condicoes=row.get("condicoes") if isinstance(row.get("condicoes"), list) else [],
            )
        )
    return results


__all__ = ["listar_ultimos_atendimentos_soap"]
