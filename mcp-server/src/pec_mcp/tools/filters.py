"""
Helpers de filtros compartilhados entre tools de paciente/condições.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

# Expressão de idade parametrizada pelo alias da tabela de cidadão.
_AGE_EXPR_TEMPLATE = "DATE_PART('year', AGE(CURRENT_DATE, {alias}.dt_nascimento))"

_SEX_ALIASES = {
    "M": "MASCULINO",
    "F": "FEMININO",
    "I": "INDETERMINADO",
    "MASCULINO": "MASCULINO",
    "FEMININO": "FEMININO",
    "INDETERMINADO": "INDETERMINADO",
}


def normalize_sex(sex: Optional[str]) -> Optional[str]:
    """
    Normaliza sexo para valores do banco (MASCULINO, FEMININO, INDETERMINADO).
    """

    if sex is None:
        return None
    value = str(sex).strip().upper()
    return _SEX_ALIASES.get(value)


def build_patient_filters(
    paciente_id: Optional[int],
    name_prefix: Optional[str],
    sex: Optional[str],
    age_min: Optional[int],
    age_max: Optional[int],
    alias: str = "c",
) -> Tuple[List[str], List]:
    """
    Monta cláusulas e parâmetros de filtros de paciente (sem WHERE).
    """

    if age_min is not None and age_max is not None and age_min > age_max:
        raise ValueError("age_min não pode ser maior que age_max.")

    clauses: List[str] = []
    params: List = []

    age_expr = _AGE_EXPR_TEMPLATE.format(alias=alias)

    if paciente_id is not None:
        clauses.append(f"{alias}.co_seq_cidadao = %s")
        params.append(paciente_id)
    if name_prefix:
        clauses.append(f"{alias}.no_cidadao ILIKE %s")
        params.append(f"{name_prefix}%")
    if sex:
        normalized = normalize_sex(sex)
        if not normalized:
            raise ValueError("Sexo inválido. Use MASCULINO, FEMININO ou INDETERMINADO (ou M/F/I).")
        clauses.append(f"{alias}.no_sexo = %s")
        params.append(normalized)
    if age_min is not None:
        clauses.append(f"{age_expr} >= %s")
        params.append(age_min)
    if age_max is not None:
        clauses.append(f"{age_expr} <= %s")
        params.append(age_max)

    return clauses, params


def _normalize_code_prefix(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    normalized = str(code).strip().upper()
    if "%" not in normalized and "_" not in normalized:
        normalized = f"{normalized}%"
    return normalized


def build_condition_filters(
    cid_code: Optional[str],
    cid_codes: Optional[Sequence[str]],
    ciap_code: Optional[str],
    condition_text: Optional[str],
    cid_logic: str = "OR",
    allow_cid_and: bool = False,
    patient_alias: str = "c",
) -> Tuple[List[str], List]:
    """
    Monta cláusulas e parâmetros de filtros de condição (CID/CIAP/texto).
    """

    clauses: List[str] = []
    params: List = []

    cid_patterns: List[str] = []
    if cid_code:
        cid_patterns.append(_normalize_code_prefix(cid_code))
    if cid_codes:
        cid_patterns.extend([_normalize_code_prefix(code) for code in cid_codes if code])
    cid_patterns = [pat for pat in cid_patterns if pat]

    cid_logic_upper = cid_logic.upper() if cid_logic else "OR"
    if cid_patterns:
        if cid_logic_upper not in {"OR", "AND"}:
            raise ValueError("cid_logic deve ser OR ou AND.")

        if cid_logic_upper == "AND" and not allow_cid_and and len(cid_patterns) > 1:
            raise ValueError("cid_logic=AND não é suportado aqui; use OR para múltiplos CID-10.")

        if cid_logic_upper == "AND" and len(cid_patterns) > 1:
            # Cada pattern deve existir para o paciente.
            for pat in cid_patterns:
                clauses.append(
                    "EXISTS (SELECT 1 FROM tb_problema p2 "
                    "JOIN tb_prontuario pr2 ON pr2.co_seq_prontuario = p2.co_prontuario "
                    "LEFT JOIN tb_cid10 cid2 ON cid2.co_cid10 = p2.co_cid10 "
                    f"WHERE pr2.co_cidadao = {patient_alias}.co_seq_cidadao AND cid2.nu_cid10 ILIKE %s)"
                )
                params.append(pat)
        else:
            clauses.append("cid.nu_cid10 ILIKE ANY(%s)")
            params.append(cid_patterns)

    ciap_like = _normalize_code_prefix(ciap_code)
    if ciap_like:
        clauses.append("ciap.co_ciap ILIKE %s")
        params.append(ciap_like)

    if condition_text:
        text = str(condition_text).strip()
        if len(text) > 100:
            raise ValueError("condition_text muito longo (máx 100 caracteres).")
        like = f"%{text}%"
        clauses.append(
            "("
            "cid.no_cid10 ILIKE %s OR "
            "ciap.ds_ciap ILIKE %s OR "
            "COALESCE(p.ds_outro, '') ILIKE %s OR "
            "COALESCE(ue.ds_observacao, '') ILIKE %s"
            ")"
        )
        params.extend([like, like, like, like])

    return clauses, params


__all__ = ["build_patient_filters", "normalize_sex", "build_condition_filters"]
