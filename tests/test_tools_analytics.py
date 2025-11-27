from __future__ import annotations

import pytest

from pec_mcp.tools.analytics import consulta_epidemiologia, consulta_pessoal
from conftest import find_paciente_com_atendimento


def test_consulta_epidemiologia_basica(ctx):
    resultados = consulta_epidemiologia(ctx, tipo="comorbidades_por_filtro", limite=5)
    assert isinstance(resultados, list)
    if not resultados:
        pytest.skip("Sem dados de comorbidades para validar agregação")

    esperado = {
        "codigo_cid10",
        "descricao_cid10",
        "total_pacientes",
        "sexo",
        "faixa_etaria",
        "localidade_id",
    }
    assert esperado.issubset(resultados[0].keys())
    assert resultados[0]["total_pacientes"] >= 0


def test_consulta_pessoal_hba1c(ctx):
    resultados = consulta_pessoal(ctx, tipo="hba1c_maior_8", limite=5)
    assert isinstance(resultados, list)
    if not resultados:
        pytest.skip("Nenhum HbA1c > 8 encontrado para validar")
    esperado = {"paciente_id", "data_referencia", "detalhe", "metrica"}
    assert esperado.issubset(resultados[0].keys())


def test_consulta_pessoal_pa(ctx):
    resultados = consulta_pessoal(ctx, tipo="pa_maior_140_90", limite=5)
    assert isinstance(resultados, list)
    if not resultados:
        pytest.skip("Nenhuma PA > 140/90 encontrada para validar")
    assert "metrica" in resultados[0]


def test_consulta_pessoal_sem_atendimento(ctx, db_conn):
    paciente_id = find_paciente_com_atendimento(db_conn)
    resultados = consulta_pessoal(ctx, tipo="sem_atendimento_ano", limite=5)
    assert isinstance(resultados, list)
    # Pode retornar vazio se todos têm atendimento recente; apenas checamos chaves.
    if resultados:
        assert "paciente_id" in resultados[0]
        assert "data_referencia" in resultados[0]
