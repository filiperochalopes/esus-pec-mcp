# PEC-MCP – Agente de Consulta Clínica (MVP)

## Overview
- Servidor MCP em Python para fornecer dados clínicos do PEC (somente leitura) a agentes LLM.
- Foco inicial: pré-natal, problemas/comorbidades (CID-10) e últimos atendimentos SOAP.
- Conexão única ao PostgreSQL, reutilizada pelas tools para reduzir latência.

## Tools disponíveis

### listar_gestantes
- Descrição: lista gestações ativas (2–42 semanas) em acompanhamento pré-natal.
- Parâmetros:
  - `limite` (int, opcional, default 50, máx 200)
- Saída (`GestanteResult`):
  - gestacao_id, paciente_id, nome_paciente
  - dpp (ISO 8601), idade_gestacional_semanas, idade_gestacional_dias, idade_gestacional_str (ex.: "5s4d")
  - tp_gravidez, st_alto_risco, situacao="ativa"
- Exemplos de prompt:
  - "Liste até 5 gestantes em acompanhamento ativo com idade gestacional e DPP."
  - "Quais gestantes têm maior idade gestacional? Use limite 20."

### listar_problemas_paciente
- Descrição: retorna problemas/comorbidades (CID-10) de um paciente usando a última evolução por problema.
- Parâmetros:
  - `paciente_id` (int, co_cidadao)
- Saída (`ProblemaResult`):
  - problema_id, paciente_id
  - codigo_cid10, descricao_cid10
  - dt_inicio_problema (ISO), dt_fim_problema (ISO)
  - situacao_id, observacao
- Exemplos:
  - "Recupere as comorbidades do paciente 123 com datas de início e fim."
  - "Liste os CID-10 atuais do paciente 456."

### listar_ultimos_atendimentos_soap
- Descrição: últimos atendimentos (médicos 225xx, enfermeiros 2235x; dentistas comentado) com campos SOAP.
- Parâmetros:
  - `paciente_id` (int, co_cidadao)
  - `limite` (int, opcional, default 10, máx 200)
- Saída (`AtendimentoSOAPResult`):
  - atendimento_id, paciente_id, data_hora (ISO)
  - cbo_codigo, cbo_descricao, profissional, tipo_profissional_id, tipo_atendimento_id
  - soap_s, soap_o, soap_a, soap_p (podem ser nulos)
- Exemplos:
  - "Traga os 5 últimos atendimentos SOAP do paciente 789 feitos por médico ou enfermeiro."
  - "Busque os atendimentos do paciente 321 e informe o plano (P) de cada um."

### consulta_epidemiologia
- Descrição: agregação de comorbidades (CID-10) com filtros de sexo, faixa etária e localidade.
- Parâmetros:
  - `tipo`: literal `comorbidades_por_filtro` (default)
  - `sexo` (str opcional), `idade_min` (int opcional), `idade_max` (int opcional), `localidade_id` (int opcional), `limite` (int, default 50, máx 500)
- Saída (`EpidemiologiaComorbidadeResult`):
  - codigo_cid10, descricao_cid10, sexo, faixa_etaria (faixas pré-definidas), localidade_id, total_pacientes
- Exemplos:
  - "Quantos pacientes com hipertensão por sexo e faixa etária? limite 20"
  - "Liste comorbidades por localidade 123 com no máximo 30 resultados"

### consulta_pessoal
- Descrição: retorna pacientes que atendem a filtros clínicos pré-definidos.
- Parâmetros:
  - `tipo`: um de
    - `sem_atendimento_ano` (último atendimento > 365 dias)
    - `gestante_sem_atendimento_mes` (gestante ativa sem atendimento > 30 dias)
    - `hipertenso_sem_atendimento_6m` (CID-10 hipertensão, última consulta > 180 dias)
    - `hba1c_maior_8` (último exame HbA1c > 8%)
    - `pa_maior_140_90` (última PA registrada > 140/90)
  - `limite` (int, default 50, máx 500)
- Saída (`PessoalFiltroResult`):
  - paciente_id, nome_paciente (quando disponível), data_referencia (ISO), detalhe (ex.: "HbA1c", "PA"), metrica (valor do exame/PA)
- Exemplos:
  - "Liste gestantes sem atendimento há mais de 30 dias, limite 10"
  - "Traga pacientes com HbA1c acima de 8% (máximo 20)"
  - "Quais hipertensos estão sem atendimento há mais de 6 meses? limite 15"

## Limitações
- Somente leitura; sem escrita ou alteração de dados clínicos.
- Base utiliza CID-10 (não inclui CID-11).
- Registros SOAP podem estar vazios ou incompletos dependendo do preenchimento.

## Segurança e privacidade
- Não exponha identificadores sensíveis em canais não autorizados.
- Prefira anonimizar nomes/IDs ao relatar resultados para usuários finais.
- Utilize filtros de limite para evitar vazamentos massivos de dados.
