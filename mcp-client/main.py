"""
Aplicação FastAPI com Jinja2/Alpine para inspecionar o PEC MCP.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, List, Optional
import html
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import DbConfig, apply_db_config, load_db_config, persist_db_config
from pec_mcp.db import get_connection, query_all, query_one
from services.mcp_proxy import call_tool, list_tools
from services.llm_agent import reset_conversation, run_llm_chat
from fastapi import Query

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


class ChatPayload(BaseModel):
    provider: str = Field(default="anthropic", description="Provedor de LLM (anthropic, openai, ollama)")
    api_key: Optional[str] = Field(default=None, description="API key do provedor")
    api_base: Optional[str] = Field(default=None, description="Base URL para Ollama/OpenAI compatível")
    model: str = Field(..., description="Nome do modelo (ex.: claude-3-5-sonnet, gpt-4o, llama3)")
    prompt: str = Field(..., description="Mensagem do usuário")
    system_prompt: str = Field(
        default=(
            "Você é um agente clínico que usa tools MCP para recuperar dados. "
            "Sempre que responder com pacientes (lista ou item), acrescente o identificador real "
            "no formato @<paciente_id> usando o co_seq_cidadao devolvido pelas tools. "
            "Em tabelas Markdown, coloque o @<paciente_id> em uma coluna ou célula própria para não quebrar a formatação. "
            "Não invente ids."
        ),
        description="System prompt a ser passado ao agente.",
    )
    max_turns: int = Field(default=4, ge=1, le=10, description="Máximo de iterações tool calling.")
    tool_alias: str = Field(default="server", description="Prefixo de alias para as tools MCP.")
    conversation_id: Optional[str] = Field(default=None, description="ID da conversa em memória.")


class ChatResetPayload(BaseModel):
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


def _load_paciente_history(paciente_id: int, limite: int | None = None) -> List[Dict[str, Any]]:
    """
    Busca últimos atendimentos SOAP via tool MCP.
    """

    safe_limit = None if limite is None else max(1, min(int(limite), 1000))
    try:
        payload = call_tool(
            "listar_ultimos_atendimentos_soap",
            {"paciente_id": int(paciente_id), **({"limite": safe_limit} if safe_limit is not None else {})},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - dependente de integração MCP
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not payload.get("ok", False):
        raise HTTPException(status_code=500, detail="Falha ao consultar histórico SOAP.")

    result = payload.get("result")
    return result if isinstance(result, list) else []


def _summarize_soap_history(entries: List[Dict[str, Any]]) -> str:
    """
    Gera resumo textual simples a partir de itens SOAP.
    """

    if not entries:
        return "Nenhum atendimento SOAP encontrado para este paciente."

    def _plain(text: Any) -> Optional[str]:
        if text is None:
            return None
        raw = html.unescape(str(text))
        clean = re.sub(r"<[^>]+>", " ", raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean or None

    lines: List[str] = []
    total = len(entries)
    latest = entries[0]

    lines.append(f"{total} atendimento(s) encontrados (mais recentes primeiro).")

    latest_bits = []
    if latest.get("data_hora"):
        latest_bits.append(f"em {latest['data_hora']}")
    if latest.get("profissional"):
        latest_bits.append(f"com {latest['profissional']}")
    if latest.get("cbo_descricao"):
        latest_bits.append(f"({latest['cbo_descricao']})")
    if latest_bits:
        lines.append("Último atendimento " + " ".join(latest_bits) + ".")

    section_map = [("S", "soap_s"), ("O", "soap_o"), ("A", "soap_a"), ("P", "soap_p")]
    for label, key in section_map:
        snippets: List[str] = []
        seen: set[str] = set()
        for entry in entries:
            raw = _plain(entry.get(key))
            if not raw:
                continue
            text = " ".join(str(raw).split())
            normalized = text.lower()
            if not text or normalized in seen:
                continue
            seen.add(normalized)
            stamped = entry.get("data_hora")
            snippet = text if not stamped else f"{text} (em {stamped})"
            snippets.append(snippet)
            if len(snippets) >= 3:
                break
        if snippets:
            lines.append(f"{label}: " + " | ".join(snippets))

    return "\n".join(lines)


def _load_paciente_condicoes(paciente_id: int, limite: int = 200) -> List[Dict[str, Any]]:
    """
    Busca condições já cadastradas do paciente via tool MCP.
    """

    safe_limit = max(1, min(int(limite), 200))
    try:
        payload = call_tool(
            "listar_condicoes_pacientes",
            {"paciente_id": int(paciente_id), "limite": safe_limit},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - dependente de integração MCP
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not payload.get("ok", False):
        raise HTTPException(status_code=500, detail="Falha ao consultar condições.")

    result = payload.get("result")
    return result if isinstance(result, list) else []


_SQL_SAUDE_360_C3 = """
WITH params AS (
    SELECT %s::date AS start_date, %s::date AS end_date
),
unidade_eventos AS (
    SELECT ai.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = ai.co_dim_unidade_saude_1
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY ai.co_fat_cidadao_pec, dus.nu_cnes

    UNION ALL

    SELECT vd.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = vd.co_dim_unidade_saude
    WHERE tt.dt_registro BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY vd.co_fat_cidadao_pec, dus.nu_cnes

    UNION ALL

    SELECT v.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_vacinacao v ON v.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = v.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = v.co_dim_unidade_saude
    WHERE COALESCE(v.dt_inicial_atendimento::date, tt.dt_registro) BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY v.co_fat_cidadao_pec, dus.nu_cnes
),
unidade_inferida AS (
    SELECT
        co_fat_cidadao_pec,
        (
            SELECT nu_cnes
            FROM unidade_eventos ue2
            WHERE ue2.co_fat_cidadao_pec = ue.co_fat_cidadao_pec
            GROUP BY nu_cnes
            ORDER BY SUM(freq) DESC
            LIMIT 1
        ) AS nu_cnes
    FROM unidade_eventos ue
    GROUP BY co_fat_cidadao_pec
),
coorte AS (
    SELECT DISTINCT ON (fc.co_cidadao)
        g.co_seq_fat_rel_op_gestante AS gestacao_id,
        fc.co_seq_fat_cidadao_pec,
        fc.co_cidadao,
        fc.no_cidadao                AS nome_paciente,
        g.dt_inicio_gestacao::date AS dt_inicio_gestacao,
        g.dt_inicio_puerperio::date AS dt_inicio_puerperio,
        g.dt_fim_puerperio::date AS dt_fim_puerperio,
        COALESCE(dus.nu_cnes, ui.nu_cnes) AS nu_cnes
    FROM params p
    JOIN tb_fat_rel_op_gestante g
      ON daterange(g.dt_inicio_gestacao, g.dt_fim_puerperio, '[]')
         && daterange(p.start_date, p.end_date, '[]')
    JOIN tb_fat_cidadao_pec fc ON fc.co_seq_fat_cidadao_pec = g.co_fat_cidadao_pec
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = fc.co_dim_unidade_saude_vinc
    LEFT JOIN unidade_inferida ui ON ui.co_fat_cidadao_pec = fc.co_seq_fat_cidadao_pec
    WHERE COALESCE(dus.nu_cnes, ui.nu_cnes) IS NOT NULL
    ORDER BY fc.co_cidadao, g.dt_inicio_gestacao DESC
),
coorte_unidade AS (
    SELECT
        c.*,
        u.co_seq_unidade_saude AS unidade_id,
        u.no_unidade_saude
    FROM coorte c
    LEFT JOIN tb_unidade_saude u ON u.nu_cnes = c.nu_cnes
),
coorte_filtrada AS (
    SELECT *
    FROM coorte_unidade
    WHERE (%s IS NULL OR unidade_id = %s)
),
consulta_ate_12s AS (
    SELECT
        c.gestacao_id,
        MIN(COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)) AS primeira_consulta
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    JOIN tb_dim_cbo cbo ON cbo.co_seq_dim_cbo = ai.co_dim_cbo_1
    WHERE (cbo.nu_cbo LIKE '225%%' OR cbo.nu_cbo LIKE '2235%%')
      AND COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND LEAST(c.dt_inicio_gestacao + INTERVAL '84 days', c.dt_fim_puerperio)
    GROUP BY c.gestacao_id
),
consultas_total AS (
    SELECT
        c.gestacao_id,
        COUNT(*) AS total_consultas
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
    GROUP BY c.gestacao_id
),
pressao_eventos AS (
    SELECT DISTINCT
        c.gestacao_id,
        COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND (ai.nu_pressao_sistolica IS NOT NULL OR ai.nu_pressao_diastolica IS NOT NULL)

    UNION

    SELECT DISTINCT
        c.gestacao_id,
        tt.dt_registro AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND NULLIF(TRIM(vd.nu_medicao_pressao_arterial), '') IS NOT NULL
),
pressao_count AS (
    SELECT gestacao_id, COUNT(*) AS total_pa
    FROM pressao_eventos
    GROUP BY gestacao_id
),
antropometria_eventos AS (
    SELECT DISTINCT
        c.gestacao_id,
        COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND ai.nu_peso IS NOT NULL AND ai.nu_altura IS NOT NULL

    UNION

    SELECT DISTINCT
        c.gestacao_id,
        tt.dt_registro AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
),
antropometria_count AS (
    SELECT gestacao_id, COUNT(*) AS total_antropometria
    FROM antropometria_eventos
    GROUP BY gestacao_id
),
visitas_gestante AS (
    SELECT
        c.gestacao_id,
        COUNT(*) AS total_visitas
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND vd.st_acomp_gestante = 1
    GROUP BY c.gestacao_id
),
vacina_dtpa AS (
    SELECT DISTINCT
        c.gestacao_id
    FROM coorte_filtrada c
    JOIN tb_fat_vacinacao v ON v.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = v.co_dim_tempo
    JOIN tb_fat_vacinacao_vacina vv ON vv.co_fat_vacinacao = v.co_seq_fat_vacinacao
    JOIN tb_dim_imunobiologico im ON im.co_seq_dim_imunobiologico = vv.co_dim_imunobiologico
    WHERE im.nu_identificador = '57'
      AND COALESCE(v.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao + INTERVAL '140 days' AND c.dt_inicio_puerperio
),
indicadores AS (
    SELECT
        c.gestacao_id,
        c.unidade_id,
        c.nu_cnes AS unidade_cnes,
        COALESCE(c.no_unidade_saude, 'Unidade ' || COALESCE(c.nu_cnes, 'N/A')) AS unidade_nome,
        CASE WHEN a.primeira_consulta IS NOT NULL THEN 1 ELSE 0 END AS hit_a,
        CASE WHEN COALESCE(b.total_consultas, 0) >= 7 THEN 1 ELSE 0 END AS hit_b,
        CASE WHEN COALESCE(pc.total_pa, 0) >= 7 THEN 1 ELSE 0 END AS hit_c,
        CASE WHEN COALESCE(an.total_antropometria, 0) >= 7 THEN 1 ELSE 0 END AS hit_d,
        CASE WHEN COALESCE(vg.total_visitas, 0) >= 3 THEN 1 ELSE 0 END AS hit_e,
        CASE WHEN f.gestacao_id IS NOT NULL THEN 1 ELSE 0 END AS hit_f
    FROM coorte_unidade c
    LEFT JOIN consulta_ate_12s a ON a.gestacao_id = c.gestacao_id
    LEFT JOIN consultas_total b ON b.gestacao_id = c.gestacao_id
    LEFT JOIN pressao_count pc ON pc.gestacao_id = c.gestacao_id
    LEFT JOIN antropometria_count an ON an.gestacao_id = c.gestacao_id
    LEFT JOIN visitas_gestante vg ON vg.gestacao_id = c.gestacao_id
    LEFT JOIN vacina_dtpa f ON f.gestacao_id = c.gestacao_id
),
scores AS (
    SELECT
        i.*,
        (10 * hit_a + 9 * hit_b + 9 * hit_c + 9 * hit_d + 9 * hit_e + 9 * hit_f) AS score_total
    FROM indicadores i
)
SELECT
    s.unidade_id,
    s.unidade_cnes,
    s.unidade_nome,
    COUNT(*) AS gestacoes,
    SUM(hit_a) AS total_a,
    SUM(hit_b) AS total_b,
    SUM(hit_c) AS total_c,
    SUM(hit_d) AS total_d,
    SUM(hit_e) AS total_e,
    SUM(hit_f) AS total_f,
    SUM(score_total) AS total_score,
    ROUND(SUM(score_total)::numeric / NULLIF(COUNT(*), 0), 2) AS c3_score
FROM scores s
GROUP BY s.unidade_id, s.unidade_cnes, s.unidade_nome
ORDER BY c3_score DESC NULLS LAST, s.unidade_nome;
"""

_SQL_SAUDE_360_C3_DETAIL_TEMPLATE = """
WITH params AS (
    SELECT %s::date AS start_date, %s::date AS end_date
),
unidade_eventos AS (
    SELECT ai.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = ai.co_dim_unidade_saude_1
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY ai.co_fat_cidadao_pec, dus.nu_cnes

    UNION ALL

    SELECT vd.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = vd.co_dim_unidade_saude
    WHERE tt.dt_registro BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY vd.co_fat_cidadao_pec, dus.nu_cnes

    UNION ALL

    SELECT v.co_fat_cidadao_pec, dus.nu_cnes, COUNT(*) AS freq
    FROM params p
    JOIN tb_fat_vacinacao v ON v.co_fat_cidadao_pec IS NOT NULL
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = v.co_dim_tempo
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = v.co_dim_unidade_saude
    WHERE COALESCE(v.dt_inicial_atendimento::date, tt.dt_registro) BETWEEN p.start_date AND p.end_date
      AND dus.nu_cnes IS NOT NULL
    GROUP BY v.co_fat_cidadao_pec, dus.nu_cnes
),
unidade_inferida AS (
    SELECT
        co_fat_cidadao_pec,
        (
            SELECT nu_cnes
            FROM unidade_eventos ue2
            WHERE ue2.co_fat_cidadao_pec = ue.co_fat_cidadao_pec
            GROUP BY nu_cnes
            ORDER BY SUM(freq) DESC
            LIMIT 1
        ) AS nu_cnes
    FROM unidade_eventos ue
    GROUP BY co_fat_cidadao_pec
),
coorte AS (
    SELECT DISTINCT ON (fc.co_cidadao)
        g.co_seq_fat_rel_op_gestante AS gestacao_id,
        fc.co_seq_fat_cidadao_pec,
        fc.co_cidadao,
        fc.no_cidadao                AS nome_paciente,
        g.dt_inicio_gestacao::date AS dt_inicio_gestacao,
        g.dt_inicio_puerperio::date AS dt_inicio_puerperio,
        g.dt_fim_puerperio::date AS dt_fim_puerperio,
        COALESCE(dus.nu_cnes, ui.nu_cnes) AS nu_cnes
    FROM params p
    JOIN tb_fat_rel_op_gestante g
      ON daterange(g.dt_inicio_gestacao, g.dt_fim_puerperio, '[]')
         && daterange(p.start_date, p.end_date, '[]')
    JOIN tb_fat_cidadao_pec fc ON fc.co_seq_fat_cidadao_pec = g.co_fat_cidadao_pec
    LEFT JOIN tb_dim_unidade_saude dus ON dus.co_seq_dim_unidade_saude = fc.co_dim_unidade_saude_vinc
    LEFT JOIN unidade_inferida ui ON ui.co_fat_cidadao_pec = fc.co_seq_fat_cidadao_pec
    WHERE COALESCE(dus.nu_cnes, ui.nu_cnes) IS NOT NULL
    ORDER BY fc.co_cidadao, g.dt_inicio_gestacao DESC
),
coorte_unidade AS (
    SELECT
        c.*,
        u.co_seq_unidade_saude AS unidade_id,
        u.no_unidade_saude
    FROM coorte c
    LEFT JOIN tb_unidade_saude u ON u.nu_cnes = c.nu_cnes
),
coorte_filtrada AS (
    SELECT *
    FROM coorte_unidade
    WHERE (%s IS NULL OR unidade_id = %s)
),
consulta_ate_12s AS (
    SELECT
        c.gestacao_id,
        MIN(COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)) AS primeira_consulta
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    JOIN tb_dim_cbo cbo ON cbo.co_seq_dim_cbo = ai.co_dim_cbo_1
    WHERE (cbo.nu_cbo LIKE '225%%' OR cbo.nu_cbo LIKE '2235%%')
      AND COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND LEAST(c.dt_inicio_gestacao + INTERVAL '84 days', c.dt_fim_puerperio)
    GROUP BY c.gestacao_id
),
consultas_total AS (
    SELECT
        c.gestacao_id,
        COUNT(*) AS total_consultas
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
    GROUP BY c.gestacao_id
),
pressao_eventos AS (
    SELECT DISTINCT
        c.gestacao_id,
        COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND (ai.nu_pressao_sistolica IS NOT NULL OR ai.nu_pressao_diastolica IS NOT NULL)

    UNION

    SELECT DISTINCT
        c.gestacao_id,
        tt.dt_registro AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND NULLIF(TRIM(vd.nu_medicao_pressao_arterial), '') IS NOT NULL
),
pressao_count AS (
    SELECT gestacao_id, COUNT(*) AS total_pa
    FROM pressao_eventos
    GROUP BY gestacao_id
),
antropometria_eventos AS (
    SELECT DISTINCT
        c.gestacao_id,
        COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro) AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_atendimento_individual ai ON ai.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = ai.co_dim_tempo
    WHERE COALESCE(ai.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND ai.nu_peso IS NOT NULL AND ai.nu_altura IS NOT NULL

    UNION

    SELECT DISTINCT
        c.gestacao_id,
        tt.dt_registro AS data_evento
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
),
antropometria_count AS (
    SELECT gestacao_id, COUNT(*) AS total_antropometria
    FROM antropometria_eventos
    GROUP BY gestacao_id
),
visitas_gestante AS (
    SELECT
        c.gestacao_id,
        COUNT(*) AS total_visitas
    FROM coorte_filtrada c
    JOIN tb_fat_visita_domiciliar vd ON vd.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = vd.co_dim_tempo
    WHERE tt.dt_registro BETWEEN c.dt_inicio_gestacao AND c.dt_inicio_puerperio
      AND vd.st_acomp_gestante = 1
    GROUP BY c.gestacao_id
),
vacina_dtpa AS (
    SELECT DISTINCT
        c.gestacao_id
    FROM coorte_filtrada c
    JOIN tb_fat_vacinacao v ON v.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_tempo tt ON tt.co_seq_dim_tempo = v.co_dim_tempo
    JOIN tb_fat_vacinacao_vacina vv ON vv.co_fat_vacinacao = v.co_seq_fat_vacinacao
    JOIN tb_dim_imunobiologico im ON im.co_seq_dim_imunobiologico = vv.co_dim_imunobiologico
    WHERE im.nu_identificador = '57'
      AND COALESCE(v.dt_inicial_atendimento::date, tt.dt_registro)
          BETWEEN c.dt_inicio_gestacao + INTERVAL '140 days' AND c.dt_inicio_puerperio
),
detalhes AS (
    SELECT
        c.gestacao_id,
        c.co_cidadao AS paciente_id,
        c.nome_paciente,
        c.unidade_id,
        c.nu_cnes AS unidade_cnes,
        COALESCE(c.no_unidade_saude, 'Unidade ' || COALESCE(c.nu_cnes, 'N/A')) AS unidade_nome,
        c.dt_inicio_gestacao,
        c.dt_inicio_puerperio,
        a.primeira_consulta,
        COALESCE(b.total_consultas, 0) AS total_consultas,
        COALESCE(pc.total_pa, 0) AS total_pa,
        COALESCE(an.total_antropometria, 0) AS total_antropometria,
        COALESCE(vg.total_visitas, 0) AS total_visitas,
        CASE WHEN f.gestacao_id IS NOT NULL THEN 1 ELSE 0 END AS hit_f
    FROM coorte_filtrada c
    LEFT JOIN consulta_ate_12s a ON a.gestacao_id = c.gestacao_id
    LEFT JOIN consultas_total b ON b.gestacao_id = c.gestacao_id
    LEFT JOIN pressao_count pc ON pc.gestacao_id = c.gestacao_id
    LEFT JOIN antropometria_count an ON an.gestacao_id = c.gestacao_id
    LEFT JOIN visitas_gestante vg ON vg.gestacao_id = c.gestacao_id
    LEFT JOIN vacina_dtpa f ON f.gestacao_id = c.gestacao_id
)
SELECT
    d.*,
    COUNT(*) OVER() AS total_rows
