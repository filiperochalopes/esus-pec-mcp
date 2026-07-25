"""
Anonimização em listar_visitas_acs.

A tool tinha uma segunda implementação de geração de iniciais, inline, que não
ignorava a conjunção "e" — logo divergia de `domain.patient.to_initials` para
nomes como "Maria e Joana Silva" ("MEJS" contra "MJS"). Duas implementações da
mesma regra de privacidade significam que corrigir uma não corrige a outra.

Estes testes travam a unificação: a tool tem de concordar com `to_initials`
para qualquer nome, inclusive nos casos em que as duas implementações divergiam.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from pec_mcp.domain.patient import to_initials

from casos_tools import CASOS, executar_caso

_CASO = CASOS["listar_visitas_acs"]

# Nomes onde a implementação inline divergia de to_initials (conjunção "e"),
# mais nomes de controle onde as duas concordavam.
NOMES = (
    "Maria e Joana Silva",
    "Ana Beatriz e Souza",
    "João de Carvalho Lima",
    "Maria da Silva Santos",
    "Antônio dos Santos e Oliveira",
    "Ana",
)


@pytest.mark.parametrize("nome", NOMES, ids=NOMES)
def test_iniciais_do_paciente_seguem_to_initials(monkeypatch, nome):
    """A tool usa a mesma regra de iniciais do resto do projeto."""

    linha = {**_CASO.linhas[0], "paciente_nome": nome}
    caso = replace(_CASO, linhas=[linha])

    resultado = executar_caso(monkeypatch, caso)

    assert resultado, "A tool não devolveu nenhuma visita."
    assert resultado[0]["paciente_nome"] == to_initials(nome), (
        f"listar_visitas_acs devolveu iniciais {resultado[0]['paciente_nome']!r} "
        f"para {nome!r}; to_initials() produz {to_initials(nome)!r}. As duas "
        f"implementações voltaram a divergir."
    )


def test_paciente_sem_nome_nao_recebe_iniciais(monkeypatch):
    """Visita sem nome de paciente devolve None, não um marcador falso."""

    linha = {**_CASO.linhas[0], "paciente_nome": None}
    caso = replace(_CASO, linhas=[linha])

    resultado = executar_caso(monkeypatch, caso)

    assert resultado[0]["paciente_nome"] is None, (
        f"listar_visitas_acs devolveu {resultado[0]['paciente_nome']!r} para uma "
        f"visita sem nome de paciente; esperado None."
    )
