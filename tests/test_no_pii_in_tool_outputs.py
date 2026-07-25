"""
T1 — varredura de PII na saída de TODAS as tools registradas.

Este é o teste central da garantia de anonimização, e o par de
test_projected_columns.py (T2):

  T2 — colunas proibidas nunca entram na consulta.
  T1 (aqui) — colunas sensíveis que entram (`no_cidadao`, `dt_nascimento`)
     nunca saem sem transformação, e nenhuma coluna proibida escapa caso venha
     a ser selecionada por acidente.

Como funciona: para cada tool de `server.STANDALONE_TOOLS`, interceptamos a
consulta (ver tests/casos_tools.py) e devolvemos linhas sintéticas
deliberadamente carregadas de PII — nome completo, CPF, CNS, telefone,
endereço, nome da mãe e data de nascimento. A saída é serializada com
`json.dumps(..., default=str)` e nada disso pode sobreviver.

Escopo — o sujeito protegido é o PACIENTE. As tools de atendimento, medição e
visita devolvem o nome do PROFISSIONAL em claro por decisão de produto (ele não
é o sujeito anonimizado); por isso o nome de profissional usado nas linhas
sintéticas é um valor separado, sem token em comum com os dados do paciente.
Isso também explica por que a proibição de "token em caixa mista" é aplicada
aos campos de identidade do paciente, e não ao payload inteiro: descrições de
CID/CIAP, texto SOAP, CBO, turno e desfecho são texto livre legítimo e
naturalmente contêm palavras em caixa mista.

Nenhum destes testes toca o banco: rodam em CI limpa, sem PEC_TEST_DB_DSN.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, List, Tuple

import pytest

from pec_mcp.server import STANDALONE_TOOLS

from casos_tools import (
    BAIRRO,
    CASOS,
    CNS,
    CPF,
    DATA_NASCIMENTO,
    EMAIL,
    INICIAIS_ESPERADAS,
    LOGRADOURO,
    NOME_MAE,
    NOME_PACIENTE,
    TELEFONE,
    executar_caso,
    linhas_de_saida,
)

# ──────────────────────────────────────────────────────────────
# Padrões proibidos
# ──────────────────────────────────────────────────────────────

_ANO_NASCIMENTO = str(DATA_NASCIMENTO.year)

# Data de nascimento em qualquer formato plausível de serialização.
_FORMATOS_DATA_NASCIMENTO = (
    DATA_NASCIMENTO.isoformat(),                     # 1985-03-07
    DATA_NASCIMENTO.strftime("%d/%m/%Y"),            # 07/03/1985
    DATA_NASCIMENTO.strftime("%Y/%m/%d"),            # 1985/03/07
    DATA_NASCIMENTO.strftime("%d-%m-%Y"),            # 07-03-1985
    DATA_NASCIMENTO.strftime("%d.%m.%Y"),            # 07.03.1985
)

# (rótulo, padrão) — o rótulo entra na mensagem de falha.
PADROES_PROIBIDOS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("CPF", re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")),
    ("CNS", re.compile(r"\d{15}")),
    ("telefone", re.compile(r"\d{10,11}")),
    ("nome completo do paciente", re.compile(re.escape(NOME_PACIENTE))),
    # Tokens isolados do nome do paciente, da mãe e do endereço: pegam também
    # vazamento parcial (ex.: só o primeiro nome, ou o nome sem as preposições).
    ("token do nome do paciente", re.compile(r"Maria|Silva|Santos")),
    ("token do nome da mãe", re.compile(r"Josefa|Oliveira")),
    ("token do endereço", re.compile(r"Acácias|Federação")),
    ("e-mail do paciente", re.compile(r"@exemplo\.com\.br")),
    ("data de nascimento", re.compile("|".join(
        re.escape(formato) for formato in _FORMATOS_DATA_NASCIMENTO
    ))),
    ("ano de nascimento", re.compile(re.escape(_ANO_NASCIMENTO))),
)

# Iniciais legítimas: apenas maiúsculas isoladas (ou o marcador de ausência).
_INICIAIS_VALIDAS = re.compile(r"^(?:[A-ZÁ-Ú]+|N/A)$")

# Qualquer token com 2+ letras em caixa mista — um nome que não foi reduzido.
_TOKEN_CAIXA_MISTA = re.compile(r"[A-ZÁ-Ú][a-zá-ú]+")


def _percorrer(valor: Any, caminho: str = "$") -> Iterator[Tuple[str, Any]]:
    """Percorre a saída da tool devolvendo (caminho, valor folha)."""

    if isinstance(valor, dict):
        for chave, item in valor.items():
            yield from _percorrer(item, f"{caminho}.{chave}")
    elif isinstance(valor, (list, tuple)):
        for indice, item in enumerate(valor):
            yield from _percorrer(item, f"{caminho}[{indice}]")
    else:
        yield caminho, valor


def _campos_com_padrao(resultado: Any, padrao: re.Pattern[str]) -> List[str]:
    """Lista os caminhos da saída cujo valor casa com o padrão proibido."""

    encontrados = []
    for caminho, valor in _percorrer(resultado):
        if valor is None or isinstance(valor, bool):
            continue
        if padrao.search(str(valor)):
            encontrados.append(f"{caminho}={valor!r}")
    return encontrados


# ──────────────────────────────────────────────────────────────
# Cobertura: a lista de casos deriva de STANDALONE_TOOLS
# ──────────────────────────────────────────────────────────────


def test_todas_as_tools_registradas_tem_caso_de_pii():
    """
    Uma tool nova em STANDALONE_TOOLS não pode entrar sem cobertura de PII.

    Se este teste falhar, acrescente a tool em tests/casos_tools.py — não
    relaxe a asserção.
    """

    registradas = {tool.__name__ for tool in STANDALONE_TOOLS}
    cobertas = set(CASOS)

    assert registradas == cobertas, (
        "Divergência entre STANDALONE_TOOLS e a tabela de casos de PII.\n"
        f"  registradas sem caso: {sorted(registradas - cobertas)}\n"
        f"  casos sem tool registrada: {sorted(cobertas - registradas)}"
    )


# ──────────────────────────────────────────────────────────────
# T1 propriamente dito
# ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("nome_tool", sorted(CASOS), ids=sorted(CASOS))
@pytest.mark.parametrize("rotulo,padrao", PADROES_PROIBIDOS, ids=[
    rotulo for rotulo, _ in PADROES_PROIBIDOS
])
def test_saida_da_tool_nao_contem_pii(monkeypatch, nome_tool, rotulo, padrao):
    """Nenhum padrão de PII sobrevive à serialização da saída da tool."""

    caso = CASOS[nome_tool]
    resultado = executar_caso(monkeypatch, caso)

    # Serializa como o servidor MCP faria, para pegar também objetos date/datetime
    # que só viram texto na serialização.
    serializado = json.dumps(resultado, default=str, ensure_ascii=False)

    if padrao.search(serializado):
        campos = _campos_com_padrao(resultado, padrao)
        raise AssertionError(
            f"A tool '{nome_tool}' expôs {rotulo} na saída. "
            f"Campo(s) responsável(is): {campos or ['(não localizado; ver payload)']}. "
            f"Payload serializado: {serializado}"
        )


_TOOLS_COM_IDENTIDADE = sorted(
    nome for nome, caso in CASOS.items() if caso.campos_de_iniciais
)


@pytest.mark.parametrize(
    "nome_tool", _TOOLS_COM_IDENTIDADE, ids=_TOOLS_COM_IDENTIDADE
)
def test_campos_de_identidade_contem_apenas_iniciais(monkeypatch, nome_tool):
    """
    Os campos que carregam a identidade do paciente só podem ter iniciais.

    Congela a proteção contra o caso em que alguém troque `to_initials(...)` por
    um nome parcial ("Maria S.") — que passaria pelos padrões acima se o token
    proibido mudasse, mas não é anonimização.
    """

    caso = CASOS[nome_tool]
    resultado = executar_caso(monkeypatch, caso)

    for linha in linhas_de_saida(resultado):
        for campo in caso.campos_de_iniciais:
            assert campo in linha, (
                f"A tool '{nome_tool}' deixou de devolver o campo de identidade "
                f"'{campo}'; ajuste a tabela de casos se o contrato mudou."
            )
            valor = linha[campo]
            assert valor == INICIAIS_ESPERADAS, (
                f"A tool '{nome_tool}' devolveu '{campo}'={valor!r}; esperado "
                f"{INICIAIS_ESPERADAS!r} para o nome sintético "
                f"{NOME_PACIENTE!r} (to_initials ignora preposições)."
            )
            assert _INICIAIS_VALIDAS.match(str(valor)), (
                f"A tool '{nome_tool}' devolveu '{campo}'={valor!r}, que não é um "
                f"conjunto de iniciais (apenas maiúsculas isoladas ou 'N/A')."
            )
            assert not _TOKEN_CAIXA_MISTA.search(str(valor)), (
                f"A tool '{nome_tool}' devolveu '{campo}'={valor!r} com token em "
                f"caixa mista — nome não reduzido a iniciais."
            )


def test_padroes_proibidos_realmente_pegariam_um_vazamento():
    """
    Sanidade dos padrões: um payload com PII em claro tem de falhar.

    Sem isto, um erro de digitação numa regex transformaria todo o T1 em um
    teste que passa sempre.
    """

    vazamento = json.dumps(
        {
            "name": NOME_PACIENTE,
            "nu_cpf": CPF,
            "nu_cns": CNS,
            "nu_telefone": TELEFONE,
            "no_mae": NOME_MAE,
            "endereco": LOGRADOURO,
            "no_bairro": BAIRRO,
            "ds_email": EMAIL,
            "birth_date": DATA_NASCIMENTO.isoformat(),
        },
        default=str,
        ensure_ascii=False,
    )
    nao_detectados = [
        rotulo for rotulo, padrao in PADROES_PROIBIDOS if not padrao.search(vazamento)
    ]
    assert not nao_detectados, (
        f"Padrões que deveriam detectar o vazamento de exemplo falharam: {nao_detectados}"
    )
