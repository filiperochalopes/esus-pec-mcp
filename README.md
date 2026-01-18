# PEC MCP Server

Um servidor [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) construído com `FastMCP` para consulta segura e otimizada de dados clínicos no Prontuário Eletrônico do Cidadão (PEC).

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
uv pip install mcp psycopg2-binary python-dotenv
```

### Usando pip

```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install mcp psycopg2-binary python-dotenv
```

## Configuração

O servidor é configurado via variáveis de ambiente. Você pode criar um arquivo `.env` na raiz do projeto ou exportar as variáveis diretamente.

### Variáveis de Banco de Dados

| Variável          | Padrão      | Descrição                                  |
|-------------------|-------------|--------------------------------------------|
| `PEC_DB_HOST`     | `localhost` | Host do banco de dados PostgreSQL          |
| `PEC_DB_PORT`     | `5432`      | Porta do banco de dados                    |
| `PEC_DB_NAME`     | `postgres`  | Nome do banco de dados (ex: `esus`)        |
| `PEC_DB_USER`     | `postgres`  | Usuário do banco de dados                  |
| `PEC_DB_PASSWORD` | `pass`      | Senha do usuário                           |

### Variáveis do Servidor MCP

| Variável        | Padrão      | Descrição                                     |
|-----------------|-------------|-----------------------------------------------|
| `MCP_HTTP_HOST` | `127.0.0.1` | Host para o servidor HTTP                     |
| `MCP_HTTP_PORT` | `5174`      | Porta para o servidor HTTP                    |

Exemplo de arquivo `.env`:

```env
PEC_DB_HOST=192.168.1.100
PEC_DB_NAME=esus
PEC_DB_USER=esus_leitura
PEC_DB_PASSWORD=senha_segura
```

## Uso

Para iniciar o servidor:

```bash
# Se o diretório src estiver no PYTHONPATH
python -m src.pec_mcp.server

# Ou executando diretamente se estiver na raiz
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python src/pec_mcp/server.py
```

O servidor iniciará em `http://127.0.0.1:5174` (ou conforme configurado) usando transporte SSE (Server-Sent Events) compatível com clientes MCP.

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
Recupera o histórico de atendimentos (SOAP) de um paciente específico.
- **Filtros**: `paciente_id` (obrigatório).

### `obter_codigos_condicao_saude`
Busca códigos CID-10 ou CIAP correspondentes a um termo de busca. Útil para descobrir códigos antes de usar filtros de condição.

## Segurança

- **Somente Leitura**: O servidor deve ser conectado a um usuário de banco com permissões estritas de `SELECT`.
- **Anonimização**: As ferramentas retornam apenas iniciais dos nomes e dados agregados onde possível.
- **Limites**: Todas as consultas possuem limites (`LIMIT`) forçados para evitar exfiltração massiva de dados.

## Licença

MIT
