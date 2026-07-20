from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pec_mcp.tools import atendimentos, medicoes


class _Context:
    state = {"db_conn": object()}


def test_listar_atendimentos_exclui_cancelados(monkeypatch):
    captured: dict[str, object] = {}

    def fake_query_all(_conn, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return [
            {
                "atendimento_id": 101,
                "paciente_id": 202,
                "data_hora": datetime(2026, 1, 2, 10, 30),
                "cbo_codigo": "225000",
                "cbo_descricao": "Profissional sintético",
                "profissional": "PS",
                "tipo_profissional_id": "1",
                "tipo_atendimento_id": "2",
                "soap_s": None,
                "soap_o": None,
                "soap_a": None,
                "soap_p": None,
                "condicoes": [],
            }
        ]

    monkeypatch.setattr(atendimentos, "query_all", fake_query_all)

    result = atendimentos.listar_ultimos_atendimentos_soap(
        _Context(), paciente_id=202, limite=5
    )

    normalized_sql = " ".join(str(captured["sql"]).lower().split())
    assert "coalesce(ap.st_cancelado, 0) = 0" in normalized_sql
    assert captured["params"] == (202, 5)
    assert len(result) == 1
    assert result[0]["atendimento_id"] == 101


def test_demais_consultas_clinicas_excluem_atendimentos_cancelados():
    normalized_medicoes = " ".join(medicoes._FROM_PEC.lower().split())
    assert "coalesce(ap.st_cancelado, 0) = 0" in normalized_medicoes

    sem_consulta_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "pec_mcp"
        / "tools"
        / "sem_consulta.py"
    )
    normalized_sem_consulta = " ".join(
        sem_consulta_path.read_text(encoding="utf-8").lower().split()
    )
    assert "coalesce(ap.st_cancelado, 0) = 0" in normalized_sem_consulta
