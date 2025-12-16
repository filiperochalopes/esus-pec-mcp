"""
Aplicação FastAPI com Jinja2/Alpine para inspecionar o PEC MCP.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import DbConfig, apply_db_config, load_db_config, persist_db_config
from pec_mcp.db import get_connection, query_all, query_one
from services.mcp_proxy import call_tool, list_tools
from services.claude_agent import reset_conversation, run_claude_chat

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

app = FastAPI(title="PEC MCP UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


class ConfigPayload(BaseModel):
    host: str = Field(..., description="Host do banco")
    port: str = Field(..., description="Porta")
    name: str = Field(..., description="Nome do DB")
    user: str = Field(..., description="Usuário")
    password: str = Field(..., description="Senha")

    def to_config(self) -> DbConfig:
        return DbConfig(
            host=self.host.strip(),
            port=self.port.strip(),
            name=self.name.strip(),
            user=self.user.strip(),
            password=self.password.strip(),
        )


class ToolCallPayload(BaseModel):
    tool: str = Field(..., description="Nome da tool MCP")
    arguments: Optional[Dict[str, Any]] = Field(default=None, description="Payload de argumentos")


class ClaudeChatPayload(BaseModel):
    api_key: str = Field(..., description="Anthropic API key")
    model: str = Field(..., description="Modelo Claude (ex.: claude-3-5-sonnet-20241022)")
    prompt: str = Field(..., description="Mensagem do usuário")
    system_prompt: str = Field(
        default=(
            "Você é um agente clínico que usa tools MCP para recuperar dados. "
            "Sempre que responder com pacientes (lista ou item), acrescente ao final de cada linha "
            "o identificador real no formato @<paciente_id> usando o co_seq_cidadao devolvido pelas tools. "
            "Não invente ids."
        ),
        description="System prompt a ser passado ao Claude.",
    )
    max_turns: int = Field(default=4, ge=1, le=8, description="Máximo de iterações tool calling.")
    tool_alias: str = Field(default="server", description="Prefixo de alias para as tools MCP.")
    conversation_id: Optional[str] = Field(default=None, description="ID da conversa em memória.")


class ClaudeResetPayload(BaseModel):
    conversation_id: str = Field(..., description="ID da conversa para limpar")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


_SQL_UNIDADES = """
SELECT
    us.co_seq_unidade_saude   AS unidade_id,
    us.nu_cnes                AS cnes,
    us.no_unidade_saude       AS nome,
    us.co_localidade_endereco AS localidade_id,
    us.st_ativo               AS ativo
FROM tb_unidade_saude us
ORDER BY us.no_unidade_saude;
"""


def _load_unidades_saude():
    """
    Busca unidades direto no banco, sem passar pelo MCP/tool calling.
    """

    cfg = load_db_config()
    apply_db_config(cfg)
    conn = get_connection()
    try:
        rows = query_all(conn, _SQL_UNIDADES)
        result = []
        for row in rows:
            result.append(
                {
                    "unidade_id": int(row["unidade_id"]),
                    "cnes": row.get("cnes"),
                    "name": row.get("nome"),
                    "localidade_id": int(row["localidade_id"]) if row.get("localidade_id") is not None else None,
                    "is_active": bool(row.get("ativo")),
                }
            )
        return result
    finally:
        conn.close()


_SQL_PACIENTE_BY_ID = """
SELECT
    c.co_seq_cidadao AS paciente_id,
    c.no_cidadao     AS nome,
    c.dt_nascimento  AS data_nascimento,
    c.no_sexo        AS sexo
FROM tb_cidadao c
WHERE c.co_seq_cidadao = %s
LIMIT 1;
"""


def _to_iso_date(value):
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _calc_age_years(birth_date) -> Optional[int]:
    if birth_date is None:
        return None
    try:
        today = date.today()
        years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return max(years, 0)
    except Exception:
        return None


def _load_paciente_by_id(paciente_id: int) -> Dict[str, Any]:
    cfg = load_db_config()
    apply_db_config(cfg)
    conn = get_connection()
    try:
        row = query_one(conn, _SQL_PACIENTE_BY_ID, [paciente_id])
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")

    birth_date = row.get("data_nascimento")
    birth_iso = _to_iso_date(birth_date)
    return {
        "id": int(row["paciente_id"]),
        "name": row.get("nome"),
        "sex": row.get("sexo"),
        "birth_date": birth_iso,
        "age_years": _calc_age_years(birth_date),
    }


@app.get("/")
async def index(request: Request):
    cfg = load_db_config()
    initial_config_json = json.dumps(cfg.as_dict())
    model_env = os.getenv("ANTHROPIC_MODEL") or os.getenv("CLAUDE_MODEL")
    claude_defaults = {
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        # Usa ANTHROPIC_MODEL (ou CLAUDE_MODEL por compat) e cai em sonnet padrão.
        "model": model_env or "claude-3-5-sonnet-20241022",
    }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "initial_config": cfg.as_dict(),
            "initial_config_json": initial_config_json,
            "claude_defaults": claude_defaults,
        },
    )


@app.get("/api/config")
async def get_config():
    cfg = load_db_config()
    return cfg.as_dict()


@app.post("/api/config")
async def save_config(payload: ConfigPayload):
    cfg = payload.to_config()
    persist_db_config(cfg)
    apply_db_config(cfg)
    return {"ok": True, "config": cfg.as_dict()}


@app.get("/api/tools")
async def api_list_tools():
    tools = await run_in_threadpool(list_tools)
    return {"tools": tools}


@app.post("/api/tools/call")
async def api_call_tool(payload: ToolCallPayload):
    try:
        result = await run_in_threadpool(call_tool, payload.tool, payload.arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - depende de runtime externo
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/claude/chat")
async def api_claude_chat(payload: ClaudeChatPayload):
    try:
        conversation_id, events = await run_in_threadpool(
            run_claude_chat,
            payload.api_key,
            payload.model,
            payload.prompt,
            payload.system_prompt,
            payload.max_turns,
            payload.tool_alias,
            payload.conversation_id,
        )
    except Exception as exc:  # pragma: no cover - dependente do cliente Anthropic
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"conversation_id": conversation_id, "events": events}


@app.post("/api/claude/reset")
async def api_claude_reset(payload: ClaudeResetPayload):
    reset_conversation(payload.conversation_id)
    return {"ok": True}


@app.get("/api/unidades")
async def api_list_unidades():
    try:
        unidades = await run_in_threadpool(_load_unidades_saude)
    except Exception as exc:  # pragma: no cover - depende do banco
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"unidades": unidades}


@app.get("/api/pacientes/{paciente_id}")
async def api_get_paciente(paciente_id: int):
    try:
        paciente = await run_in_threadpool(_load_paciente_by_id, paciente_id)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - depende do banco
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"paciente": paciente}


__all__ = ["app"]