FROM detalhes d
WHERE {where_clause}
ORDER BY d.unidade_nome, d.nome_paciente
LIMIT %s OFFSET %s;
"""


def _calc_saude_360_c3(
    start_date: Optional[date],
    end_date: Optional[date],
    unidade_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calcula o indicador C3 (gestante/puérpera) agrupado por unidade, sem usar LLM.
    """

    today = date.today()
    start = start_date or (today - timedelta(days=365))
    end = end_date or today
    if start > end:
        raise HTTPException(status_code=400, detail="start_date não pode ser maior que end_date.")

    cfg = load_db_config()
    apply_db_config(cfg)
    conn = get_connection()
    try:
        unit_param = int(unidade_id) if unidade_id is not None else None
        rows = query_all(conn, _SQL_SAUDE_360_C3, [start, end, unit_param, unit_param])
    finally:
        conn.close()

    unidades: List[Dict[str, Any]] = []
    coorte_total = 0
    for row in rows:
        gestacoes = int(row.get("gestacoes", 0) or 0)
        coorte_total += gestacoes
        c3_score = row.get("c3_score")
        unidades.append(
            {
                "unidade_id": row.get("unidade_id"),
                "cnes": row.get("unidade_cnes"),
                "nome": row.get("unidade_nome"),
                "gestacoes": gestacoes,
                "score_total": float(row.get("total_score") or 0.0),
                "score_c3": float(c3_score) if c3_score is not None else None,
                "componentes": {
                    "a_primeira_consulta_ate_12s": int(row.get("total_a", 0) or 0),
                    "b_consultas_7_ou_mais": int(row.get("total_b", 0) or 0),
                    "c_pressao_arterial_7": int(row.get("total_c", 0) or 0),
                    "d_peso_altura_7": int(row.get("total_d", 0) or 0),
                    "e_visitas_gestante_3": int(row.get("total_e", 0) or 0),
                    "f_dtpa_apos_20s": int(row.get("total_f", 0) or 0),
                },
            }
        )

    return {
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "coorte_total": coorte_total,
        "unidades": unidades,
    }


