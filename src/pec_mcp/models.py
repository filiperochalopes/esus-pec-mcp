"""
Tipagens de saída das ferramentas MCP.

Usamos TypedDict para manter respostas previsíveis e amigáveis a LLMs,
evitando ambiguidade de campos.
"""

from __future__ import annotations

from typing import Optional, TypedDict


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
    situacao: str


class ProblemaResult(TypedDict):
    problema_id: int
    paciente_id: int
    codigo_cid10: Optional[str]
    descricao_cid10: Optional[str]
    dt_inicio_problema: Optional[str]
    dt_fim_problema: Optional[str]
    situacao_id: Optional[str]
    observacao: Optional[str]


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


__all__ = [
    "GestanteResult",
    "ProblemaResult",
    "AtendimentoSOAPResult",
]
