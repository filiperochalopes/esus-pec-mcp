from __future__ import annotations

from pec_mcp.tools.gestantes import listar_gestantes


class _DummyCtx:
    state = {}


def test_listar_gestantes_com_filtros_usa_alias_g(monkeypatch):
    captured = {}

    def fake_query_all(_conn, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("pec_mcp.tools.gestantes.get_db_conn", lambda _ctx: object())
    monkeypatch.setattr("pec_mcp.tools.gestantes.query_all", fake_query_all)

    result = listar_gestantes(
        _DummyCtx(),
        unidade_saude_id=3,
        equipe_id=4,
        micro_area="01",
    )

    assert result == []
    sql = captured["sql"]
    assert "pr2.co_cidadao = g.co_seq_cidadao" in sql
    assert "ve.co_cidadao = g.co_seq_cidadao" in sql
    assert "fp.co_cidadao = g.co_seq_cidadao" in sql
    assert "pr2.co_cidadao = c.co_seq_cidadao" not in sql
    assert "ve.co_cidadao = c.co_seq_cidadao" not in sql
    assert "fp.co_cidadao = c.co_seq_cidadao" not in sql
    # Não afirmamos ausência de `no_cidadao`/`nome_paciente` no SQL: a CTE seleciona
    # o nome de propósito, como insumo de to_initials(). Proibi-los aqui contradiz
    # o desenho de anonimização — a garantia correta está em
    # test_projected_columns.py (colunas proibidas / repasse cru) e em
    # test_no_pii_in_tool_outputs.py (o nome não sai da tool).
    assert captured["params"] == [7, 294, 3, 3, 4, "01", 50]
