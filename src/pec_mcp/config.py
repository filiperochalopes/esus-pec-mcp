"""Configuração do modo standalone do servidor MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from psycopg2.extensions import make_dsn

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependência opcional
    load_dotenv = None


if load_dotenv is not None:
    # Variáveis exportadas pelo processo têm precedência sobre o arquivo .env.
    load_dotenv(Path.cwd() / ".env", override=False)


_DB_REQUIRED_VARS = (
    "PEC_DB_HOST",
    "PEC_DB_NAME",
    "PEC_DB_USER",
    "PEC_DB_PASSWORD",
)
_VALID_TRANSPORTS = {"stdio", "sse", "streamable-http"}


@dataclass(frozen=True)
class ServerSettings:
    """Configuração de transporte do processo standalone."""

    transport: str = "streamable-http"
    host: str = "127.0.0.1"
    port: int = 5174


def _value(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "")).strip()


def get_db_dsn(env: Mapping[str, str] | None = None) -> str:
    """Retorna a DSN clínica do standalone, exigindo credenciais explícitas."""

    source = os.environ if env is None else env
    direct_dsn = _value(source, "PEC_DB_DSN")
    if direct_dsn:
        # Também valida a sintaxe antes de tentar abrir a conexão.
        try:
            return make_dsn(direct_dsn)
        except Exception:
            # Não propaga a mensagem original, pois ela pode conter a senha.
            raise RuntimeError("PEC_DB_DSN inválida.") from None

    missing = [name for name in _DB_REQUIRED_VARS if not _value(source, name)]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            "Configuração clínica incompleta para o modo standalone. "
            f"Defina PEC_DB_DSN ou as variáveis: {missing_text}."
        )

    port_text = _value(source, "PEC_DB_PORT") or "5432"
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("PEC_DB_PORT deve ser um número inteiro.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PEC_DB_PORT deve estar entre 1 e 65535.")

    options = {
        "host": _value(source, "PEC_DB_HOST"),
        "port": str(port),
        "dbname": _value(source, "PEC_DB_NAME"),
        "user": _value(source, "PEC_DB_USER"),
        "password": _value(source, "PEC_DB_PASSWORD"),
    }
    sslmode = _value(source, "PEC_DB_SSLMODE")
    if sslmode:
        options["sslmode"] = sslmode
    try:
        return make_dsn(**options)
    except Exception:
        raise RuntimeError("Configuração PEC_DB_* inválida.") from None


def get_server_settings(env: Mapping[str, str] | None = None) -> ServerSettings:
    """Lê e valida host, porta e transporte do processo standalone."""

    source = os.environ if env is None else env
    transport = _value(source, "MCP_TRANSPORT") or "streamable-http"
    if transport not in _VALID_TRANSPORTS:
        valid = ", ".join(sorted(_VALID_TRANSPORTS))
        raise RuntimeError(f"MCP_TRANSPORT inválido. Use um de: {valid}.")

    host = _value(source, "MCP_HTTP_HOST") or "127.0.0.1"
    port_text = _value(source, "MCP_HTTP_PORT") or "5174"
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("MCP_HTTP_PORT deve ser um número inteiro.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("MCP_HTTP_PORT deve estar entre 1 e 65535.")

    return ServerSettings(transport=transport, host=host, port=port)


__all__ = ["ServerSettings", "get_db_dsn", "get_server_settings"]
