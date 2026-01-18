"""
Configuração centralizada das variáveis de ambiente do servidor MCP.

Mantemos defaults seguros para exploração local (somente leitura) e
permitimos sobreposição via variáveis de ambiente ou arquivo .env.
"""

from __future__ import annotations

import os
from typing import Final

try:
    # python-dotenv é opcional, mas ajuda no dev local.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback simples caso não instalado
    load_dotenv = None

# Carrega .env se a lib estiver disponível. Isso é idempotente.
if load_dotenv is not None:
    # override=True garante que ajustes no .env substituam env pré-existentes no dev local.
    load_dotenv(override=True)

# Defaults para exploração inicial. Em produção, sobrescrever via env.
_DEFAULT_HOST: Final[str] = "localhost"
_DEFAULT_PORT: Final[str] = "5432"
_DEFAULT_DBNAME: Final[str] = "postgres"
_DEFAULT_USER: Final[str] = "postgres"
_DEFAULT_PASSWORD: Final[str] = "pass"


def _get(name: str, default: str) -> str:
    """
    Obtém variável de ambiente com default explícito.

    Usamos str para manter compatibilidade com psycopg2 DSN.
    """

    return os.getenv(name, default)


# Expondo configurações de banco em nível de módulo para reuso.
PEC_DB_HOST: Final[str] = _get("PEC_DB_HOST", _DEFAULT_HOST)
PEC_DB_PORT: Final[str] = _get("PEC_DB_PORT", _DEFAULT_PORT)
PEC_DB_NAME: Final[str] = _get("PEC_DB_NAME", _DEFAULT_DBNAME)
PEC_DB_USER: Final[str] = _get("PEC_DB_USER", _DEFAULT_USER)
PEC_DB_PASSWORD: Final[str] = _get("PEC_DB_PASSWORD", _DEFAULT_PASSWORD)


def get_db_dsn() -> str:
    """
    Monta a DSN no formato aceito pelo psycopg2.

    Mantemos função pequena (KISS) e reutilizável (DRY) para evitar
    repetição de strings de conexão em múltiplos pontos.
    """

    return (
        f"host={PEC_DB_HOST} "
        f"port={PEC_DB_PORT} "
        f"dbname={PEC_DB_NAME} "
        f"user={PEC_DB_USER} "
        f"password={PEC_DB_PASSWORD}"
    )


__all__ = [
    "PEC_DB_HOST",
    "PEC_DB_PORT",
    "PEC_DB_NAME",
    "PEC_DB_USER",
    "PEC_DB_PASSWORD",
    "get_db_dsn",
]