def _calc_saude_360_c3_detail(
    component: str,
    start_date: Optional[date],
    end_date: Optional[date],
    unidade_id: Optional[int],
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    """
    Retorna pacientes/gestações em déficit para um componente (A-F) do C3 em uma unidade.
    """

    today = date.today()
    start = start_date or (today - timedelta(days=365))
    end = end_date or today
    if start > end:
        raise HTTPException(status_code=400, detail="start_date não pode ser maior que end_date.")

    comp = component.upper()
    where_map = {
        "A": "d.primeira_consulta IS NULL",
        "B": "d.total_consultas < 7",
        "C": "d.total_pa < 7",
        "D": "d.total_antropometria < 7",
        "E": "d.total_visitas < 3",
        "F": "d.hit_f = 0",
    }
    if comp not in where_map:
        raise HTTPException(status_code=400, detail="Componente inválido (use A, B, C, D, E ou F).")

    safe_page_size = max(1, min(int(page_size), 200))
    safe_page = max(1, int(page))
    offset = (safe_page - 1) * safe_page_size

    sql = _SQL_SAUDE_360_C3_DETAIL_TEMPLATE.format(where_clause=where_map[comp])
    unit_param = int(unidade_id) if unidade_id is not None else None

    cfg = load_db_config()
    apply_db_config(cfg)
    conn = get_connection()
    try:
        rows = query_all(conn, sql, [start, end, unit_param, unit_param, safe_page_size, offset])
    finally:
        conn.close()

    total_rows = rows[0]["total_rows"] if rows else 0
    results = []
    for row in rows:
        results.append(
            {
                "paciente_id": row.get("paciente_id"),
                "nome": row.get("nome_paciente"),
                "gestacao_id": row.get("gestacao_id"),
                "unidade_id": row.get("unidade_id"),
                "unidade_cnes": row.get("unidade_cnes"),
                "unidade_nome": row.get("unidade_nome"),
                "dt_inicio_gestacao": _to_iso_date(row.get("dt_inicio_gestacao")),
                "dt_inicio_puerperio": _to_iso_date(row.get("dt_inicio_puerperio")),
                "primeira_consulta": _to_iso_date(row.get("primeira_consulta")),
                "total_consultas": int(row.get("total_consultas", 0) or 0),
                "total_pa": int(row.get("total_pa", 0) or 0),
                "total_antropometria": int(row.get("total_antropometria", 0) or 0),
                "total_visitas": int(row.get("total_visitas", 0) or 0),
                "tem_dtpa": bool(row.get("hit_f")),
            }
        )

    total_pages = (total_rows + safe_page_size - 1) // safe_page_size if total_rows else 0
    return {
        "component": comp,
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "unidade_id": unidade_id,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": int(total_rows),
        "total_pages": int(total_pages),
        "results": results,
    }


@app.get("/")
async def index(request: Request):
    cfg = load_db_config()
    initial_config_json = json.dumps(cfg.as_dict())
    
    # Defaults from env
    chat_defaults = {
        "provider": os.getenv("LLM_PROVIDER", "anthropic"),
        "api_key": os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", ""),
        "api_base": os.getenv("LLM_API_BASE", ""),
        "model": os.getenv("LLM_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022",
    }
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "initial_config": cfg.as_dict(),
            "initial_config_json": initial_config_json,
            "chat_defaults": chat_defaults,
        },
    )


