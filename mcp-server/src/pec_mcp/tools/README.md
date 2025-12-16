# Tool: capturar_paciente

- **Descrição**: retorna dados mínimos de pacientes de forma anonimizada (iniciais, data de nascimento, sexo/gênero) usando filtros obrigatórios para evitar varreduras.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_cidadao`:
    - `co_seq_cidadao` (PK interna)
    - `no_cidadao` (usado apenas para gerar iniciais)
    - `dt_nascimento` (cálculo de idade/data de nascimento)
    - `no_sexo` (sexo, também usado como `gender` por fallback) — valores típicos: `MASCULINO`, `FEMININO`, `INDETERMINADO`
  - `tb_unidade_saude` / `tb_atend`:
    - `tb_unidade_saude.co_seq_unidade_saude` (PK), `nu_cnes` (CNES), `no_unidade_saude`, `st_ativo`
    - `tb_atend.co_unidade_saude` (unidade do atendimento) + `co_prontuario` (para cruzar com paciente)
    - usados para filtrar pacientes que têm atendimento na unidade escolhida
  - `tb_cidadao_vinculacao_equipe`:
    - `co_cidadao`, `nu_cnes` (CNES da equipe/unidade vinculada); cobre pacientes sem atendimento
- **Filtros suportados**:
  - `paciente_id` (co_seq_cidadao)
  - `name_starts_with` (prefixo de nome, ILIKE)
  - `sex` (ex.: `MASCULINO`/`FEMININO`/`INDETERMINADO` ou aliases `M`/`F`/`I`)
  - `age_min` / `age_max` (anos, via `DATE_PART('year', AGE(...))`)
  - `unidade_saude_id` (co_seq_unidade_saude; opcional; usa atendimentos e vínculos por CNES)
  - `limite` (1–200; default 50)
- **Guardrails**:
  - Exige pelo menos um critério (id, prefixo, sexo ou idade) antes de consultar.
  - `unidade_saude_id` só filtra quando informado; default considera todas as unidades.
  - Retorno traz apenas iniciais, nunca nome completo ou documentos.
  - Limite máximo de 200 linhas para evitar vazamento massivo.

# Tool: listar_condicoes

- **Descrição**: lista condições de saúde (CID/CIAP) de pacientes usando filtros mínimos para evitar varreduras.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_problema`:
    - `co_seq_problema` (PK interna da condição)
    - `co_cid10` (FK para CID-10)
    - `co_prontuario` (FK para prontuário/paciente)
    - `co_unico_problema` (chave para evoluções)
  - `tb_problema_evolucao`:
    - `dt_inicio_problema`, `dt_fim_problema`, `co_situacao_problema`, `ds_observacao`
    - usa `co_unico_problema` para obter a última evolução
  - `tb_prontuario`: `co_seq_prontuario`, `co_cidadao`
  - `tb_cidadao`: `co_seq_cidadao`, `no_cidadao`, `dt_nascimento`, `no_sexo`
  - `tb_cid10`: `nu_cid10`, `no_cid10`
  - `tb_unidade_saude` / `tb_atend` / `tb_cidadao_vinculacao_equipe`:
    - `tb_atend.co_unidade_saude` aponta para `tb_unidade_saude.co_seq_unidade_saude` (CNES em `nu_cnes`)
    - filtro opcional `unidade_saude_id` considera atendimentos ou vínculos por CNES (tabela de vinculação)
- **Filtros suportados** (ao menos um é obrigatório):
  - `paciente_id` (co_seq_cidadao)
  - `name_starts_with` (prefixo de nome, ILIKE)
  - `sex` (MASCULINO/FEMININO/INDETERMINADO ou aliases M/F/I)
  - `age_min` / `age_max` (anos, via `DATE_PART('year', AGE(...))`)
  - `unidade_saude_id` (co_seq_unidade_saude; opcional; usa atendimentos e vínculos por CNES)
  - `cid_code` (código/prefixo CID-10, ILIKE) ou `cid_codes` (lista; combinados com `cid_logic`, default OR)
  - `cid_logic` (OR para múltiplos códigos; AND não é suportado na listagem)
  - `ciap_code` (código/prefixo CIAP, ILIKE)
  - `condition_text` (trecho textual nas descrições CID/CIAP ou observação)
  - `limite` (1–200; default 50)
- **Guardrails**:
  - Exige ao menos um filtro antes de consultar.
  - `unidade_saude_id` é opcional; se não informado, considera todas as unidades.
  - Retorno inclui iniciais em vez de nome completo.
  - Limite máximo de 200 linhas por chamada.

# Tool: contar_pacientes

- **Descrição**: retorna apenas a contagem (`count`) de pacientes distintos aplicando filtros de paciente e/ou condição.
- **Consulta**: somente leitura; não retorna payload de pacientes.
- **Tabelas/colunas relevantes**: mesmas de `listar_condicoes`, mas usa `COUNT(DISTINCT c.co_seq_cidadao)`; só faz JOIN em `tb_problema`/`tb_cid10`/`tb_ciap` se filtros de condição forem informados; `unidade_saude_id` usa `tb_atend` (co_unidade_saude) ou `tb_cidadao_vinculacao_equipe` (nu_cnes) cruzados com `tb_unidade_saude`.
- **Filtros suportados** (ao menos um é obrigatório):
  - Paciente: `paciente_id`, `name_starts_with`, `sex`, `age_min`, `age_max`, `unidade_saude_id`
  - Condição: `cid_code`, `cid_codes` (lista), `cid_logic` (OR/AND), `ciap_code`, `condition_text` (ILIKE em descrições/observações)
- **Guardrails**:
  - Exige pelo menos um filtro para evitar contagens amplas sem contexto.
  - Filtro de unidade é opcional; default considera todas as unidades.
  - Valida faixa etária (age_min <= age_max) e tamanho de `condition_text` (máx 100 chars).

# Tool: listar_unidades_saude

- **Descrição**: lista todas as unidades de saúde cadastradas (uso típico: popular select de filtro).
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_unidade_saude`:
    - `co_seq_unidade_saude` (PK usada nos filtros), `nu_cnes` (CNES), `no_unidade_saude`
    - `co_localidade_endereco`, `st_ativo`
- **Filtros suportados**: nenhum (retorna todas as unidades; no dump atual são 21, com 12 usadas em atendimentos e 10 com vínculos por CNES).
- **Guardrails**:
  - Apenas leitura; ordena pelo nome da unidade.
