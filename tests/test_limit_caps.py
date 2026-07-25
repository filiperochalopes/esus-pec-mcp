"""
Teto de paginação: `limite` exagerado é reduzido ao máximo da tool.

O teto é a defesa contra exfiltração em bloco — uma única chamada com
`limite=10000` não pode devolver a base inteira. Aqui capturamos os `params`
recebidos pela consulta e verificamos o valor que realmente chega ao `LIMIT`.

Tetos confirmados no código (não na documentação):
  - 200  : capturar_paciente, listar_condicoes_pacientes,
           obter_codigos_condicao_saude, listar_registros_antropometria,
           listar_registros_pa, listar_registros_hgt
  - 500  : listar_visitas_acs
  - 1000 : listar_ultimos_atendimentos_soap

Ficam fora: `contar_pacientes` e `listar_unidades_saude`, que não aceitam
`limite` (a primeira devolve só uma contagem; a segunda, a lista fechada de UBS).
"""

from __future__ import annotations

import pytest

from casos_tools import CASOS, executar_caso

_TOOLS_COM_TETO = sorted(
    nome for nome, caso in CASOS.items() if caso.teto_limite is not None
)


@pytest.mark.parametrize("nome_tool", _TOOLS_COM_TETO, ids=_TOOLS_COM_TETO)
def test_limite_exagerado_e_reduzido_ao_teto(monkeypatch, nome_tool):
    """`limite=10_000` chega à consulta como o teto real da tool."""

    caso = CASOS[nome_tool]
    registro: list[dict] = []

    executar_caso(
        monkeypatch,
        caso,
        argumentos_extra=caso.argumentos_limite,
        registro=registro,
    )

    assert registro, f"A tool '{nome_tool}' não executou nenhuma consulta."

    for indice, chamada in enumerate(registro):
        params = chamada["params"]
        assert params, (
            f"A tool '{nome_tool}' executou a consulta {indice} sem parâmetros; "
            f"o LIMIT não pôde ser verificado."
        )
        # Em todas as tools o LIMIT é o último parâmetro vinculado.
        limite_efetivo = params[-1]
        assert limite_efetivo == caso.teto_limite, (
            f"A tool '{nome_tool}' aplicou LIMIT {limite_efetivo!r} na consulta "
            f"{indice} para limite=10000; esperado o teto {caso.teto_limite}. "
            f"Um teto maior (ou ausente) permite exfiltração em bloco."
        )


@pytest.mark.parametrize("nome_tool", _TOOLS_COM_TETO, ids=_TOOLS_COM_TETO)
def test_limite_abaixo_do_teto_e_respeitado(monkeypatch, nome_tool):
    """Um `limite` pequeno passa intacto — o teto não é um valor fixo."""

    caso = CASOS[nome_tool]
    registro: list[dict] = []

    executar_caso(
        monkeypatch,
        caso,
        argumentos_extra={"limite": 3},
        registro=registro,
    )

    for indice, chamada in enumerate(registro):
        limite_efetivo = chamada["params"][-1]
        assert limite_efetivo == 3, (
            f"A tool '{nome_tool}' aplicou LIMIT {limite_efetivo!r} na consulta "
            f"{indice} para limite=3; o teto não deveria alterar valores menores."
        )
