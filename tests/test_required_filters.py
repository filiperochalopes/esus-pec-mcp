"""
Filtro obrigatório: as tools de busca ampla recusam chamada sem critério.

Sem isto, uma pergunta vaga da LM viraria uma varredura de toda a base de
cidadãos — o oposto da minimização de dados. As três tools abaixo exigem ao
menos um critério e devem dizer, na própria mensagem de erro, quais critérios
aceitam, para que a LM consiga se corrigir sozinha.

Não toca o banco: o ValueError é levantado antes de `get_db_conn`.
"""

from __future__ import annotations

import pytest

from pec_mcp.tools.condicoes import listar_condicoes_pacientes
from pec_mcp.tools.contar_pacientes import contar_pacientes
from pec_mcp.tools.paciente import capturar_paciente

from casos_tools import ContextoFalso

# (nome, tool, termos que a mensagem de erro precisa citar)
TOOLS_COM_FILTRO_OBRIGATORIO = (
    ("capturar_paciente", capturar_paciente, ("critério", "id", "nome", "sexo", "idade")),
    (
        "listar_condicoes_pacientes",
        listar_condicoes_pacientes,
        ("critério", "paciente", "condição"),
    ),
    ("contar_pacientes", contar_pacientes, ("critério", "paciente", "condição")),
)


@pytest.mark.parametrize(
    "nome_tool,tool,termos_esperados",
    TOOLS_COM_FILTRO_OBRIGATORIO,
    ids=[nome for nome, _, _ in TOOLS_COM_FILTRO_OBRIGATORIO],
)
def test_tool_exige_pelo_menos_um_criterio(nome_tool, tool, termos_esperados):
    """Chamada sem nenhum filtro levanta ValueError citando os critérios aceitos."""

    with pytest.raises(ValueError) as erro:
        tool(ContextoFalso())

    mensagem = str(erro.value).lower()
    ausentes = [termo for termo in termos_esperados if termo.lower() not in mensagem]
    assert not ausentes, (
        f"A tool '{nome_tool}' recusou a chamada sem critério (correto), mas a "
        f"mensagem não cita {ausentes}: {str(erro.value)!r}. A LM depende dessa "
        f"mensagem para reformular a chamada."
    )
