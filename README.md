# PEC MCP (MVP)

Profissional assistência (Médico, Enfermagem) Capture sumários rápidos sobre o quadro de um paciente de forma completa: dados e condições de saúde com a segurança de dados anonimizados. Criador pelo médico engenheiro de Software e consultor PEC [Dr. Filipe Lopes](https://link.orango.io/Gq7N8).
Gestor: Obtenha dados de gestão e epidemiologia na distancia de uma pergunta e até mesmo dados e métricas relacionados ao modelo de coparticipação Saúde 360 com componente de busca ativa.

## Gostaria de saber sua opnião

O que você queria que essa aplicação tivesse? [Faça suas perguntas aqui](https://wa.me/5571992518950&text=Ol%C3%A1%2C%20%C3%A9%20sobre%20o%20projeto%20PEC%20MCP)

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

As tools expostas pelo servidor MCP (`pec_mcp` em `mcp-server/src/pec_mcp`) seguem as mesmas regras de conexão do Model Context Protocol via HTTP (`streamable-http`) e são usadas tanto pela UI quanto por clientes externos. Todas fazem apenas leituras no banco do PEC e exigem ao menos um critério para evitar varreduras.

### capturar_paciente
- **Parâmetros principais**: `paciente_id`, `name_starts_with`, `sex` (aceita M/F/I como alias), `age_min`, `age_max`, `limite` (default 50, máximo 200), `unidade_saude_id` (filtra atendimentos ou vínculos por CNES).
- **Retorno**: `name` (iniciais do nome completo), `birth_date` (YYYY-MM-DD), `sex` (coluna `no_sexo`), `gender` (mesmo valor de `sex` até haver coluna dedicada) e identificadores internos como `paciente_id`/`co_seq_cidadao`.
- **Guardrails**: exige ao menos um filtro de paciente, limita resultados a 200 linhas, nunca expõe nomes completos ou documentos, e aplica os filtros de unidade apenas quando informado (`co_seq_unidade_saude` ou CNES vinculado).

### listar_condicoes
- **Parâmetros principais**: mesmo conjunto paciente (id, prefixo de nome, sexo, faixa etária, unidade) e filtros de condição (`cid_code`, lista `cid_codes` combinadas com `cid_logic` (default OR), `ciap_code`, `condition_text`, `limite` 1–200).
- **Retorno**: lista de `ConditionResult` com `paciente_id`, `paciente_initials`, `birth_date`, `sex`, `condition_id`, `cid_code`/`cid_description`, `ciap_code`/`ciap_description`, `dt_inicio_condicao`, `dt_fim_condicao`, `situacao_id`, `observacao`. Os valores textuais (CID/CIAP/observação) são filtrados com `ILIKE`.
- **Guardrails**: exige pelo menos um filtro antes de executar a consulta; `cid_logic` opera apenas como OR; o limite máximo é 200 registros e as iniciais substituem nomes completos para manter anonimização.

### contar_pacientes
- **Parâmetros principais**: qualquer filtro de paciente (`paciente_id`, `name_starts_with`, `sex`, `age_min`, `age_max`, `unidade_saude_id`) e/ou condição (`cid_code`, `cid_codes` com `cid_logic` OR/AND, `ciap_code`, `condition_text` com até 100 caracteres).
- **Retorno**: objeto simples `{ "count": int }` representando `COUNT(DISTINCT paciente_id)` que atende aos filtros; não retorna listas de pacientes.
- **Guardrails**: valida faixa etária (`age_min <= age_max`); `condition_text` é limitado a 100 caracteres; exige ao menos um critério de filtro; `cid_logic` pode ser OR ou AND nesse contexto.

### listar_unidades_saude
- **Parâmetros principais**: nenhum; retorna todas as unidades cadastradas ordenadas por nome.
- **Retorno**: cada unidade traz `co_seq_unidade_saude`, `nu_cnes`, `no_unidade_saude`, `st_ativo`, `co_localidade_endereco`.
- **Uso**: alimenta selects da UI e filtros opcionais das demais tools.

### listar_ultimos_atendimentos_soap
- **Parâmetros principais**: `paciente_id` (obrigatório, `co_seq_cidadao`) e `limite` (1–1000; quando omisso, retorna todos os atendimentos encontrados).
- **Retorno**: `AtendimentoSOAPResult` com `atendimento_id`, `paciente_id`, `data_hora`, `cbo_codigo`, `cbo_descricao`, `profissional`, `tipo_profissional_id`, `tipo_atendimento_id`, `soap_s`, `soap_o`, `soap_a`, `soap_p`, e informações auxiliares (CID/CIAP da evolução mais recente).
- **Guardrails**: filtra apenas profissionais médicos (`cbo_codigo` começando com `225`) ou enfermeiros (`2235`); ordena do mais recente para o mais antigo.

### Observações gerais
- Todas as tools reutilizam a conexão PostgreSQL configurada em `mcp-server/src/pec_mcp/db.py`.
- O schema PEC usa prefixos como `tb_`/`rl_`/`co_`/`no_`/`dt_` (veja seção “Convenções...” abaixo).

## Auto-tools da UI FastAPI + Claude (mcp-client)

A interface FastAPI + Jinja2 (rodando em `mcp-client/`) reconhece comandos rápidos ("auto-tools") ao digitar `/` no prompt e exibir um menu de ações. Os auto-tools embarcam rotas REST adicionais que não passam pelo MCP mas complementam a experiência para médicos e gestores.

- **/paciente-id**: abre um modal pedindo um identificador numérico interno e usa as rotas `GET /api/pacientes/{paciente_id}`, `/api/pacientes/{paciente_id}/historico` e `/api/pacientes/{paciente_id}/condicoes` para mostrar detalhes, histórico SOAP, e condições filtradas daquele paciente. A validação exige um número inteiro e a modal inclui abas para histórico e condições sem expor nomes completos.
- **/saude-360-c3**: dispara a rota `GET /saude-360/c3` (com filtros opcionais `start_date`, `end_date`, `unidade_id`) para calcular o indicador C3 de gestantes/puérperas por unidade. A UI exibe uma tabela com score geral, componentes (A–F) e total de gestantes; clicar em um componente chama `/saude-360/c3/{component}` para ver pacientes em déficit naquele item.
- **Como ativar**: tecle `/` no campo de prompt (ou clique no botão “?” ao lado) para abrir o menu; ferramentas ativas exibem o texto em monoespaçado e permitem seleção via Enter. `/paciente-id` abre um campo numérico e `/saude-360-c3` já dispara a requisição diretamente.
- **Outros auto-tools guardados** (ex.: `/paciente-cpf`, `/gestantes`, `/gestante-cpf`, `/gestante-id`) estão no menu mas ainda aparecem como “Em breve” porque `active: false` em `mcp-client/static/js/app.js`.

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

Quem quiser testar a ferramenta (entre em contato)[https://wa.me/5571992518950]