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

# Tool: listar_condicoes_pacientes

- **Descricao**: lista condicoes de saude (CID/CIAP) registradas em pacientes usando filtros minimos para evitar varreduras. Nao use para descobrir codigos; use `obter_codigos_condicao_saude`.
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
- **Tabelas/colunas relevantes**: mesmas de `listar_condicoes_pacientes`, mas usa `COUNT(DISTINCT c.co_seq_cidadao)`; só faz JOIN em `tb_problema`/`tb_cid10`/`tb_ciap` se filtros de condição forem informados; `unidade_saude_id` usa `tb_atend` (co_unidade_saude) ou `tb_cidadao_vinculacao_equipe` (nu_cnes) cruzados com `tb_unidade_saude`.
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

# Tool: contar_pacientes_sem_consulta

- **Descrição**: retorna apenas a contagem (`count`) de pacientes sem consulta recente (médicos/enfermeiros) por perfil clínico: `hipertensao`, `diabetes` ou `gestante`.
- **Consulta**: somente leitura; não retorna lista de pacientes.
- **Tabelas/colunas relevantes**:
  - `tb_atend_prof` + `tb_atend`: base para última consulta (`dt_inicio`) com filtro de CBO médico/enfermeiro.
  - `tb_lotacao` / `tb_cbo`: filtro por CBO (`co_cbo_2002` prefixos `225%` e `2235%`).
  - `tb_problema` + `tb_cid10` + `tb_ciap`: identifica hipertensão/diabetes via CID-10/CIAP.
  - `tb_pre_natal`: identifica gestantes ativas (`dt_desfecho IS NULL`).
  - `tb_cidadao`: vínculo do paciente (`co_seq_cidadao`) e filtros opcionais de unidade.
  - `tb_cidadao_vinculacao_equipe` + `tb_unidade_saude`: filtro opcional de unidade por CNES.
- **Filtros suportados**:
  - `tipo` (obrigatório): `hipertensao`, `diabetes` ou `gestante`.
  - `dias_sem_consulta` (opcional; default 180 para hipertensão/diabetes e 60 para gestantes).
  - `unidade_saude_id` (opcional; filtra pacientes vinculados e considera consultas apenas na unidade).
- **Gestantes**:
  - Aplica o mesmo recorte de idade gestacional do `listar_gestantes` (1 a 42 semanas), baseado em `dt_ultima_menstruacao`.
- **Guardrails**:
  - Retorna somente contagem agregada.
  - `unidade_saude_id` valida inteiro positivo quando informado.
  - Sempre filtra consultas por CBO médico (`225%`) e enfermeiro (`2235%`).

# Tool: listar_pacientes_sem_consulta

- **Descrição**: lista pacientes sem consulta recente (médicos/enfermeiros) por perfil clínico, com paginação.
- **Consulta**: somente leitura; retorna apenas iniciais do paciente.
- **Tabelas/colunas relevantes**: mesmas de `contar_pacientes_sem_consulta`.
- **Filtros suportados**:
  - `tipo` (obrigatório): `hipertensao`, `diabetes` ou `gestante`.
  - `dias_sem_consulta` (opcional; default 180/60).
  - `unidade_saude_id` (opcional).
  - `limite` (1–200; default 50) e `offset` (>= 0).
- **Gestantes**:
  - Mesmo recorte de idade gestacional do `listar_gestantes` (1 a 42 semanas).
- **Guardrails**:
  - Retorna apenas iniciais, data de nascimento, sexo, última consulta e dias desde a última consulta.
  - Limite máximo de 200 registros por chamada.
  - Ordena por `ultima_consulta` (NULLS FIRST) para priorizar quem não tem consulta registrada.

# Tool: listar_gestantes

- **Descrição**: lista gestações ativas em acompanhamento pré-natal, com idade gestacional calculada.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_pre_natal`: `co_seq_pre_natal`, `co_prontuario`, `dt_ultima_menstruacao`, `dt_desfecho`, `tp_gravidez`, `st_alto_risco`
  - `tb_prontuario`: `co_seq_prontuario`, `co_cidadao`
  - `tb_cidadao`: `co_seq_cidadao`, `no_cidadao`
  - `tb_exame_prenatal`: `co_exame_requisitado`, `dt_provavel_parto_eco` (DPP via eco)
- **Filtros suportados**:
  - `trimestre` (opcional: `primeiro`, `segundo`, `terceiro`)
  - `limite` (1–200; default 50)
- **Guardrails**:
  - Considera apenas gestantes ativas (`dt_desfecho IS NULL`).
  - Recorte de idade gestacional: 1 a 42 semanas, baseado em `dt_ultima_menstruacao`.
  - DPP calculada por eco quando disponível, senão `DUM + 280 dias`.
  - Idade gestacional formatada como `<semanas>s<dias>d` (ex.: `12s3d`).
  - Limite máximo de 200 linhas para evitar vazamento massivo.

# Tool: listar_ultimos_atendimentos_soap

- **Descrição**: recupera os últimos atendimentos SOAP (S/O/A/P) de um paciente específico, incluindo data/hora, profissional e CBO.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_atend_prof`: `co_seq_atend_prof` (PK do atendimento profissional), `co_atend` (FK para atendimento), `tp_atend_prof`/`tp_atend` (tipos), `co_lotacao` (lotação do profissional)
  - `tb_atend`: `co_seq_atend`, `co_prontuario`, `co_unidade_saude`, `dt_inicio` (timestamp para ordenação)
  - `tb_prontuario`: `co_seq_prontuario`, `co_cidadao` (ligação com paciente)
  - `tb_evolucao_subjetivo`/`tb_evolucao_objetivo`/`tb_evolucao_avaliacao`/`tb_evolucao_plano`: texto livre das seções SOAP, todas referenciando `co_atend_prof`
  - `tb_lotacao`/`tb_prof`/`tb_cbo`: enriquecem com nome do profissional e código/descrição do CBO (`co_cbo_2002`)
  - `tb_problema_evolucao` + `tb_problema` + `tb_cid10`/`tb_ciap`: agregam CID/CIAP ligados ao atendimento (`co_atend_prof`) na mesma resposta
- **Filtros suportados**:
  - `paciente_id` (obrigatório, `co_seq_cidadao`)
  - `limite` (opcional; 1–1000; sem limite quando não informado)
- **Guardrails**:
  - Restringe resultados a profissionais médicos (`225%`) ou enfermeiros (`2235%`) via `co_cbo_2002`.
  - Ordena do mais recente para o mais antigo pelo `dt_inicio`; quando `limite` não é informado, retorna todos os registros encontrados.

# Tool: obter_codigos_condicao_saude

- **Descricao**: retorna codigos CID-10/CIAP associados a uma condicao de saude para uso em filtros de outras tools.
- **Uso recomendado**: perguntas do tipo "quais CID/CIAP de X?" e antes de filtrar por condicao.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_cid10`: `nu_cid10`, `no_cid10`, `no_cid10_filtro`
  - `tb_ciap`: `co_ciap`, `ds_ciap`, `ds_ciap_filtro`
- **Filtros suportados**:
  - `condicao` (obrigatorio)
  - `limite` (1-200; default 50)
- **Guardrails**:
  - Valida `condicao` (nao vazia; max 100 chars).
  - Limite maximo de 200 resultados por sistema.
  - Quando nao ha match, retorna `fallback_condition_text` para uso em `condition_text`.
- **Documentacao detalhada**: `mcp-server/src/pec_mcp/tools/docs/obter_codigos_condicao_saude/README.md`
