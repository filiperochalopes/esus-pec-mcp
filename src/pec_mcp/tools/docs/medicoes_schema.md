# Schema de Medições Clínicas

Referência das tabelas e joins usados pelas tools `listar_registros_antropometria`,
`listar_registros_pa` e `listar_registros_hgt`.

## Fontes de dados

As tools consolidam medições de **duas fontes distintas** via UNION ALL:

### 1. PEC (Atendimento Clínico) — `tl_medicao`

Medições registradas durante atendimentos no Prontuário Eletrônico do Cidadão.

**Cadeia de joins (paciente)**:
```
tl_medicao.co_atend_prof
  → tb_atend_prof.co_seq_atend_prof
    → tb_atend.co_seq_atend (via co_atend)
      → tb_prontuario.co_seq_prontuario (via co_prontuario)
        → tb_cidadao.co_seq_cidadao (via co_cidadao) ← paciente_id
```

**Cadeia de joins (profissional)**:
```
tb_atend_prof.co_lotacao
  → tb_lotacao.co_ator_papel
    → tb_prof.co_seq_prof (via co_prof) ← profissional_id + nome
    → tb_cbo.co_cbo (via co_cbo) ← CBO para classificação
```

**Colunas de medição em `tl_medicao`** (todas varchar(20)):

| Coluna | Descrição | Exemplo |
|---|---|---|
| `nu_medicao_peso` | Peso em kg | "66.0" |
| `nu_medicao_altura` | Altura em cm | "158.0" |
| `nu_medicao_imc` | IMC (frequentemente NULL) | "26.43" |
| `nu_medicao_pressao_arterial` | PA formato PAS/PAD | "130/80" |
| `nu_medicao_glicemia` | Glicemia capilar mg/dL | "93" |
| `tp_glicemia` | Momento aferição (bigint) | 0 |
| `nu_medicao_frequencia_cardiaca` | FC bpm | "80" |
| `nu_medicao_frequnca_resprtria` | FR irpm | "20" |
| `nu_medicao_temperatura` | Temperatura corporal | "36.5" |
| `nu_medicao_saturacao_o2` | SpO2 % | "98" |
| `nu_medicao_perimetro_cefalico` | PC (pediátrico) | "35" |
| `nu_medicao_altura_uterina` | AU (obstétrico) | "28" |
| `nu_medicao_batimnto_cardco_ftl` | BCF (obstétrico) | "140" |
| `nu_medicao_circunf_abdominal` | Circunferência abdominal | "88" |
| `nu_perimetro_panturrilha` | Perímetro de panturrilha | "33" |

**Mapeamento tp_glicemia → texto**:

| Valor | Descrição |
|---|---|
| 0 | Jejum |
| 1 | Pós-prandial |
| 2 | Pré-prandial |
| 3 | Não especificado |
| NULL | Não informado |

### 2. Visita Domiciliar (CDS) — `tb_fat_visita_domiciliar`

Medições registradas pelo ACS durante visitas domiciliares.

**Cadeia de joins (paciente)**:
```
tb_fat_visita_domiciliar.co_fat_cidadao_pec
  → tb_fat_cidadao_pec.co_seq_fat_cidadao_pec
    → tb_fat_cidadao_pec.co_cidadao ← paciente_id (= tb_cidadao.co_seq_cidadao)
```

**Cadeia de joins (profissional)**:
```
tb_fat_visita_domiciliar.co_dim_profissional
  → tb_dim_profissional.co_seq_dim_profissional ← profissional_id + nome
tb_fat_visita_domiciliar.co_dim_cbo
  → tb_dim_cbo.co_seq_dim_cbo ← CBO para classificação
```

**Cadeia de joins (tempo)**:
```
tb_fat_visita_domiciliar.co_dim_tempo
  → tb_dim_tempo.co_seq_dim_tempo ← dt_registro (data da visita)
```

**Colunas de medição**:

| Coluna | Tipo | Descrição |
|---|---|---|
| `nu_peso` | double | Peso em kg |
| `nu_altura` | double | Altura em cm |
| `nu_medicao_pressao_arterial` | varchar(20) | PA formato PAS/PAD |
| `nu_medicao_glicemia` | varchar(20) | Glicemia mg/dL |
| `nu_medicao_temperatura` | varchar(20) | Temperatura |
| `co_dim_tipo_glicemia` | bigint FK | → tb_dim_tipo_glicemia |

## Classificação de Profissional (derivada do CBO)

| Prefixo CBO | tipo_profissional |
|---|---|
| `225xxx` | "médico" |
| `2235xx` | "enfermeiro" |
| `515105` | "ACS" |
| `5151xx` | "agente de saúde" |
| `2232xx` | "dentista" |
| outro | descrição CBO original (lowercase) |

## Volumes de dados (dataset de referência)

| Tipo | Registros (PEC) | Registros (Visita) |
|---|---|---|
| Peso | ~2.254 | ~7.139 |
| Altura | ~1.433 | ~4.458 |
| Peso+Altura | ~1.432 | ~4.458 |
| PA | ~4.214 | ~5.683 |
| Glicemia | ~180 | ~1.014 |

**Overlap entre fontes**: ~6 registros (mesmo paciente+dia com peso em ambas).
