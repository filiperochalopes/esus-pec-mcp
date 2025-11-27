# PEC MCP (MVP)

Servidor MCP em Python para consultar dados clínicos do PEC (pré-natal, problemas CID-10 e atendimentos SOAP) via FastMCP.

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
export PYTHONPATH=src  # garante resolução do pacote pec_mcp
python -m pec_mcp.server
```
- O transporte padrão é `streamable-http`, compatível com `mcp` CLI.

## Testes
```bash
export PYTHONPATH=src
pytest
```
- Para focar em atendimentos SOAP: `export PYTHONPATH=src && pytest tests/test_tools_atendimentos.py`
- Cobertura adicional de cenários de SOAP (campo a campo) será ampliada em breve.

## Tools adicionais (analytics)
- `consulta_epidemiologia`: agregação de comorbidades (CID-10) com filtros de sexo, faixa etária e localidade.
- `consulta_pessoal`: filtros clínicos pré-definidos (sem atendimento em períodos, gestantes, hipertensos, HbA1c>8, PA>140/90).
- Para exercitar apenas estas ferramentas: `export PYTHONPATH=src && pytest tests/test_tools_analytics.py`
- Os testes pulam automaticamente se o banco estiver indisponível.
- Para validar ferramentas, garanta que o PostgreSQL esteja acessível com os dados fornecidos nas variáveis de ambiente.

## Estrutura
- `src/pec_mcp/`: código-fonte (config, conexão, models, tools e servidor MCP)
- `tests/`: suíte pytest cobrindo conexão e tools
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
