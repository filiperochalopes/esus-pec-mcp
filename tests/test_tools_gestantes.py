from __future__ import annotations

import pytest

from pec_mcp.tools.gestantes import listar_gestantes


def test_listar_gestantes_keys(ctx):
    resultados = listar_gestantes(ctx, limite=5)
    assert isinstance(resultados, list)
    if not resultados:
        pytest.skip("Nenhuma gestante ativa encontrada para validar campos")

    esperado = {
        "gestacao_id",
        "paciente_id",
        "nome_paciente",
        "dpp",
        "idade_gestacional_semanas",
        "idade_gestacional_dias",
        "idade_gestacional_str",
        "tp_gravidez",
        "st_alto_risco",
        "situacao",
    }
    primeiro = resultados[0]
    assert esperado.issubset(primeiro.keys())


def test_listar_gestantes_intervalo(ctx):
    resultados = listar_gestantes(ctx, limite=20)
    for gestante in resultados:
        semanas = gestante.get("idade_gestacional_semanas")
        if semanas is None:
            continue
        assert 2 <= semanas <= 42
