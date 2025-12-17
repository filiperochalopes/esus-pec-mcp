# PEC MCP (MVP)

Servidor MCP em Python para consultar dados clínicos do PEC. No MVP atual, expomos apenas uma ferramenta focada em captura anonimizada de paciente (iniciais, data de nascimento, sexo e gênero).

## Requisitos
- Python 3.11+
- Acesso de leitura ao PostgreSQL do PEC.
- Chave Anthropic (Desejável)

## Segurança e Privacidade

Esse MCP busca anonimizar dados antes de tornar legível para a LM, criando um canal de seguranca e privacidade para os dados do cidadão.

> [!IMPORTANT]
> Essa aplicação é um MVP, possui rotas de API expostas e não conta com mecanismos de autenticação nativos. Certifique-se de utilizá-la em um ambiente seguro (VPN/Rede Interna) ou implementar BasicAuth via proxy reverso (Nginx/Apache).


## Configuração
1. Crie um virtualenv (opcional) e instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure variáveis de ambiente ou copie `.env.example` para `.env` e ajuste credenciais conforme o ambiente (porta padrão 54323):
   ```bash
   cp .env.example .env
   # Edite host/porta/usuário/senha se necessário
   ```

## Rodando o servidor MCP
```bash
export PYTHONPATH=mcp-server/src  # garante resolução do pacote pec_mcp
export MCP_HTTP_PORT=5174        # porta separada da UI
export MCP_HTTP_HOST=127.0.0.1
python -m pec_mcp.server
```
- O transporte padrão é `streamable-http`, compatível com `mcp` CLI.

## Integração MCP standalone
- Rode apenas o servidor acima (sem UI) para plugar em qualquer cliente/orquestrador compatível com o Model Context Protocol via HTTP (`streamable-http`).
- Aponte seu cliente para `http://<MCP_HTTP_HOST>:<MCP_HTTP_PORT>` e use o server id `pec-mcp`; nenhuma integração proprietária é necessária.
- As tools expostas no modo standalone são as mesmas do servidor: `capturar_paciente`, `listar_condicoes`, `contar_pacientes`, `listar_unidades_saude` e `listar_ultimos_atendimentos_soap`.
- Caso precise isolar o acesso, mantenha o host em `127.0.0.1` e exponha só via túnel/SSH ou reverse proxy com BasicAuth.

## Rodando a UI FastAPI/Jinja2
```bash
export PYTHONPATH="mcp-server/src:mcp-client"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --app-dir mcp-client
```
- Tema escuro, Tailwind+Alpine, painel retrátil para tool calls e engrenagem no topo para ajustar credenciais do banco (persistidas em `.env`).
- Integração direta (sem GraphQL), chamando as tools via backend Python.
- Também há um chat Claude+MCP (abaixo na página): informe `Anthropic API Key`, modelo (ex.: `claude-3-5-sonnet-20241022`) e prompt; o backend orquestra tool calls.

## Entrypoint combinado
Suba MCP + UI em um comando:
```bash
chmod +x entrypoint.sh
./entrypoint.sh
```
- MCP: porta `5174` (`MCP_HTTP_PORT`), UI: porta `8000` (`UI_PORT`).

## Testes
```bash
export PYTHONPATH=mcp-server/src
pytest mcp-server/tests
```
 - Para focar na tool de captura anonimizada: `export PYTHONPATH=mcp-server/src && pytest mcp-server/tests/test_tool_paciente.py`

## Tools disponíveis (MVP)
- `capturar_paciente`: recebe filtros (ex.: `paciente_id`, `name_starts_with`, `sex`, `age_min/age_max`) e retorna um registro mínimo sem PII direta:
  - `name`: iniciais do nome completo (ex.: \"Joao de Carvalho Lima\" -> \"JCL\")
  - `birth_date`: data de nascimento (YYYY-MM-DD)
  - `sex`: sexo (coluna `no_sexo`, valores típicos: MASCULINO/FEMININO/INDETERMINADO; aceita aliases M/F/I)
  - `gender`: igual ao sexo por enquanto (fallback até existir coluna dedicada)
  - aceita `unidade_saude_id` opcional (filtra pacientes com atendimento ou vínculo CNES na unidade)
- `listar_condicoes`: lista condições (CID/CIAP) de pacientes, exigindo ao menos um filtro (paciente, nome, sexo, faixa etária ou filtros de condição) e limite máximo de 200 registros; aceita filtro opcional `unidade_saude_id`.
- `contar_pacientes`: retorna apenas `{ "count": int }` com `COUNT(DISTINCT paciente_id)` aplicando filtros de paciente e/ou condição (CID/CIAP/texto); exige pelo menos um critério; aceita filtro opcional `unidade_saude_id`.
- `listar_unidades_saude`: devolve todas as unidades (`co_seq_unidade_saude`, CNES, nome) para popular selects de filtro.

## Estrutura
- `mcp-server/src/pec_mcp/`: código-fonte (config, conexão, models, tools e servidor MCP)
- `mcp-server/tests/`: suíte pytest cobrindo conexão e tools
- `mcp-client/`: UI FastAPI + Jinja2 + Alpine/Tailwind (tema escuro)
- `mcp-client-react/`: UI React legada (referência de UX)
- `AGENTS.md`: guia para agentes LLM sobre as capabilities do servidor

## Convenções de prefixos (schema PEC)
- Tabelas: `tb_` (tabela principal), `rl_` (relações), `tb_..._hist` (histórico), `rl_...` (relacionamentos).
- Colunas comuns:
  - `co_`: identificadores/chaves (codes, bigint)
  - `no_`: nomes (strings)
  - `dt_`: datas ou timestamps
  - `ds_`: descrições/textos
  - `nu_`: números/documentos/códigos alfanuméricos
  - `tp_`: tipos/categorias (FK para domínio)
  - `st_`: status/flags (inteiros)
  - `qt_`: quantidades
