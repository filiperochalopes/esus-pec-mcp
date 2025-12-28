"""
Tool para obter codigos CID-10/CIAP associados a uma condicao de saude.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Pattern, Tuple

from mcp.server.fastmcp import Context

from ..db import query_all
from ..models import HealthConditionCaptureResult, HealthConditionCode
from . import get_db_conn

_SQL_CID10 = """
SELECT
    cid.nu_cid10 AS code,
    cid.no_cid10 AS description
FROM tb_cid10 cid
WHERE {where_clause}
ORDER BY cid.nu_cid10
LIMIT %s;
"""

_SQL_CIAP = """
SELECT
    ciap.co_ciap AS code,
    ciap.ds_ciap AS description
FROM tb_ciap ciap
WHERE {where_clause}
ORDER BY ciap.co_ciap
LIMIT %s;
"""

_CID_CODE_RE = re.compile(r"^[A-Z][0-9]{1,2}(?:\\.[0-9]{1,2})?$")
_CIAP_CODE_RE = re.compile(r"^[A-Z][0-9]{2,3}$")

_PRESET_CONDITIONS = {
    "gravidez": {
        "ciap": ["W03", "W05", "W71", "W78", "W79", "W80", "W81", "W84", "W85"],
        "cid": [
            "Z32.1",
            "Z33",
            "Z34.0",
            "Z34.8",
            "Z34.9",
            "Z35.0",
            "Z35.1",
            "Z35.2",
            "Z35.3",
            "Z35.4",
            "Z35.5",
            "Z35.6",
            "Z35.7",
            "Z35.8",
            "Z35.9",
        ],
    },
    "desfecho gestacao": {
        "ciap": ["W82", "W83", "W90", "W91", "W92", "W93"],
        "cid": [
            "O02",
            "O03",
            "O05",
            "O06",
            "O04",
            "Z30.3",
            "O80",
            "Z37.0",
            "Z37.9",
            "Z38",
            "Z39",
            "Z37.1",
            "O42",
            "O45",
            "O60",
            "O61",
            "O62",
            "O63",
            "O64",
            "O65",
            "O66",
            "O67",
            "O68",
            "O69",
            "O70",
            "O71",
            "O73",
            "O75.0",
            "O75.1",
            "O75.4",
            "O75.5",
            "O75.6",
            "O75.7",
            "O75.8",
            "O75.9",
            "O81",
            "O82",
            "O83",
            "O84",
            "Z37.2",
            "Z37.5",
            "Z37.3",
            "Z37.4",
            "Z37.6",
            "Z37.7",
        ],
    },
    "diabetes": {
        "ciap": ["T89", "T90"],
        "cid": ["E10", "E11", "E12", "E13", "E14"],
    },
    "hipertensao": {
        "ciap": ["K86", "K87"],
        "cid": [
            "I10",
            "I11",
            "I11.0",
            "I11.9",
            "I12",
            "I12.0",
            "I12.9",
            "I13",
            "I13.0",
            "I13.1",
            "I13.2",
            "I13.9",
            "I15",
            "I15.0",
            "I15.1",
            "I15.2",
            "I15.8",
            "I15.9",
        ],
    },
}

_PRESET_ALIASES = {
    "gravidez": {"gravidez", "gestacao"},
    "desfecho gestacao": {
        "desfecho gestacao",
        "desfecho da gestacao",
        "desfecho de gestacao",
        "desfecho gravidez",
    },
    "diabetes": {"diabetes", "diabetes mellitus"},
    "hipertensao": {"hipertensao", "hipertensao arterial", "has"},
}


def _normalize_text(value: str) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\\s]", " ", normalized)
    normalized = re.sub(r"\\s+", " ", normalized).strip()
    return normalized


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for key, aliases in _PRESET_ALIASES.items():
        for alias in aliases:
            normalized = _normalize_text(alias)
            if normalized:
                index[normalized] = key
    return index


_PRESET_ALIAS_INDEX = _build_alias_index()


def _dedupe_codes(codes: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for code in codes:
        if not code:
            continue
        normalized = str(code).strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _dedupe_matches(rows: List[dict]) -> List[HealthConditionCode]:
    seen = set()
    matches: List[HealthConditionCode] = []
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        normalized = str(code).strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        description = row.get("description")
        matches.append(
            HealthConditionCode(
                code=normalized,
                description=str(description) if description is not None else None,
            )
        )
    return matches


def _token_like(normalized: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", normalized)
    if not tokens:
        return "%"
    return "%" + "%".join(tokens) + "%"


def _code_like(raw: str, pattern: Pattern[str]) -> Optional[str]:
    candidate = re.sub(r"\\s+", "", str(raw or "")).upper()
    if pattern.match(candidate):
        return f"{candidate}%"
    return None


def _build_where_and_params(
    raw_like: str,
    normalized_like: str,
    code_like: Optional[str],
    name_column: str,
    filter_column: str,
    code_column: str,
) -> Tuple[str, List]:
    clauses = [f"{filter_column} ILIKE %s", f"{name_column} ILIKE %s"]
    params: List = [normalized_like, raw_like]
    if code_like:
        clauses.append(f"{code_column} ILIKE %s")
        params.append(code_like)
    return " OR ".join(clauses), params


def obter_codigos_condicao_saude(
    ctx: Context,
    condicao: str,
    limite: int = 50,
) -> HealthConditionCaptureResult:
    """
    Retorna codigos CID-10/CIAP associados a uma condicao informada.

    Use esta tool para responder perguntas do tipo "quais CID/CIAP de X?".
    Presets sao aplicados para condicoes comuns; caso contrario, busca no
    banco por nomes/descricoes normalizadas. Quando nao houver match,
    retorna fallback_condition_text para usar como condition_text em filtros.
    """

    if not condicao or not str(condicao).strip():
        raise ValueError("condicao e obrigatoria.")
    raw = str(condicao).strip()
    if len(raw) > 100:
        raise ValueError("condicao muito longa (max 100 caracteres).")

    normalized = _normalize_text(raw)
    if not normalized:
        raise ValueError("condicao invalida.")

    preset_key = _PRESET_ALIAS_INDEX.get(normalized)
    if preset_key:
        preset = _PRESET_CONDITIONS[preset_key]
        cid_codes = _dedupe_codes(preset.get("cid", []))
        ciap_codes = _dedupe_codes(preset.get("ciap", []))
        cid_matches = [HealthConditionCode(code=code, description=None) for code in cid_codes]
        ciap_matches = [HealthConditionCode(code=code, description=None) for code in ciap_codes]
        return HealthConditionCaptureResult(
            condition=preset_key,
            source="preset",
            cid_codes=cid_codes,
            ciap_codes=ciap_codes,
            cid=cid_matches,
            ciap=ciap_matches,
            fallback_condition_text=None,
        )

    safe_limit = max(1, min(limite, 200))
    raw_like = f"%{raw}%"
    normalized_like = _token_like(normalized)

    cid_code_like = _code_like(raw, _CID_CODE_RE)
    ciap_code_like = _code_like(raw, _CIAP_CODE_RE)

    cid_where, cid_params = _build_where_and_params(
        raw_like,
        normalized_like,
        cid_code_like,
        name_column="cid.no_cid10",
        filter_column="cid.no_cid10_filtro",
        code_column="cid.nu_cid10",
    )
    ciap_where, ciap_params = _build_where_and_params(
        raw_like,
        normalized_like,
        ciap_code_like,
        name_column="ciap.ds_ciap",
        filter_column="ciap.ds_ciap_filtro",
        code_column="ciap.co_ciap",
    )

    conn = get_db_conn(ctx)
    cid_rows = query_all(conn, _SQL_CID10.format(where_clause=cid_where), cid_params + [safe_limit])
    ciap_rows = query_all(conn, _SQL_CIAP.format(where_clause=ciap_where), ciap_params + [safe_limit])

    cid_matches = _dedupe_matches(cid_rows)
    ciap_matches = _dedupe_matches(ciap_rows)

    if not cid_matches and not ciap_matches:
        return HealthConditionCaptureResult(
            condition=raw,
            source="fallback",
            cid_codes=[],
            ciap_codes=[],
            cid=[],
            ciap=[],
            fallback_condition_text=raw,
        )

    cid_codes = [row["code"] for row in cid_matches]
    ciap_codes = [row["code"] for row in ciap_matches]
    return HealthConditionCaptureResult(
        condition=raw,
        source="database",
        cid_codes=cid_codes,
        ciap_codes=ciap_codes,
        cid=cid_matches,
        ciap=ciap_matches,
        fallback_condition_text=None,
    )


__all__ = ["obter_codigos_condicao_saude"]
