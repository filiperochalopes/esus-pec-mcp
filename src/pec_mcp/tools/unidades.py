"""
Tool para listar unidades de saúde cadastradas no PEC.
"""

from __future__ import annotations

from typing import List

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import HealthUnitResult
from . import get_db_conn

_SQL_LISTAR_UNIDADES = """
SELECT
    us.co_seq_unidade_saude   AS unidade_id,
    us.nu_cnes                AS cnes,
    us.no_unidade_saude       AS nome,
    us.co_localidade_endereco AS localidade_id,
    us.st_ativo               AS ativo
FROM tb_unidade_saude us
JOIN tb_tipo_unidade_saude tu ON tu.co_seq_tipo_unidade_saude = us.tp_unidade_saude
WHERE tu.no_tipo_unidade_saude = 'CENTRO DE SAUDE/UNIDADE BASICA'
ORDER BY us.no_unidade_saude;
"""


def listar_unidades_saude(ctx: Context) -> List[HealthUnitResult]:
    """
    Retorna unidades básicas de saúde (UBS) para popular selects de filtros.
    """

    conn = get_db_conn(ctx)
    rows = query_all(conn, _SQL_LISTAR_UNIDADES)

    results: List[HealthUnitResult] = []
    for row in rows:
        results.append(
            HealthUnitResult(
                unidade_id=int(row["unidade_id"]),
                cnes=str(row.get("cnes")) if row.get("cnes") is not None else None,
                name=str(row.get("nome")) if row.get("nome") is not None else None,
                localidade_id=int(row["localidade_id"]) if row.get("localidade_id") is not None else None,
                is_active=bool(row.get("ativo")),
            )
        )
    return results


__all__ = ["listar_unidades_saude"]