@app.get("/help")
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})


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


@app.post("/api/chat/run")
async def api_chat_run(payload: ChatPayload):
    try:
        conversation_id, events = await run_in_threadpool(
            run_llm_chat,
            payload.provider,
            payload.model,
            payload.api_key,
            payload.prompt,
            payload.system_prompt,
            payload.max_turns,
            payload.tool_alias,
            payload.conversation_id,
            payload.api_base
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"conversation_id": conversation_id, "events": events}


@app.post("/api/chat/stream")
async def api_chat_stream(payload: ChatPayload):
    queue: Queue = Queue()
    done = object()

    def push_event(event: Dict[str, Any]) -> None:
        queue.put({"event": event})

    def worker() -> None:
        try:
            conversation_id, _ = run_llm_chat(
                payload.provider,
                payload.model,
                payload.api_key,
                payload.prompt,
                payload.system_prompt,
                payload.max_turns,
                payload.tool_alias,
                payload.conversation_id,
                payload.api_base,
                event_callback=push_event,
                collect_events=False,
            )
            queue.put({"conversation_id": conversation_id})
        except Exception as exc:
            queue.put({"error": str(exc)})
        finally:
            queue.put(done)

    Thread(target=worker, daemon=True).start()

    def iter_lines():
        while True:
            item = queue.get()
            if item is done:
                break
            yield (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(iter_lines(), media_type="application/x-ndjson")


@app.post("/api/chat/reset")
async def api_chat_reset(payload: ChatResetPayload):
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


@app.get("/api/pacientes/{paciente_id}/historico")
async def api_get_paciente_historico(paciente_id: int, limite: int | None = None):
    try:
        historico = await run_in_threadpool(_load_paciente_history, paciente_id, limite)
        resumo = _summarize_soap_history(historico)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - depende do banco/tool
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"historico": historico, "resumo": resumo}


