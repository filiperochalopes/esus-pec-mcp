"""
Tool de histórico estruturado de prescrições de medicamentos.

O contrato mantém campos estruturados, posologia e recomendação separados.
Isso evita transformar texto narrativo em dose vigente e permite à LLM
descrever aumentos, reduções, renovações e interrupções sem inferir além do
registro eletrônico.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import List, Literal

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import MedicationPrescriptionResult
from . import get_db_conn, to_iso_datetime

_SQL_PRESCRICOES = """
WITH grupos_paciente AS (
    SELECT DISTINCT COALESCE(pr.co_prontuario_grupo, pr.co_seq_prontuario) AS grupo_id
    FROM tb_prontuario pr
    WHERE pr.co_cidadao = %s
)
SELECT
    rm.co_seq_receita_medicamento       AS prescricao_id,
    rm.co_atend_prof                    AS atendimento_id,
    COALESCE(ap.dt_fim, a.dt_inicio)    AS data_prescricao,
    med.no_principio_ativo              AS medicamento,
    med.ds_concentracao                 AS concentracao,
    med.ds_unidade_fornecimento         AS unidade_fornecimento,
    rm.qt_dose                          AS dose,
    rm.co_unidade_medida_dose           AS unidade_dose_id,
    rm.qt_dose_manha                    AS dose_manha,
    rm.qt_dose_tarde                    AS dose_tarde,
    rm.qt_dose_noite                    AS dose_noite,
    rm.tp_frequencia_dose               AS frequencia_tipo,
    rm.ds_frequencia_dose               AS frequencia_descricao,
    rm.qt_periodo_frequencia            AS frequencia_periodo,
    rm.tp_un_medida_tempo_frequencia    AS frequencia_unidade_tempo,
    rm.no_posologia                     AS posologia,
    rm.co_aplicacao_medicamento         AS via_administracao_id,
    rm.qt_receitada                     AS quantidade_receitada,
    rm.dt_inicio_tratamento             AS inicio_tratamento,
    rm.dt_fim_tratamento                AS fim_tratamento,
    rm.qt_duracao_tratamento            AS duracao_tratamento,
    rm.tp_un_medida_tempo_tratamento    AS duracao_unidade_tempo,
    rm.st_uso_continuo                  AS uso_continuo,
    rm.st_dose_unica                    AS dose_unica,
    rm.ds_recomendacao                  AS recomendacao,
    rm.st_interrompido                  AS interrompido,
    rm.dt_interrupcao                   AS data_interrupcao,
    rm.ds_observacao_interrupcao        AS motivo_interrupcao,
    rm.co_receita_uso_continuo_grupo    AS grupo_renovacao_id,
    cid.nu_cid10                        AS cid_code,
    ciap.co_ciap                        AS ciap_code
FROM tb_receita_medicamento rm
JOIN tb_atend_prof ap ON ap.co_seq_atend_prof = rm.co_atend_prof
JOIN tb_atend a ON a.co_seq_atend = ap.co_atend
JOIN tb_prontuario pr ON pr.co_seq_prontuario = a.co_prontuario
JOIN grupos_paciente gp
  ON gp.grupo_id = COALESCE(pr.co_prontuario_grupo, pr.co_seq_prontuario)
JOIN tb_medicamento med ON med.co_seq_medicamento = rm.co_medicamento
LEFT JOIN tb_cid10 cid ON cid.co_cid10 = rm.co_cid10
LEFT JOIN tb_ciap ciap ON ciap.co_seq_ciap = rm.co_ciap
WHERE COALESCE(ap.st_cancelado, 0) = 0
{filters}
ORDER BY COALESCE(ap.dt_fim, a.dt_inicio) DESC NULLS LAST,
         rm.dt_inicio_tratamento DESC NULLS LAST,
         rm.co_seq_receita_medicamento DESC
