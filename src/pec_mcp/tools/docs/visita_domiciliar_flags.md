# Flags da Visita Domiciliar (tb_fat_visita_domiciliar)

Referência completa dos campos de flag (integer 0/1) presentes na tabela fato
`tb_fat_visita_domiciliar`, usados pelas tools `listar_visitas_acs`.

## Tabela de origem

- **Tabela**: `tb_fat_visita_domiciliar`
- **Tipo**: Tabela fato desnormalizada (CDS — Coleta de Dados Simplificada)
- **Volume aproximado**: ~870k visitas, ~88 profissionais, ~30k pacientes
- **Profissional principal**: ACS — CBO `515105` (Agente Comunitário de Saúde)

## Dimensões relacionadas

| Dimensão | Tabela | FK na fato | Campos úteis |
|---|---|---|---|
| Profissional | `tb_dim_profissional` | `co_dim_profissional` | `no_profissional` |
| CBO | `tb_dim_cbo` | `co_dim_cbo` | `nu_cbo`, `no_cbo` |
| Tempo | `tb_dim_tempo` | `co_dim_tempo` | `dt_registro`, `nu_ano`, `nu_mes` |
| Turno | `tb_dim_turno` | `co_dim_turno` | `ds_turno` (Manhã/Tarde/Noite) |
| Desfecho | `tb_dim_desfecho_visita` | `co_dim_desfecho_visita` | `ds_desfecho_visita` |
| Unidade | `tb_dim_unidade_saude` | `co_dim_unidade_saude` | — |
| Equipe | `tb_dim_equipe` | `co_dim_equipe` | — |
| Paciente | `tb_fat_cidadao_pec` | `co_fat_cidadao_pec` | `co_cidadao`, `no_cidadao` |

### Valores de Desfecho

| ID | Descrição |
|---|---|
| 1 | Visita realizada |
| 2 | Visita recusada |
| 3 | Ausente |
| 4 | Não informado |

### Valores de Turno

| ID | Descrição |
|---|---|
| 1 | Não informado |
| 2 | Manhã |
| 3 | Tarde |
| 4 | Noite |

## Flags de Motivo da Visita (9 flags)

Cada flag indica um ou mais motivos registrados para a visita.
Uma mesma visita pode ter múltiplos motivos ativos (ex.: periódica + orientação).

| Flag (coluna) | Label na tool | Descrição |
|---|---|---|
| `st_mot_vis_cad_att` | `cadastro` | Cadastro ou atualização cadastral |
| `st_mot_vis_visita_periodica` | `periodica` | Visita periódica de rotina |
| `st_mot_vis_busca_ativa` | `busca_ativa` | Busca ativa (consulta, exame, vacina, Bolsa Família) |
| `st_mot_vis_acompanhamento` | `acompanhamento` | Acompanhamento de condicionalidade |
| `st_mot_vis_egresso_internacao` | `egresso_internacao` | Acompanhamento pós-internação |
| `st_mot_vis_ctrl_ambnte_vetor` | `controle_ambiental` | Controle ambiental/vetorial |
| `st_mot_vis_convte_atvidd_cltva` | `convite_atividade` | Convite para atividade coletiva |
| `st_mot_vis_orintacao_prevncao` | `orientacao_prevencao` | Orientação/prevenção |
| `st_mot_vis_outros` | `outros` | Outros motivos |

### Sub-flags de busca ativa

| Flag (coluna) | Descrição |
|---|---|
| `st_busca_ativa_consulta` | Busca ativa — consulta |
| `st_busca_ativa_exame` | Busca ativa — exame |
| `st_busca_ativa_vacina` | Busca ativa — vacina |
| `st_busca_ativa_bolsa_familia` | Busca ativa — Bolsa Família |

## Flags de Acompanhamento por Condição (23 flags)

Cada flag indica que a visita incluiu acompanhamento daquela condição.
Permite cruzamento direto sem joins adicionais (ex.: "visitas a gestantes").

