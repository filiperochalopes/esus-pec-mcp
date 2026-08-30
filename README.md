# PEC MCP Server

Servidor MCP e biblioteca de tools clínicas para consultas somente leitura no
Prontuário Eletrônico do Cidadão (PEC). Pode ser executado de duas formas:

- **Standalone:** processo MCP independente configurado por variáveis de ambiente.
- **Integrado ao SaaS:** biblioteca Python cuja conexão é injetada pela instalação
  autenticada, sem depender das variáveis `PEC_DB_*` do processo.

Este servidor expõe ferramentas (tools) para LLMs interagirem com a base de dados do PEC (PostgreSQL) de forma somente leitura, permitindo consultas sobre pacientes, condições de saúde, atendimentos e indicadores.

## Funcionalidades

- **Consulta de Pacientes**: Busca anonimizada por iniciais, idade, sexo e unidade de saúde.
- **Condições de Saúde**: Listagem e contagem de pacientes por condições (CID-10/CIAP).
- **Atendimentos**: Histórico de atendimentos SOAP.
- **Indicadores**: Contagem e listagem de pacientes sem consulta recente (Hipertensos, Diabéticos, Gestantes).
- **Metadados**: Busca de códigos CID-10/CIAP e listagem de unidades de saúde.

## Pré-requisitos

- Python 3.10+
- Acesso a um banco de dados PostgreSQL do PEC (ou réplica).

## Instalação

Recomendamos o uso do [uv](https://github.com/astral-sh/uv) para gerenciamento de dependências, mas o `pip` também funciona.

### Usando uv (Recomendado)

```bash
# Clone o repositório
git clone <url-do-repo>
cd mcp-server-pec

# Crie um ambiente virtual e instale as dependências
uv venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
uv pip install -e .
```

### Usando pip

```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -e .
```

## Modo standalone

Copie o exemplo e preencha uma conta PostgreSQL com permissão somente de leitura:

```bash
cp .env.example .env
```

As credenciais não possuem valores padrão. Configure uma DSN completa em
`PEC_DB_DSN` **ou** as variáveis separadas abaixo:

| Variável | Obrigatória | Padrão | Descrição |
|---|---:|---|---|
| `PEC_DB_DSN` | alternativa | — | DSN completa do PostgreSQL |
| `PEC_DB_HOST` | sim* | — | Host do banco clínico |
| `PEC_DB_PORT` | não | `5432` | Porta do PostgreSQL |
| `PEC_DB_NAME` | sim* | — | Database do PEC |
| `PEC_DB_USER` | sim* | — | Usuário somente leitura |
| `PEC_DB_PASSWORD` | sim* | — | Senha do usuário |
| `PEC_DB_SSLMODE` | não | — | Modo SSL, por exemplo `require` |
| `MCP_TRANSPORT` | não | `streamable-http` | `streamable-http`, `sse` ou `stdio` |
| `MCP_HTTP_HOST` | não | `127.0.0.1` | Endereço do servidor HTTP |
| `MCP_HTTP_PORT` | não | `5174` | Porta do servidor HTTP |

\* Obrigatória quando `PEC_DB_DSN` não for usada.

Depois, inicie pelo comando instalado:

```bash
pec-mcp
```

Ou diretamente pelo módulo:

```bash
PYTHONPATH=src python -m pec_mcp.server
```

No transporte padrão, o endpoint MCP fica em `http://127.0.0.1:5174/mcp`.
Para clientes que iniciam o processo via stdio, use `MCP_TRANSPORT=stdio`.

## Modo integrado ao SaaS

A aplicação injeta em cada chamada uma conexão criada com a configuração clínica
da instalação autenticada. Nesse modo, o SaaS continua chamando
`get_connection(dsn=cfg.as_dsn())` e entregando a conexão em `ctx.state`; portanto,
as variáveis standalone não participam da seleção da instalação.

O servidor standalone usa a mesma implementação das tools, mas entrega sua
conexão pelo `lifespan_context` nativo do FastMCP.

O entrypoint standalone registra o mesmo conjunto atualmente integrado ao SaaS:
captura de paciente, condições, contagem, unidades, SOAP, antropometria, pressão
arterial, HGT e visitas de ACS.

## Ferramentas Disponíveis

### `capturar_paciente`
Retorna dados mínimos de pacientes de forma anonimizada (iniciais, data de nascimento, sexo).
- **Filtros**: `paciente_id`, `name_starts_with`, `sex`, `age_min`, `age_max`, `unidade_saude_id`.

### `listar_condicoes_pacientes`
Lista condições de saúde (CID/CIAP) registradas em pacientes.
- **Filtros**: `cid_code`, `ciap_code`, `condition_text`, `paciente_id`, etc.

### `contar_pacientes`
Retorna apenas a contagem de pacientes que atendem aos filtros especificados. Útil para análises populacionais sem expor dados individuais.

### `listar_unidades_saude`
Lista todas as unidades de saúde cadastradas e ativas.

### `contar_pacientes_sem_consulta`
Conta pacientes sem consulta recente para perfis específicos: `hipertensao`, `diabetes` ou `gestante`.
- **Filtros**: `tipo` (obrigatório), `dias_sem_consulta`, `unidade_saude_id`.

### `listar_pacientes_sem_consulta`
Lista (paginada e anonimizada) os pacientes sem consulta recente encontrados pela ferramenta de contagem.

### `listar_ultimos_atendimentos_soap`
Recupera o histórico de atendimentos (SOAP) válidos e não cancelados de um paciente específico. Não inclui o módulo estruturado de prescrições, portanto o SOAP não deve ser usado para afirmar ausência, dose vigente ou recomendações da prescrição.
- **Filtros**: `paciente_id` (obrigatório).

### `listar_prescricoes_medicamentos`
Lista o histórico estruturado de prescrições, incluindo doses, frequência,
posologia, vigência, uso contínuo, renovação e interrupção. Abrange prontuários
agrupados e exclui atendimentos cancelados.
- **Filtros**: `paciente_id`, `estado`, `medicamento`, `limite`.

### `listar_resultados_hba1c`
Lista resultados históricos de hemoglobina glicada para correlações temporais
com HGT e mudanças documentadas de prescrição.
- **Filtros**: `paciente_id`, `data_inicio`, `data_fim`, `limite`.

### `obter_codigos_condicao_saude`
Busca códigos CID-10 ou CIAP correspondentes a um termo de busca. Útil para descobrir códigos antes de usar filtros de condição.

## Segurança

- **Somente Leitura**: O servidor deve ser conectado a um usuário de banco com permissões estritas de `SELECT`.
- **Transação protegida**: o standalone configura a sessão PostgreSQL como `readonly` e `autocommit`.
- **Sem credenciais padrão**: o modo standalone falha ao iniciar se a configuração clínica estiver incompleta.
- **Isolamento SaaS**: o modo integrado usa exclusivamente a DSN da instalação autenticada.
- **Anonimização**: As ferramentas retornam apenas iniciais dos nomes e dados agregados onde possível.
- **Limites**: Todas as consultas possuem limites (`LIMIT`) forçados para evitar exfiltração massiva de dados.

## Licença

MIT