LIMIT %s
"""


def _clean_recommendation(value: object) -> str | None:
    if value is None:
        return None
    raw = html.unescape(str(value))
    raw = re.sub(r"(?i)<br\s*/?>|</p\s*>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    clean = "\n".join(line for line in lines if line).strip()
    return clean[:2000] or None


def _state(row: dict) -> Literal["ativo", "concluído", "interrompido"]:
    if bool(row.get("interrompido")):
        return "interrompido"
    end = row.get("fim_tratamento")
    if end is None:
        return "ativo"
    if isinstance(end, datetime):
        end = end.date()
    return "ativo" if end >= date.today() else "concluído"


def _has_document_consistency_warning(row: dict, recommendation: str | None) -> bool:
    if not recommendation:
        return False
    has_turn_dose = any(
        row.get(field) is not None for field in ("dose_manha", "dose_tarde", "dose_noite")
    )
    mentions_turn = bool(re.search(r"\b(manh[ãa]|tarde|noite)\b", recommendation, re.IGNORECASE))
    return mentions_turn and not has_turn_dose


def listar_prescricoes_medicamentos(
    ctx: Context,
    paciente_id: int,
    estado: Literal["ativo", "concluído", "interrompido"] | None = None,
    medicamento: str | None = None,
    limite: int = 200,
) -> List[MedicationPrescriptionResult]:
    """
    Lista o histórico estruturado de medicamentos prescritos ao paciente.

    Abrange prontuários do mesmo grupo e ignora atendimentos cancelados.
    O estado calculado dá precedência explícita à interrupção.
    """

    paciente_id_int = int(paciente_id)
    if paciente_id_int <= 0:
        raise ValueError("paciente_id deve ser um inteiro positivo.")
    if estado not in (None, "ativo", "concluído", "interrompido"):
        raise ValueError("estado deve ser ativo, concluído ou interrompido.")

    safe_limit = max(1, min(int(limite), 500))
    filters: list[str] = []
    params: list[object] = [paciente_id_int]

    if estado == "interrompido":
        filters.append("AND COALESCE(rm.st_interrompido, 0) = 1")
    elif estado == "ativo":
        filters.append(
            "AND COALESCE(rm.st_interrompido, 0) = 0 "
            "AND (rm.dt_fim_tratamento IS NULL OR rm.dt_fim_tratamento >= CURRENT_DATE)"
        )
    elif estado == "concluído":
        filters.append(
            "AND COALESCE(rm.st_interrompido, 0) = 0 "
            "AND rm.dt_fim_tratamento < CURRENT_DATE"
        )

    if medicamento and medicamento.strip():
        filters.append("AND med.no_principio_ativo ILIKE %s")
        params.append(f"%{medicamento.strip()[:120]}%")

    params.append(safe_limit)
    sql = _SQL_PRESCRICOES.format(filters="\n".join(filters))
    rows = query_all(get_db_conn(ctx), sql, tuple(params))

    results: List[MedicationPrescriptionResult] = []
    for row in rows:
        recommendation = _clean_recommendation(row.get("recomendacao"))
        results.append(
            MedicationPrescriptionResult(
                paciente_id=paciente_id_int,
                prescricao_id=int(row["prescricao_id"]),
                atendimento_id=int(row["atendimento_id"]),
                data_prescricao=to_iso_datetime(row.get("data_prescricao")),
                medicamento=str(row.get("medicamento")) if row.get("medicamento") is not None else None,
                concentracao=str(row.get("concentracao")) if row.get("concentracao") is not None else None,
                unidade_fornecimento=str(row.get("unidade_fornecimento"))
                if row.get("unidade_fornecimento") is not None
                else None,
                dose=str(row.get("dose")) if row.get("dose") is not None else None,
                unidade_dose_id=int(row["unidade_dose_id"])
                if row.get("unidade_dose_id") is not None
                else None,
                dose_manha=str(row.get("dose_manha")) if row.get("dose_manha") is not None else None,
                dose_tarde=str(row.get("dose_tarde")) if row.get("dose_tarde") is not None else None,
                dose_noite=str(row.get("dose_noite")) if row.get("dose_noite") is not None else None,
                frequencia_tipo=int(row["frequencia_tipo"])
                if row.get("frequencia_tipo") is not None
                else None,
                frequencia_descricao=str(row.get("frequencia_descricao"))
                if row.get("frequencia_descricao") is not None
                else None,
                frequencia_periodo=str(row.get("frequencia_periodo"))
                if row.get("frequencia_periodo") is not None
                else None,
                frequencia_unidade_tempo=int(row["frequencia_unidade_tempo"])
                if row.get("frequencia_unidade_tempo") is not None
                else None,
                posologia=str(row.get("posologia")) if row.get("posologia") is not None else None,
                via_administracao_id=int(row["via_administracao_id"])
                if row.get("via_administracao_id") is not None
                else None,
                quantidade_receitada=str(row.get("quantidade_receitada"))
                if row.get("quantidade_receitada") is not None
                else None,
                inicio_tratamento=to_iso_datetime(row.get("inicio_tratamento")),
                fim_tratamento=to_iso_datetime(row.get("fim_tratamento")),
                duracao_tratamento=str(row.get("duracao_tratamento"))
                if row.get("duracao_tratamento") is not None
                else None,
                duracao_unidade_tempo=int(row["duracao_unidade_tempo"])
                if row.get("duracao_unidade_tempo") is not None
                else None,
                uso_continuo=bool(row.get("uso_continuo")),
                dose_unica=bool(row.get("dose_unica")),
                recomendacao=recommendation,
                interrompido=bool(row.get("interrompido")),
                data_interrupcao=to_iso_datetime(row.get("data_interrupcao")),
                motivo_interrupcao=str(row.get("motivo_interrupcao"))
                if row.get("motivo_interrupcao") is not None
                else None,
                grupo_renovacao_id=int(row["grupo_renovacao_id"])
                if row.get("grupo_renovacao_id") is not None
                else None,
                cid_code=str(row.get("cid_code")) if row.get("cid_code") is not None else None,
                ciap_code=str(row.get("ciap_code")) if row.get("ciap_code") is not None else None,
                estado=_state(row),
                alerta_consistencia_documental=_has_document_consistency_warning(
                    row, recommendation
                ),
            )
        )
    return results


__all__ = ["listar_prescricoes_medicamentos"]