| Flag (coluna) | Label na tool | Descrição |
|---|---|---|
| `st_acomp_gestante` | `gestante` | Gestante |
| `st_acomp_puerpera` | `puerpera` | Puérpera |
| `st_acomp_recem_nascido` | `recem_nascido` | Recém-nascido |
| `st_acomp_crianca` | `crianca` | Criança |
| `st_acomp_pessoa_desnutricao` | `desnutricao` | Pessoa com desnutrição |
| `st_acomp_pessoa_reabil_deficie` | `reabilitacao` | Reabilitação/deficiência |
| `st_acomp_pessoa_hipertensao` | `hipertensao` | Hipertensão arterial |
| `st_acomp_pessoa_diabetes` | `diabetes` | Diabetes mellitus |
| `st_acomp_pessoa_asma` | `asma` | Asma |
| `st_acomp_pessoa_dpoc_enfisema` | `dpoc` | DPOC/enfisema |
| `st_acomp_pessoa_cancer` | `cancer` | Câncer |
| `st_acomp_pessoa_doenca_cronica` | `doenca_cronica` | Outra doença crônica |
| `st_acomp_pessoa_hanseniase` | `hanseniase` | Hanseníase |
| `st_acomp_pessoa_tuberculose` | `tuberculose` | Tuberculose |
| `st_acomp_sintomaticos_respirat` | `sintomatico_respiratorio` | Sintomáticos respiratórios |
| `st_acomp_tabagista` | `tabagista` | Tabagista |
| `st_acomp_domiciliados_acamados` | `acamado` | Domiciliados/acamados |
| `st_acomp_condi_vulnerab_social` | `vulnerabilidade_social` | Vulnerabilidade social |
| `st_acomp_condi_bolsa_familia` | `bolsa_familia` | Bolsa Família |
| `st_acomp_saude_mental` | `saude_mental` | Saúde mental |
| `st_acomp_usuario_alcool` | `alcool` | Uso de álcool |
| `st_acomp_usuario_outras_drogra` | `drogas` | Uso de outras drogas |
| `st_acomp_pessoa_idosa` | `idoso` | Pessoa idosa |

### Sub-flags de controle ambiental/vetorial

| Flag (coluna) | Descrição |
|---|---|
| `st_ctrl_amb_vet_acao_educativa` | Ação educativa |
| `st_ctrl_amb_vet_imovel_foco` | Imóvel com foco |
| `st_ctrl_amb_vet_acao_mecanica` | Ação mecânica |
| `st_ctrl_amb_vet_tratamnt_focal` | Tratamento focal |

## Campos de Aferição na Visita

Medições que o ACS pode realizar durante a visita domiciliar.
Os **valores detalhados** são retornados pelas tools de medição (`listar_registros_*`);
na tool de visitas expomos apenas **presença** (booleanos).

| Coluna | Tipo | Descrição |
|---|---|---|
| `nu_peso` | double | Peso em kg |
| `nu_altura` | double | Altura em cm |
| `nu_medicao_pressao_arterial` | varchar(20) | PA no formato "PAS/PAD" (ex.: "130/80") |
| `nu_medicao_glicemia` | varchar(20) | Glicemia em mg/dL |
| `nu_medicao_temperatura` | varchar(20) | Temperatura corporal |
| `co_dim_tipo_glicemia` | bigint FK | Tipo de glicemia (tb_dim_tipo_glicemia) |

### Valores de Tipo de Glicemia (tb_dim_tipo_glicemia)

| ID | Descrição |
|---|---|
| 0 | Não informado |
| 1 | Não especificado |
| 2 | Jejum |
| 3 | Pós-prandial |
| 4 | Pré-prandial |

## Campos Adicionais

| Coluna | Tipo | Descrição |
|---|---|---|
| `nu_micro_area` | varchar(3) | Micro-área do ACS |
| `nu_cns` | char(15) | CNS do cidadão (quando disponível) |
| `nu_cpf_cidadao` | varchar(11) | CPF do cidadão (quando disponível) |
| `nu_prontuario` | varchar(65) | Número do prontuário |
| `st_visita_compartilhada` | integer | Visita com outro profissional |
| `nu_latitude` / `nu_longitude` | double | Geolocalização da visita |
