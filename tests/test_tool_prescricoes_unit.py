from __future__ import annotations

from datetime import date, datetime, timedelta

from pec_mcp.tools import prescricoes


class _Context:
    state = {"db_conn": object()}


def test_prescricoes_abrange_grupo_ignora_cancelados_e_preserva_campos(monkeypatch):
    captured: dict[str, object] = {}

    def fake_query_all(_conn, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return [
            {
                "prescricao_id": 10,
                "atendimento_id": 20,
                "data_prescricao": datetime(2026, 1, 2, 10, 30),
                "medicamento": "Medicamento sintético",
                "concentracao": "Concentração sintética",
                "unidade_fornecimento": "unidade",
                "dose": "1",
                "unidade_dose_id": 1,
                "dose_manha": None,
                "dose_tarde": None,
                "dose_noite": None,
                "frequencia_tipo": 1,
                "frequencia_descricao": "sintética",
                "frequencia_periodo": None,
                "frequencia_unidade_tempo": None,
                "posologia": "Posologia sintética",
                "via_administracao_id": 1,
                "quantidade_receitada": "30",
                "inicio_tratamento": date.today(),
                "fim_tratamento": date.today() + timedelta(days=30),
                "duracao_tratamento": "30",
                "duracao_unidade_tempo": 1,
                "uso_continuo": True,
                "dose_unica": False,
                "recomendacao": "<p>Usar pela manhã</p>",
                "interrompido": False,
                "data_interrupcao": None,
                "motivo_interrupcao": None,
                "grupo_renovacao_id": 10,
                "cid_code": None,
                "ciap_code": None,
            }
        ]

    monkeypatch.setattr(prescricoes, "query_all", fake_query_all)
    result = prescricoes.listar_prescricoes_medicamentos(
        _Context(), paciente_id=202, limite=5
    )

    normalized_sql = " ".join(str(captured["sql"]).lower().split())
    assert "coalesce(ap.st_cancelado, 0) = 0" in normalized_sql
    assert "coalesce(pr.co_prontuario_grupo, pr.co_seq_prontuario)" in normalized_sql
    assert captured["params"] == (202, 5)
    assert result[0]["estado"] == "ativo"
    assert result[0]["recomendacao"] == "Usar pela manhã"
    assert result[0]["alerta_consistencia_documental"] is True


def test_interrupcao_tem_precedencia_sobre_data_final(monkeypatch):
    row = {
        "prescricao_id": 10,
        "atendimento_id": 20,
        "fim_tratamento": date.today() + timedelta(days=30),
        "interrompido": True,
    }
    monkeypatch.setattr(prescricoes, "query_all", lambda *_args: [row])
    result = prescricoes.listar_prescricoes_medicamentos(
        _Context(), paciente_id=202, estado="interrompido"
    )
    assert result[0]["estado"] == "interrompido"
