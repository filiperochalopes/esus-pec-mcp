from __future__ import annotations

import json
import time
import os
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Literal, Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.tools import StructuredTool
try:
    from pydantic.v1 import create_model
except ImportError:
    from pydantic import create_model

# Providers
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

try:
    from langchain_mistralai import ChatMistralAI
except ImportError:
    ChatMistralAI = None

try:
    from langchain_community.chat_models import ChatMLX
    from langchain_community.llms import MLXPipeline
except ImportError:
    ChatMLX = None
    MLXPipeline = None

from .mcp_proxy import call_tool, list_tools, TOOL_REGISTRY

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

def _random_id() -> str:
    return f"id-{int(time.time() * 1000)}-{hex(int(time.time() * 1_000_000))[-6:]}"

# --- Tool Conversion ---

def _create_pydantic_model_from_schema(name: str, schema: Dict[str, Any]):
    """
    Creates a Pydantic model dynamically from the JSON schema provided in TOOL_REGISTRY.
    This is needed for LangChain tools to validate input.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    fields = {}
    for field_name, field_info in properties.items():
        # Map JSON types to Python types
        field_type = str
        t = field_info.get("type")
        if t == "integer":
            field_type = int
        elif t == "number":
            field_type = float
        elif t == "boolean":
            field_type = bool
        elif t == "array":
            field_type = List[str] # Simplified assumption based on current tools
        
        # Check if optional
        if field_name not in required:
            field_type = Optional[field_type]
            fields[field_name] = (field_type, None)
        else:
            fields[field_name] = (field_type, ...)
            
    return create_model(f"{name}Input", **fields)

def _get_langchain_tools(tool_alias: str = "server") -> List[StructuredTool]:
    """
    Wraps local MCP tools into LangChain StructuredTools.
    """
    lc_tools = []
    mcp_tools = list_tools() # Get metadata
    
    for tool_meta in mcp_tools:
        name = tool_meta["name"]
        description = tool_meta["description"] or ""
        input_schema = tool_meta["input_schema"] or {}
        
        # We need a function that calls mcp_proxy.call_tool
        # We capture 'name' in the closure
        def make_tool_func(tool_name):
            def tool_func(**kwargs):
                # LangChain might pass kwargs that need to be passed to call_tool
                # call_tool expects a dictionary of arguments
                result = call_tool(tool_name, kwargs)
                # Ensure we return a string or JSON dump as LangChain tools often expect text
                if result.get("ok"):
                     return json.dumps(result.get("result"), ensure_ascii=False)
                return f"Error: {result.get('error')}"
            return tool_func

        # Create dynamic pydantic model for args
        args_schema = _create_pydantic_model_from_schema(name, input_schema)
        
        # Prefix name to avoid collisions if multiple servers (logic from claude_agent)
        prefixed_name = f"mcp__{tool_alias}__{name}"
        
        lc_tool = StructuredTool.from_function(
            func=make_tool_func(name),
            name=prefixed_name,
            description=description,
            args_schema=args_schema
        )
        lc_tools.append(lc_tool)
        
    return lc_tools


# --- Conversation Management ---

_conversation_lock = Lock()
_conversations: Dict[str, List[BaseMessage]] = {}

def _load_conversation(conversation_id: str) -> List[BaseMessage]:
    with _conversation_lock:
        stored = _conversations.get(conversation_id, [])
        return list(stored)

def _persist_conversation(conversation_id: str, messages: List[BaseMessage]) -> None:
    with _conversation_lock:
        _conversations[conversation_id] = list(messages)

def reset_conversation(conversation_id: str) -> None:
    if not conversation_id:
        return
    with _conversation_lock:
        _conversations.pop(conversation_id, None)


# --- Agent Execution ---

def run_llm_chat(
    provider: Literal["anthropic", "openai", "ollama", "gemini", "mistral", "mlx"],
    model_name: str,
    api_key: Optional[str],
    prompt: str,
    system_prompt: str,
    max_turns: int = 4,
    tool_alias: str = "server",
    conversation_id: Optional[str] = None,
    # Additional config for Ollama (base_url) could be added here
    api_base: Optional[str] = None,
    event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    collect_events: bool = True,
) -> Tuple[str, List[Dict[str, Any]]]:
    
    conv_id = conversation_id or _random_id()
    events: List[Dict[str, Any]] = []

    def emit(event: Dict[str, Any]):
        if event_callback:
            try:
                event_callback(event)
            except Exception:
                pass
        if collect_events:
            events.append(event)

    # 1. Initialize LLM
    llm = None
    if provider == "anthropic":
        if not ChatAnthropic:
            raise ImportError("Provedor Anthropic não disponível. Instale 'langchain-anthropic'.")
        llm = ChatAnthropic(model=model_name, api_key=api_key, temperature=0, max_tokens=4096)
    elif provider == "openai":
        if not ChatOpenAI:
            raise ImportError("Provedor OpenAI não disponível. Instale 'langchain-openai'.")
        llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0)
    elif provider == "ollama":
        if not ChatOllama:
            raise ImportError("Provedor Ollama não disponível. Instale 'langchain-ollama'.")
        # Ensure base_url is set if provided, else defaults to localhost:11434
        llm = ChatOllama(model=model_name, temperature=0, base_url=api_base or "http://localhost:11434")
    elif provider == "gemini":
        if not ChatGoogleGenerativeAI:
            raise ImportError("Provedor Gemini não disponível. Instale 'langchain-google-genai'.")
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0)
    elif provider == "mistral":
        if not ChatMistralAI:
            raise ImportError("Provedor Mistral não disponível. Instale 'langchain-mistralai'.")
        llm = ChatMistralAI(model=model_name, mistral_api_key=api_key, temperature=0)
    elif provider == "mlx":
        if not ChatMLX or not MLXPipeline:
            raise ImportError("Provedor MLX não disponível. Instale 'mlx-lm' e 'langchain-community'.")
        
        # --- PATCH: Fix for generate_step unexpected keyword argument 'formatter' ---
        # langchain_community passes formatter -> mlx_lm.generate.stream_generate -> generate_step.
        # Newer mlx_lm removed formatter from generate_step signature.
        try:
            import importlib

            def _patch_generate_step(module):
                if not hasattr(module, "generate_step"):
                    return
                _original_generate_step = module.generate_step

                # Avoid double-patching / recursion
                if getattr(_original_generate_step, "__name__", "") == "_patched_generate_step":
                    return

                try:
                    import inspect
                    sig = inspect.signature(_original_generate_step)
                    params = sig.parameters.values()
                    accepts_formatter = (
                        "formatter" in sig.parameters
                        or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
                    )
                    if accepts_formatter:
                        return
                except Exception:
                    # If we cannot introspect, fall back to patching defensively.
                    pass

                def _patched_generate_step(*args, **kwargs):
                    if "formatter" in kwargs:
                        kwargs.pop("formatter")
                    return _original_generate_step(*args, **kwargs)

                module.generate_step = _patched_generate_step

            # Newer mlx_lm
            try:
                mlx_generate = importlib.import_module("mlx_lm.generate")
                _patch_generate_step(mlx_generate)
            except Exception:
                pass

            # Older mlx_lm (if generate_step lived in utils)
            try:
                mlx_utils = importlib.import_module("mlx_lm.utils")
                _patch_generate_step(mlx_utils)
            except Exception:
                pass
        except Exception:
            pass
        # --- END PATCH ---

        # ChatMLX requires a pipeline instance
        pipeline = MLXPipeline.from_model_id(
            model_id=model_name,
            pipeline_kwargs={"max_tokens": 2048, "temp": 0.0}
        )
        llm = ChatMLX(llm=pipeline)
    else:
        raise ValueError(f"Unknown provider: {provider}")


    # 2. Setup Tools
    tools = _get_langchain_tools(tool_alias)
    # Bind tools to the LLM (if supported). 
    # ChatAnthropic, ChatOpenAI support bind_tools. ChatOllama might support it depending on version/model.
    # We assume the model supports tool calling.
    llm_with_tools = llm.bind_tools(tools)
    
    # Map prefixed tool names back to original for logging/display if needed
    # (Though we can just use the tool call name)
    
    # 3. Load History
    messages: List[BaseMessage] = _load_conversation(conv_id)
    
    # If it's a new conversation or system prompt changed (not handled here, assumed static per chat request?)
    # We'll just ensure SystemMessage is at the start if messages is empty, 
    # BUT existing 'claude_agent' logic passed system parameter to client.create.
    # In LangChain, we add SystemMessage to history or valid prompt.
    if not messages:
        messages.append(SystemMessage(content=system_prompt))
    
    # Add User Message
    messages.append(HumanMessage(content=prompt))
    emit({"id": _random_id(), "type": "USER_MESSAGE", "text": prompt, "timestamp": _now_iso()})

    # 4. Loop
    for _ in range(max_turns):
        # Invoke LLM
        try:
            response = llm_with_tools.invoke(messages)
        except Exception as e:
            emit({"id": _random_id(), "type": "ERROR", "text": str(e), "timestamp": _now_iso()})
            break

        # Emit Model Message (Text)
        if response.content:
            text_content = response.content
            if isinstance(text_content, list):
                # Anthropic sometimes returns list of content blocks
                text_content = "\n".join([item['text'] for item in text_content if item.get('type') == 'text'])
            
            if text_content:
                emit({
                    "id": _random_id(),
                    "type": "MODEL_MESSAGE",
                    "text": str(text_content),
                    "timestamp": _now_iso(),
                })
        
        messages.append(response)

        # Check for tool calls
        if not response.tool_calls:
            break
            
        # Execute Tools
        for tool_call in response.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            t_id = tool_call["id"]
            
            # Remove prefix for display if we want, or keep it.
            # claude_agent did: actual_name = name_map.get(tool_use.name, tool_use.name)
            # Here names are prefixed "mcp___{alias}__{name}"
            # We can extract original name
            original_name = t_name.split("__")[-1] if "__" in t_name else t_name

            emit({
                "id": _random_id(),
                "type": "TOOL_CALL",
                "tool_name": original_name,
                "tool_input": t_args,
                "timestamp": _now_iso(),
            })
            
            # Find the tool object
            selected_tool = next((t for t in tools if t.name == t_name), None)
            
            result_str = ""
            duration_ms = 0
            
            if selected_tool:
                start_t = time.perf_counter()
                try:
                    # execute
                    result_str = selected_tool.invoke(t_args)
                except Exception as e:
                    result_str = f"Error executing tool: {e}"
                duration_ms = int((time.perf_counter() - start_t) * 1000)
            else:
                result_str = f"Tool {t_name} not found."
                
            # Try to parse result_str as JSON to match 'tool_output' expectation of a dict/obj
            # if possible, or just string.
            tool_output_val = result_str
            try:
                tool_output_val = json.loads(result_str)
            except:
                pass

            emit({
                "id": _random_id(),
                "type": "TOOL_RESULT",
                "tool_name": original_name,
                "tool_output": tool_output_val,
                "duration_ms": duration_ms,
                "timestamp": _now_iso(),
            })
            
            # Add ToolMessage to history
            messages.append(ToolMessage(content=result_str, tool_call_id=t_id, name=t_name))
            
    emit({"id": _random_id(), "type": "COMPLETE", "timestamp": _now_iso(), "text": "Chat completed"})
    _persist_conversation(conv_id, messages)
    return conv_id, events
