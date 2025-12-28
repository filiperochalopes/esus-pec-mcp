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
from pec_mcp.tools.condicoes import listar_condicoes_pacientes
from pec_mcp.tools.obter_codigos_condicao_saude import obter_codigos_condicao_saude
from pec_mcp.tools.contar_pacientes import contar_pacientes
from pec_mcp.tools.unidades import listar_unidades_saude
from pec_mcp.tools.atendimentos import listar_ultimos_atendimentos_soap
from pec_mcp.tools.sem_consulta import contar_pacientes_sem_consulta, listar_pacientes_sem_consulta


class _Ctx:
    """
    Contexto mínimo compatível com FastMCP (possui state.db_conn).
    """

    def __init__(self, conn):
        self.state = {"db_conn": conn}


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "capturar_paciente": {
        "func": capturar_paciente,
        "description": "Retorna pacientes anonimizados por id ou filtros; exige ao menos um criterio de paciente.",
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
    "obter_codigos_condicao_saude": {
        "func": obter_codigos_condicao_saude,
        "description": (
            "Mapeia uma condicao de saude para codigos CID-10/CIAP "
            "(presets + busca por nome). Use para perguntas do tipo "
            "\"quais CID/CIAP de X\" e antes de filtrar por condicao."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "condicao": {
                    "type": "string",
                    "description": "Nome da condicao para mapear codigos (ex.: diabetes, gravidez).",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Quantidade maxima de codigos por sistema (1-200).",
                },
            },
            "required": ["condicao"],
        },
    },
    "listar_ultimos_atendimentos_soap": {
        "func": listar_ultimos_atendimentos_soap,
        "description": "Lista os ultimos atendimentos SOAP (S/O/A/P) de um paciente por id, com profissional e CBO.",
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
                    "maximum": 1000,
                    "description": "Quantidade máxima de atendimentos (1-1000). Se omitido, retorna todos.",
                },
            },
            "required": ["paciente_id"],
        },
    },
    "listar_condicoes_pacientes": {
        "func": listar_condicoes_pacientes,
        "description": (
            "Somente para listar condicoes registradas em pacientes (CID/CIAP + ultima evolucao) "
            "usando filtros. Para descobrir codigos de uma condicao, use obter_codigos_condicao_saude."
        ),
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
        "description": (
            "Retorna apenas {count} de pacientes distintos aplicando filtros; "
            "exige ao menos um criterio e nao retorna lista de pacientes."
        ),
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
    "contar_pacientes_sem_consulta": {
        "func": contar_pacientes_sem_consulta,
        "description": (
            "Conta pacientes com hipertensao/diabetes/gestacao sem consulta recente "
            "com medico/enfermeiro (CBO 225%/2235%); retorna apenas {count}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["hipertensao", "diabetes", "gestante"],
                    "description": "Perfil clinico para o filtro (obrigatorio).",
                },
                "dias_sem_consulta": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Dias desde a ultima consulta (default 180 para hipertensao/diabetes e 60 para gestantes).",
                },
                "unidade_saude_id": {
                    "type": "integer",
                    "description": "Filtra pacientes vinculados e considera consultas apenas na unidade.",
                },
            },
            "required": ["tipo"],
        },
    },
    "listar_pacientes_sem_consulta": {
        "func": listar_pacientes_sem_consulta,
        "description": (
            "Lista pacientes com hipertensao/diabetes/gestacao sem consulta recente "
            "com medico/enfermeiro (CBO 225%/2235%), com paginacao."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["hipertensao", "diabetes", "gestante"],
                    "description": "Perfil clinico para o filtro (obrigatorio).",
                },
                "dias_sem_consulta": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Dias desde a ultima consulta (default 180 para hipertensao/diabetes e 60 para gestantes).",
                },
                "unidade_saude_id": {
                    "type": "integer",
                    "description": "Filtra pacientes vinculados e considera consultas apenas na unidade.",
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Quantidade maxima de registros (1-200).",
                },
                "offset": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                    "description": "Offset de paginacao (>= 0).",
                },
            },
            "required": ["tipo"],
        },
    },
    "listar_unidades_saude": {
        "func": listar_unidades_saude,
        "description": "Lista todas as unidades de saude (co_seq_unidade_saude, CNES e nome) para uso em filtros.",
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