@app.get("/api/pacientes/{paciente_id}/condicoes")
async def api_get_paciente_condicoes(paciente_id: int, limite: int = 200):
    try:
        condicoes = await run_in_threadpool(_load_paciente_condicoes, paciente_id, limite)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - depende do banco/tool
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"condicoes": condicoes}


@app.get("/saude-360/c3")
async def api_saude_360_c3(
    start_date: Optional[date] = Query(None, description="Data inicial (YYYY-MM-DD); default últimos 12 meses."),
    end_date: Optional[date] = Query(None, description="Data final (YYYY-MM-DD); default hoje."),
    unidade_id: Optional[int] = Query(None, description="Filtra por unidade (co_seq_unidade_saude)."),
):
    try:
        result = await run_in_threadpool(_calc_saude_360_c3, start_date, end_date, unidade_id)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - depende do banco/tool
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.get("/saude-360/c3/{component}")
async def api_saude_360_c3_component(
    component: str,
    start_date: Optional[date] = Query(None, description="Data inicial (YYYY-MM-DD); default últimos 12 meses."),
    end_date: Optional[date] = Query(None, description="Data final (YYYY-MM-DD); default hoje."),
    unidade_id: Optional[int] = Query(None, description="Filtra por unidade (co_seq_unidade_saude)."),
    page: int = Query(1, ge=1, description="Página (1-n)."),
    page_size: int = Query(25, ge=1, le=200, description="Tamanho da página (1-200)."),
):
    try:
        result = await run_in_threadpool(
            _calc_saude_360_c3_detail, component, start_date, end_date, unidade_id, page, page_size
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


__all__ = ["app"]
