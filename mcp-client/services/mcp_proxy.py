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

from config import apply_db_config, load_db_config
from pec_mcp.db import get_connection
from pec_mcp.tools.paciente import capturar_paciente
from pec_mcp.tools.condicoes import listar_condicoes
from pec_mcp.tools.contar_pacientes import contar_pacientes
from pec_mcp.tools.unidades import listar_unidades_saude
from pec_mcp.tools.atendimentos import listar_ultimos_atendimentos_soap


class _Ctx:
    """
    Contexto mínimo compatível com FastMCP (possui state.db_conn).
    """

    def __init__(self, conn):
        self.state = {"db_conn": conn}


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "capturar_paciente": {
        "func": capturar_paciente,
        "description": "Returns de-identified patient records (initials, birth date, sex, gender) by id or filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {
                    "type": "integer",
                    "description": "Identificador interno do paciente (co_seq_cidadao).",
                },
                "name_starts_with": {
                    "type": "string",
                    "description": "Prefixo do nome (por exemplo, 'A').",
                },
                "sex": {
                    "type": "string",
                    "description": "Sexo (ex.: 'MASCULINO', 'FEMININO', 'INDETERMINADO'; aceita aliases M/F/I).",
                },
                "age_min": {
                    "type": "integer",
                    "description": "Idade mínima (anos).",
                },
                "age_max": {
                    "type": "integer",
                    "description": "Idade máxima (anos).",
                },
                "unidade_saude_id": {
                    "type": "integer",
                    "description": "Filtra pacientes com atendimento/vínculo na unidade (co_seq_unidade_saude).",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Quantidade máxima de registros (1-200).",
                },
            },
            "required": [],
        },
    },
    "listar_ultimos_atendimentos_soap": {
        "func": listar_ultimos_atendimentos_soap,
        "description": "Lista os últimos atendimentos SOAP (S/O/A/P) de um paciente por id, retornando dados do profissional e CBO.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {
                    "type": "integer",
                    "description": "Identificador interno do paciente (co_seq_cidadao).",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 10,
                    "description": "Quantidade máxima de atendimentos (1-200).",
                },
            },
            "required": ["paciente_id"],
        },
    },
    "listar_condicoes": {
        "func": listar_condicoes,
        "description": "Lista condições de saúde (CID/CIAP) com iniciais e dados mínimos do paciente; exige pelo menos um filtro.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {"type": "integer", "description": "Identificador interno do paciente (co_seq_cidadao)."},
                "name_starts_with": {"type": "string", "description": "Prefixo do nome (ex.: 'A')."},
                "sex": {"type": "string", "description": "Sexo (MASCULINO/FEMININO/INDETERMINADO ou M/F/I)."},
                "age_min": {"type": "integer", "description": "Idade mínima em anos."},
                "age_max": {"type": "integer", "description": "Idade máxima em anos."},
                "unidade_saude_id": {
                    "type": "integer",
                    "description": "Filtra pacientes/condições por unidade (co_seq_unidade_saude).",
                },
                "cid_code": {"type": "string", "description": "Código ou prefixo CID-10 (ex.: 'E11' ou 'E11%')."},
                "cid_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de códigos/prefixos CID-10; combinados com cid_logic (OR por padrão).",
                },
                "cid_logic": {
                    "type": "string",
                    "enum": ["OR", "AND"],
                    "default": "OR",
                    "description": "Combina múltiplos CID-10 com OR (default). AND não é suportado para listagem com múltiplos códigos.",
                },
                "ciap_code": {"type": "string", "description": "Código ou prefixo CIAP."},
                "condition_text": {"type": "string", "description": "Trecho textual para buscar em descrições/observações."},
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Quantidade máxima de registros (1-200).",
                },
            },
            "required": [],
        },
    },
    "contar_pacientes": {
        "func": contar_pacientes,
        "description": "Retorna apenas {count} de pacientes distintos aplicando filtros de paciente e/ou condição; exige ao menos um critério.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paciente_id": {"type": "integer", "description": "Identificador interno do paciente (co_seq_cidadao)."},
                "name_starts_with": {"type": "string", "description": "Prefixo do nome (ex.: 'A')."},
                "sex": {"type": "string", "description": "Sexo (MASCULINO/FEMININO/INDETERMINADO ou M/F/I)."},
                "age_min": {"type": "integer", "description": "Idade mínima em anos."},
                "age_max": {"type": "integer", "description": "Idade máxima em anos."},
                "unidade_saude_id": {
                    "type": "integer",
                    "description": "Filtra pacientes por unidade (co_seq_unidade_saude).",
                },
                "cid_code": {"type": "string", "description": "Código ou prefixo CID-10."},
                "cid_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de códigos/prefixos CID-10; combinados via cid_logic (OR/AND).",
                },
                "cid_logic": {
                    "type": "string",
                    "enum": ["OR", "AND"],
                    "default": "OR",
                    "description": "Combina múltiplos CID-10 com OR (default) ou AND (paciente deve ter todos os códigos).",
                },
                "ciap_code": {"type": "string", "description": "Código ou prefixo CIAP."},
                "condition_text": {"type": "string", "description": "Trecho textual para descrições/observações."},
            },
            "required": [],
        },
    },
    "listar_unidades_saude": {
        "func": listar_unidades_saude,
        "description": "Lista todas as unidades de saúde (co_seq_unidade_saude, CNES e nome) para uso em filtros.",
        "input_schema": {"type": "object", "properties": {}},
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
