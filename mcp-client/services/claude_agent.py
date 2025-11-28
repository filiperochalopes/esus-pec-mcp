"""
Orquestração Claude + MCP tools usando o SDK Python da Anthropic.

Mantemos um laço simples: o modelo decide ferramentas, executamos pelo
`mcp_proxy.call_tool` e devolvemos tool_result para a próxima rodada.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

from anthropic import Anthropic
from anthropic.types import Message, MessageParam

from .mcp_proxy import call_tool, list_tools


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _random_id() -> str:
    return f"id-{int(time.time() * 1000)}-{hex(int(time.time() * 1_000_000))[-6:]}"


def _render_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _to_anthropic_tools(alias: str, tools: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Prefixa nomes de tool para evitar colisões e gera mapa reverso.
    """

    name_map: Dict[str, str] = {}
    anthropic_tools: List[Dict[str, Any]] = []

    for tool in tools:
        prefixed = f"mcp__{alias}__{tool['name']}"
        name_map[prefixed] = tool["name"]
        anthropic_tools.append(
            {
                "name": prefixed,
                "description": tool.get("description") or "",
                "input_schema": tool.get("input_schema") or {"type": "object"},
            }
        )
    return anthropic_tools, name_map


def _tool_result_blocks(tool_uses: List[Any], results: List[Dict[str, Any]]) -> List[ToolResultBlockParam]:
    """
    Converte chamadas de ferramenta em blocos tool_result para Anthropic.
    """

    blocks: List[ToolResultBlockParam] = []
    for idx, tool_use in enumerate(tool_uses):
        result = results[idx] if idx < len(results) else None
        blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "is_error": bool(result and not result.get("ok", True)),
                "content": [
                    {"type": "text", "text": _render_json(result.get("result") if result else None)}
                ],
            }
        )
    return blocks


def run_claude_chat(
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    max_turns: int = 4,
    tool_alias: str = "server",
) -> List[Dict[str, Any]]:
    """
    Executa o laço Claude + MCP tools e devolve a linha do tempo de eventos.
    """

    events: List[Dict[str, Any]] = []

    def emit(event: Dict[str, Any]):
        events.append(event)

    client = Anthropic(api_key=api_key)

    mcp_tools = list_tools()
    anthropic_tools, name_map = _to_anthropic_tools(tool_alias or "server", mcp_tools)

    messages: List[MessageParam] = [
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ]

    emit({"id": _random_id(), "type": "USER_MESSAGE", "text": prompt, "timestamp": _now_iso()})

    for _ in range(max_turns):
        response: Message = client.messages.create(
            model=model,
            system=system_prompt,
            max_tokens=8000,
            temperature=0,
            tools=anthropic_tools,
            messages=messages,
        )

        text_parts = "\n".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

        if text_parts:
            emit(
                {
                    "id": _random_id(),
                    "type": "MODEL_MESSAGE",
                    "text": text_parts,
                    "timestamp": _now_iso(),
                }
            )

        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        if not tool_use_blocks:
            break

        tool_results: List[Dict[str, Any]] = []
        for tool_use in tool_use_blocks:
            actual_name = name_map.get(tool_use.name, tool_use.name)
            args = tool_use.input if isinstance(tool_use.input, dict) else {}

            emit(
                {
                    "id": _random_id(),
                    "type": "TOOL_CALL",
                    "tool_name": actual_name,
                    "tool_input": args,
                    "timestamp": _now_iso(),
                }
            )

            result = call_tool(actual_name, args)
            tool_results.append(result)

            emit(
                {
                    "id": _random_id(),
                    "type": "TOOL_RESULT",
                    "tool_name": actual_name,
                    "tool_output": result.get("result"),
                    "duration_ms": result.get("duration_ms"),
                    "timestamp": _now_iso(),
                }
            )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": _tool_result_blocks(tool_use_blocks, tool_results)})

    emit({"id": _random_id(), "type": "COMPLETE", "timestamp": _now_iso(), "text": "Chat completed"})
    return events


__all__ = ["run_claude_chat"]
