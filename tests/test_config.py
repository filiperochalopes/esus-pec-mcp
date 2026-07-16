from __future__ import annotations

import pytest
from psycopg2.extensions import parse_dsn

from pec_mcp.config import get_db_dsn, get_server_settings


def test_db_config_requires_explicit_credentials():
    with pytest.raises(RuntimeError, match="PEC_DB_HOST"):
        get_db_dsn({})


def test_db_config_builds_quoted_dsn_from_components():
    dsn = get_db_dsn(
        {
            "PEC_DB_HOST": "db.internal",
            "PEC_DB_PORT": "5433",
            "PEC_DB_NAME": "pec",
            "PEC_DB_USER": "somente_leitura",
            "PEC_DB_PASSWORD": "senha com espaço",
            "PEC_DB_SSLMODE": "require",
        }
    )

    assert parse_dsn(dsn) == {
        "host": "db.internal",
        "port": "5433",
        "dbname": "pec",
        "user": "somente_leitura",
        "password": "senha com espaço",
        "sslmode": "require",
    }


def test_db_config_accepts_complete_dsn():
    dsn = get_db_dsn({"PEC_DB_DSN": "host=db dbname=pec user=reader password=secret"})
    assert parse_dsn(dsn)["host"] == "db"


def test_invalid_dsn_error_does_not_echo_credentials():
    secret = "senha-super-secreta"
    with pytest.raises(RuntimeError) as exc_info:
        get_db_dsn({"PEC_DB_DSN": f"not-a-dsn {secret}"})
    assert secret not in str(exc_info.value)


def test_server_config_defaults_to_local_streamable_http():
    settings = get_server_settings({})
    assert settings.transport == "streamable-http"
    assert settings.host == "127.0.0.1"
    assert settings.port == 5174


def test_server_config_validates_transport_and_port():
    with pytest.raises(RuntimeError, match="MCP_TRANSPORT"):
        get_server_settings({"MCP_TRANSPORT": "websocket"})
    with pytest.raises(RuntimeError, match="MCP_HTTP_PORT"):
        get_server_settings({"MCP_HTTP_PORT": "70000"})
