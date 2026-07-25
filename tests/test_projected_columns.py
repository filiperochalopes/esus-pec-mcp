"""
Garantia estática: colunas de identificação direta nunca entram nas consultas.

Este é o primeiro dos dois lados da garantia de anonimização:

  T2 (aqui) — colunas PROIBIDAS nunca são projetadas/consultadas no SQL.
  T1 (test_no_pii_in_tool_outputs.py) — colunas SENSÍVEIS que entram na
     consulta nunca saem da tool sem transformação.

IMPORTANTE — `no_cidadao` (nome completo) e `dt_nascimento` são PERMITIDOS e
aparecem de propósito nas queries (ex.: `tools/paciente.py`, `tools/condicoes.py`,
`tools/visitas_acs.py`, `tools/filters.py`). Eles são *insumo* das funções de
`domain/patient.py`:

  - `to_initials(no_cidadao)`      -> "João de Carvalho Lima" vira "JCL"
  - `compute_age_display(dt_nascimento)` -> "32 anos" / "3 anos e 2 meses"

A anonimização acontece em Python, antes da serialização — não no SQL. Portanto
NÃO transforme este teste em uma proibição de `no_cidadao`/`dt_nascimento`:
isso quebraria código correto. Quem garante que esses dois campos não escapam
é o T1, em test_no_pii_in_tool_outputs.py.

A leitura é feita sobre o código-fonte (pathlib) e não por introspecção, porque
várias tools montam o SQL inline em f-strings; apenas paciente.py, condicoes.py,
atendimentos.py, unidades.py, obter_codigos_condicao_saude.py e gestantes.py
têm o SQL em constante de módulo.

O arquivo tem ainda um terceiro teste, estático como os demais: nenhum campo
sensível pode ir CRU para um campo do resultado (sempre via `to_initials`/
`compute_age_display`). Ele existe porque o T1 só alcança as tools registradas —
e há módulos em `tools/` fora de STANDALONE_TOOLS. Ver VIOLACOES_CONHECIDAS.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, Set, Tuple

import pytest

from pec_mcp.server import STANDALONE_TOOLS

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "pec_mcp" / "tools"

# Identificadores diretos do cidadão em tb_cidadao/tb_fat_cidadao_pec.
# Nenhum deles pode ser consultado pelas tools: não há transformação que os
# torne seguros, então a defesa é não trazê-los do banco.
COLUNAS_PROIBIDAS = (
    "nu_cpf",
    "nu_cns",
    "no_mae",
    "nu_telefone",
    "nu_celular",
    "no_logradouro",
    "nu_numero_logradouro",
    "no_bairro",
    "ds_email",
    "nu_cep",
)

_ARQUIVOS_TOOLS = sorted(
    caminho for caminho in _TOOLS_DIR.glob("*.py") if caminho.name != "__init__.py"
)


def test_diretorio_de_tools_foi_encontrado():
    """Protege o teste contra um glob vazio por mudança de layout."""

    assert _ARQUIVOS_TOOLS, f"Nenhum módulo de tool encontrado em {_TOOLS_DIR}"


@pytest.mark.parametrize("arquivo", _ARQUIVOS_TOOLS, ids=lambda p: p.name)
def test_tool_nao_consulta_coluna_de_identificacao_direta(arquivo: Path):
    """Nenhuma coluna de identificação direta aparece no código da tool."""

    codigo = arquivo.read_text(encoding="utf-8")
    encontradas = sorted(
        coluna for coluna in COLUNAS_PROIBIDAS if coluna in codigo
    )
    assert not encontradas, (
        f"A tool '{arquivo.name}' referencia coluna(s) de identificação direta "
        f"{encontradas}. Colunas proibidas não podem entrar na consulta — não há "
        f"anonimização possível depois. Se precisar do paciente identificado, use "
        f"no_cidadao/dt_nascimento com to_initials()/compute_age_display()."
    )


# ──────────────────────────────────────────────────────────────
# Repasse cru de campo sensível para o resultado
# ──────────────────────────────────────────────────────────────

# Campos da linha do banco que só podem chegar ao resultado transformados.
_CAMPOS_SENSIVEIS = frozenset(
    {"nome_paciente", "no_cidadao", "paciente_nome", "data_nascimento", "dt_nascimento"}
)

# Funções de `domain/patient.py` que tornam o campo seguro.
_ENVOLTORIOS = frozenset({"to_initials", "compute_age_display"})

# Violações já existentes, deliberadamente NÃO corrigidas aqui. Cada entrada é
# um achado reportado, e o teste abaixo é o que impede que ela seja esquecida:
#
#   analytics.py:187 devolve `nome_paciente=row.get("nome_paciente")`, ou seja,
#   o nome completo do paciente sem passar por to_initials(). O módulo NÃO está
#   em STANDALONE_TOOLS (nem sequer importa: o TypedDict PessoalFiltroResult não
#   existe em models.py), portanto o vazamento não é alcançável hoje pela LM.
#
# Se a violação for corrigida, este teste falha pedindo a remoção da entrada —
# de propósito, para que a quarentena não sobreviva ao conserto.
VIOLACOES_CONHECIDAS: Set[Tuple[str, str]] = {
    ("analytics.py", "nome_paciente"),
}


def _leituras_de_campo_sensivel(arvore: ast.AST) -> Iterator[Tuple[ast.AST, str]]:
    """Encontra `row.get("<campo sensível>")` e `row["<campo sensível>"]`."""

    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "get"
            and no.args
            and isinstance(no.args[0], ast.Constant)
            and no.args[0].value in _CAMPOS_SENSIVEIS
        ):
            yield no, no.args[0].value
        elif (
            isinstance(no, ast.Subscript)
            and isinstance(no.slice, ast.Constant)
            and no.slice.value in _CAMPOS_SENSIVEIS
        ):
            yield no, no.slice.value


def _repasses_crus(arquivo: Path) -> Set[Tuple[str, str]]:
    """
    Campos sensíveis que vão direto para um campo do resultado, sem envoltório.

    Consideramos "ir direto para o resultado" o campo aparecer como valor de um
    argumento nomeado (`campo=row.get(...)`, como nos TypedDicts) ou de uma
    chave de dicionário. Leituras atribuídas a variável local ficam fora: são
    tratadas depois, e o T1 cobre o resultado final.
    """

    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    pais = {
        filho: no
        for no in ast.walk(arvore)
        for filho in ast.iter_child_nodes(no)
    }

    violacoes: Set[Tuple[str, str]] = set()
    for no, campo in _leituras_de_campo_sensivel(arvore):
        pai = pais.get(no)
        if isinstance(pai, ast.Call) and isinstance(pai.func, ast.Name):
            if pai.func.id in _ENVOLTORIOS:
                continue
        vai_para_o_resultado = isinstance(pai, ast.keyword) or (
            isinstance(pai, ast.Dict) and no in pai.values
        )
        if vai_para_o_resultado:
            violacoes.add((arquivo.name, campo))
    return violacoes


def test_campo_sensivel_nunca_vai_cru_para_o_resultado():
    """
    Nome e data de nascimento só chegam ao resultado via to_initials/compute_age_display.

    O T1 cobre isso para as tools registradas, executando-as. Este teste é
    estático e por isso alcança também os módulos de `tools/` que não estão em
    STANDALONE_TOOLS — onde o T1 não chega.
    """

    encontradas: Set[Tuple[str, str]] = set()
    for arquivo in _ARQUIVOS_TOOLS:
        encontradas |= _repasses_crus(arquivo)

    novas = sorted(encontradas - VIOLACOES_CONHECIDAS)
    assert not novas, (
        f"Repasse cru de campo sensível para o resultado: {novas}. Envolva o "
        f"valor em to_initials() ou compute_age_display() antes de devolvê-lo."
    )

    corrigidas = sorted(VIOLACOES_CONHECIDAS - encontradas)
    assert not corrigidas, (
        f"Violação(ões) em quarentena já corrigida(s): {corrigidas}. Remova a(s) "
        f"entrada(s) de VIOLACOES_CONHECIDAS para o teste voltar a ser estrito."
    )


@pytest.mark.parametrize(
    "modulo", sorted({arquivo for arquivo, _ in VIOLACOES_CONHECIDAS})
)
def test_modulo_em_quarentena_nao_esta_registrado(modulo: str):
    """
    Nenhuma tool de módulo em quarentena pode ser exposta à LM.

    Esta é a rede de proteção real do achado do analytics.py: enquanto o módulo
    não estiver em STANDALONE_TOOLS, o vazamento é inalcançável. Se alguém
    registrar uma tool dele, este teste — e o de cobertura do T1 — quebram.
    """

    nome_modulo = modulo.removesuffix(".py")
    registradas_no_modulo = sorted(
        tool.__name__
        for tool in STANDALONE_TOOLS
        if getattr(tool, "__module__", "").endswith(f".{nome_modulo}")
    )
    assert not registradas_no_modulo, (
        f"O módulo '{modulo}' está em quarentena por repassar campo sensível cru "
        f"(ver VIOLACOES_CONHECIDAS) mas registrou {registradas_no_modulo} em "
        f"STANDALONE_TOOLS. Corrija a anonimização antes de expor essas tools."
    )
