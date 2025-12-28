# PEC-MCP – Agente de Consulta Clínica (MVP)

## Overview
- Servidor MCP em Python para fornecer dados clínicos do PEC (somente leitura) a agentes LLM.
- Tools atuais: captura anonimizada de paciente, mapeamento de codigos CID/CIAP por condicao, listagem de condicoes registradas e contagem agregada de pacientes.
- Conexão única ao PostgreSQL, reutilizada pelas tools para reduzir latência.

## Checklist antes de criar ou ajustar tools
- Sempre valide o schema **e** alguns dados reais no banco de teste antes de implementar uma tool.
- Use uma conexão `psql` dedicada apenas para leitura, com comando no formato: `PGPASSWORD=<senha> psql -h <host> -p <porta> -U <usuario> -d <database> -c "<SQL>"`.
- Consulte metadados (ex.: `information_schema.columns`) e amostras (`SELECT ... LIMIT 5`) para confirmar nomes de colunas, tipos e como os valores aparecem na prática.

## Tool disponível

### capturar_paciente
- Descrição: retorna dados mínimos de pacientes sem PII direta (somente leitura) a partir de filtros.
- Parâmetros (informe pelo menos um critério):
  - `paciente_id` (int, co_seq_cidadao)
  - `name_starts_with` (str, prefixo do nome, ex.: "A")
  - `sex` (str, ex.: "MASCULINO" / "FEMININO" / "INDETERMINADO"; aceita aliases M/F/I)
  - `age_min` / `age_max` (int, faixa etária em anos)
  - `limite` (int, default 50, máx 200)
- Saída (`PatientCaptureResult`):
  - `name`: iniciais do nome completo (ex.: \"Joao de Carvalho Lima\" -> \"JCL\")
  - `birth_date`: data de nascimento no formato ISO (YYYY-MM-DD)
  - `sex`: sexo (coluna `no_sexo`)
  - `gender`: igual ao sexo por enquanto (fallback até existir coluna dedicada)
- Exemplos de prompt:
  - "Recupere o paciente 123 com iniciais, data de nascimento e sexo."
  - "Liste até 5 pacientes cujo nome começa com A, sexo masculino e idade mínima de 40 anos."

### obter_codigos_condicao_saude
- Descricao: retorna codigos CID-10/CIAP associados a uma condicao de saude para uso em filtros.
- Parâmetros:
  - `condicao` (str, obrigatorio)
  - `limite` (int, default 50, max 200)
- Saida (`HealthConditionCaptureResult`):
  - `cid_codes` / `ciap_codes`: listas de codigos para filtros.
  - `cid` / `ciap`: lista detalhada com `code` e `description`.
  - `fallback_condition_text`: quando nao ha match no banco.
- Uso recomendado:
  - "Quais sao os CID de diabetes?"
  - "Quais CIAP de hipertensao?"

### listar_condicoes_pacientes
- Descricao: lista condicoes de saude (CID/CIAP) registradas em pacientes, retornando apenas iniciais e dados clinicos minimos. Nao use para descobrir codigos; use `obter_codigos_condicao_saude`.
- Parâmetros (informe pelo menos um critério):
  - `paciente_id` (int, co_seq_cidadao)
  - `name_starts_with` (str, prefixo do nome, ex.: "A")
  - `sex` (str, MASCULINO/FEMININO/INDETERMINADO; aceita M/F/I)
  - `age_min` / `age_max` (int, faixa etária em anos)
  - `cid_code` (str, código ou prefixo CID-10, ex.: "I10" ou "I10%")
  - `cid_codes` (lista de códigos/prefixos CID-10; combinados via `cid_logic`, default OR)
  - `cid_logic` (OR para múltiplos códigos; AND não é suportado na listagem)
  - `ciap_code` (str, código ou prefixo CIAP)
  - `condition_text` (str, trecho textual na descrição da condição/observação)
  - `limite` (int, default 50, máx 200)
- Saída (`ConditionResult`):
  - `paciente_id`: id interno do cidadão (co_seq_cidadao)
  - `paciente_initials`: iniciais do nome
  - `birth_date`: data de nascimento (YYYY-MM-DD)
  - `sex`: sexo (no_sexo)
  - `condition_id`: id interno da condição
  - `cid_code` / `cid_description`: código e descrição do CID-10, se houver
  - `ciap_code` / `ciap_description`: código e descrição do CIAP, se houver
  - `dt_inicio_condicao` / `dt_fim_condicao`: datas ISO
  - `situacao_id`: código da situação do problema
  - `observacao`: observações da última evolução
- Exemplos de prompt:
  - "Quais CID-10 do paciente 5708?"
  - "Liste até 10 condições de pacientes cujo nome começa com J e idade mínima de 50 anos."

### contar_pacientes
- Descrição: retorna apenas `{ "count": int }` com `COUNT(DISTINCT paciente_id)` aplicando filtros.
- Parâmetros (informe pelo menos um critério de paciente ou condição):
  - `paciente_id`, `name_starts_with`, `sex`, `age_min`, `age_max`
  - `cid_code`, `cid_codes` (lista), `cid_logic` (OR/AND), `ciap_code`, `condition_text`
- Saída (`CountResult`):
  - `count`: número de pacientes distintos que atendem aos filtros
- Guardrails:
  - Não retorna lista de pacientes, apenas a contagem.
  - Valida faixa etária (age_min <= age_max) e tamanho de `condition_text` (máx 100 chars).

### listar_ultimos_atendimentos_soap
- Descrição: recupera os últimos atendimentos SOAP (S/O/A/P) de um paciente, trazendo profissional, CBO e timestamp.
- Parâmetros:
  - `paciente_id` (int, obrigatório, co_seq_cidadao)
  - `limite` (int, opcional; máx 1000; se não informado, retorna todos)
- Saída (`AtendimentoSOAPResult`):
  - `atendimento_id`, `paciente_id`, `data_hora`
  - `cbo_codigo`, `cbo_descricao`, `profissional`, `tipo_profissional_id`, `tipo_atendimento_id`
  - `soap_s`, `soap_o`, `soap_a`, `soap_p`
- Guardrails:
  - Filtra apenas CBO médicos (`225%`) e enfermeiros (`2235%`).
  - Ordena do mais recente para o mais antigo; sem limite quando `limite` não é informado (use com filtros específicos).

## Limitações
- Somente leitura; sem escrita ou alteração de dados clínicos.
- Resposta não inclui identificadores diretos (sem nomes completos ou IDs externos).
- Gender usa o mesmo valor de sexo até haver coluna dedicada.

## Segurança e privacidade
- Não exponha identificadores sensíveis em canais não autorizados.
- Utiliza iniciais para evitar exposição de nomes completos.
- Utilize limites e filtros estritos ao iterar sobre pacientes.

## Organização e documentação
- Diretório raiz do servidor MCP: `mcp-server/src/pec_mcp` (adicione `mcp-server/src` ao `PYTHONPATH`).
- Cada tool deve ter um `README.md` próprio descrevendo tabelas e colunas relevantes acessadas no banco, bem como quaisquer filtros ou guardrails aplicados.
