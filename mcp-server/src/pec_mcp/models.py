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


__all__ = ["PatientCaptureResult", "ConditionResult", "CountResult"]
