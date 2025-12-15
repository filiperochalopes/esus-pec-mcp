# PEC MCP (MVP)

Servidor MCP em Python para consultar dados clínicos do PEC. No MVP atual, expomos apenas uma ferramenta focada em captura anonimizada de paciente (iniciais, data de nascimento, sexo e gênero).

## Requisitos
- Python 3.11+
- Acesso de leitura ao PostgreSQL do PEC.

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

## Tool disponível (MVP)
- `capturar_paciente`: recebe filtros (ex.: `paciente_id`, `name_starts_with`, `sex`, `age_min/age_max`) e retorna um registro mínimo sem PII direta:
  - `name`: iniciais do nome completo (ex.: \"Joao de Carvalho Lima\" -> \"JCL\")
  - `birth_date`: data de nascimento (YYYY-MM-DD)
  - `sex`: sexo (coluna `no_sexo`, valores típicos: MASCULINO/FEMININO/INDETERMINADO; aceita aliases M/F/I)
  - `gender`: igual ao sexo por enquanto (fallback até existir coluna dedicada)

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
