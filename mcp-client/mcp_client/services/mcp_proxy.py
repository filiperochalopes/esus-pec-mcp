"""
Camada de orquestração para listar e invocar tools do servidor MCP.

Usamos chamadas diretas (stdin/stdout não é necessário aqui) para manter
latência baixa a partir da UI FastAPI, aplicando o mesmo contrato das
tools registradas no servidor.
"""

from __future__ import annotations

import inspect
import time
from typing import Any, Dict, List, get_args, get_origin

from fastapi.encoders import jsonable_encoder

from ..config import apply_db_config, load_db_config
from pec_mcp.db import get_connection
from pec_mcp.tools.analytics import consulta_epidemiologia, consulta_pessoal
from pec_mcp.tools.atendimentos import listar_ultimos_atendimentos_soap
from pec_mcp.tools.gestantes import listar_gestantes
from pec_mcp.tools.problemas import listar_problemas_paciente


class _Ctx:
    """
    Contexto mínimo compatível com FastMCP (possui state.db_conn).
    """

    def __init__(self, conn):
        self.state = {"db_conn": conn}


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "listar_gestantes": {
        "func": listar_gestantes,
        "description": "Lista gestações ativas (2–42 semanas) com DPP e status de risco.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Quantidade máxima de gestações a retornar (1-200).",
                }
            },
        },
    },
    "listar_problemas_paciente": {
        "func": listar_problemas_paciente,
        "description": "Retorna problemas/comorbidades (CID-10) do paciente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {
                    "type": "integer",
                    "description": "Identificador do paciente (co_cidadao).",
                }
            },
            "required": ["paciente_id"],
        },
    },
    "listar_ultimos_atendimentos_soap": {
        "func": listar_ultimos_atendimentos_soap,
        "description": "Últimos atendimentos SOAP do paciente por médicos/enfermeiros.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {
                    "type": "integer",
                    "description": "Identificador do paciente (co_cidadao).",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 10,
                    "description": "Quantidade máxima de registros (1-200).",
                },
            },
            "required": ["paciente_id"],
        },
    },
    "consulta_epidemiologia": {
        "func": consulta_epidemiologia,
        "description": "Agregação de comorbidades por filtros de sexo, faixa etária e localidade.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["comorbidades_por_filtro"],
                    "default": "comorbidades_por_filtro",
                },
                "sexo": {"type": "string", "description": "M/F, opcional."},
                "idade_min": {"type": "integer", "description": "Idade mínima."},
                "idade_max": {"type": "integer", "description": "Idade máxima."},
                "localidade_id": {"type": "integer", "description": "Código da localidade/endereço."},
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                    "description": "Limite de linhas agregadas (1-500).",
                },
            },
        },
    },
    "consulta_pessoal": {
        "func": consulta_pessoal,
        "description": "Retorna pacientes que atendem a filtros clínicos pré-definidos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": [
                        "sem_atendimento_ano",
                        "gestante_sem_atendimento_mes",
                        "hipertenso_sem_atendimento_6m",
                        "hba1c_maior_8",
                        "pa_maior_140_90",
                    ],
                    "description": "Filtro clínico desejado.",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                    "description": "Quantidade máxima de pacientes (1-500).",
                },
            },
            "required": ["tipo"],
        },
    },
}


def _coerce_value(value: Any, annotation: Any) -> Any:
    """
    Converte valores básicos (int/str) respeitando anotações simples.
    """

    origin = get_origin(annotation)
    target = annotation if origin is None else origin

    if origin is list or origin is dict:
        return value

    if origin is None and annotation in (int, float):
        try:
            return annotation(value)
        except Exception:
            return value
    if origin in (int, float):
        try:
            return origin(value)
        except Exception:
            return value
    if origin is None and annotation in (str,):
        return str(value)
    if str(origin).endswith("Literal"):
        return str(value)
    if origin is type(None):  # pragma: no cover - defensive
        return None
    if origin is not None and str(origin) == "typing.Union":
        for candidate in get_args(annotation):
            if candidate is type(None):
                continue
            coerced = _coerce_value(value, candidate)
            return coerced
    return value


def _sanitize_arguments(func, provided: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    sig = inspect.signature(func)

    for name, param in sig.parameters.items():
        if name == "ctx":
            continue
        if name not in provided:
            continue
        raw_value = provided[name]
        if raw_value is None:
            continue
        cleaned[name] = _coerce_value(raw_value, param.annotation)

    return cleaned


def list_tools() -> List[Dict[str, Any]]:
    """
    Retorna definições de tools em formato simples para a UI.
    """

    tools = []
    for name, meta in TOOL_REGISTRY.items():
        tools.append(
            {
                "name": name,
                "description": meta.get("description"),
                "input_schema": meta.get("input_schema") or {},
            }
        )
    return tools


def call_tool(name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Invoca uma tool com conexão fresh e retorna tempo de execução.
    """

    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool desconhecida: {name}")

    meta = TOOL_REGISTRY[name]
    func = meta["func"]
    safe_args = _sanitize_arguments(func, arguments or {})

    # Garante que config de banco atual está aplicada antes de abrir conexão.
    cfg = load_db_config()
    apply_db_config(cfg)

    conn = get_connection()
    ctx = _Ctx(conn)
    started = time.perf_counter()
    try:
        raw = func(ctx, **safe_args)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "tool": name,
            "arguments": safe_args,
            "duration_ms": duration_ms,
            "result": jsonable_encoder(raw),
        }
    finally:
        conn.close()
