"""
Granularidade da idade — a proteção contra reidentificação por data exata.

`compute_age_display` nunca devolve a data de nascimento: devolve idade textual
com granularidade proporcional à idade, para que a precisão só apareça onde é
clinicamente necessária (lactentes) e desapareça onde serviria para
reidentificar (adultos).

  - acima de 5 anos  -> "32 anos"
  - de 1 a 5 anos    -> "3 anos e 2 meses"
  - abaixo de 1 ano  -> "8 meses e 15 dias"

Se alguém "simplificar" isso para idade em anos — ou pior, voltar a expor a data
— este teste quebra.

Como `freezegun` não está disponível no projeto, fixamos a data de referência
substituindo o nome `date` dentro do módulo por uma subclasse de `datetime.date`
com `today()` constante. Assim as fronteiras podem ser afirmadas por string
exata, em vez de depender do dia em que a suíte roda.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from pec_mcp.domain import patient as modulo_paciente
from pec_mcp.domain.patient import compute_age_display

# Data de referência arbitrária, mas fixa.
HOJE = date(2026, 7, 24)


def _fixar_hoje(monkeypatch, hoje: date) -> None:
    """Substitui `date` no módulo por uma subclasse com `today()` constante."""

    class DataFixa(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return hoje

    monkeypatch.setattr(modulo_paciente, "date", DataFixa)


@pytest.fixture()
def hoje_fixo(monkeypatch):
    _fixar_hoje(monkeypatch, HOJE)
    return HOJE


# (rótulo, data de nascimento, saída exata esperada)
CASOS_DE_FRONTEIRA = (
    ("0 dias", HOJE, "0 dias"),
    ("1 dia", HOJE - timedelta(days=1), "1 dia"),
    ("29 dias", HOJE - timedelta(days=29), "29 dias"),
    ("11 meses", date(2025, 8, 24), "11 meses"),
    # A partir de 1 ano entra a faixa "anos e meses".
    ("exatamente 1 ano", date(2025, 7, 24), "1 ano"),
    ("1 ano e 2 meses", date(2025, 5, 24), "1 ano e 2 meses"),
    # 5 anos ainda está na faixa detalhada (a regra é `> 5` para virar só anos).
    ("exatamente 5 anos", date(2021, 7, 24), "5 anos"),
    # 5 anos + 1 dia continua "5 anos": com months == 0 o dia é descartado.
    ("5 anos e 1 dia", date(2021, 7, 23), "5 anos"),
    ("5 anos e 2 meses", date(2021, 5, 24), "5 anos e 2 meses"),
    # Acima de 5 anos, só o total em anos.
    ("6 anos", date(2020, 7, 24), "6 anos"),
    ("32 anos", date(1994, 7, 24), "32 anos"),
    # Entradas inválidas não produzem saída.
    ("data futura", HOJE + timedelta(days=1), None),
    ("string ISO válida", "1994-07-24", "32 anos"),
    ("string inválida", "nao-e-uma-data", None),
    ("None", None, None),
)


@pytest.mark.parametrize(
    "rotulo,nascimento,esperado",
    CASOS_DE_FRONTEIRA,
    ids=[rotulo for rotulo, _, _ in CASOS_DE_FRONTEIRA],
)
def test_granularidade_da_idade_nas_fronteiras(hoje_fixo, rotulo, nascimento, esperado):
    """A idade textual é exatamente a esperada em cada fronteira de faixa."""

    obtido = compute_age_display(nascimento)
    assert obtido == esperado, (
        f"compute_age_display({nascimento!r}) com hoje={hoje_fixo} devolveu "
        f"{obtido!r}; esperado {esperado!r} ({rotulo})."
    )


@pytest.mark.parametrize(
    "nascimento",
    [
        date(1994, 7, 24),
        date(2021, 5, 24),
        HOJE - timedelta(days=29),
    ],
    ids=["adulto", "pre-escolar", "lactente"],
)
def test_idade_nunca_contem_a_data_de_nascimento(hoje_fixo, nascimento):
    """A saída não contém o ano, o mês nem o dia da data de nascimento."""

    obtido = compute_age_display(nascimento)
    assert obtido is not None
    assert str(nascimento.year) not in obtido, (
        f"compute_age_display({nascimento!r}) devolveu {obtido!r}, que contém o "
        f"ano de nascimento."
    )
    assert nascimento.isoformat() not in obtido
    assert nascimento.strftime("%d/%m/%Y") not in obtido


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug conhecido em compute_age_display: o ajuste de carry só empresta os "
        "dias do mês anterior UMA vez, então nascimentos em 30/31 de janeiro "
        "avaliados no início de março produzem dias negativos "
        "(ex.: '1 mês e -2 dias'). Achado reportado, não corrigido aqui — "
        "corrigir o cálculo deve fazer este teste passar (e falhar como XPASS, "
        "sinalizando que a marca xfail pode sair)."
    ),
)
def test_idade_nunca_expoe_dias_negativos(monkeypatch):
    """Nenhuma faixa de idade pode produzir contagem negativa de dias."""

    _fixar_hoje(monkeypatch, date(2026, 3, 1))
    obtido = compute_age_display(date(2026, 1, 31))
    assert obtido is not None
    assert "-" not in obtido, (
        f"compute_age_display(2026-01-31) com hoje=2026-03-01 devolveu {obtido!r}, "
        f"com contagem negativa de dias."
    )
