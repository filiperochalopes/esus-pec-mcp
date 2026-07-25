"""
Contrato de chaves da saída de cada tool registrada.

Complementa o T1 (test_no_pii_in_tool_outputs.py): o T1 garante que os valores
conhecidos de PII não escapam; este teste garante que a *forma* da saída não
cresce sem revisão. Uma coluna acrescentada por acidente numa query — e
repassada para o resultado — passaria pelo T1 se o valor não casasse com
nenhum padrão, mas quebra aqui.

O conjunto autorizado de chaves de cada tool vive em tests/casos_tools.py, junto
com as linhas sintéticas, para que os dois testes descrevam o mesmo contrato num
único lugar.

A verificação é de primeiro nível. Estruturas aninhadas (`condicoes` em
listar_ultimos_atendimentos_soap, `cid`/`ciap` em obter_codigos_condicao_saude)
são cobertas pelo T1, que percorre a saída inteira.
"""

from __future__ import annotations

import pytest

from casos_tools import CASOS, executar_caso, linhas_de_saida


@pytest.mark.parametrize("nome_tool", sorted(CASOS), ids=sorted(CASOS))
def test_saida_da_tool_nao_tem_chave_nao_autorizada(monkeypatch, nome_tool):
    """Toda chave de primeiro nível da saída está no contrato da tool."""

    caso = CASOS[nome_tool]
    resultado = executar_caso(monkeypatch, caso)
    linhas = linhas_de_saida(resultado)

    assert linhas, (
        f"A tool '{nome_tool}' não devolveu nenhum registro para as linhas "
        f"sintéticas; o contrato de chaves não foi exercitado."
    )

    for indice, linha in enumerate(linhas):
        excedentes = sorted(set(linha) - caso.chaves_permitidas)
        assert not excedentes, (
            f"A tool '{nome_tool}' devolveu chave(s) fora do contrato no registro "
            f"{indice}: {excedentes}. Se a nova chave é intencional, acrescente-a a "
            f"`chaves_permitidas` em tests/casos_tools.py e confirme que ela não "
            f"carrega dado identificável."
        )


@pytest.mark.parametrize("nome_tool", sorted(CASOS), ids=sorted(CASOS))
def test_contrato_de_chaves_nao_ficou_obsoleto(monkeypatch, nome_tool):
    """
    O contrato declarado não lista chaves que a tool deixou de emitir.

    Sem esta asserção, `chaves_permitidas` viraria uma lista de desejos: bastaria
    manter nomes antigos para o teste acima continuar passando — foi exatamente
    o que aconteceu com test_tool_paciente.py e test_tool_condicoes.py, que
    exigiam `birth_date`/`gender` muito depois de as tools passarem a emitir
    `age`/`paciente_id`.
    """

    caso = CASOS[nome_tool]
    resultado = executar_caso(monkeypatch, caso)

    emitidas = set()
    for linha in linhas_de_saida(resultado):
        emitidas.update(linha)

    orfas = sorted(caso.chaves_permitidas - emitidas)
    assert not orfas, (
        f"O contrato de '{nome_tool}' declara chave(s) que a tool não emite mais: "
        f"{orfas}. Atualize `chaves_permitidas` em tests/casos_tools.py."
    )
