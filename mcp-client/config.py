"""
Gerenciamento de configuração do banco para a UI FastAPI.

Mantemos leitura/escrita simples em .env (na raiz do repo) e aplicamos
os valores diretamente no módulo pec_mcp.config para refletir mudanças
sem reiniciar o processo.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

from dotenv import dotenv_values

# Garante acesso ao pacote pec_mcp a partir do caminho achatado em mcp-server.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "mcp-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from pec_mcp import config as mcp_config  # noqa: E402

ENV_FILE = PROJECT_ROOT / ".env"
ENV_KEYS = ["PEC_DB_HOST", "PEC_DB_PORT", "PEC_DB_NAME", "PEC_DB_USER", "PEC_DB_PASSWORD"]
_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


@dataclass
class DbConfig:
    host: str
    port: str
    name: str
    user: str
    password: str

    def as_env(self) -> Dict[str, str]:
        return {
            "PEC_DB_HOST": self.host,
            "PEC_DB_PORT": self.port,
            "PEC_DB_NAME": self.name,
            "PEC_DB_USER": self.user,
            "PEC_DB_PASSWORD": self.password,
        }

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


def _read_env_file() -> Dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values = dotenv_values(ENV_FILE)
    return {key: str(value) for key, value in values.items() if value is not None}


def load_db_config() -> DbConfig:
    """
    Retorna config atual priorizando env em runtime, depois .env e por fim defaults do módulo.
    """

    raw_env = _read_env_file()
    return DbConfig(
        host=os.getenv("PEC_DB_HOST", raw_env.get("PEC_DB_HOST", mcp_config.PEC_DB_HOST)),
        port=os.getenv("PEC_DB_PORT", raw_env.get("PEC_DB_PORT", mcp_config.PEC_DB_PORT)),
        name=os.getenv("PEC_DB_NAME", raw_env.get("PEC_DB_NAME", mcp_config.PEC_DB_NAME)),
        user=os.getenv("PEC_DB_USER", raw_env.get("PEC_DB_USER", mcp_config.PEC_DB_USER)),
        password=os.getenv("PEC_DB_PASSWORD", raw_env.get("PEC_DB_PASSWORD", mcp_config.PEC_DB_PASSWORD)),
    )


def apply_db_config(cfg: DbConfig) -> None:
    """
    Ajusta variáveis de ambiente e atualiza o módulo pec_mcp.config em runtime.
    """

    os.environ.update(cfg.as_env())
    mcp_config.PEC_DB_HOST = cfg.host
    mcp_config.PEC_DB_PORT = cfg.port
    mcp_config.PEC_DB_NAME = cfg.name
    mcp_config.PEC_DB_USER = cfg.user
    mcp_config.PEC_DB_PASSWORD = cfg.password


def persist_db_config(cfg: DbConfig) -> None:
    """
    Grava/atualiza as chaves do banco em .env preservando linhas existentes.
    """

    env_map = cfg.as_env()
    existing_lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    seen = set()
    new_lines = []

    for line in existing_lines:
        match = _ENV_LINE.match(line)
        if match and match.group(1) in env_map:
            key = match.group(1)
            new_lines.append(f"{key}={env_map[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in env_map.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n")


__all__ = [
    "DbConfig",
    "load_db_config",
    "apply_db_config",
    "persist_db_config",
    "ENV_FILE",
    "PROJECT_ROOT",
]
