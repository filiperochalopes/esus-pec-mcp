"""
Tabela de casos para exercitar as tools registradas SEM banco de dados.

Este módulo não contém testes: ele descreve, para cada tool de
`server.STANDALONE_TOOLS`, tudo que os testes de privacidade precisam saber:

  - onde interceptar a consulta (`modulo` + `consulta`);
  - quais argumentos mínimos válidos usar;
  - quais linhas sintéticas o banco "devolveria" — deliberadamente carregadas
    de PII, para que qualquer vazamento apareça na saída serializada;
  - quais chaves a saída pode ter (contrato) e qual é o teto de paginação.

É reaproveitado por test_no_pii_in_tool_outputs.py (T1), test_tool_output_keys.py
e test_limit_caps.py.

Atenção ao alvo do monkeypatch: cada tool faz `from ..db import query_all`, ou
seja, o nome fica ligado ao *módulo da tool*. Patchear `pec_mcp.db.query_all`
não tem efeito — é preciso patchear `pec_mcp.tools.<modulo>.<consulta>`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from pec_mcp.tools.atendimentos import listar_ultimos_atendimentos_soap
from pec_mcp.tools.condicoes import listar_condicoes_pacientes
from pec_mcp.tools.contar_pacientes import contar_pacientes
from pec_mcp.tools.medicoes import (
    listar_registros_antropometria,
    listar_registros_hgt,
    listar_registros_pa,
)
from pec_mcp.tools.exames import listar_resultados_hba1c
from pec_mcp.tools.gestantes import listar_gestantes
from pec_mcp.tools.obter_codigos_condicao_saude import obter_codigos_condicao_saude
from pec_mcp.tools.paciente import capturar_paciente
from pec_mcp.tools.prescricoes import listar_prescricoes_medicamentos
from pec_mcp.tools.unidades import listar_unidades_saude
from pec_mcp.tools.visitas_acs import listar_visitas_acs

# ──────────────────────────────────────────────────────────────
# Contexto falso
# ──────────────────────────────────────────────────────────────


class ContextoFalso:
    """
    Contexto mínimo aceito por `tools.get_db_conn`, que só exige um objeto com
    `state = {"db_conn": <qualquer coisa>}`.

    Não usamos a fixture `ctx` de conftest.py de propósito: ela depende de
    `db_conn`, que chama `pytest.skip()` quando PEC_TEST_DB_DSN não está
    definida — e estes testes precisam rodar sempre, em CI limpa.
    """

    def __init__(self) -> None:
        # A conexão nunca é usada: query_all/query_one são interceptados.
        self.state = {"db_conn": object()}


# ──────────────────────────────────────────────────────────────
# Valores sintéticos de PII (reconhecíveis de propósito)
# ──────────────────────────────────────────────────────────────

NOME_PACIENTE = "Maria da Silva Santos"
INICIAIS_ESPERADAS = "MSS"  # to_initials ignora a preposição "da"
NOME_MAE = "Josefa Santos Oliveira"
CPF = "529.982.247-25"
CNS = "898001160125871"
TELEFONE = "71988887777"
CELULAR = "7133334444"
LOGRADOURO = "Rua das Acácias 123"
BAIRRO = "Federação"
EMAIL = "maria.silva@exemplo.com.br"
CEP = "40210320"
DATA_NASCIMENTO = date(1985, 3, 7)

# Nome de PROFISSIONAL. As tools de atendimento/medição/visita devolvem o nome
# do profissional em claro, por decisão de produto (o profissional não é o
# sujeito anonimizado). Usamos um valor separado, sem nenhum token em comum com
# os dados do paciente, para que o T1 não confunda os dois casos.
NOME_PROFISSIONAL = "Dra. Helena Fontes Ribeiro"

# Datas que NÃO são data de nascimento — anos distintos de 1985 para que o T1
# possa proibir "1985" em qualquer formato sem falso positivo.
DATA_CONDICAO_INICIO = date(2020, 1, 15)
DATA_CONDICAO_FIM = date(2021, 11, 30)
DATA_ATENDIMENTO = datetime(2024, 3, 10, 9, 45)
DATA_MEDICAO = datetime(2024, 5, 20, 14, 30)
DATA_VISITA = date(2024, 6, 1)

# Colunas de identificação direta. São injetadas em TODAS as linhas sintéticas,
# mesmo quando a query real não as seleciona: assim o T1 também cobre o dia em
# que alguém acrescentar uma dessas colunas à consulta ou passar a linha adiante
# com um `**row`.
COLUNAS_PROIBIDAS_SINTETICAS: Dict[str, Any] = {
    "nu_cpf": CPF,
    "nu_cns": CNS,
    "no_mae": NOME_MAE,
    "nu_telefone": TELEFONE,
    "nu_celular": CELULAR,
    "no_logradouro": LOGRADOURO,
    "nu_numero_logradouro": "123",
    "no_bairro": BAIRRO,
    "ds_email": EMAIL,
    "nu_cep": CEP,
}


def _linha(**campos: Any) -> Dict[str, Any]:
    """Monta uma linha sintética com as colunas da query + toda a PII proibida."""

    return {**COLUNAS_PROIBIDAS_SINTETICAS, **campos}


# ──────────────────────────────────────────────────────────────
# Descrição de um caso
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CasoTool:
    """Como invocar uma tool sem banco e o que a saída dela pode conter."""

    tool: Callable[..., Any]
    modulo: str
    consulta: str
    argumentos: Dict[str, Any]
    linhas: List[Dict[str, Any]]
    chaves_permitidas: frozenset
    # Campos da saída que carregam a identidade do paciente e por isso só podem
    # conter iniciais (ou "N/A"/None).
    campos_de_iniciais: Tuple[str, ...] = ()
    # Teto de paginação efetivo; None quando a tool não aceita `limite`.
    teto_limite: Optional[int] = None
    # Argumentos extras usados só no teste de teto (ex.: limite=10_000).
    argumentos_limite: Dict[str, Any] = field(default_factory=dict)

    @property
    def alvo_monkeypatch(self) -> str:
        return f"pec_mcp.tools.{self.modulo}.{self.consulta}"


# ──────────────────────────────────────────────────────────────
# Linhas sintéticas por tool
# ──────────────────────────────────────────────────────────────

_LINHA_PACIENTE = _linha(
    paciente_id=1,
    nome_paciente=NOME_PACIENTE,
    data_nascimento=DATA_NASCIMENTO,
    sexo="FEMININO",
)

_LINHA_CONDICAO = _linha(
    paciente_id=1,
    nome_paciente=NOME_PACIENTE,
    data_nascimento=DATA_NASCIMENTO,
    sexo="FEMININO",
    condition_id=11,
    cid_code="E11",
    cid_description="Diabetes mellitus nao-insulino-dependente",
    ciap_code="T90",
    ciap_description="Diabetes nao insulino-dependente",
    dt_inicio_condicao=DATA_CONDICAO_INICIO,
    dt_fim_condicao=DATA_CONDICAO_FIM,
    situacao_id=0,
    observacao="Controle glicemico irregular.",
)

_LINHA_ATENDIMENTO = _linha(
    atendimento_id=21,
    paciente_id=1,
    data_hora=DATA_ATENDIMENTO,
    cbo_codigo="225125",
    cbo_descricao="Medico clinico",
    profissional=NOME_PROFISSIONAL,
    tipo_profissional_id=1,
    tipo_atendimento_id=2,
    soap_s="Refere tontura ha tres dias.",
    soap_o="PA 150/95.",
    soap_a="Hipertensao em investigacao.",
    soap_p="Solicitados exames e retorno em 30 dias.",
    condicoes=[
        {
            "condition_id": 11,
            "cid_code": "I10",
            "cid_description": "Hipertensao essencial",
            "ciap_code": "K86",
            "ciap_description": "Hipertensao sem complicacoes",
            "observacao": "Sem lesao de orgao alvo.",
            "dt_inicio_condicao": DATA_CONDICAO_INICIO.isoformat(),
            "dt_fim_condicao": None,
            "situacao_id": 0,
        }
    ],
)

_MEDICAO_COMUM = {
    "paciente_id": 1,
    "data_medicao": DATA_MEDICAO,
    "prof_id": 31,
    "prof_nome": NOME_PROFISSIONAL,
    "cbo_codigo": "225125",
    "cbo_nome": "Medico clinico",
    "origem": "pec",
}

_LINHA_ANTROPOMETRIA = _linha(
    peso_kg=70.5,
    altura_cm=162.0,
    imc=26.86,
    **_MEDICAO_COMUM,
)

_LINHA_PA = _linha(
    pas_str="130",
    pad_str="80",
    pressao_raw="130/80",
    **_MEDICAO_COMUM,
)

_LINHA_HGT = _linha(
    valor_str="118",
    tp_glicemia=0,
    **_MEDICAO_COMUM,
)

_LINHA_HBA1C = _linha(
    valor_percentual="7.4",
    dt_realizacao=DATA_MEDICAO,
    dt_resultado=DATA_MEDICAO,
)

_LINHA_PRESCRICAO = _linha(
    prescricao_id=51,
    atendimento_id=21,
    data_prescricao=DATA_ATENDIMENTO,
    medicamento="Medicamento sintetico",
    concentracao="Concentracao sintetica",
    unidade_fornecimento="comprimido",
    dose="1",
    unidade_dose_id=1,
    dose_manha="1",
    dose_tarde=None,
    dose_noite=None,
    frequencia_tipo=1,
    frequencia_descricao="Manha",
    frequencia_periodo=None,
    frequencia_unidade_tempo=None,
    posologia="Posologia sintetica",
    via_administracao_id=1,
    quantidade_receitada="30",
    inicio_tratamento=DATA_CONDICAO_INICIO,
    fim_tratamento=DATA_CONDICAO_FIM,
    duracao_tratamento="30",
    duracao_unidade_tempo=1,
    uso_continuo=True,
    dose_unica=False,
    recomendacao="Recomendacao clinica sintetica.",
    interrompido=False,
    data_interrupcao=None,
    motivo_interrupcao=None,
    grupo_renovacao_id=51,
    cid_code="E11",
    ciap_code="T90",
)

_LINHA_UNIDADE = _linha(
    unidade_id=7,
    cnes="1234567",
    nome="UBS Centro",
    localidade_id=3,
    ativo=True,
)

_LINHA_CODIGO = _linha(code="J45", description="Asma")

_LINHA_GESTANTE = _linha(
    gestacao_id=61,
    paciente_id=1,
    nome_paciente=NOME_PACIENTE,
    dpp=DATA_VISITA,
    idade_gestacional_semanas=20,
    idade_gestacional_dias=3,
    idade_gestacional_str="20s3d",
    tp_gravidez="Unica",
    st_alto_risco="Nao",
    situacao="ativa",
)

_LINHA_VISITA = _linha(
    visita_id=41,
    profissional=NOME_PROFISSIONAL,
    data_visita=DATA_VISITA,
    paciente_pec_id=1,
    paciente_nome=NOME_PACIENTE,
    turno="Manha",
    desfecho="Realizada",
    tem_peso_altura=True,
    tem_pa=True,
    tem_glicemia=False,
    st_acomp_pessoa_hipertensao=1,
    st_mot_vis_visita_periodica=1,
)


# ──────────────────────────────────────────────────────────────
# Tabela de casos, indexada pelo nome da tool
# ──────────────────────────────────────────────────────────────

CASOS: Dict[str, CasoTool] = {
    "capturar_paciente": CasoTool(
        tool=capturar_paciente,
        modulo="paciente",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_PACIENTE],
        chaves_permitidas=frozenset({"paciente_id", "name", "age", "sex"}),
        campos_de_iniciais=("name",),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "obter_codigos_condicao_saude": CasoTool(
        tool=obter_codigos_condicao_saude,
        # "asma" não é preset: força o caminho que consulta o banco.
        modulo="obter_codigos_condicao_saude",
        consulta="query_all",
        argumentos={"condicao": "asma"},
        linhas=[_LINHA_CODIGO],
        chaves_permitidas=frozenset(
            {
                "condition",
                "source",
                "cid_codes",
                "ciap_codes",
                "cid",
                "ciap",
                "fallback_condition_text",
            }
        ),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_condicoes_pacientes": CasoTool(
        tool=listar_condicoes_pacientes,
        modulo="condicoes",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_CONDICAO],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "paciente_initials",
                "age",
                "sex",
                "condition_id",
                "cid_code",
                "cid_description",
                "ciap_code",
                "ciap_description",
                "dt_inicio_condicao",
                "dt_fim_condicao",
                "situacao_id",
                "observacao",
            }
        ),
        campos_de_iniciais=("paciente_initials",),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "contar_pacientes": CasoTool(
        tool=contar_pacientes,
        modulo="contar_pacientes",
        consulta="query_one",
        argumentos={"paciente_id": 1},
        linhas=[_linha(total=42)],
        chaves_permitidas=frozenset({"count"}),
        # Não aceita `limite`: devolve apenas uma contagem.
        teto_limite=None,
    ),
    "listar_unidades_saude": CasoTool(
        tool=listar_unidades_saude,
        modulo="unidades",
        consulta="query_all",
        argumentos={},
        linhas=[_LINHA_UNIDADE],
        chaves_permitidas=frozenset(
            {"unidade_id", "cnes", "name", "localidade_id", "is_active"}
        ),
        teto_limite=None,
    ),
    "listar_ultimos_atendimentos_soap": CasoTool(
        tool=listar_ultimos_atendimentos_soap,
        modulo="atendimentos",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_ATENDIMENTO],
        chaves_permitidas=frozenset(
            {
                "atendimento_id",
                "paciente_id",
                "data_hora",
                "cbo_codigo",
                "cbo_descricao",
                "profissional",
                "tipo_profissional_id",
                "tipo_atendimento_id",
                "soap_s",
                "soap_o",
                "soap_a",
                "soap_p",
                "condicoes",
            }
        ),
        teto_limite=1000,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_registros_antropometria": CasoTool(
        tool=listar_registros_antropometria,
        modulo="medicoes",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_ANTROPOMETRIA],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "peso_kg",
                "altura_cm",
                "imc",
                "data_medicao",
                "profissional_id",
                "profissional_nome",
                "tipo_profissional",
                "origem",
            }
        ),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_registros_pa": CasoTool(
        tool=listar_registros_pa,
        modulo="medicoes",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_PA],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "pas",
                "pad",
                "pressao_raw",
                "data_medicao",
                "profissional_id",
                "profissional_nome",
                "tipo_profissional",
                "origem",
            }
        ),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_registros_hgt": CasoTool(
        tool=listar_registros_hgt,
        modulo="medicoes",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_HGT],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "valor_mg_dl",
                "momento_afericao",
                "data_medicao",
                "profissional_id",
                "profissional_nome",
                "tipo_profissional",
                "origem",
            }
        ),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_resultados_hba1c": CasoTool(
        tool=listar_resultados_hba1c,
        modulo="exames",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_HBA1C],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "valor_percentual",
                "data_realizacao",
                "data_resultado",
            }
        ),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_prescricoes_medicamentos": CasoTool(
        tool=listar_prescricoes_medicamentos,
        modulo="prescricoes",
        consulta="query_all",
        argumentos={"paciente_id": 1},
        linhas=[_LINHA_PRESCRICAO],
        chaves_permitidas=frozenset(
            {
                "paciente_id",
                "prescricao_id",
                "atendimento_id",
                "data_prescricao",
                "medicamento",
                "concentracao",
                "unidade_fornecimento",
                "dose",
                "unidade_dose_id",
                "dose_manha",
                "dose_tarde",
                "dose_noite",
                "frequencia_tipo",
                "frequencia_descricao",
                "frequencia_periodo",
                "frequencia_unidade_tempo",
                "posologia",
                "via_administracao_id",
                "quantidade_receitada",
                "inicio_tratamento",
                "fim_tratamento",
                "duracao_tratamento",
                "duracao_unidade_tempo",
                "uso_continuo",
                "dose_unica",
                "recomendacao",
                "interrompido",
                "data_interrupcao",
                "motivo_interrupcao",
                "grupo_renovacao_id",
                "cid_code",
                "ciap_code",
                "estado",
                "alerta_consistencia_documental",
            }
        ),
        teto_limite=500,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_gestantes": CasoTool(
        tool=listar_gestantes,
        modulo="gestantes",
        consulta="query_all",
        argumentos={},
        linhas=[_LINHA_GESTANTE],
        chaves_permitidas=frozenset(
            {
                "gestacao_id",
                "paciente_id",
                "paciente_initials",
                "dpp",
                "idade_gestacional_semanas",
                "idade_gestacional_dias",
                "idade_gestacional_str",
                "tp_gravidez",
                "st_alto_risco",
                "situacao",
            }
        ),
        campos_de_iniciais=("paciente_initials",),
        teto_limite=200,
        argumentos_limite={"limite": 10_000},
    ),
    "listar_visitas_acs": CasoTool(
        tool=listar_visitas_acs,
        modulo="visitas_acs",
        consulta="query_all",
        argumentos={},
        linhas=[_LINHA_VISITA],
        chaves_permitidas=frozenset(
            {
                "visita_id",
                "profissional",
                "data_visita",
                "paciente_id",
                "paciente_nome",
                "turno",
                "desfecho",
                "motivo_visita",
                "acompanhamentos",
                "tem_peso_altura",
                "tem_pa",
                "tem_glicemia",
            }
        ),
        campos_de_iniciais=("paciente_nome",),
        teto_limite=500,
        argumentos_limite={"limite": 10_000},
    ),
}


# ──────────────────────────────────────────────────────────────
# Execução de um caso
# ──────────────────────────────────────────────────────────────


def instalar_consulta_falsa(
    monkeypatch, caso: CasoTool, registro: Optional[List[dict]] = None
) -> None:
    """
    Substitui query_all/query_one do módulo da tool por um stub em memória.

    Quando `registro` é passado, cada chamada é anexada a ele como
    {"sql": ..., "params": [...]}, o que permite inspecionar o LIMIT efetivo.
    """

    devolve_lista = caso.consulta == "query_all"

    def _consulta_falsa(conn, sql: str, params: Optional[Sequence] = None):
        if registro is not None:
            registro.append({"sql": sql, "params": list(params or ())})
        return list(caso.linhas) if devolve_lista else dict(caso.linhas[0])

    monkeypatch.setattr(caso.alvo_monkeypatch, _consulta_falsa)


def executar_caso(
    monkeypatch,
    caso: CasoTool,
    *,
    argumentos_extra: Optional[Dict[str, Any]] = None,
    registro: Optional[List[dict]] = None,
) -> Any:
    """Invoca a tool do caso com a consulta interceptada."""

    instalar_consulta_falsa(monkeypatch, caso, registro)
    argumentos = {**caso.argumentos, **(argumentos_extra or {})}
    return caso.tool(ContextoFalso(), **argumentos)


def linhas_de_saida(resultado: Any) -> List[Dict[str, Any]]:
    """
    Normaliza o retorno de uma tool numa lista de dicionários de primeiro nível.

    Algumas tools devolvem lista (capturar_paciente), outras um único objeto
    (contar_pacientes, obter_codigos_condicao_saude).
    """

    if isinstance(resultado, dict):
        return [resultado]
    if isinstance(resultado, list):
        return [item for item in resultado if isinstance(item, dict)]
    raise AssertionError(f"Retorno inesperado da tool: {type(resultado)!r}")


__all__ = [
    "CASOS",
    "CasoTool",
    "ContextoFalso",
    "executar_caso",
    "instalar_consulta_falsa",
    "linhas_de_saida",
]
