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
    unidade_saude_id: Optional[int] = None,
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
    if unidade_saude_id is not None:
        unit_id = int(unidade_saude_id)
        if unit_id <= 0:
            raise ValueError("unidade_saude_id deve ser um inteiro positivo.")
        clauses.append(
            "("
            "EXISTS ("
            "SELECT 1 FROM tb_prontuario pr2 "
            "JOIN tb_atend a ON a.co_prontuario = pr2.co_seq_prontuario "
            f"WHERE pr2.co_cidadao = {alias}.co_seq_cidadao AND a.co_unidade_saude = %s"
            ") "
            "OR EXISTS ("
            "SELECT 1 FROM tb_cidadao_vinculacao_equipe ve "
            "JOIN tb_unidade_saude us ON us.nu_cnes = ve.nu_cnes "
            f"WHERE ve.co_cidadao = {alias}.co_seq_cidadao "
            "AND ve.nu_cnes IS NOT NULL AND ve.nu_cnes <> '' "
            "AND us.co_seq_unidade_saude = %s"
            ")"
            ")"
        )
        params.extend([unit_id, unit_id])

    return clauses, params


def _normalize_code_prefix(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    normalized = str(code).strip().upper()
    if "%" not in normalized and "_" not in normalized:
        normalized = f"{normalized}%"
    return normalized


def build_condition_filters(
    cid_code: Optional[str] = None,
    cid_codes: Optional[Sequence[str]] = None,
    ciap_code: Optional[str] = None,
    ciap_codes: Optional[Sequence[str]] = None,
    condition_text: Optional[str] = None,
    cid_logic: str = "OR",
    cid_ciap_logic: str = "OR",
    allow_cid_and: bool = False,
    patient_alias: str = "c",
) -> Tuple[List[str], List]:
    """
    Monta cláusulas e parâmetros de filtros de condição (CID/CIAP/texto).
    Suporta lógica combinada entre CID e CIAP (OR/AND).
    """

    clauses: List[str] = []
    params: List = []

    # --- 1. CID Filters ---
    cid_patterns: List[str] = []
    if cid_code:
        cid_patterns.append(_normalize_code_prefix(cid_code))
    if cid_codes:
        cid_patterns.extend([_normalize_code_prefix(code) for code in cid_codes if code])
    cid_patterns = [pat for pat in cid_patterns if pat]

    cid_clause_sql = ""
    cid_clause_params = []

    cid_logic_upper = cid_logic.upper() if cid_logic else "OR"
    if cid_patterns:
        if cid_logic_upper not in {"OR", "AND"}:
            raise ValueError("cid_logic deve ser OR ou AND.")

        if cid_logic_upper == "AND":
            if not allow_cid_and and len(cid_patterns) > 1:
                raise ValueError("cid_logic=AND não é suportado aqui; use OR para múltiplos CID-10.")
            
            # Para AND, usamos múltiplos EXISTS (mais restritivo)
            sub_clauses = []
            for pat in cid_patterns:
                sub_clauses.append(
                    "EXISTS (SELECT 1 FROM tb_problema p2 "
                    "JOIN tb_prontuario pr2 ON pr2.co_seq_prontuario = p2.co_prontuario "
                    "LEFT JOIN tb_cid10 cid2 ON cid2.co_cid10 = p2.co_cid10 "
                    f"WHERE pr2.co_cidadao = {patient_alias}.co_seq_cidadao AND cid2.nu_cid10 ILIKE %s)"
                )
                cid_clause_params.append(pat)
            cid_clause_sql = " AND ".join(sub_clauses)
        else:
            # Padrão OR
            cid_clause_sql = "cid.nu_cid10 ILIKE ANY(%s)"
            cid_clause_params.append(cid_patterns)

    # --- 2. CIAP Filters ---
    ciap_patterns: List[str] = []
    if ciap_code:
        ciap_patterns.append(_normalize_code_prefix(ciap_code))
    if ciap_codes:
        ciap_patterns.extend([_normalize_code_prefix(code) for code in ciap_codes if code])
    ciap_patterns = [pat for pat in ciap_patterns if pat]

    ciap_clause_sql = ""
    ciap_clause_params = []

    if ciap_patterns:
        # CIAP sempre trata lista como OR (IN)
        ciap_clause_sql = "ciap.co_ciap ILIKE ANY(%s)"
        ciap_clause_params.append(ciap_patterns)

    # --- 3. Combine CID & CIAP Logic ---
    logic_combiner = cid_ciap_logic.upper()
    if logic_combiner not in {"OR", "AND"}:
        logic_combiner = "OR"

    # Se tivermos CID AND (complexo) e tentarmos combinar com CIAP via OR, 
    # a query pode ficar ambígua sem parênteses cuidadosos. 
    # Simplificação: se CID=AND, ele já força subqueries EXISTS.
    # Aqui focamos no caso principal: Lista CIDs (OR) combinado com Lista CIAPs (OR) via OR global.

    if cid_clause_sql and ciap_clause_sql:
        if logic_combiner == "OR":
             clauses.append(f"({cid_clause_sql} OR {ciap_clause_sql})")
             params.extend(cid_clause_params)
             params.extend(ciap_clause_params)
        else:
             # AND
             clauses.append(cid_clause_sql)
             params.extend(cid_clause_params)
             clauses.append(ciap_clause_sql)
             params.extend(ciap_clause_params)
    elif cid_clause_sql:
        clauses.append(cid_clause_sql)
        params.extend(cid_clause_params)
    elif ciap_clause_sql:
        clauses.append(ciap_clause_sql)
        params.extend(ciap_clause_params)

    # --- 4. Condition Text (Refinamento Global) ---
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
