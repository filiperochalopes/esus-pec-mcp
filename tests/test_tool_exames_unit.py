from __future__ import annotations

from datetime import datetime

from pec_mcp.tools import exames


class _Context:
    state = {"db_conn": object()}


def test_hba1c_filtra_paciente_periodo_e_limite(monkeypatch):
    captured: dict[str, object] = {}

    def fake_query_all(_conn, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return [
            {
                "valor_percentual": "7.4",
                "dt_realizacao": datetime(2026, 1, 1),
                "dt_resultado": datetime(2026, 1, 2),
            }
        ]

    monkeypatch.setattr(exames, "query_all", fake_query_all)
    result = exames.listar_resultados_hba1c(
        _Context(),
        paciente_id=202,
        data_inicio="2025-01-01",
        data_fim="2026-01-31",
        limite=10,
    )
    assert captured["params"] == (
        202,
        "2025-01-01",
        "2025-01-01",
        "2026-01-31",
        "2026-01-31",
        10,
    )
    assert result[0]["valor_percentual"] == 7.4
    assert "tb_exame_hemoglobina_glicada" in str(captured["sql"]).lower()
