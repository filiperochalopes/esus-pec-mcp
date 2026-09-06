from pathlib import Path


def test_unidades_uses_stable_cnes_unit_type_code():
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "pec_mcp"
        / "tools"
        / "unidades.py"
    ).read_text(encoding="utf-8")

    assert "tu.co_tipo_unidade_cnes = 2" in source
    assert "tu.no_tipo_unidade_saude" not in source
