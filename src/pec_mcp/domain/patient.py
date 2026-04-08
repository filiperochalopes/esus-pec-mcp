"""
Entidade de domínio Patient.

Centraliza toda lógica de privacidade e anonimização relacionada a pacientes,
garantindo conformidade com a LGPD: nenhum dado identificável (nome completo,
data de nascimento exata, CPF, CNS) é exposto ao modelo de linguagem.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional


def to_initials(full_name: Optional[str]) -> str:
    """
    Converte nome completo em iniciais maiúsculas.

    Ignora artigos/preposições comuns do português.
    Ex.: "João de Carvalho Lima" -> "JCL"
    Retorna "N/A" se o nome for nulo ou vazio.
    """
    if not full_name:
        return "N/A"
    skip = {"de", "da", "do", "das", "dos", "e"}
    parts = re.split(r"\s+", str(full_name).strip())
    initials = [p[0].upper() for p in parts if p and p.lower() not in skip]
    return "".join(initials) if initials else "N/A"


def compute_age_display(birth_date: Optional[date | str]) -> Optional[str]:
    """
    Calcula a idade a partir da data de nascimento e retorna uma representação
    textual com granularidade proporcional à idade — impedindo a re-identificação
    do paciente a partir da data exata.

    Regras:
      - > 5 anos           → "32 anos"
      - Entre 1 e 5 anos   → "3 anos e 2 meses"
      - < 1 ano            → "8 meses e 15 dias"

    Retorna None se a data for nula ou inválida.
    """
    if birth_date is None:
        return None

    # Normaliza para date
    if isinstance(birth_date, str):
        try:
            birth_date = date.fromisoformat(birth_date)
        except ValueError:
            return None
    elif isinstance(birth_date, datetime):
        birth_date = birth_date.date()

    today = date.today()
    if birth_date > today:
        return None

    years = today.year - birth_date.year
    months = today.month - birth_date.month
    days = today.day - birth_date.day

    # Ajustes de carry
    if days < 0:
        months -= 1
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        import calendar
        days += calendar.monthrange(prev_year, prev_month)[1]

    if months < 0:
        years -= 1
        months += 12

    if years > 5:
        return f"{years} anos"
    elif years >= 1:
        if months == 0:
            return f"{years} {'ano' if years == 1 else 'anos'}"
        return f"{years} {'ano' if years == 1 else 'anos'} e {months} {'mês' if months == 1 else 'meses'}"
    else:
        total_months = years * 12 + months
        if total_months == 0:
            return f"{days} {'dia' if days == 1 else 'dias'}"
        if days == 0:
            return f"{total_months} {'mês' if total_months == 1 else 'meses'}"
        return f"{total_months} {'mês' if total_months == 1 else 'meses'} e {days} {'dia' if days == 1 else 'dias'}"


__all__ = ["to_initials", "compute_age_display"]
