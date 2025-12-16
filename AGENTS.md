# PEC-MCP – Agente de Consulta Clínica (MVP)

## Overview
- Servidor MCP em Python para fornecer dados clínicos do PEC (somente leitura) a agentes LLM.
- Tools atuais: captura anonimizada de paciente, listagem de condições (CID/CIAP) e contagem agregada de pacientes.
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

### listar_condicoes
- Descrição: lista condições de saúde (CID/CIAP) de pacientes, retornando apenas iniciais e dados clínicos mínimos.
- Parâmetros (informe pelo menos um critério):
  - `paciente_id` (int, co_seq_cidadao)
  - `name_starts_with` (str, prefixo do nome, ex.: "A")
  - `sex` (str, MASCULINO/FEMININO/INDETERMINADO; aceita M/F/I)
  - `age_min` / `age_max` (int, faixa etária em anos)
  - `cid_code` (str, código ou prefixo CID-10, ex.: "I10" ou "I10%")
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
- Descrição: retorna apenas `{ \"count\": int }` com `COUNT(DISTINCT paciente_id)` aplicando filtros.
- Parâmetros (informe pelo menos um critério de paciente ou condição):
  - `paciente_id`, `name_starts_with`, `sex`, `age_min`, `age_max`
  - `cid_code`, `ciap_code`, `condition_text`
- Saída (`CountResult`):
  - `count`: número de pacientes distintos que atendem aos filtros
- Guardrails:
  - Não retorna lista de pacientes, apenas a contagem.
  - Valida faixa etária (age_min <= age_max) e tamanho de `condition_text` (máx 100 chars).

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
