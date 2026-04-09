# Schema de Gestantes (Pré-natal)

Referência das tabelas usadas pela tool `listar_gestantes`.

## Tabelas principais

### tb_pre_natal

Registro de gestação em acompanhamento pré-natal.

| Coluna | Tipo | Descrição |
|---|---|---|
| `co_seq_pre_natal` | bigint PK | ID da gestação |
| `co_prontuario` | bigint FK | → tb_prontuario |
| `dt_ultima_menstruacao` | timestamp | DUM (para cálculo de IG) |
| `dt_desfecho` | timestamp | Data do desfecho (NULL = gestação ativa) |
| `tp_gravidez` | integer | Tipo de gravidez |
| `st_alto_risco` | integer | Flag de alto risco |

### tb_exame_prenatal

Exames complementares do pré-natal.

| Coluna | Tipo | Descrição |
|---|---|---|
| `co_exame_requisitado` | bigint FK | → tb_pre_natal.co_seq_pre_natal |
| `dt_provavel_parto_eco` | timestamp | DPP por ecografia (mais precisa que DUM) |

## Cadeia de joins (paciente)

```
tb_pre_natal.co_prontuario
  → tb_prontuario.co_seq_prontuario
    → tb_cidadao.co_seq_cidadao (via co_cidadao) ← paciente_id
```

## Cálculos

- **Idade gestacional**: `(CURRENT_DATE - dt_ultima_menstruacao) / 7` semanas + dias restantes
- **DPP**: `dt_provavel_parto_eco` (ecografia) ou `dt_ultima_menstruacao + 280 dias` (Naegele)
- **Filtro de gestação ativa**: `dt_desfecho IS NULL AND gest_days BETWEEN 14 AND 294` (2 a 42 semanas)
