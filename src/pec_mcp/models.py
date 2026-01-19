"""
Tipagens de saída das ferramentas MCP.

Usamos TypedDict para manter respostas previsíveis e amigáveis a LLMs,
evitando ambiguidade de campos.
"""

from __future__ import annotations

from typing import Optional

try:  # Pydantic <3 exige typing_extensions.TypedDict em Python < 3.12
    from typing_extensions import TypedDict  # type: ignore
except ImportError:  # pragma: no cover - fallback para ambientes que já suportam
    from typing import TypedDict  # type: ignore


class PatientCaptureResult(TypedDict):
    name: str
    birth_date: Optional[str]
    sex: Optional[str]
    gender: Optional[str]


class ConditionResult(TypedDict):
    paciente_id: int
    paciente_initials: str
    birth_date: Optional[str]
    sex: Optional[str]
    condition_id: int
    cid_code: Optional[str]
    cid_description: Optional[str]
    ciap_code: Optional[str]
    ciap_description: Optional[str]
    dt_inicio_condicao: Optional[str]
    dt_fim_condicao: Optional[str]
    situacao_id: Optional[str]
    observacao: Optional[str]


class CountResult(TypedDict):
    count: int


class HealthConditionCode(TypedDict):
    code: str
    description: Optional[str]


class HealthConditionCaptureResult(TypedDict):
    condition: str
    source: str
    cid_codes: list[str]
    ciap_codes: list[str]
    cid: list["HealthConditionCode"]
    ciap: list["HealthConditionCode"]
    fallback_condition_text: Optional[str]


class HealthUnitResult(TypedDict):
    unidade_id: int
    cnes: Optional[str]
    name: Optional[str]
    localidade_id: Optional[int]
    is_active: bool


class AtendimentoSOAPResult(TypedDict):
    atendimento_id: int
    paciente_id: int
    data_hora: Optional[str]
    cbo_codigo: Optional[str]
    cbo_descricao: Optional[str]
    profissional: Optional[str]
    tipo_profissional_id: Optional[str]
    tipo_atendimento_id: Optional[str]
    soap_s: Optional[str]
    soap_o: Optional[str]
    soap_a: Optional[str]
    soap_p: Optional[str]
    condicoes: Optional[list["SOAPCondition"]]


class SOAPCondition(TypedDict, total=False):
    condition_id: Optional[int]
    cid_code: Optional[str]
    cid_description: Optional[str]
    ciap_code: Optional[str]
    ciap_description: Optional[str]
    observacao: Optional[str]
    dt_inicio_condicao: Optional[str]
    dt_fim_condicao: Optional[str]
    situacao_id: Optional[str]


class PacienteSemConsultaResult(TypedDict):
    paciente_id: int
    paciente_initials: str
    birth_date: Optional[str]
    sex: Optional[str]
    ultima_consulta: Optional[str]
    dias_sem_consulta: Optional[int]


class GestanteResult(TypedDict):
    gestacao_id: int
    paciente_id: int
    nome_paciente: str
    dpp: Optional[str]
    idade_gestacional_semanas: Optional[int]
    idade_gestacional_dias: Optional[int]
    idade_gestacional_str: Optional[str]
    tp_gravidez: Optional[str]
    st_alto_risco: Optional[str]
    situacao: Optional[str]


__all__ = [
    "PatientCaptureResult",
    "ConditionResult",
    "CountResult",
    "HealthConditionCode",
    "HealthConditionCaptureResult",
    "HealthUnitResult",
    "AtendimentoSOAPResult",
    "SOAPCondition",
    "PacienteSemConsultaResult",
    "GestanteResult",
]
